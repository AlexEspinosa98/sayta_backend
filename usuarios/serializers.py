from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import serializers

from roles.models import Rol
from .models import PerfilUsuario


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, data):
        identificador = data.get('username') or data.get('email')
        if not identificador:
            raise serializers.ValidationError('Debes enviar username o email.')

        username = identificador
        if '@' in identificador:
            user_by_email = User.objects.filter(email__iexact=identificador).first()
            if user_by_email:
                username = user_by_email.username

        user = authenticate(username=username, password=data['password'])
        if not user:
            raise serializers.ValidationError('Credenciales incorrectas.')
        if not user.is_active:
            raise serializers.ValidationError('Usuario inactivo.')
        data['user'] = user
        return data


class PerfilSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerfilUsuario
        fields = ['rol', 'etnia', 'comunidad', 'created_at']
        read_only_fields = ['created_at']


def _validar_codigo_rol(value):
    if not Rol.objects.filter(codigo=value, activo=True).exists():
        raise serializers.ValidationError(
            f'"{value}" no es un rol válido o está inactivo. '
            'Consulta los roles disponibles en GET /api/admin/roles/.'
        )
    return value


class UsuarioSerializer(serializers.ModelSerializer):
    rol = serializers.SerializerMethodField()
    rol_display = serializers.SerializerMethodField()
    etnia = serializers.SerializerMethodField()
    etnia_display = serializers.SerializerMethodField()
    comunidad = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'is_active', 'rol', 'rol_display', 'etnia', 'etnia_display',
            'comunidad', 'date_joined',
        ]
        read_only_fields = ['id', 'date_joined']

    def get_rol(self, obj):
        try:
            return obj.perfil.rol.codigo
        except PerfilUsuario.DoesNotExist:
            return None

    def get_rol_display(self, obj):
        try:
            return obj.perfil.rol.nombre
        except PerfilUsuario.DoesNotExist:
            return None

    def get_etnia(self, obj):
        try:
            return obj.perfil.etnia or None
        except PerfilUsuario.DoesNotExist:
            return None

    def get_etnia_display(self, obj):
        try:
            return obj.perfil.get_etnia_display() if obj.perfil.etnia else None
        except PerfilUsuario.DoesNotExist:
            return None

    def get_comunidad(self, obj):
        try:
            return obj.perfil.comunidad or None
        except PerfilUsuario.DoesNotExist:
            return None


class _DatosCuentaSerializer(serializers.Serializer):
    """Campos comunes de cuenta compartidos por el registro admin y el público."""

    username = serializers.CharField(max_length=150, required=False, allow_blank=True)
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True, min_length=8, style={'input_type': 'password'}
    )
    first_name = serializers.CharField(max_length=150, required=False, default='')
    last_name = serializers.CharField(max_length=150, required=False, default='')
    etnia = serializers.ChoiceField(
        choices=PerfilUsuario.ETNIA_CHOICES,
        required=False,
        allow_blank=True,
    )
    comunidad = serializers.CharField(max_length=150, required=False, allow_blank=True, default='')

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('Este nombre de usuario ya existe.')
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Este correo ya está registrado.')
        return value

    def validate(self, data):
        username = (data.get('username') or '').strip()
        if not username:
            username = data['email'].split('@')[0]
            base = username
            contador = 2
            while User.objects.filter(username=username).exists():
                username = f'{base}{contador}'
                contador += 1
            data['username'] = username
        return data


class RegistroSerializer(_DatosCuentaSerializer):
    """Registro hecho por un administrador: elige el rol explícitamente."""

    rol = serializers.CharField()

    def validate_rol(self, value):
        return _validar_codigo_rol(value)

    def create(self, validated_data):
        rol_codigo = validated_data.pop('rol')
        password = validated_data.pop('password')
        etnia = validated_data.pop('etnia', '')
        comunidad = validated_data.pop('comunidad', '')
        user = User.objects.create_user(password=password, **validated_data)
        rol = Rol.objects.get(codigo=rol_codigo)
        PerfilUsuario.objects.create(
            usuario=user,
            rol=rol,
            etnia=etnia,
            comunidad=comunidad,
        )
        return user


class RegistroPublicoSerializer(_DatosCuentaSerializer):
    """
    Auto-registro público, sin autenticación.

    La cuenta nace con el rol 'pendiente' (sin ningún permiso). Un
    administrador debe asignarle un rol real desde
    PATCH /api/auth/usuarios/<id>/ antes de que pueda usar el sistema.
    """

    def create(self, validated_data):
        password = validated_data.pop('password')
        etnia = validated_data.pop('etnia', '')
        comunidad = validated_data.pop('comunidad', '')
        user = User.objects.create_user(password=password, **validated_data)
        rol = Rol.objects.get(codigo='pendiente')
        PerfilUsuario.objects.create(
            usuario=user,
            rol=rol,
            etnia=etnia,
            comunidad=comunidad,
        )
        return user


class ActualizarUsuarioSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, required=False)
    email = serializers.EmailField(required=False)
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
    rol = serializers.CharField(required=False)
    etnia = serializers.ChoiceField(
        choices=PerfilUsuario.ETNIA_CHOICES,
        required=False,
        allow_blank=True,
    )
    comunidad = serializers.CharField(max_length=150, required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)
    password = serializers.CharField(
        write_only=True, min_length=8, required=False, style={'input_type': 'password'}
    )

    def validate_rol(self, value):
        return _validar_codigo_rol(value)

    def validate_email(self, value):
        user_id = self.context.get('user_id')
        if User.objects.filter(email=value).exclude(pk=user_id).exists():
            raise serializers.ValidationError('Este correo ya está en uso.')
        return value

    def validate_username(self, value):
        user_id = self.context.get('user_id')
        if User.objects.filter(username=value).exclude(pk=user_id).exists():
            raise serializers.ValidationError('Este nombre de usuario ya está en uso.')
        return value
