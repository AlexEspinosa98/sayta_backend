from django.contrib.auth.models import User
from django.db import models


class PerfilUsuario(models.Model):
    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='perfil',
    )
    rol = models.ForeignKey(
        'roles.Rol',
        on_delete=models.PROTECT,
        related_name='perfiles',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'perfiles_usuario'
        verbose_name = 'Perfil de Usuario'
        verbose_name_plural = 'Perfiles de Usuario'

    def __str__(self):
        return f'{self.usuario.username} [{self.rol.nombre}]'
