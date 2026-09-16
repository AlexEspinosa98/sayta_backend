from django.contrib.auth.models import User
from django.db import models


class PerfilUsuario(models.Model):
    ETNIA_ARHUACO = 'arhuaco'
    ETNIA_KOGUI = 'kogui'
    ETNIA_CHOICES = [
        (ETNIA_ARHUACO, 'Arhuaco'),
        (ETNIA_KOGUI, 'Kogui'),
    ]

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
    etnia = models.CharField(max_length=30, choices=ETNIA_CHOICES, blank=True)
    comunidad = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'perfiles_usuario'
        verbose_name = 'Perfil de Usuario'
        verbose_name_plural = 'Perfiles de Usuario'

    def __str__(self):
        return f'{self.usuario.username} [{self.rol.nombre}]'
