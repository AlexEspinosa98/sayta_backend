"""
Crea el primer usuario administrador del sistema.

Uso:
  python manage.py crear_admin
  python manage.py crear_admin --username=admin --email=admin@sayta.co --password=MiClave123
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from usuarios.models import PerfilUsuario


class Command(BaseCommand):
    help = 'Crea el primer usuario administrador con perfil de rol admin.'

    def add_arguments(self, parser):
        parser.add_argument('--username', default='admin')
        parser.add_argument('--email', default='admin@sayta.co')
        parser.add_argument('--password', default='admin1234')
        parser.add_argument('--first_name', default='Admin')
        parser.add_argument('--last_name', default='Sayta')

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password']

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(
                f'El usuario "{username}" ya existe. Omitiendo creación.'
            ))
            user = User.objects.get(username=username)
        else:
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
                first_name=options['first_name'],
                last_name=options['last_name'],
            )
            self.stdout.write(self.style.SUCCESS(f'Usuario "{username}" creado.'))

        perfil, created = PerfilUsuario.objects.get_or_create(
            usuario=user,
            defaults={'rol': PerfilUsuario.ROL_ADMIN},
        )
        if not created and perfil.rol != PerfilUsuario.ROL_ADMIN:
            perfil.rol = PerfilUsuario.ROL_ADMIN
            perfil.save(update_fields=['rol'])

        self.stdout.write(self.style.SUCCESS(
            f'\n✓ Admin listo:\n'
            f'  username : {username}\n'
            f'  email    : {email}\n'
            f'  password : {password}\n'
            f'  rol      : Administrador\n\n'
            f'Cambia la contraseña con:\n'
            f'  python manage.py changepassword {username}\n'
        ))
