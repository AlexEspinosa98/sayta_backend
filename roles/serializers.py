from rest_framework import serializers

from .models import Modulo, Permiso, Rol


class PermisoSerializer(serializers.ModelSerializer):
    modulo_codigo = serializers.CharField(source='modulo.codigo', read_only=True)

    class Meta:
        model = Permiso
        fields = ['id', 'modulo', 'modulo_codigo', 'codigo', 'nombre', 'descripcion']
        read_only_fields = ['id', 'modulo', 'modulo_codigo']


class PermisoCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permiso
        fields = ['codigo', 'nombre', 'descripcion']


class ModuloSerializer(serializers.ModelSerializer):
    permisos = PermisoSerializer(many=True, read_only=True)

    class Meta:
        model = Modulo
        fields = ['id', 'codigo', 'nombre', 'descripcion', 'orden', 'activo', 'permisos']
        read_only_fields = ['id', 'permisos']


class ModuloCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Modulo
        fields = ['codigo', 'nombre', 'descripcion', 'orden', 'activo']


class RolSerializer(serializers.ModelSerializer):
    total_usuarios = serializers.SerializerMethodField()
    total_permisos = serializers.SerializerMethodField()

    class Meta:
        model = Rol
        fields = [
            'id', 'codigo', 'nombre', 'descripcion', 'es_sistema', 'activo',
            'total_usuarios', 'total_permisos', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'es_sistema', 'created_at', 'updated_at']

    def get_total_usuarios(self, obj):
        return obj.perfiles.count()

    def get_total_permisos(self, obj):
        return obj.rol_permisos.count()


class RolCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rol
        fields = ['codigo', 'nombre', 'descripcion', 'activo']


class AsignarPermisosSerializer(serializers.Serializer):
    permiso_ids = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=True
    )

    def validate_permiso_ids(self, value):
        existentes = set(Permiso.objects.filter(id__in=value).values_list('id', flat=True))
        faltantes = set(value) - existentes
        if faltantes:
            raise serializers.ValidationError(f'IDs de permiso inexistentes: {sorted(faltantes)}')
        return value
