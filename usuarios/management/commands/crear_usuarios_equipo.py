"""
Crea o asegura las cuentas reales del equipo Sayta:
  - 1 administrador
  - 3 desarrolladores
  - 2 colaboradores de comunidad (kogui, arhuaco) con el rol restringido
    'colaborador_lengua': solo pueden etiquetar audios y editar el glosario,
    nunca crear ni eliminar. Toda acción queda registrada en roles.Auditoria.

Es idempotente: si el usuario ya existe, no lo recrea ni le toca la
contraseña — solo asegura que tenga el rol correcto. Para usuarios nuevos
genera una contraseña aleatoria y la imprime una sola vez en consola (no se
guarda en ningún archivo del repo).

Uso:
  python manage.py crear_usuarios_equipo
"""

import secrets
import string

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from roles.models import Rol
from usuarios.models import PerfilUsuario

USUARIOS_EQUIPO = [
    {
        'email': 'alexanderespinosaev@unimagdalena.edu.co',
        'first_name': 'Alexander',
        'last_name': 'Espinosa',
        'rol': 'admin',
        'is_staff': True,
        'is_superuser': True,
    },
    {
        'email': 'dilancabasam@unimagdalena.edu.co',
        'first_name': 'Dilan',
        'last_name': 'Cabas',
        'rol': 'desarrollador',
        'is_staff': True,
        'is_superuser': False,
    },
    {
        'email': 'haroldhernandezds@unimagdalena.edu.co',
        'first_name': 'Harold',
        'last_name': 'Hernandez',
        'rol': 'desarrollador',
        'is_staff': True,
        'is_superuser': False,
    },
    {
        'email': 'josesalgadofc@unimagdalena.edu.co',
        'first_name': 'Jose',
        'last_name': 'Salgado',
        'rol': 'desarrollador',
        'is_staff': True,
        'is_superuser': False,
    },
    {
        'username': 'kogui',
        'email': 'colaborador.kogui@sayta.co',
        'first_name': 'Colaborador',
        'last_name': 'Kogui',
        'rol': 'colaborador_lengua',
        'is_staff': False,
        'is_superuser': False,
    },
    {
        'username': 'arhuaco',
        'email': 'colaborador.arhuaco@sayta.co',
        'first_name': 'Colaborador',
        'last_name': 'Arhuaco',
        'rol': 'colaborador_lengua',
        'is_staff': False,
        'is_superuser': False,
    },
]


def _username_from_email(email: str) -> str:
    return email.split('@')[0]


def _generar_password() -> str:
    alfabeto = string.ascii_letters + string.digits
    cuerpo = ''.join(secrets.choice(alfabeto) for _ in range(14))
    return cuerpo + secrets.choice('!@#%*-_')


class Command(BaseCommand):
    help = 'Crea/asegura las cuentas reales del equipo Sayta con sus roles.'

    def handle(self, *args, **options):
        creados = []

        for data in USUARIOS_EQUIPO:
            username = data.get('username') or _username_from_email(data['email'])
            rol = Rol.objects.filter(codigo=data['rol']).first()
            if rol is None:
                self.stderr.write(self.style.ERROR(
                    f'Rol "{data["rol"]}" no existe todavía. Corre las migraciones primero '
                    f'(python manage.py migrate).'
                ))
                continue

            user = User.objects.filter(username=username).first()
            if user is None:
                password = _generar_password()
                user = User.objects.create_user(
                    username=username,
                    email=data['email'],
                    password=password,
                    first_name=data['first_name'],
                    last_name=data['last_name'],
                    is_staff=data['is_staff'],
                    is_superuser=data['is_superuser'],
                )
                PerfilUsuario.objects.create(usuario=user, rol=rol)
                creados.append((username, data['email'], password, rol.nombre))
                self.stdout.write(self.style.SUCCESS(f'Usuario creado: {username} [{rol.nombre}]'))
            else:
                perfil, _ = PerfilUsuario.objects.get_or_create(usuario=user, defaults={'rol': rol})
                if perfil.rol_id != rol.id:
                    perfil.rol = rol
                    perfil.save(update_fields=['rol'])
                self.stdout.write(self.style.WARNING(
                    f'Usuario "{username}" ya existía — rol asegurado como "{rol.nombre}".'
                ))

        if creados:
            self.stdout.write('\n' + '=' * 70)
            self.stdout.write(self.style.SUCCESS(
                'CREDENCIALES NUEVAS — cópialas ahora, no se vuelven a mostrar:'
            ))
            self.stdout.write('=' * 70)
            for username, email, password, rol_nombre in creados:
                self.stdout.write(f'  usuario  : {username}')
                self.stdout.write(f'  email    : {email}')
                self.stdout.write(f'  password : {password}')
                self.stdout.write(f'  rol      : {rol_nombre}')
                self.stdout.write('  ' + '-' * 40)
            self.stdout.write(
                '\nPide a cada persona cambiar su contraseña en el primer login, '
                'o hazlo tú con: python manage.py changepassword <usuario>\n'
            )
        else:
            self.stdout.write('\nNo se crearon usuarios nuevos (todos ya existían).')
