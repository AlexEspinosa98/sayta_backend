from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from .views import EmbeddingVersionViewSet, LenguaViewSet, TerminoEsViewSet, TerminoLengViewSet

router = DefaultRouter()
router.register(r'lenguas', LenguaViewSet, basename='lengua')
router.register(r'terminos-es', TerminoEsViewSet, basename='termino-es')
router.register(r'terminos', TerminoLengViewSet, basename='termino-leng')
router.register(r'embeddings', EmbeddingVersionViewSet, basename='embedding-version')

urlpatterns = [
    path('openapi.json', SpectacularAPIView.as_view(), name='schema-spectacular'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema-spectacular'), name='swagger-terminos'),
] + router.urls
