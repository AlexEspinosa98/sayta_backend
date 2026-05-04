from django.urls import path
from .views import (
    openapi_schema_view,
    recordings_by_community_view,
    recordings_debug_path_view,
    recordings_root_view,
    swagger_ui_view,
    translate_view,
)


urlpatterns = [
    path('schema/', openapi_schema_view, name='openapi_schema'),
    path('docs/', swagger_ui_view, name='swagger_ui'),
    path('traducir/', translate_view, name='traducir'),
    path('grabaciones/debug/path/', recordings_debug_path_view, name='grabaciones_debug_path'),
    path('grabaciones/', recordings_root_view, name='grabaciones_root'),
    path('grabaciones/<str:community>/', recordings_by_community_view, name='grabaciones_community'),
]
