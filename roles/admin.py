from django.contrib import admin

from .models import Auditoria, Modulo, Permiso, Rol, RolPermiso


class PermisoInline(admin.TabularInline):
    model = Permiso
    extra = 0


@admin.register(Modulo)
class ModuloAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'orden', 'activo')
    list_filter = ('activo',)
    search_fields = ('codigo', 'nombre')
    inlines = [PermisoInline]


class RolPermisoInline(admin.TabularInline):
    model = RolPermiso
    extra = 0
    autocomplete_fields = ['permiso']


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'es_sistema', 'activo', 'created_at')
    list_filter = ('es_sistema', 'activo')
    search_fields = ('codigo', 'nombre')
    inlines = [RolPermisoInline]


@admin.register(Permiso)
class PermisoAdmin(admin.ModelAdmin):
    list_display = ('modulo', 'codigo', 'nombre')
    list_filter = ('modulo',)
    search_fields = ('codigo', 'nombre')


@admin.register(Auditoria)
class AuditoriaAdmin(admin.ModelAdmin):
    list_display = ('creado_en', 'usuario', 'modulo', 'accion', 'metodo_http', 'ruta', 'ip')
    list_filter = ('modulo', 'accion')
    search_fields = ('usuario__username', 'ruta', 'objeto_id')
    readonly_fields = [f.name for f in Auditoria._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
