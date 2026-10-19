"""
Reconstruye el historial de autoría de las etiquetas que se hicieron ANTES de existir el
registro de cambios, cruzando la auditoría con los archivos de etiqueta (.txt):

  * Las ediciones (PUT) traen el nombre del audio en la ruta -> autor y hora exactos.
  * Las etiquetas nuevas (POST) no guardaron qué audio era; se asocian por cercanía entre la
    hora de modificación del .txt y la hora del registro de auditoría de esa misma jornada
    (ventana de 15 s). Quedan marcadas como «aproximado».

Es repetible: borra solo lo reconstruido antes (origen='auditoria') y lo vuelve a generar.
Uso:  python manage.py reconstruir_historial_etiquetas [--dry-run]
"""
from datetime import datetime, timedelta, timezone as dt_timezone
from urllib.parse import unquote

from django.core.management.base import BaseCommand

from roles.models import Auditoria
from translator_api.models import EtiquetaHistorial
from translator_api.views import GRABACIONES_BASE_PATH, AUDIO_EXTENSIONS, _nombre_usuario

VENTANA = timedelta(seconds=15)


class Command(BaseCommand):
    help = "Reconstruye quién creó/editó cada etiqueta a partir de la auditoría y los archivos .txt"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Solo muestra los conteos, no escribe.')

    def handle(self, *args, **opts):
        base = GRABACIONES_BASE_PATH
        auditoria = list(Auditoria.objects.filter(modulo='dataset_audio', accion='etiquetar')
                         .select_related('usuario').order_by('creado_en'))
        # ruta -> (comunidad, jornada, archivo|None)
        def parse(ruta):
            partes = [unquote(p) for p in ruta.strip('/').split('/')]
            if len(partes) >= 5 and partes[0] == 'api' and partes[1] == 'grabaciones':
                if partes[4] == 'etiquetar':
                    return partes[2], partes[3], None
                if partes[4] == 'etiqueta' and len(partes) >= 6:
                    return partes[2], partes[3], partes[5]
            return None

        posts, puts = {}, []
        for a in auditoria:
            r = parse(a.ruta)
            if not r:
                continue
            if a.metodo_http == 'POST' and r[2] is None:
                posts.setdefault((r[0].lower(), r[1].lower()), []).append(a)
            elif a.metodo_http == 'PUT' and r[2]:
                puts.append((r, a))

        nuevos = []
        sin_autor = 0
        usados = set()
        for comunidad_dir in sorted(p for p in base.iterdir() if p.is_dir()):
            for jornada_dir in sorted(p for p in comunidad_dir.iterdir() if p.is_dir()):
                procesados = jornada_dir / 'audios_procesados'
                sin_proc = jornada_dir / 'audios_sin_procesar'
                if not procesados.exists():
                    continue
                candidatos = posts.get((comunidad_dir.name.lower(), jornada_dir.name.lower()), [])
                audios = {f.stem: f.name for f in sin_proc.iterdir()
                          if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS} if sin_proc.exists() else {}
                for txt in sorted(procesados.glob('*.txt')):
                    mtime = datetime.fromtimestamp(txt.stat().st_mtime, tz=dt_timezone.utc)
                    mejor, dif = None, None
                    for a in candidatos:
                        if a.id in usados:
                            continue
                        d = abs(a.creado_en - mtime)
                        if d <= VENTANA and (dif is None or d < dif):
                            mejor, dif = a, d
                    if not mejor:
                        sin_autor += 1
                        continue
                    usados.add(mejor.id)
                    nuevos.append(EtiquetaHistorial(
                        comunidad=comunidad_dir.name, jornada=jornada_dir.name,
                        audio=audios.get(txt.stem, txt.stem), accion='crear',
                        etiqueta_nueva=txt.read_text(encoding='utf-8').strip(),
                        usuario=mejor.usuario, usuario_nombre=_nombre_usuario(mejor.usuario),
                        origen='auditoria', aproximado=True, creado_en=mejor.creado_en))

        for (comunidad, jornada, archivo), a in puts:
            c_dir = next((p for p in base.iterdir() if p.is_dir() and p.name.lower() == comunidad.lower()), None)
            j_dir = next((p for p in c_dir.iterdir() if p.is_dir() and p.name.lower() == jornada.lower()), None) if c_dir else None
            nuevos.append(EtiquetaHistorial(
                comunidad=c_dir.name if c_dir else comunidad, jornada=j_dir.name if j_dir else jornada,
                audio=archivo, accion='editar', usuario=a.usuario, usuario_nombre=_nombre_usuario(a.usuario),
                origen='auditoria', aproximado=False, creado_en=a.creado_en))

        self.stdout.write(f"Etiquetas nuevas atribuidas: {sum(1 for n in nuevos if n.accion == 'crear')} · "
                          f"ediciones: {sum(1 for n in nuevos if n.accion == 'editar')} · "
                          f"archivos .txt sin autor identificable: {sin_autor}")
        if opts['dry_run']:
            self.stdout.write("(dry-run: no se escribió nada)")
            return
        EtiquetaHistorial.objects.filter(origen='auditoria').delete()
        EtiquetaHistorial.objects.bulk_create(nuevos, batch_size=500)
        self.stdout.write(self.style.SUCCESS(f"Historial reconstruido: {len(nuevos)} registros."))
