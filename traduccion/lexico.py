"""
Capa léxica del traductor: coincidencia exacta, aproximada y parcial contra el glosario,
más patrones productivos de cada lengua (fórmulas de dolor en Ikʉn, paradigma de tiempos
verbales de síntomas en Kogui).

Se ejecuta ANTES de la búsqueda semántica. Una coincidencia exacta con un término del
glosario siempre gana (confianza 100), cosa que los embeddings por sí solos no garantizan.

Todo trabaja sobre texto normalizado (`normalizar`): minúsculas, sin tildes ni diacríticos,
ʉ→u, ɉ→j, ɨ→i, sin apóstrofos ni signos de puntuación. Así «Kʉkʉ», «KUKU» y «kuku» coinciden,
y «Munzhi zawa» encuentra «Munzhi zhawa» como aproximada.
"""
import difflib
import logging
import re
import threading
import time
import unicodedata
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_MAPA = str.maketrans({'ʉ': 'u', 'Ʉ': 'u', 'ɉ': 'j', 'Ɉ': 'j', 'ɨ': 'i', 'Ɨ': 'i', 'ç': 's'})
_APOSTROFOS = "'’‘´`ʼ"


def normalizar(texto: str) -> str:
    if not texto:
        return ''
    t = texto.translate(_MAPA)
    t = ''.join(c for c in t if c not in _APOSTROFOS)
    t = unicodedata.normalize('NFKD', t)
    t = ''.join(c for c in t if not unicodedata.combining(c))
    t = t.lower()
    t = re.sub(r'[^a-z0-9ñ ]+', ' ', t.replace('ñ', 'ñ'))
    return re.sub(r'\s+', ' ', t).strip()


def _variantes_es(termino_es: str) -> List[str]:
    """«Alegría / Tranquilidad / Calma» → las tres; también sin signos de pregunta."""
    partes = [p for p in re.split(r'\s*/\s*', termino_es or '') if p.strip()]
    salida = []
    for p in partes:
        n = normalizar(p)
        if n and n not in salida:
            salida.append(n)
    return salida


# ---------------------------------------------------------------------------
# Índice léxico por lengua (cache en memoria, se refresca si cambia el glosario)
# ---------------------------------------------------------------------------

class _IndiceLexico:
    TTL = 120  # segundos entre comprobaciones de cambios en BD

    def __init__(self, codigo: str):
        self.codigo = codigo
        self.entradas: List[Dict] = []
        self._firma = None
        self._comprobado = 0.0
        self._lock = threading.Lock()

    def _firma_bd(self):
        from django.db.models import Count, Max
        from terminos.models import TerminoLeng
        agg = TerminoLeng.objects.filter(lengua__codigo=self.codigo, activo=True).aggregate(n=Count('id'), u=Max('updated_at'))
        return (agg['n'], str(agg['u']))

    def asegurar(self):
        ahora = time.time()
        if self.entradas and ahora - self._comprobado < self.TTL:
            return
        with self._lock:
            if self.entradas and ahora - self._comprobado < self.TTL:
                return
            try:
                firma = self._firma_bd()
            except Exception as exc:  # BD no disponible: seguimos con lo que haya
                logger.warning('Índice léxico %s: no se pudo leer la BD (%s)', self.codigo, exc)
                self._comprobado = ahora
                return
            if firma != self._firma or not self.entradas:
                self._cargar()
                self._firma = firma
            self._comprobado = ahora

    def _cargar(self):
        from terminos.models import TerminoLeng
        qs = TerminoLeng.objects.filter(lengua__codigo=self.codigo, activo=True).select_related('termino_es')
        entradas = []
        for t in qs:
            es = t.termino_es.termino if t.termino_es else ''
            entradas.append({
                'termino': t.termino,
                'termino_es': es,
                'definicion': t.definicion or '',
                'pos': t.pos or '',
                'tipo_morfema': t.tipo_morfema,
                'nt': normalizar(t.termino),
                'nsin': [normalizar(s) for s in (t.sinonimos or []) if isinstance(s, str) and normalizar(s)],
                'nes': _variantes_es(es),
            })
        self.entradas = entradas
        logger.info('Índice léxico %s cargado: %d entradas', self.codigo, len(entradas))


_indices: Dict[str, _IndiceLexico] = {}
_indices_lock = threading.Lock()


def indice(codigo: str) -> _IndiceLexico:
    with _indices_lock:
        idx = _indices.get(codigo)
        if idx is None:
            idx = _indices[codigo] = _IndiceLexico(codigo)
    idx.asegurar()
    return idx


# ---------------------------------------------------------------------------
# Coincidencias léxicas
# ---------------------------------------------------------------------------

UMBRAL_APROX = 0.86


def _resultado(e: Dict, confianza: int, nivel: str, coincidencia: str, fuente: str = 'glosario', nota: str = '') -> Dict:
    return {
        'termino': e['termino'], 'termino_es': e['termino_es'], 'definicion': e['definicion'], 'pos': e['pos'],
        'score': round(confianza / 100, 4), 'confianza': confianza, 'nivel': nivel, 'fuente': fuente,
        'coincidencia': coincidencia, 'nota': nota,
        'hipotesis': (e.get('tipo_morfema') or '') == 'hipótesis',
    }


def buscar_lexico(texto: str, codigo: str, direccion: str, max_resultados: int = 5) -> List[Dict]:
    """
    direccion = 'lengua_a_es' → compara el texto con el término indígena (y sinónimos).
    direccion = 'es_a_lengua' → compara con el término en español (y sus variantes).
    Devuelve resultados ordenados por confianza: exacta (100) > aproximada (86–96) > parcial (55–78).
    """
    q = normalizar(texto)
    if not q:
        return []
    idx = indice(codigo)
    campo = 'nes' if direccion == 'es_a_lengua' else None
    q_tokens = q.split()
    hallazgos: Dict[str, Dict] = {}

    def claves(e):
        return e['nes'] if campo else [e['nt']] + e['nsin']

    # 1) exacta
    for e in idx.entradas:
        for k in claves(e):
            if k == q:
                hallazgos[e['termino']] = _resultado(e, 100, 'exacta', texto)
                break
    # 2) aproximada (errores de tipeo / grafía)
    if len(q) >= 4:
        for e in idx.entradas:
            if e['termino'] in hallazgos:
                continue
            mejor = 0.0
            for k in claves(e):
                if abs(len(k) - len(q)) > max(6, len(q) // 2):
                    continue
                r = difflib.SequenceMatcher(None, q, k).ratio()
                if r > mejor:
                    mejor = r
            if mejor >= UMBRAL_APROX:
                conf = int(round(80 + (mejor - UMBRAL_APROX) / (1 - UMBRAL_APROX) * 16))
                hallazgos[e['termino']] = _resultado(e, conf, 'aproximada', texto, nota='Coincidencia aproximada (posible variación de escritura).')
    # 3) parcial: un término del glosario dentro del texto, o el texto dentro de un término
    if len(q_tokens) >= 1:
        for e in idx.entradas:
            if e['termino'] in hallazgos:
                continue
            for k in claves(e):
                kt = k.split()
                if not kt:
                    continue
                # término (≥2 palabras, o 1 palabra de ≥4 letras) contenido en el texto
                if len(kt) < len(q_tokens) and (len(kt) >= 2 or len(k) >= 4) and _subsecuencia(kt, q_tokens):
                    cobertura = len(k) / max(len(q), 1)
                    conf = int(round(55 + 23 * min(cobertura, 1)))
                    hallazgos[e['termino']] = _resultado(e, conf, 'parcial', k, nota='El glosario contiene una parte del texto.')
                    break
                # texto (≥4 letras) contenido en un término más largo
                if len(q_tokens) < len(kt) and len(q) >= 4 and _subsecuencia(q_tokens, kt):
                    cobertura = len(q) / max(len(k), 1)
                    conf = int(round(50 + 20 * min(cobertura, 1)))
                    hallazgos[e['termino']] = _resultado(e, conf, 'parcial', texto, nota='El texto es parte de una entrada más larga del glosario.')
                    break

    salida = sorted(hallazgos.values(), key=lambda r: -r['confianza'])
    return salida[:max_resultados]


def _subsecuencia(corta: List[str], larga: List[str]) -> bool:
    n = len(corta)
    return any(larga[i:i + n] == corta for i in range(len(larga) - n + 1))


# ---------------------------------------------------------------------------
# Patrones productivos
# ---------------------------------------------------------------------------

# Ikʉn: «X na'mʉchʉyin» = me duele X · «Xse' na'mʉchʉyin» = me duele en X · «Xzanʉ na'zʉnin» = tengo dolor de X
_IKU_DUELE = re.compile(r'^(?P<x>.+?)(?P<se> ?se)? ?namuchuyin$')
_IKU_TENGO = re.compile(r'^(?P<x>.+?) ?zanu ?nazunin$')
_ES_DUELE = re.compile(r'^(me duelen?|le duelen?|te duelen?) (en )?(la |el |los |las |mi |mis )?(?P<x>.+)$')
_ES_TENGO = re.compile(r'^(tengo|siento) (un )?dolor (de|en) (la |el |los |las )?(?P<x>.+)$')

# Kogui: paradigma de tiempos para preguntas de síntoma (triage Dumingueka, 2026)
_KOGUI_TIEMPOS: List[Tuple[str, str]] = [
    ('mikzegate naugaki naumalde shi na', '¿No estuviste teniendo {s}?'),
    ('nagate naugaki naumalde shi na', '¿No estuviste teniendo {s}?'),
    ('nagate naugaki shi balda', '¿No has venido teniendo {s}?'),
    ('mikzeishi nagate shi balauk', '¿Has venido teniendo {s}?'),
    ('mikzeishi nagate naugaki shi balda', '¿Has venido teniendo {s}?'),
    ('mikzeishi shi balda', '¿Has venido teniendo {s}?'),
    ('mikzegate naune shi na', '¿Estuviste con {s}?'),
    ('mikzegate nauke', '¿Te está dando {s}?'),
    ('mikzeishi shi balak', '¿Viniste con {s}?'),
    ('mikzeishi shi guatauk', '¿Estás teniendo {s}?'),
    ('shi mikzeki', '¿Tienes {s}?'),
    ('shi mikzek', '¿Tienes {s}?'),
]
_ES_TIEMPOS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r'^no estuviste teniendo (?P<s>.+)$'), 'mikzegate naugaki naumalde shi na'),
    (re.compile(r'^no has venido teniendo (?P<s>.+)$'), 'nagate naugaki shi balda'),
    (re.compile(r'^has venido teniendo (?P<s>.+)$'), 'mikzeishi shi balda'),
    (re.compile(r'^estuviste con (?P<s>.+)$'), 'mikzegate naune shi na'),
    (re.compile(r'^te esta dando (?P<s>.+)$'), 'mikzegate nauke'),
    (re.compile(r'^viniste con (?P<s>.+)$'), 'mikzeishi shi balak'),
    (re.compile(r'^estas teniendo (?P<s>.+)$'), 'mikzeishi shi guatauk'),
    (re.compile(r'^tienes (?P<s>.+)$'), 'shi mikzek'),
]


def _buscar_nombre(idx: _IndiceLexico, x: str, por_es: bool) -> Optional[Tuple[Dict, int]]:
    """Encuentra la entrada (parte del cuerpo / síntoma) que corresponde a x. Devuelve (entrada, confianza)."""
    x = normalizar(x)
    if not x:
        return None
    candidatos = [e for e in idx.entradas if e['pos'] in ('NOM', '', 'NOM_PR', 'FRS')]
    for e in candidatos:
        claves = e['nes'] if por_es else [e['nt']] + e['nsin']
        if x in claves:
            return e, 100
    # variantes: el nombre puede llevar o no «zalda» (Kogui) o perder la vocal final (Ikʉn: umʉ→uma)
    mejor, mejor_r = None, 0.0
    for e in candidatos:
        for k in (e['nes'] if por_es else [e['nt']] + e['nsin']):
            if not k:
                continue
            kk = k.replace(' zalda', '').strip() if not por_es else k
            r = difflib.SequenceMatcher(None, x, kk).ratio()
            if r > mejor_r:
                mejor, mejor_r = e, r
    if mejor is not None and mejor_r >= 0.8:
        return mejor, int(round(70 + (mejor_r - 0.8) * 100))
    return None


def buscar_patrones(texto: str, codigo: str, direccion: str) -> List[Dict]:
    q = normalizar(texto)
    if not q:
        return []
    idx = indice(codigo)
    salida: List[Dict] = []

    if codigo == '1':  # Ikʉn
        if direccion == 'lengua_a_es':
            for rx, plantilla, nota in ((_IKU_DUELE, 'me duele {en}{x}', "Fórmula «[parte] na'mʉchʉyin» = me duele [parte]"),
                                        (_IKU_TENGO, 'tengo dolor de {x}', "Fórmula «[parte]zanʉ na'zʉnin» = tengo dolor de [parte]")):
                m = rx.match(q)
                if not m:
                    continue
                enc = _buscar_nombre(idx, m.group('x'), por_es=False)
                if not enc:
                    continue
                e, conf = enc
                x_es = e['termino_es'].lower().split(' / ')[0]
                art = '' if re.match(r'^(el|la|los|las|mi|mis) ', x_es) else ('las ' if x_es.endswith('as') else 'los ' if x_es.endswith('os') else 'la ' if x_es.endswith('a') else 'el ')
                en = 'en ' if (rx is _IKU_DUELE and m.group('se')) else ''
                es = plantilla.format(x=art + x_es, en=en)
                salida.append({'termino': texto.strip(), 'termino_es': es, 'definicion': f'{nota}. Parte del cuerpo reconocida: {e["termino"]} = {e["termino_es"]}.',
                               'pos': 'FRS', 'score': round(min(conf, 96) / 100, 4), 'confianza': min(conf, 96), 'nivel': 'exacta' if conf == 100 else 'aproximada',
                               'fuente': 'patrón', 'coincidencia': e['termino'], 'nota': 'Traducción construida con un patrón de la lengua.', 'hipotesis': False})
        else:
            for rx, plantilla, nota in ((_ES_DUELE, "{t} na'mʉchʉyin", "Fórmula «[parte] na'mʉchʉyin» = me duele [parte]"),
                                        (_ES_TENGO, "{t}zanʉ na'zʉnin", "Fórmula «[parte]zanʉ na'zʉnin» = tengo dolor de [parte]")):
                m = rx.match(q)
                if not m:
                    continue
                enc = _buscar_nombre(idx, m.group('x'), por_es=True)
                if not enc:
                    continue
                e, conf = enc
                t = e['termino'].split(' - ')[0]
                salida.append({'termino': plantilla.format(t=t), 'termino_es': texto.strip(), 'definicion': f'{nota}. Parte del cuerpo: {e["termino"]} = {e["termino_es"]}. Forma construida: conviene confirmarla con un hablante (algunas raíces cambian la vocal final, p. ej. umʉ → uma).',
                               'pos': 'FRS', 'score': round(min(conf, 90) / 100, 4), 'confianza': min(conf, 90), 'nivel': 'aproximada',
                               'fuente': 'patrón', 'coincidencia': e['termino_es'], 'nota': 'Forma construida a partir de un patrón; verificar con hablante.', 'hipotesis': False})

    elif codigo.lower() == 'kogui':
        if direccion == 'lengua_a_es':
            for cola, plantilla in _KOGUI_TIEMPOS:
                if q.endswith(' ' + cola):
                    s = q[: -len(cola)].strip()
                    enc = _buscar_nombre(idx, s, por_es=False) or _buscar_nombre(idx, s.replace(' zalda', ''), por_es=False)
                    if not enc:
                        break
                    e, conf = enc
                    es = plantilla.format(s=e['termino_es'].lower())
                    salida.append({'termino': texto.strip(), 'termino_es': es, 'definicion': f'Pregunta de síntoma construida con el paradigma de tiempos verbales kogui («{cola}»). Síntoma reconocido: {e["termino"]} = {e["termino_es"]}.',
                                   'pos': 'FRS', 'score': round(min(conf, 96) / 100, 4), 'confianza': min(conf, 96), 'nivel': 'exacta' if conf == 100 else 'aproximada',
                                   'fuente': 'patrón', 'coincidencia': e['termino'], 'nota': 'Traducción construida con el paradigma de tiempos del triage Dumingueka.', 'hipotesis': False})
                    break
        else:
            for rx, cola in _ES_TIEMPOS:
                m = rx.match(q)
                if not m:
                    continue
                enc = _buscar_nombre(idx, m.group('s'), por_es=True)
                if not enc:
                    continue
                e, conf = enc
                base = e['termino'].rstrip('?¿ ')
                if 'zalda' not in normalizar(base) and e['pos'] == 'NOM':
                    base = f'{base} zalda'
                salida.append({'termino': f'¿{base} {cola}?', 'termino_es': texto.strip(), 'definicion': f'Pregunta construida con el paradigma de tiempos verbales kogui. Síntoma: {e["termino"]} = {e["termino_es"]}. Forma construida: conviene confirmarla con un hablante.',
                               'pos': 'FRS', 'score': round(min(conf, 88) / 100, 4), 'confianza': min(conf, 88), 'nivel': 'aproximada',
                               'fuente': 'patrón', 'coincidencia': e['termino_es'], 'nota': 'Forma construida a partir de un patrón; verificar con hablante.', 'hipotesis': False})
                break
    return salida
