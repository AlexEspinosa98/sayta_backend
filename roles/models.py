from django.conf import settings
from django.db import models


class Modulo(models.Model):
    """Una sección funcional del sistema: glosario, etiquetas, entrenamiento..."""

    codigo = models.SlugField(max_length=50, unique=True, db_index=True)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    orden = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'roles_modulos'
        ordering = ['orden', 'nombre']
        verbose_name = 'Módulo'
        verbose_name_plural = 'Módulos'

    def __str__(self):
        return self.nombre


class SubModulo(models.Model):
    """Una vista o bloque funcional dentro de un módulo."""

    modulo = models.ForeignKey(Modulo, related_name='submodulos', on_delete=models.CASCADE)
    codigo = models.SlugField(max_length=50)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    orden = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'roles_submodulos'
        unique_together = ('modulo', 'codigo')
        ordering = ['modulo__orden', 'orden', 'nombre']
        verbose_name = 'Submódulo'
        verbose_name_plural = 'Submódulos'

    def __str__(self):
        return f'{self.modulo.codigo}.{self.codigo}'


class Permiso(models.Model):
    """Una acción concreta dentro de un módulo: ver, crear, editar, entrenar..."""

    modulo = models.ForeignKey(Modulo, related_name='permisos', on_delete=models.CASCADE)
    submodulo = models.ForeignKey(
        SubModulo,
        related_name='permisos',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    codigo = models.SlugField(max_length=50)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    activo = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'roles_permisos_catalogo'
        unique_together = ('modulo', 'submodulo', 'codigo')
        ordering = ['modulo__orden', 'submodulo__orden', 'codigo']
        verbose_name = 'Permiso'
        verbose_name_plural = 'Permisos'

    def __str__(self):
        if self.submodulo_id:
            return f'{self.modulo.codigo}.{self.submodulo.codigo}.{self.codigo}'
        return f'{self.modulo.codigo}.{self.codigo}'


class Rol(models.Model):
    """Un conjunto con nombre de permisos, asignable a usuarios."""

    codigo = models.SlugField(max_length=50, unique=True, db_index=True)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    es_sistema = models.BooleanField(
        default=False,
        help_text='Roles semilla protegidos contra borrado accidental.',
    )
    activo = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'roles_roles'
        ordering = ['nombre']
        verbose_name = 'Rol'
        verbose_name_plural = 'Roles'

    def __str__(self):
        return self.nombre


class RolPermiso(models.Model):
    """La matriz rol × permiso."""

    rol = models.ForeignKey(Rol, related_name='rol_permisos', on_delete=models.CASCADE)
    permiso = models.ForeignKey(Permiso, related_name='rol_permisos', on_delete=models.CASCADE)

    class Meta:
        db_table = 'roles_rol_permisos'
        unique_together = ('rol', 'permiso')
        verbose_name = 'Permiso de Rol'
        verbose_name_plural = 'Permisos de Rol'

    def __str__(self):
        return f'{self.rol.codigo} → {self.permiso}'


class Auditoria(models.Model):
    """
    Rastro de acciones sensibles: quién hizo qué, dónde y cuándo.

    Se registra automáticamente en el motor de permisos (roles.services) para
    toda acción distinta de "ver" — pensado especialmente para roles con
    permisos restringidos (ej. colaboradores de comunidad que solo etiquetan
    o editan, sin poder eliminar nada).
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='acciones_auditadas',
    )
    modulo = models.CharField(max_length=50, db_index=True)
    accion = models.CharField(max_length=50, db_index=True)
    metodo_http = models.CharField(max_length=10)
    ruta = models.CharField(max_length=500)
    objeto_id = models.CharField(max_length=100, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'roles_auditoria'
        ordering = ['-creado_en']
        verbose_name = 'Registro de Auditoría'
        verbose_name_plural = 'Registros de Auditoría'

    def __str__(self):
        usuario = self.usuario.username if self.usuario else '(usuario eliminado)'
        return f'{self.creado_en:%Y-%m-%d %H:%M} — {usuario} — {self.modulo}.{self.accion}'
