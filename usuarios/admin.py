from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import PerfilUsuario


class PerfilInline(admin.StackedInline):
    model = PerfilUsuario
    can_delete = False
    verbose_name_plural = 'Perfil y Rol'
    fk_name = 'usuario'


class UsuarioConPerfilAdmin(UserAdmin):
    inlines = (PerfilInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_rol', 'is_active')

    def get_rol(self, obj):
        try:
            return obj.perfil.get_rol_display()
        except PerfilUsuario.DoesNotExist:
            return '—'
    get_rol.short_description = 'Rol'


admin.site.unregister(User)
admin.site.register(User, UsuarioConPerfilAdmin)
admin.site.register(PerfilUsuario)
