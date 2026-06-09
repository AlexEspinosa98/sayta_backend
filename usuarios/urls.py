from django.urls import path

from .views import (
    LoginView,
    LogoutView,
    PerfilView,
    RegistroView,
    SetupAdminView,
    UsuarioDetailView,
    UsuariosListView,
)

urlpatterns = [
    path('setup/', SetupAdminView.as_view(), name='auth_setup'),
    path('login/', LoginView.as_view(), name='auth_login'),
    path('logout/', LogoutView.as_view(), name='auth_logout'),
    path('perfil/', PerfilView.as_view(), name='auth_perfil'),
    path('registro/', RegistroView.as_view(), name='auth_registro'),
    path('usuarios/', UsuariosListView.as_view(), name='auth_usuarios'),
    path('usuarios/<int:pk>/', UsuarioDetailView.as_view(), name='auth_usuario_detail'),
]
