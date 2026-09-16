from rest_framework import serializers

from .models import Modulo, Permiso, Rol, SubModulo


class PermisoSerializer(serializers.ModelSerializer):
    modulo_codigo = serializers.CharField(source='modulo.codigo', read_only=True)
    submodulo_codigo = serializers.CharField(source='submodulo.codigo', read_only=True, allow_null=True)

    class Meta:
        model = Permiso
        fields = [
            'id', 'modulo', 'modulo_codigo', 'submodulo', 'submodulo_codigo',
            'codigo', 'nombre', 'descripcion', 'activo',
        ]
        read_only_fields = ['id', 'modulo', 'modulo_codigo', 'submodulo', 'submodulo_codigo']


class PermisoCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permiso
        fields = ['codigo', 'nombre', 'descripcion', 'activo']


class SubModuloSerializer(serializers.ModelSerializer):
    modulo_codigo = serializers.CharField(source='modulo.codigo', read_only=True)
    permisos = PermisoSerializer(many=True, read_only=True)

    class Meta:
        model = SubModulo
        fields = [
            'id', 'modulo', 'modulo_codigo', 'codigo', 'nombre',
            'descripcion', 'orden', 'activo', 'permisos',
        ]
        read_only_fields = ['id', 'modulo', 'modulo_codigo', 'permisos']


class SubModuloCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubModulo
        fields = ['codigo', 'nombre', 'descripcion', 'orden', 'activo']


class ModuloSerializer(serializers.ModelSerializer):
    submodulos = SubModuloSerializer(many=True, read_only=True)
    permisos = serializers.SerializerMethodField()

    class Meta:
        model = Modulo
        fields = [
            'id', 'codigo', 'nombre', 'descripcion', 'orden',
            'activo', 'submodulos', 'permisos',
        ]
        read_only_fields = ['id', 'submodulos', 'permisos']

    def get_permisos(self, obj):
        permisos = obj.permisos.filter(submodulo__isnull=True)
        return PermisoSerializer(permisos, many=True).data


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
