"""
Normaliza la escritura de las etiquetas (transcripciones) del corpus de audio.

  python manage.py normalizar_etiquetas                      # solo informe: cuántas etiquetas cambiarían y por qué regla
  python manage.py normalizar_etiquetas --aplicar            # aplica las reglas seguras (nfc, espacios, comillas, j_gancho)
  python manage.py normalizar_etiquetas --aplicar --reglas nfc,espacios,comillas,j_gancho,tilde_a_saltillo,minusculas
  python manage.py normalizar_etiquetas --comunidad Arhuaco --aplicar

Reglas:
  nfc               Unicode NFC (una sola forma para letras con diacríticos).
  espacios          Quita espacios dobles y espacios al inicio/final.
  comillas          Comillas tipográficas “ ” → ", apóstrofos ‘ ` ʼ → ’.
  j_gancho          ɟ/Ɉ (j con gancho) → ɉ/Ɉ (j cortada), la grafía del corpus.
  tilde_a_saltillo  «´» suelto después de letra → ’ (saltillo). SOLO si la comunidad/lingüista lo confirma: no está activa por defecto.
  minusculas        Etiquetas escritas TODO EN MAYÚSCULAS → minúsculas con inicial mayúscula.
  punto_final       Quita el punto final de etiquetas de una sola oración.

Cada archivo modificado deja rastro en EtiquetaHistorial (acción «editar», usuario «normalización automática»).
"""
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

SEGURAS = ['nfc', 'espacios', 'comillas', 'j_gancho']
TODAS = SEGURAS + ['tilde_a_saltillo', 'minusculas', 'punto_final']


def aplicar_reglas(texto: str, reglas) -> tuple[str, list]:
    usadas = []
    t = texto
    if 'nfc' in reglas:
        n = unicodedata.normalize('NFC', t)
        if n != t:
            usadas.append('nfc'); t = n
    if 'comillas' in reglas:
        n = re.sub(r'[“”«»]', '"', t)
        n = re.sub(r'[‘`ʼ]', '’', n)
        if n != t:
            usadas.append('comillas'); t = n
    if 'j_gancho' in reglas:
        n = t.replace('ɟ', 'ɉ').replace('Ɉ', 'Ɉ')
        if n != t:
            usadas.append('j_gancho'); t = n
    if 'tilde_a_saltillo' in reglas:
        n = re.sub(r'(?<=[A-Za-zÁÉÍÓÚáéíóúñÑʉɄɉɈ])´', '’', t)
        if n != t:
            usadas.append('tilde_a_saltillo'); t = n
    if 'minusculas' in reglas:
        letras = [c for c in t if c.isalpha()]
        if letras and all(c.isupper() for c in letras) and len(letras) >= 4:
            n = t.lower()
            n = n[0].upper() + n[1:]
            usadas.append('minusculas'); t = n
    if 'punto_final' in reglas:
        n = re.sub(r'\.\s*$', '', t.strip())
        if n != t.strip():
            usadas.append('punto_final'); t = n
    if 'espacios' in reglas:
        n = re.sub(r'[ \t]+', ' ', t).strip()
        n = re.sub(r'\n{3,}', '\n\n', n)
        if n != t:
            usadas.append('espacios'); t = n
    return t, usadas


class Command(BaseCommand):
    help = 'Informe y normalización de la escritura de las etiquetas del corpus de audio.'

    def add_arguments(self, parser):
        parser.add_argument('--aplicar', action='store_true', help='Escribe los cambios (por defecto solo informa).')
        parser.add_argument('--reglas', default=','.join(SEGURAS), help=f'Reglas separadas por coma. Disponibles: {", ".join(TODAS)}')
        parser.add_argument('--comunidad', help='Solo esta comunidad (carpeta en Grabaciones).')
        parser.add_argument('--base', help='Carpeta base de grabaciones (por defecto settings/GRABACIONES).')

    def handle(self, *args, **o):
        from translator_api.models import EtiquetaHistorial
        from translator_api.views import _build_grabaciones_path

        reglas = [r.strip() for r in o['reglas'].split(',') if r.strip()]
        desconocidas = [r for r in reglas if r not in TODAS]
        if desconocidas:
            self.stderr.write(f'Reglas desconocidas: {desconocidas}. Disponibles: {TODAS}')
            return
        base = Path(o['base']) if o['base'] else _build_grabaciones_path()
        patron = f"{o['comunidad']}/*/audios_procesados/*.txt" if o['comunidad'] else '*/*/audios_procesados/*.txt'
        total = 0
        cambiarian = 0
        por_regla = Counter()
        por_comunidad = defaultdict(Counter)
        ejemplos = {}
        aplicados = 0
        for txt in sorted(base.glob(patron)):
            total += 1
            original = txt.read_text(encoding='utf-8', errors='ignore')
            nuevo, usadas = aplicar_reglas(original, reglas)
            if not usadas:
                continue
            cambiarian += 1
            comunidad = txt.parents[2].name
            jornada = txt.parents[1].name
            for r in usadas:
                por_regla[r] += 1
                por_comunidad[comunidad][r] += 1
                ejemplos.setdefault(r, (original.strip()[:50], nuevo.strip()[:50]))
            if o['aplicar']:
                txt.write_text(nuevo, encoding='utf-8')
                try:
                    EtiquetaHistorial.objects.create(
                        comunidad=comunidad, jornada=jornada, audio=txt.stem, accion='editar', etiqueta_anterior=original,
                        etiqueta_nueva=nuevo, usuario=None, usuario_nombre='normalización automática (' + ','.join(usadas) + ')',
                        origen='app', aproximado=False)
                except Exception as exc:
                    self.stderr.write(f'Sin historial para {txt}: {exc}')
                aplicados += 1

        self.stdout.write(f'Etiquetas revisadas: {total} | cambiarían: {cambiarian} ({100 * cambiarian / max(total, 1):.1f} %) | reglas: {", ".join(reglas)}')
        for r, n in por_regla.most_common():
            a, b = ejemplos[r]
            self.stdout.write(f'  {r:18} {n:6}   ej: {a!r} → {b!r}')
        for com, cnt in por_comunidad.items():
            self.stdout.write(f'  {com}: ' + ', '.join(f'{r}={n}' for r, n in cnt.most_common()))
        if o['aplicar']:
            self.stdout.write(self.style.SUCCESS(f'Aplicado en {aplicados} etiquetas (con rastro en el historial).'))
        else:
            self.stdout.write('Modo informe: nada se modificó. Usa --aplicar para escribir los cambios.')
