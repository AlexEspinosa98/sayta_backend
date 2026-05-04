from django.urls import path
from .views import (
    recordings_by_community_view,
    recordings_root_view,
    translate_view,
)


urlpatterns = [
    path('traducir/', translate_view, name='traducir'),
    path('grabaciones/', recordings_root_view, name='grabaciones_root'),
    path('grabaciones/<str:community>/', recordings_by_community_view, name='grabaciones_community'),
]
