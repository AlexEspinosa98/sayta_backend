from django.urls import path

from .views import TraducirView
from .views_aprendizaje import (CorreccionesView, EleccionConsultaView, EstadisticasTraduccionView,
                                AudioEjemploView, HistorialGlosarioView, PendientesValidacionView, RevisarCorreccionView)

urlpatterns = [
    path('traducir/', TraducirView.as_view(), name='traduccion-traducir'),
    path('consultas/<uuid:pk>/eleccion/', EleccionConsultaView.as_view(), name='traduccion-eleccion'),
    path('correcciones/', CorreccionesView.as_view(), name='traduccion-correcciones'),
    path('correcciones/<uuid:pk>/revisar/', RevisarCorreccionView.as_view(), name='traduccion-revisar'),
    path('pendientes-validacion/', PendientesValidacionView.as_view(), name='traduccion-pendientes'),
    path('estadisticas/', EstadisticasTraduccionView.as_view(), name='traduccion-estadisticas'),
    path('historial-glosario/', HistorialGlosarioView.as_view(), name='traduccion-historial-glosario'),
    path('audio-ejemplo/', AudioEjemploView.as_view(), name='traduccion-audio-ejemplo'),
]
