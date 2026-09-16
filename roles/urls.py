from django.urls import path

from .admin_views import (
    MatrizView,
    ModuloDetailView,
    ModuloListCreateView,
    ModuloPermisosView,
    ModuloSubModulosView,
    PermisoDetailView,
    RolDetailView,
    RolListCreateView,
    RolPermisosView,
    SubModuloDetailView,
    SubModuloPermisosView,
)

urlpatterns = [
    path('modulos/', ModuloListCreateView.as_view(), name='admin_modulos'),
    path('modulos/<int:pk>/', ModuloDetailView.as_view(), name='admin_modulo_detail'),
    path('modulos/<int:pk>/permisos/', ModuloPermisosView.as_view(), name='admin_modulo_permisos'),
    path('modulos/<int:pk>/submodulos/', ModuloSubModulosView.as_view(), name='admin_modulo_submodulos'),
    path('submodulos/<int:pk>/', SubModuloDetailView.as_view(), name='admin_submodulo_detail'),
    path('submodulos/<int:pk>/permisos/', SubModuloPermisosView.as_view(), name='admin_submodulo_permisos'),
    path('permisos/<int:pk>/', PermisoDetailView.as_view(), name='admin_permiso_detail'),
    path('roles/', RolListCreateView.as_view(), name='admin_roles'),
    path('roles/<int:pk>/', RolDetailView.as_view(), name='admin_rol_detail'),
    path('roles/<int:pk>/permisos/', RolPermisosView.as_view(), name='admin_rol_permisos'),
    path('matriz/', MatrizView.as_view(), name='admin_matriz'),
]
