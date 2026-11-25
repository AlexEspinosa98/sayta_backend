"""
Evalúa el traductor contra el propio glosario y contra texto fuera de él.

  python manage.py evaluar_traductor            # todas las lenguas, resumen
  python manage.py evaluar_traductor --lengua Kogui --json salida.json --muestra 200

Métricas por lengua y dirección:
  acierto@1 / acierto@3  — al consultar exactamente el término (o su español), ¿sale el correcto 1.º / entre los 3?
  ruido@1                — al consultar el término con una letra cambiada, ¿sigue saliendo el correcto?
  falso_en_glosario      — % de textos de control (fuera del glosario) que el sistema marca como «en glosario»
  latencia               — mediana y p95 en ms
"""
import json
import random
import statistics
import time

from django.core.management.base import BaseCommand

CONTROL = ['computador portátil', 'carro rojo', 'universidad del magdalena', 'reunión del consejo', 'internet', 'fútbol',
           'zzzz qqqq', 'Kaxxa wupu zent', 'factura de la luz', 'pasaporte vencido', 'teléfono celular', 'semáforo en rojo']


def _ruido(texto: str, rnd: random.Random) -> str:
    letras = [i for i, c in enumerate(texto) if c.isalpha()]
    if len(letras) < 4:
        return texto
    i = rnd.choice(letras[1:])
    return texto[:i] + ('a' if texto[i] != 'a' else 'e') + texto[i + 1:]


class Command(BaseCommand):
    help = 'Mide acierto, robustez y latencia del traductor sobre el glosario.'

    def add_arguments(self, parser):
        parser.add_argument('--lengua', help='Código de lengua (por defecto todas las activas)')
        parser.add_argument('--muestra', type=int, default=0, help='Evaluar solo N términos al azar por lengua (0 = todos)')
        parser.add_argument('--json', help='Guardar el resumen en este archivo')
        parser.add_argument('--semilla', type=int, default=7)

    def handle(self, *args, **o):
        from terminos.models import Lengua, TerminoLeng
        from traduccion.lexico import normalizar
        from traduccion.pipeline import TranslationPipeline
        from translator_api.search_engine import MultiLanguageSearchEngine

        rnd = random.Random(o['semilla'])
        engine = MultiLanguageSearchEngine.get_instance()
        lenguas = Lengua.objects.filter(activa=True)
        if o['lengua']:
            lenguas = lenguas.filter(codigo=o['lengua'])
        resumen = {}
        for l in lenguas:
            pipe = TranslationPipeline(engine, language_code=l.codigo)
            terms = list(TerminoLeng.objects.filter(lengua=l, activo=True, termino_es__isnull=False).select_related('termino_es'))
            if o['muestra'] and o['muestra'] < len(terms):
                terms = rnd.sample(terms, o['muestra'])
            try:
                pipe.traducir('hola', 'es_a_lengua', 3)   # calentar
            except Exception as exc:
                self.stderr.write(f'{l.codigo}: {exc}')
                continue
            res = {}
            for direccion, consulta in (('es_a_lengua', lambda t: t.termino_es.termino), ('lengua_a_es', lambda t: t.termino)):
                a1 = a3 = r1 = 0
                ms = []
                for t in terms:
                    q = consulta(t)
                    t0 = time.time()
                    r = pipe.traducir(q, direccion, 3)['resultados']
                    ms.append((time.time() - t0) * 1000)
                    ok = [x['termino'] == t.termino or normalizar(x['termino_es']) == normalizar(t.termino_es.termino) for x in r]
                    a1 += bool(ok and ok[0]); a3 += any(ok)
                    rr = pipe.traducir(_ruido(q, rnd), direccion, 3)['resultados']
                    r1 += bool(rr and (rr[0]['termino'] == t.termino or normalizar(rr[0]['termino_es']) == normalizar(t.termino_es.termino)))
                n = max(len(terms), 1)
                res[direccion] = {'n': len(terms), 'acierto@1': round(100 * a1 / n, 1), 'acierto@3': round(100 * a3 / n, 1), 'ruido@1': round(100 * r1 / n, 1),
                                  'ms_mediana': round(statistics.median(ms)) if ms else None, 'ms_p95': round(sorted(ms)[int(len(ms) * 0.95)]) if ms else None}
            fe = 0
            for q in CONTROL:
                if pipe.traducir(q, 'es_a_lengua', 3)['en_glosario']:
                    fe += 1
            res['falso_en_glosario_pct'] = round(100 * fe / len(CONTROL), 1)
            resumen[l.codigo] = res
            self.stdout.write(f'{l.codigo} ({l.nombre}): {json.dumps(res, ensure_ascii=False)}')
        if o['json']:
            with open(o['json'], 'w', encoding='utf-8') as f:
                json.dump(resumen, f, ensure_ascii=False, indent=2)
            self.stdout.write(f'Guardado en {o["json"]}')
