from django.urls import path
from .views import (
    recordings_by_community_view,
    recordings_debug_path_view,
    recordings_root_view,
    session_audio_file_view,
    session_audios_view,
    session_estado_view,
    session_etiqueta_view,
    session_etiquetar_view,
    session_glosario_view,
    translate_view,
)


urlpatterns = [
    path('traducir/', translate_view, name='traducir'),

    # Grabaciones — raíz y comunidad
    path('grabaciones/debug/path/', recordings_debug_path_view, name='grabaciones_debug_path'),
    path('grabaciones/', recordings_root_view, name='grabaciones_root'),
    path('grabaciones/<str:community>/', recordings_by_community_view, name='grabaciones_community'),

    # Grabaciones — jornada / sesión
    path('grabaciones/<str:community>/<str:session>/audios/', session_audios_view, name='session_audios'),
    path('grabaciones/<str:community>/<str:session>/audios/<str:filename>', session_audio_file_view, name='session_audio_file'),
    path('grabaciones/<str:community>/<str:session>/glosario/', session_glosario_view, name='session_glosario'),
    path('grabaciones/<str:community>/<str:session>/etiquetar/', session_etiquetar_view, name='session_etiquetar'),
    path('grabaciones/<str:community>/<str:session>/etiqueta/<str:filename>/', session_etiqueta_view, name='session_etiqueta'),
    path('grabaciones/<str:community>/<str:session>/estado/', session_estado_view, name='session_estado'),
]
