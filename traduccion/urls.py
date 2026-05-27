from django.urls import path
from .views import TraducirView

urlpatterns = [
    path('traducir/', TraducirView.as_view(), name='traduccion-traducir'),
]
