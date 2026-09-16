"""
Semilla del catálogo de módulos/permisos y de los roles del sistema.

Reproduce exactamente la matriz ya documentada en HISTORIAS_USUARIO_AUTH.md para
los 5 roles fijos, y agrega un nuevo rol `colaborador_lengua` para colaboradores
de comunidad (ej. usuarios kogui/arhuaco) con acceso restringido: solo pueden
etiquetar audios y editar el glosario de su lengua, nunca eliminar ni crear.
Toda acción de este tipo queda registrada en roles.Auditoria.
"""

from django.db import migrations

# ---------------------------------------------------------------------------
# Catálogo de módulos y permisos
# ---------------------------------------------------------------------------

MODULOS = [
    {
        'codigo': 'usuarios',
        'nombre': 'Usuarios',
        'descripcion': 'Cuentas, login y gestión del equipo.',
        'orden': 1,
        'permisos': [
            ('ver', 'Ver usuarios'),
            ('crear', 'Registrar usuarios'),
            ('editar', 'Editar usuarios'),
            ('eliminar', 'Desactivar usuarios'),
            ('gestionar_roles', 'Administrar roles y permisos (panel de administración)'),
        ],
    },
    {
        'codigo': 'glosario',
        'nombre': 'Glosario y Términos',
        'descripcion': 'Lenguas, términos en español y términos en lengua indígena.',
        'orden': 2,
        'permisos': [
            ('ver', 'Ver lenguas y términos'),
            ('crear', 'Crear lenguas y términos'),
            ('editar', 'Editar lenguas y términos'),
            ('eliminar', 'Eliminar/desactivar términos'),
            ('carga_masiva', 'Carga masiva de términos'),
        ],
    },
    {
        'codigo': 'embeddings',
        'nombre': 'Embeddings',
        'descripcion': 'Versiones de embeddings semánticos por lengua.',
        'orden': 3,
        'permisos': [
            ('ver', 'Ver embeddings'),
            ('generar', 'Generar embeddings'),
            ('activar', 'Activar versión de embedding'),
        ],
    },
    {
        'codigo': 'dataset_audio',
        'nombre': 'Dataset de Audios',
        'descripcion': 'Grabaciones, sesiones, subida y etiquetado de audio.',
        'orden': 4,
        'permisos': [
            ('ver', 'Ver dataset y estadísticas'),
            ('subir', 'Subir audios al dataset'),
            ('etiquetar', 'Etiquetar/transcribir audios'),
            ('eliminar', 'Eliminar etiquetas de audios'),
        ],
    },
    {
        'codigo': 'modelos_asr',
        'nombre': 'Modelos ASR',
        'descripcion': 'Catálogo, descarga y entrenamiento de modelos de reconocimiento de voz.',
        'orden': 5,
        'permisos': [
            ('ver', 'Ver catálogo y modelos'),
            ('descargar_modelo', 'Descargar modelos HuggingFace'),
            ('entrenar', 'Lanzar entrenamiento'),
            ('activar_experimento', 'Activar experimento entrenado'),
            ('cancelar_experimento', 'Cancelar entrenamiento en curso'),
            ('liberar_memoria', 'Liberar memoria GPU/caché'),
        ],
    },
    {
        'codigo': 'transcripcion',
        'nombre': 'Transcripción',
        'descripcion': 'Transcripción de audio con modelo ASR activo.',
        'orden': 6,
        'permisos': [
            ('ejecutar', 'Transcribir audio'),
        ],
    },
    {
        'codigo': 'traduccion',
        'nombre': 'Traducción',
        'descripcion': 'Traducción semántica de texto.',
        'orden': 7,
        'permisos': [
            ('ejecutar', 'Traducir texto'),
        ],
    },
]

# ---------------------------------------------------------------------------
# Roles del sistema y su matriz de permisos
# ---------------------------------------------------------------------------

# 'TODO' es un atajo: expande a todos los permisos del módulo.
TODO = '__todos__'

ROLES = [
    {
        'codigo': 'admin',
        'nombre': 'Administrador',
        'descripcion': 'Acceso total. Registra usuarios y administra roles/permisos.',
        'permisos': {
            'usuarios': TODO,
            'glosario': TODO,
            'embeddings': TODO,
            'dataset_audio': TODO,
            'modelos_asr': TODO,
            'transcripcion': TODO,
            'traduccion': TODO,
        },
    },
    {
        'codigo': 'desarrollador',
        'nombre': 'Desarrollador',
        'descripcion': 'Equipo técnico. Mismo acceso funcional que investigador, sin gestión de usuarios.',
        'permisos': {
            'glosario': TODO,
            'embeddings': TODO,
            'dataset_audio': TODO,
            'modelos_asr': TODO,
            'transcripcion': TODO,
            'traduccion': TODO,
        },
    },
    {
        'codigo': 'investigador',
        'nombre': 'Investigador',
        'descripcion': 'Investigador lingüístico. Lenguas, términos, embeddings y entrenamiento ASR.',
        'permisos': {
            'glosario': TODO,
            'embeddings': TODO,
            'dataset_audio': TODO,
            'modelos_asr': TODO,
            'transcripcion': TODO,
            'traduccion': TODO,
        },
    },
    {
        'codigo': 'anotador',
        'nombre': 'Anotador',
        'descripcion': 'Equipo de campo. Sube y etiqueta audios en el dataset.',
        'permisos': {
            'glosario': ['ver'],
            'embeddings': ['ver'],
            'dataset_audio': TODO,
            'modelos_asr': ['ver'],
            'transcripcion': TODO,
            'traduccion': TODO,
        },
    },
    {
        'codigo': 'consultor',
        'nombre': 'Consultor',
        'descripcion': 'Usuario de solo lectura. Consulta y traduce, no modifica datos.',
        'permisos': {
            'glosario': ['ver'],
            'embeddings': ['ver'],
            'dataset_audio': ['ver'],
            'modelos_asr': ['ver'],
            'transcripcion': TODO,
            'traduccion': TODO,
        },
    },
    {
        'codigo': 'colaborador_lengua',
        'nombre': 'Colaborador de Lengua',
        'descripcion': (
            'Colaborador de comunidad (ej. hablantes kogui/arhuaco). Puede etiquetar '
            'audios y editar el glosario, pero nunca crear registros nuevos ni eliminar '
            'nada. Toda acción queda registrada en la auditoría.'
        ),
        'permisos': {
            'glosario': ['ver', 'editar'],
            'embeddings': ['ver'],
            'dataset_audio': ['ver', 'etiquetar'],
            'modelos_asr': ['ver'],
            'transcripcion': TODO,
            'traduccion': TODO,
        },
    },
    {
        'codigo': 'pendiente',
        'nombre': 'Pendiente de aprobación',
        'descripcion': (
            'Rol asignado automáticamente al auto-registrarse desde '
            'POST /api/auth/registro-publico/. No tiene ningún permiso — '
            'un administrador debe asignarle un rol real desde '
            'PATCH /api/auth/usuarios/<id>/ antes de que pueda usar el sistema.'
        ),
        'permisos': {},
    },
]


def poblar_catalogo(apps, schema_editor):
    Modulo = apps.get_model('roles', 'Modulo')
    Permiso = apps.get_model('roles', 'Permiso')
    Rol = apps.get_model('roles', 'Rol')
    RolPermiso = apps.get_model('roles', 'RolPermiso')

    permisos_por_modulo = {}

    for modulo_data in MODULOS:
        modulo, _ = Modulo.objects.get_or_create(
            codigo=modulo_data['codigo'],
            defaults={
                'nombre': modulo_data['nombre'],
                'descripcion': modulo_data['descripcion'],
                'orden': modulo_data['orden'],
            },
        )
        permisos_por_modulo[modulo_data['codigo']] = {}
        for codigo_permiso, nombre_permiso in modulo_data['permisos']:
            permiso, _ = Permiso.objects.get_or_create(
                modulo=modulo,
                codigo=codigo_permiso,
                defaults={'nombre': nombre_permiso},
            )
            permisos_por_modulo[modulo_data['codigo']][codigo_permiso] = permiso

    for rol_data in ROLES:
        rol, _ = Rol.objects.get_or_create(
            codigo=rol_data['codigo'],
            defaults={
                'nombre': rol_data['nombre'],
                'descripcion': rol_data['descripcion'],
                'es_sistema': True,
            },
        )
        for modulo_codigo, seleccion in rol_data['permisos'].items():
            permisos_modulo = permisos_por_modulo[modulo_codigo]
            codigos = permisos_modulo.keys() if seleccion == TODO else seleccion
            for codigo_permiso in codigos:
                RolPermiso.objects.get_or_create(rol=rol, permiso=permisos_modulo[codigo_permiso])


def revertir_catalogo(apps, schema_editor):
    Modulo = apps.get_model('roles', 'Modulo')
    Rol = apps.get_model('roles', 'Rol')
    Rol.objects.filter(codigo__in=[r['codigo'] for r in ROLES]).delete()
    Modulo.objects.filter(codigo__in=[m['codigo'] for m in MODULOS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('roles', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(poblar_catalogo, revertir_catalogo),
    ]
