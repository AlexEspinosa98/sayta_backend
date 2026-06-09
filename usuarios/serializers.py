from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import serializers

from .models import PerfilUsuario


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, data):
        user = authenticate(username=data['username'], password=data['password'])
        if not user:
            raise serializers.ValidationError('Credenciales incorrectas.')
        if not user.is_active:
            raise serializers.ValidationError('Usuario inactivo.')
        data['user'] = user
        return data


class PerfilSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerfilUsuario
        fields = ['rol', 'created_at']
        read_only_fields = ['created_at']


class UsuarioSerializer(serializers.ModelSerializer):
    rol = serializers.SerializerMethodField()
    rol_display = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'is_active', 'rol', 'rol_display', 'date_joined',
        ]
        read_only_fields = ['id', 'date_joined']

    def get_rol(self, obj):
        try:
            return obj.perfil.rol
        except PerfilUsuario.DoesNotExist:
            return None

    def get_rol_display(self, obj):
        try:
            return obj.perfil.get_rol_display()
        except PerfilUsuario.DoesNotExist:
            return None


class RegistroSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True, min_length=8, style={'input_type': 'password'}
    )
    first_name = serializers.CharField(max_length=150, required=False, default='')
    last_name = serializers.CharField(max_length=150, required=False, default='')
    rol = serializers.ChoiceField(choices=PerfilUsuario.ROL_CHOICES)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('Este nombre de usuario ya existe.')
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Este correo ya está registrado.')
        return value

    def create(self, validated_data):
        rol = validated_data.pop('rol')
        password = validated_data.pop('password')
        user = User.objects.create_user(password=password, **validated_data)
        PerfilUsuario.objects.create(usuario=user, rol=rol)
        return user


class ActualizarUsuarioSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
    rol = serializers.ChoiceField(choices=PerfilUsuario.ROL_CHOICES, required=False)
    is_active = serializers.BooleanField(required=False)
    password = serializers.CharField(
        write_only=True, min_length=8, required=False, style={'input_type': 'password'}
    )

    def validate_email(self, value):
        user_id = self.context.get('user_id')
        if User.objects.filter(email=value).exclude(pk=user_id).exists():
            raise serializers.ValidationError('Este correo ya está en uso.')
        return value
