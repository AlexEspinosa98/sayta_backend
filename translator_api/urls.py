from django.urls import path
from .views import translate_view


urlpatterns = [
    path('traducir/', translate_view, name='traducir'),
]
