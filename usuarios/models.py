from django.contrib.auth.models import User
from django.db import models


class PerfilUsuario(models.Model):
    ROL_ADMIN = 'admin'
    ROL_DESARROLLADOR = 'desarrollador'
    ROL_INVESTIGADOR = 'investigador'
    ROL_ANOTADOR = 'anotador'
    ROL_CONSULTOR = 'consultor'

    ROL_CHOICES = [
        (ROL_ADMIN, 'Administrador'),
        (ROL_DESARROLLADOR, 'Desarrollador'),
        (ROL_INVESTIGADOR, 'Investigador'),
        (ROL_ANOTADOR, 'Anotador'),
        (ROL_CONSULTOR, 'Consultor'),
    ]

    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='perfil',
    )
    rol = models.CharField(
        max_length=20,
        choices=ROL_CHOICES,
        default=ROL_CONSULTOR,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'perfiles_usuario'
        verbose_name = 'Perfil de Usuario'
        verbose_name_plural = 'Perfiles de Usuario'

    def __str__(self):
        return f'{self.usuario.username} [{self.get_rol_display()}]'
