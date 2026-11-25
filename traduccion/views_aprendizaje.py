"""
Aprendizaje del traductor con el uso: registro de consultas, elección del usuario, correcciones
y cola de validación (hipótesis y traducciones compuestas), más estadísticas de uso.
"""
import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from roles.permissions import requiere_permiso
from . import lexico
from .models import ConsultaTraduccion, CorreccionTraduccion, HistorialTermino

logger = logging.getLogger(__name__)

EjecutarTraduccion = requiere_permiso('traduccion', 'ejecutar')
VerGlosario = requiere_permiso('glosario', 'ver')
EditarGlosario = requiere_permiso('glosario', 'editar')


def registrar_consulta(request, lengua, direccion, texto, salida, verificacion, ms_total, origen='texto'):
    """Guarda la consulta (nunca rompe la traducción si falla)."""
    try:
        mejor = salida['resultados'][0] if salida.get('resultados') else None
        c = ConsultaTraduccion.objects.create(
            lengua=lengua, direccion=direccion, origen=origen, texto=texto[:2000],
            texto_normalizado=lexico.normalizar(texto)[:500],
            mejor_termino=(mejor or {}).get('termino', '')[:500], mejor_termino_es=(mejor or {}).get('termino_es', '')[:500],
            confianza=(mejor or {}).get('confianza'), nivel=(mejor or {}).get('nivel', ''), fuente=(mejor or {}).get('fuente', ''),
            en_glosario=bool(salida.get('en_glosario')),
            verificacion_estado=(verificacion or {}).get('estado', '') or '', verificacion_ms=(verificacion or {}).get('ms'),
            ms_total=ms_total, usuario=request.user if getattr(request, 'user', None) and request.user.is_authenticated else None,
        )
        return str(c.id)
    except Exception as exc:
        logger.warning('No se pudo registrar la consulta: %s', exc)
        return None


def _nombre(user) -> str:
    if not user or not user.is_authenticated:
        return ''
    return (user.get_full_name() or user.username or '')[:150]


def _correccion_dict(c: CorreccionTraduccion) -> dict:
    return {
        'id': str(c.id), 'tipo': c.tipo, 'veredicto': c.veredicto, 'aplicada': c.aplicada,
        'lengua': {'id': c.lengua_id, 'codigo': c.lengua.codigo, 'nombre': c.lengua.nombre},
        'termino': {'id': c.termino_id, 'termino': c.termino.termino, 'termino_es': c.termino.termino_es.termino if c.termino.termino_es else '',
                    'definicion': c.termino.definicion, 'tipo_morfema': c.termino.tipo_morfema} if c.termino else None,
        'direccion': c.direccion, 'texto_origen': c.texto_origen, 'propuesta_sistema': c.propuesta_sistema,
        'correccion': c.correccion, 'es_correcta': c.es_correcta, 'comentario': c.comentario,
        'usuario': c.usuario_nombre, 'creado_en': c.creado_en.isoformat(),
        'revisor': _nombre(c.revisor), 'revisado_en': c.revisado_en.isoformat() if c.revisado_en else None, 'nota_revision': c.nota_revision,
        'consulta_id': str(c.consulta_id) if c.consulta_id else None,
    }


class EleccionConsultaView(APIView):
    permission_classes = [EjecutarTraduccion]

    @extend_schema(tags=['Traducción'], summary='Registrar qué opción eligió el usuario (índice de resultados)')
    def post(self, request, pk):
        try:
            idx = int(request.data.get('indice'))
        except (TypeError, ValueError):
            return Response({'error': 'Falta "indice".'}, status=status.HTTP_400_BAD_REQUEST)
        n = ConsultaTraduccion.objects.filter(pk=pk).update(eleccion_usuario=idx)
        if not n:
            return Response({'error': 'Consulta no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'ok': True})


class CorreccionesView(APIView):
    def get_permissions(self):
        return [VerGlosario()] if self.request.method == 'GET' else [EjecutarTraduccion()]

    @extend_schema(tags=['Traducción'], summary='Listar correcciones y validaciones (filtros: veredicto, tipo, lengua)')
    def get(self, request):
        qs = CorreccionTraduccion.objects.select_related('lengua', 'termino', 'termino__termino_es', 'usuario', 'revisor')
        for campo in ('veredicto', 'tipo'):
            if request.query_params.get(campo):
                qs = qs.filter(**{campo: request.query_params[campo]})
        if request.query_params.get('lengua'):
            qs = qs.filter(lengua__codigo=request.query_params['lengua'])
        limite = min(int(request.query_params.get('limite', 100)), 500)
        total = qs.count()
        return Response({'total': total, 'resultados': [_correccion_dict(c) for c in qs[:limite]]})

    @extend_schema(tags=['Traducción'], summary='Proponer una corrección o validar una hipótesis / traducción compuesta')
    def post(self, request):
        from terminos.models import Lengua, TerminoLeng
        d = request.data
        tipo = d.get('tipo', 'correccion')
        if tipo not in dict(CorreccionTraduccion.TIPOS):
            return Response({'error': 'Tipo no válido.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            lengua = Lengua.objects.get(pk=d.get('lengua_id'))
        except (Lengua.DoesNotExist, ValueError, TypeError):
            return Response({'error': 'lengua_id no válido.'}, status=status.HTTP_400_BAD_REQUEST)
        termino = None
        if d.get('termino_id'):
            termino = TerminoLeng.objects.filter(pk=d['termino_id'], lengua=lengua).first()
            if termino is None:
                return Response({'error': 'termino_id no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        correccion = (d.get('correccion') or '').strip()
        es_correcta = d.get('es_correcta')
        if tipo == 'correccion' and not correccion:
            return Response({'error': 'Escribe la traducción correcta.'}, status=status.HTTP_400_BAD_REQUEST)
        if tipo != 'correccion' and es_correcta is None and not correccion:
            return Response({'error': 'Indica si es correcta o escribe la forma correcta.'}, status=status.HTTP_400_BAD_REQUEST)
        consulta = ConsultaTraduccion.objects.filter(pk=d['consulta_id']).first() if d.get('consulta_id') else None
        c = CorreccionTraduccion.objects.create(
            tipo=tipo, consulta=consulta, lengua=lengua, termino=termino, direccion=(d.get('direccion') or '')[:20],
            texto_origen=(d.get('texto_origen') or '')[:2000], propuesta_sistema=(d.get('propuesta_sistema') or '')[:2000],
            correccion=correccion[:2000], es_correcta=es_correcta if es_correcta is None else bool(es_correcta),
            comentario=(d.get('comentario') or '')[:2000], usuario=request.user, usuario_nombre=_nombre(request.user),
        )
        return Response(_correccion_dict(c), status=status.HTTP_201_CREATED)


class RevisarCorreccionView(APIView):
    permission_classes = [EditarGlosario]

    @extend_schema(tags=['Traducción'], summary='Aprobar/rechazar una corrección y, si se pide, aplicarla al glosario',
                   description='Body: {"veredicto": "aprobada"|"rechazada", "aplicar": true|false, "nota": "...", '
                               '"termino": "...", "termino_es": "...", "definicion": "..."} (los tres últimos permiten ajustar lo que se escribe en el glosario).')
    def post(self, request, pk):
        from terminos.models import TerminoEs, TerminoLeng
        c = CorreccionTraduccion.objects.select_related('lengua', 'termino', 'termino__termino_es').filter(pk=pk).first()
        if c is None:
            return Response({'error': 'No encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        veredicto = request.data.get('veredicto')
        if veredicto not in ('aprobada', 'rechazada'):
            return Response({'error': 'veredicto debe ser "aprobada" o "rechazada".'}, status=status.HTTP_400_BAD_REQUEST)
        aplicar = bool(request.data.get('aplicar', veredicto == 'aprobada'))
        detalle = {}
        with transaction.atomic():
            c.veredicto = veredicto
            c.revisor = request.user
            c.revisado_en = timezone.now()
            c.nota_revision = (request.data.get('nota') or '')[:2000]
            if aplicar:
                if c.tipo == 'validacion_hipotesis' and c.termino:
                    if veredicto == 'aprobada' and (c.es_correcta or c.correccion):
                        if c.correccion and c.direccion != 'es_a_lengua':
                            # la persona corrigió el español
                            es_obj, _ = TerminoEs.objects.get_or_create(termino=(request.data.get('termino_es') or c.correccion).strip()[:255])
                            c.termino.termino_es = es_obj
                        c.termino.tipo_morfema = None     # deja de ser hipótesis
                        c.termino.definicion = (request.data.get('definicion') or c.termino.definicion.replace('Hipótesis derivada del análisis de segmentos', 'Validado con hablante (antes hipótesis)'))[:5000]
                        c.termino.save(update_fields=['termino_es', 'tipo_morfema', 'definicion', 'updated_at'])
                        detalle = {'accion': 'hipotesis_validada', 'termino_id': c.termino_id}
                    elif veredicto == 'rechazada' or c.es_correcta is False:
                        c.termino.activo = False
                        c.termino.save(update_fields=['activo', 'updated_at'])
                        detalle = {'accion': 'hipotesis_desactivada', 'termino_id': c.termino_id}
                elif veredicto == 'aprobada':
                    # corrección o compuesta aprobada → entra al glosario como término nuevo o actualiza uno existente
                    if c.direccion == 'es_a_lengua':
                        t_leng, t_es = (request.data.get('termino') or c.correccion), (request.data.get('termino_es') or c.texto_origen)
                    else:
                        t_leng, t_es = (request.data.get('termino') or c.texto_origen), (request.data.get('termino_es') or c.correccion)
                    t_leng, t_es = t_leng.strip()[:255], t_es.strip()[:255]
                    if t_leng and t_es:
                        es_obj, _ = TerminoEs.objects.get_or_create(termino=t_es)
                        defi = (request.data.get('definicion') or f'Validado por {c.usuario_nombre or "usuario"} y aprobado por {_nombre(request.user)} desde el traductor: {t_es}.')[:5000]
                        obj, creado = TerminoLeng.objects.get_or_create(
                            termino=t_leng, lengua=c.lengua,
                            defaults={'termino_es': es_obj, 'definicion': defi, 'pos': 'FRS' if ' ' in t_leng else 'NOM', 'activo': True})
                        if not creado:
                            obj.termino_es = es_obj
                            obj.activo = True
                            if request.data.get('definicion'):
                                obj.definicion = defi
                            obj.save(update_fields=['termino_es', 'activo', 'definicion', 'updated_at'])
                        detalle = {'accion': 'termino_creado' if creado else 'termino_actualizado', 'termino_id': obj.id}
                c.aplicada = bool(detalle)
            c.save()
        return Response({'ok': True, 'correccion': _correccion_dict(c), 'detalle': detalle})


class PendientesValidacionView(APIView):
    permission_classes = [VerGlosario]

    @extend_schema(tags=['Traducción'], summary='Cola de validación: hipótesis sin validar y correcciones pendientes')
    def get(self, request):
        from terminos.models import TerminoLeng
        hip = TerminoLeng.objects.filter(tipo_morfema='hipótesis', activo=True).select_related('lengua', 'termino_es')
        if request.query_params.get('lengua'):
            hip = hip.filter(lengua__codigo=request.query_params['lengua'])
        ya = set(CorreccionTraduccion.objects.filter(tipo='validacion_hipotesis', veredicto='pendiente').values_list('termino_id', flat=True))
        return Response({
            'hipotesis': [{'id': t.id, 'lengua': t.lengua.codigo, 'termino': t.termino, 'termino_es': t.termino_es.termino if t.termino_es else '',
                           'definicion': t.definicion, 'pos': t.pos, 'con_validacion_pendiente': t.id in ya} for t in hip],
            'correcciones_pendientes': CorreccionTraduccion.objects.filter(veredicto='pendiente').count(),
        })


class EstadisticasTraduccionView(APIView):
    permission_classes = [VerGlosario]

    @extend_schema(tags=['Traducción'], summary='Estadísticas de uso del traductor (últimos N días, por defecto 30)')
    def get(self, request):
        dias = min(int(request.query_params.get('dias', 30)), 365)
        desde = timezone.now() - timedelta(days=dias)
        qs = ConsultaTraduccion.objects.filter(creado_en__gte=desde)
        total = qs.count()
        por_lengua = list(qs.values('lengua__codigo', 'lengua__nombre', 'direccion').annotate(n=Count('id'), en_glosario=Count('id', filter=Q(en_glosario=True))).order_by('-n'))
        sin = (qs.filter(en_glosario=False).values('texto_normalizado', 'lengua__codigo', 'direccion')
               .annotate(n=Count('id')).order_by('-n')[:30])
        sin_coincidencia = []
        for s in sin:
            ejemplo = qs.filter(texto_normalizado=s['texto_normalizado'], lengua__codigo=s['lengua__codigo']).values_list('texto', flat=True).first()
            sin_coincidencia.append({'texto': ejemplo, 'lengua': s['lengua__codigo'], 'direccion': s['direccion'], 'veces': s['n']})
        verif = list(qs.exclude(verificacion_estado='').values('verificacion_estado').annotate(n=Count('id')).order_by('-n'))
        fuentes = list(qs.exclude(fuente='').values('fuente').annotate(n=Count('id')).order_by('-n'))
        cambiaron = qs.filter(eleccion_usuario__isnull=False).exclude(eleccion_usuario=0).count()
        return Response({
            'dias': dias, 'total_consultas': total,
            'pct_en_glosario': round(100 * qs.filter(en_glosario=True).count() / total, 1) if total else None,
            'pct_usuario_cambio_opcion': round(100 * cambiaron / total, 1) if total else None,
            'por_lengua_direccion': por_lengua, 'por_fuente': fuentes, 'por_estado_verificacion': verif,
            'sin_coincidencia_frecuentes': sin_coincidencia,
            'correcciones': {k: CorreccionTraduccion.objects.filter(veredicto=k).count() for k in ('pendiente', 'aprobada', 'rechazada')},
            'hipotesis_sin_validar': __import__('terminos.models', fromlist=['TerminoLeng']).TerminoLeng.objects.filter(tipo_morfema='hipótesis', activo=True).count(),
        })


class HistorialGlosarioView(APIView):
    permission_classes = [VerGlosario]

    @extend_schema(tags=['Traducción'], summary='Historial de cambios del glosario (filtros: termino_id, lengua, accion, usuario, limite)')
    def get(self, request):
        qs = HistorialTermino.objects.select_related('usuario')
        q = request.query_params
        if q.get('termino_id'):
            qs = qs.filter(Q(termino_id=q['termino_id']) | Q(termino_id_original=q['termino_id']))
        if q.get('lengua'):
            qs = qs.filter(lengua_codigo=q['lengua'])
        if q.get('accion'):
            qs = qs.filter(accion=q['accion'])
        if q.get('usuario'):
            qs = qs.filter(usuario_nombre__icontains=q['usuario'])
        limite = min(int(q.get('limite', 100)), 1000)
        total = qs.count()
        return Response({'total': total, 'resultados': [{
            'id': h.id, 'termino_id': h.termino_id or h.termino_id_original, 'termino': h.termino_texto, 'lengua': h.lengua_codigo,
            'accion': h.accion, 'cambios': h.cambios, 'usuario': h.usuario_nombre or 'sistema', 'origen': h.origen, 'creado_en': h.creado_en.isoformat(),
        } for h in qs[:limite]]})
