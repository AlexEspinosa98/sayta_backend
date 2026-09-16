# Historias de Usuario — Sistema de Autenticación y Roles
## Proyecto Sayta — Traductor de Lenguas Indígenas

> **Base URL:** `http://localhost:8000`
> **Swagger UI:** `http://localhost:8000/api/docs/`
> **Prefijo auth:** `/api/auth/`

---

## ⚠️ Actualización: sistema de roles ahora es dinámico

Los roles y permisos dejaron de estar fijos en código. Ahora viven en la base de
datos (app `roles`) y son administrables en vivo desde `/api/admin/` sin
redesplegar. Diseño completo en `PLANIFICACION_ROLES_ADMIN.md`.

Lo que cambia respecto a lo documentado abajo:
- El campo `rol` en las respuestas de `/api/auth/...` sigue siendo un string
  (su `codigo`), pero ahora corresponde a un `Rol` en base de datos, no a una
  lista fija en `usuarios/permissions.py` (ese archivo ya no existe).
- Los permisos están divididos por **módulo** (`glosario`, `dataset_audio`,
  `embeddings`, `modelos_asr`, `transcripcion`, `traduccion`, `usuarios`) y
  **acción** dentro de cada módulo. La matriz completa se consulta en vivo con
  `GET /api/admin/matriz/` (requiere el permiso `usuarios.gestionar_roles`).
- Se agregó un sexto rol, **`colaborador_lengua`**: pensado para colaboradores
  de comunidad (hablantes kogui/arhuaco). Solo puede `ver`, `etiquetar` audios
  y `editar` el glosario — nunca `crear` ni `eliminar`. Toda acción que
  realiza queda registrada en `roles.Auditoria` (rastro de auditoría).
- Antes, `terminos`, `entrenamiento` y `translator_api` no aplicaban ningún
  control de acceso real (el default de DRF era `AllowAny`). Ahora todo
  requiere autenticación y el permiso correspondiente por defecto.
- Nuevo endpoint público **`POST /api/auth/registro-publico/`** (sin token):
  cualquier persona puede crearse una cuenta. Nace con el rol `pendiente`
  (séptimo rol de sistema, sin ningún permiso asignado) — puede loguearse y
  ver su propio perfil, pero cualquier otro endpoint le devuelve `403` hasta
  que un administrador le asigne un rol real con
  `PATCH /api/auth/usuarios/<id>/`.
- El comando `python manage.py crear_usuarios_equipo` (admin + 3
  desarrolladores + colaboradores kogui/arhuaco) ahora corre automáticamente
  en cada arranque del contenedor (`entrypoint.sh`, después de `migrate`).
  Es idempotente: no toca cuentas que ya existen, salvo la contraseña fija
  del admin que se re-asegura en cada corrida.

## Roles del sistema

| Rol | Descripción | Accesos principales |
|---|---|---|
| `admin` | Administrador total | Registra usuarios, administra roles/permisos, acceso completo |
| `desarrollador` | Equipo técnico | Mismo acceso que investigador + panel Django admin |
| `investigador` | Investigador lingüístico | Lenguas, términos, embeddings, entrenamiento ASR |
| `anotador` | Equipo de campo | Sube y etiqueta audios en el dataset |
| `consultor` | Usuario de solo lectura | Consulta y traduce, no modifica datos |
| `colaborador_lengua` | Colaborador de comunidad (kogui/arhuaco) | Solo etiquetar audios y editar glosario — nunca crear ni eliminar. Con rastro de auditoría. |
| `pendiente` | Rol por defecto del auto-registro público | Cero permisos — solo login y ver su propio perfil, hasta que un admin le asigne un rol real. |

### Jerarquía de permisos (roles de sistema originales)

```
admin
  └─ desarrollador
       └─ investigador
            └─ anotador
                 └─ consultor  (solo lectura + traducción)

colaborador_lengua  (rol aparte, acceso acotado a glosario + etiquetado, sin crear/eliminar)
```

Estos 6 roles son los roles semilla (`es_sistema=True`, no se pueden borrar).
Un administrador puede crear roles adicionales en cualquier momento desde
`POST /api/admin/roles/` sin tocar código.

---

## Épica 7 — Autenticación y Gestión de Usuarios

---

### HU-AUTH-01 — Configuración inicial: crear el primer administrador

**Como** equipo técnico en el primer despliegue, **quiero** crear el usuario administrador sin necesitar un token previo, **para** arrancar el sistema sin dependencias circulares.

**Criterios de aceptación:**
- El endpoint solo funciona si NO existe ningún usuario con rol `admin` en el sistema.
- Una vez creado el primer admin, el endpoint devuelve `403` permanentemente.
- La respuesta incluye el token de acceso listo para usar de inmediato.
- El usuario creado tiene `is_staff: true` e `is_superuser: true` (acceso al panel Django admin).

**Endpoint:** `POST /api/auth/setup/`  
**Autenticación requerida:** No (endpoint público)

```bash
# Primer despliegue — sin ningún admin previo
curl -X POST http://localhost:8000/api/auth/setup/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "email": "admin@sayta.co",
    "password": "MiClave2026!",
    "first_name": "Admin",
    "last_name": "Sayta"
  }'

# Respuesta 201 — admin creado
{
  "mensaje": "Administrador \"admin\" creado correctamente.",
  "token": "f6c741a929969027f35a...",
  "usuario": {
    "id": 1,
    "username": "admin",
    "email": "admin@sayta.co",
    "first_name": "Admin",
    "last_name": "Sayta",
    "is_active": true,
    "rol": "admin",
    "rol_display": "Administrador",
    "date_joined": "2026-06-09T10:00:00Z"
  }
}
```

```bash
# Si ya existe un admin → 403
{
  "error": "Ya existe un administrador en el sistema. Usa POST /api/auth/login/ para obtener un token y POST /api/auth/registro/ para crear más usuarios."
}
```

**Comandos alternativos (CLI):**
```bash
# Si tienes acceso al servidor directamente:
python manage.py crear_admin
python manage.py crear_admin --username=admin --email=admin@sayta.co --password=MiClave2026!
```

---

### HU-AUTH-02 — Iniciar sesión y obtener token

**Como** cualquier usuario registrado, **quiero** autenticarme con mi usuario y contraseña, **para** obtener un token que me permita acceder a los endpoints protegidos.

**Criterios de aceptación:**
- Si las credenciales son incorrectas → `400` con mensaje claro.
- Si el usuario está inactivo → `400` con mensaje "Usuario inactivo."
- La respuesta incluye el token y la información completa del usuario (incluyendo rol).
- El token es persistente — no expira automáticamente (debe invalidarse con logout).

**Endpoint:** `POST /api/auth/login/`  
**Autenticación requerida:** No

```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "investigador_sayta",
    "password": "Investigador2026!"
  }'

# Respuesta 200
{
  "token": "a1b2c3d4e5f6...",
  "usuario": {
    "id": 2,
    "username": "investigador_sayta",
    "email": "investigador@sayta.co",
    "nombre": "Investigador Sayta",
    "rol": "investigador",
    "rol_display": "Investigador"
  }
}
```

```bash
# Credenciales incorrectas → 400
{
  "non_field_errors": ["Credenciales incorrectas."]
}
```

**Cómo usar el token en todas las llamadas siguientes:**
```bash
# Cabecera requerida en TODOS los endpoints (salvo login y setup):
Authorization: Token a1b2c3d4e5f6...
```

---

### HU-AUTH-03 — Cerrar sesión e invalidar token

**Como** usuario autenticado, **quiero** cerrar sesión y destruir mi token, **para** que nadie más pueda usarlo si el dispositivo cae en manos de otro.

**Criterios de aceptación:**
- El token queda eliminado de la base de datos al hacer logout.
- Cualquier request posterior con ese token recibe `401 Unauthorized`.
- Si el token ya no existe, el logout igual responde `200` (idempotente).

**Endpoint:** `POST /api/auth/logout/`  
**Autenticación requerida:** Sí (`Authorization: Token ...`)

```bash
curl -X POST http://localhost:8000/api/auth/logout/ \
  -H "Authorization: Token a1b2c3d4e5f6..."

# Respuesta 200
{
  "mensaje": "Sesión cerrada correctamente."
}

# Usar el token ya invalidado → 401
{
  "detail": "Token inválido."
}
```

---

### HU-AUTH-04 — Ver el perfil del usuario autenticado

**Como** cualquier usuario, **quiero** consultar mi propio perfil, **para** saber qué rol tengo asignado y verificar mis datos.

**Endpoint:** `GET /api/auth/perfil/`  
**Autenticación requerida:** Sí

```bash
curl http://localhost:8000/api/auth/perfil/ \
  -H "Authorization: Token a1b2c3d4e5f6..."

# Respuesta 200
{
  "id": 2,
  "username": "investigador_sayta",
  "email": "investigador@sayta.co",
  "first_name": "Investigador",
  "last_name": "Sayta",
  "is_active": true,
  "rol": "investigador",
  "rol_display": "Investigador",
  "date_joined": "2026-06-09T10:05:00Z"
}
```

---

### HU-AUTH-05 — Registrar un nuevo usuario (solo admin)

**Como** administrador, **quiero** crear cuentas para los miembros del equipo con el rol adecuado, **para** que cada persona acceda solo a lo que le corresponde.

**Criterios de aceptación:**
- Solo usuarios con rol `admin` pueden acceder a este endpoint (`403` para otros roles).
- El campo `rol` es obligatorio y debe ser uno de: `admin`, `desarrollador`, `investigador`, `anotador`, `consultor`.
- Si el `username` o el `email` ya existen → `400` con el mensaje de cuál campo está duplicado.
- La contraseña debe tener al menos 8 caracteres.

**Endpoint:** `POST /api/auth/registro/`  
**Autenticación requerida:** Sí — solo rol `admin`

```bash
# Registrar un anotador
curl -X POST http://localhost:8000/api/auth/registro/ \
  -H "Authorization: Token <token-del-admin>" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "maria.lopez",
    "email": "maria@unimagdalena.edu.co",
    "password": "Campo2026!",
    "first_name": "María",
    "last_name": "López",
    "rol": "anotador"
  }'

# Respuesta 201
{
  "mensaje": "Usuario \"maria.lopez\" registrado correctamente.",
  "usuario": {
    "id": 4,
    "username": "maria.lopez",
    "email": "maria@unimagdalena.edu.co",
    "first_name": "María",
    "last_name": "López",
    "is_active": true,
    "rol": "anotador",
    "rol_display": "Anotador",
    "date_joined": "2026-06-09T11:00:00Z"
  }
}
```

```bash
# Registrar un investigador
curl -X POST http://localhost:8000/api/auth/registro/ \
  -H "Authorization: Token <token-del-admin>" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "carlos.gomez",
    "email": "cgomez@unimagdalena.edu.co",
    "password": "Linguist2026!",
    "first_name": "Carlos",
    "last_name": "Gómez",
    "rol": "investigador"
  }'
```

```bash
# Registrar un desarrollador
curl -X POST http://localhost:8000/api/auth/registro/ \
  -H "Authorization: Token <token-del-admin>" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "ana.dev",
    "email": "ana@sayta.co",
    "password": "Dev2026Secure!",
    "first_name": "Ana",
    "last_name": "Martínez",
    "rol": "desarrollador"
  }'
```

```bash
# Sin token → 401
{ "detail": "Las credenciales de autenticación no se proveyeron." }

# Con token de investigador → 403
{ "detail": "Se requiere rol de Administrador." }

# Username duplicado → 400
{ "username": ["Este nombre de usuario ya existe."] }

# Email duplicado → 400
{ "email": ["Este correo ya está registrado."] }
```

---

### HU-AUTH-06 — Listar todos los usuarios del sistema (solo admin)

**Como** administrador, **quiero** ver todos los usuarios registrados con su estado y rol, **para** tener visibilidad del equipo y detectar cuentas que deben actualizarse.

**Endpoint:** `GET /api/auth/usuarios/`  
**Autenticación requerida:** Sí — solo rol `admin`

```bash
curl http://localhost:8000/api/auth/usuarios/ \
  -H "Authorization: Token <token-del-admin>"

# Respuesta 200
{
  "total": 4,
  "usuarios": [
    {
      "id": 1,
      "username": "admin",
      "email": "admin@sayta.co",
      "first_name": "Admin",
      "last_name": "Sayta",
      "is_active": true,
      "rol": "admin",
      "rol_display": "Administrador",
      "date_joined": "2026-06-09T10:00:00Z"
    },
    {
      "id": 3,
      "username": "dev_sayta",
      "email": "dev@sayta.co",
      "first_name": "Desarrollador",
      "last_name": "Sayta",
      "is_active": true,
      "rol": "desarrollador",
      "rol_display": "Desarrollador",
      "date_joined": "2026-06-09T10:00:00Z"
    },
    {
      "id": 2,
      "username": "investigador_sayta",
      "email": "investigador@sayta.co",
      "first_name": "Investigador",
      "last_name": "Sayta",
      "is_active": true,
      "rol": "investigador",
      "rol_display": "Investigador",
      "date_joined": "2026-06-09T10:00:00Z"
    },
    {
      "id": 4,
      "username": "maria.lopez",
      "email": "maria@unimagdalena.edu.co",
      "first_name": "María",
      "last_name": "López",
      "is_active": true,
      "rol": "anotador",
      "rol_display": "Anotador",
      "date_joined": "2026-06-09T11:00:00Z"
    }
  ]
}
```

---

### HU-AUTH-07 — Actualizar datos o rol de un usuario (solo admin)

**Como** administrador, **quiero** cambiar el rol, el email o la contraseña de un usuario, **para** adaptar los accesos cuando el equipo cambia de función.

**Endpoint:** `PATCH /api/auth/usuarios/<id>/`  
**Autenticación requerida:** Sí — solo rol `admin`

```bash
# Cambiar rol de anotador a investigador
curl -X PATCH http://localhost:8000/api/auth/usuarios/4/ \
  -H "Authorization: Token <token-del-admin>" \
  -H "Content-Type: application/json" \
  -d '{"rol": "investigador"}'

# Cambiar contraseña
curl -X PATCH http://localhost:8000/api/auth/usuarios/4/ \
  -H "Authorization: Token <token-del-admin>" \
  -H "Content-Type: application/json" \
  -d '{"password": "NuevaClave2026!"}'

# Actualizar email y nombre
curl -X PATCH http://localhost:8000/api/auth/usuarios/4/ \
  -H "Authorization: Token <token-del-admin>" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "maria.lopez.nueva@unimagdalena.edu.co",
    "first_name": "María Camila"
  }'

# Respuesta 200 — usuario actualizado
{
  "id": 4,
  "username": "maria.lopez",
  "email": "maria.lopez.nueva@unimagdalena.edu.co",
  "first_name": "María Camila",
  "last_name": "López",
  "is_active": true,
  "rol": "investigador",
  "rol_display": "Investigador",
  "date_joined": "2026-06-09T11:00:00Z"
}
```

**Campos editables via PATCH:**

| Campo | Tipo | Descripción |
|---|---|---|
| `email` | string | Nuevo correo (debe ser único) |
| `first_name` | string | Nombre |
| `last_name` | string | Apellido |
| `rol` | string | `admin`, `desarrollador`, `investigador`, `anotador`, `consultor` |
| `is_active` | boolean | `false` = suspender acceso sin eliminar |
| `password` | string | Nueva contraseña (mínimo 8 caracteres) |

---

### HU-AUTH-08 — Desactivar un usuario (solo admin)

**Como** administrador, **quiero** suspender el acceso de un usuario sin eliminar su historial, **para** revocar permisos cuando alguien sale del equipo.

**Criterios de aceptación:**
- El usuario queda con `is_active: false` — no puede hacer login.
- Su token activo es invalidado automáticamente.
- El registro histórico (experimentos, audios subidos, etc.) se conserva.
- Un admin no puede desactivarse a sí mismo.

**Endpoint:** `DELETE /api/auth/usuarios/<id>/`  
**Autenticación requerida:** Sí — solo rol `admin`

```bash
curl -X DELETE http://localhost:8000/api/auth/usuarios/4/ \
  -H "Authorization: Token <token-del-admin>"

# Respuesta 200
{
  "mensaje": "Usuario \"maria.lopez\" desactivado."
}

# Intentar desactivar la propia cuenta → 400
{
  "error": "No puedes desactivar tu propia cuenta."
}

# Reactivar un usuario suspendido (usar PATCH):
curl -X PATCH http://localhost:8000/api/auth/usuarios/4/ \
  -H "Authorization: Token <token-del-admin>" \
  -H "Content-Type: application/json" \
  -d '{"is_active": true}'
```

---

## Tabla resumen de endpoints de autenticación

| # | Método | Endpoint | Autenticación | Roles | Descripción |
|---|---|---|---|---|---|
| 1 | POST | `/api/auth/setup/` | No | — | Crear primer admin (solo si no hay ninguno) |
| 2 | POST | `/api/auth/login/` | No | — | Iniciar sesión, obtener token |
| 3 | POST | `/api/auth/logout/` | Sí | Todos | Cerrar sesión, invalidar token |
| 4 | GET | `/api/auth/perfil/` | Sí | Todos | Ver propio perfil y rol |
| 5 | POST | `/api/auth/registro/` | Sí | `admin` | Registrar nuevo usuario |
| 6 | GET | `/api/auth/usuarios/` | Sí | `admin` | Listar todos los usuarios |
| 7 | GET | `/api/auth/usuarios/<id>/` | Sí | `admin` | Ver detalle de un usuario |
| 8 | PATCH | `/api/auth/usuarios/<id>/` | Sí | `admin` | Actualizar datos o rol |
| 9 | DELETE | `/api/auth/usuarios/<id>/` | Sí | `admin` | Desactivar usuario |

---

## Tabla de permisos por módulo

| Módulo / Acción | admin | desarrollador | investigador | anotador | consultor |
|---|:---:|:---:|:---:|:---:|:---:|
| **Autenticación** |||||
| Login / Logout / Perfil | ✅ | ✅ | ✅ | ✅ | ✅ |
| Registrar usuarios | ✅ | ❌ | ❌ | ❌ | ❌ |
| Ver / Editar usuarios | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Lenguas y Términos** |||||
| Leer (listar, buscar) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Crear / Editar / Eliminar | ✅ | ✅ | ✅ | ❌ | ❌ |
| Carga masiva de términos | ✅ | ✅ | ✅ | ❌ | ❌ |
| **Embeddings** |||||
| Listar / Ver estado | ✅ | ✅ | ✅ | ✅ | ✅ |
| Generar / Activar | ✅ | ✅ | ✅ | ❌ | ❌ |
| **Dataset de audios** |||||
| Ver estadísticas | ✅ | ✅ | ✅ | ✅ | ✅ |
| Subir audios y etiquetar | ✅ | ✅ | ✅ | ✅ | ❌ |
| **Modelos ASR** |||||
| Ver catálogo / modelos | ✅ | ✅ | ✅ | ✅ | ✅ |
| Descargar modelos HF | ✅ | ✅ | ✅ | ❌ | ❌ |
| Lanzar entrenamiento | ✅ | ✅ | ✅ | ❌ | ❌ |
| Activar / Cancelar exp. | ✅ | ✅ | ✅ | ❌ | ❌ |
| Liberar memoria GPU | ✅ | ✅ | ✅ | ❌ | ❌ |
| **Transcripción** |||||
| Transcribir audio | ✅ | ✅ | ✅ | ✅ | ✅ |
| Transcribir + traducir | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Traducción** |||||
| Traducir texto | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## Usuarios semilla incluidos en la migración

Los siguientes usuarios se crean automáticamente al ejecutar `python manage.py migrate`:

| Username | Email | Contraseña inicial | Rol |
|---|---|---|---|
| `investigador_sayta` | `investigador@sayta.co` | `Investigador2026!` | `investigador` |
| `dev_sayta` | `dev@sayta.co` | `Developer2026!` | `desarrollador` |

> **Importante:** Cambiar las contraseñas antes de poner en producción:
> ```bash
> python manage.py changepassword investigador_sayta
> python manage.py changepassword dev_sayta
> ```

El usuario `admin` inicial se crea con:
```bash
python manage.py crear_admin
# o en despliegue sin acceso a CLI:
POST /api/auth/setup/
```

---

## Flujo completo de integración frontend

### 1. Primera vez (despliegue inicial)

```bash
# Paso 1 — Verificar que no hay admin (opcional, el endpoint lo comprueba)
# Paso 2 — Crear el primer admin
curl -X POST http://localhost:8000/api/auth/setup/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "email": "admin@sayta.co", "password": "MiClave2026!"}'
# → Guardar el token de la respuesta

# Paso 3 — Crear el resto del equipo
curl -X POST http://localhost:8000/api/auth/registro/ \
  -H "Authorization: Token <token-del-admin>" \
  -d '{"username": "maria", "email": "maria@uni.edu.co", "password": "Pass2026!", "rol": "anotador"}'
```

### 2. Login normal

```javascript
// Frontend — guardar token en localStorage o cookie httpOnly
const login = async (username, password) => {
  const res = await fetch('/api/auth/login/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  const data = await res.json();
  if (res.ok) {
    localStorage.setItem('token', data.token);
    localStorage.setItem('rol', data.usuario.rol);
  }
  return data;
};

// Añadir token a todas las llamadas
const authHeaders = {
  'Authorization': `Token ${localStorage.getItem('token')}`,
  'Content-Type': 'application/json',
};
```

### 3. Guard de rutas por rol

```javascript
// Verificar rol antes de mostrar pantallas restringidas
const puedoEntrenar = ['admin', 'desarrollador', 'investigador'].includes(rol);
const puedoAnotar  = ['admin', 'desarrollador', 'investigador', 'anotador'].includes(rol);
const puedoGestionar = rol === 'admin';
```

### 4. Manejo de errores de autenticación

```javascript
// Si cualquier llamada devuelve 401:
if (response.status === 401) {
  localStorage.removeItem('token');
  navigate('/login');
}

// Si devuelve 403 (rol insuficiente):
if (response.status === 403) {
  showError('No tienes permisos para realizar esta acción.');
}
```

---

## Errores frecuentes

| Código | Mensaje | Causa | Solución |
|---|---|---|---|
| `401` | `"Las credenciales de autenticación no se proveyeron."` | Falta el header `Authorization` | Añadir `Authorization: Token <token>` |
| `401` | `"Token inválido."` | Token incorrecto o eliminado (logout) | Hacer login de nuevo |
| `400` | `"Credenciales incorrectas."` | Usuario o contraseña erróneos | Verificar datos de login |
| `400` | `"Usuario inactivo."` | La cuenta fue desactivada | Contactar al admin |
| `403` | `"Se requiere rol de Administrador."` | Tu rol no tiene permiso | El admin debe cambiar tu rol |
| `403` | `"Ya existe un administrador."` | Setup llamado dos veces | Usar `/api/auth/login/` en su lugar |

---

---

## Épica 8 — Data Augmentation en Entrenamiento ASR

> **Prefijo:** `/api/entrenamiento/`  
> **Autenticación requerida en todos los endpoints:** Sí (`Authorization: Token ...`)

Data Augmentation genera nuevas muestras de audio a partir de las grabaciones existentes
aplicando transformaciones (ruido, velocidad, tono, volumen, etc.) sin modificar los archivos
originales. Cada muestra generada hereda la transcripción del audio fuente.

**¿Por qué importa para lenguas indígenas?**  
Los corpus de lenguas como Iku o Kogui suelen tener menos de 500 grabaciones. Con un 30 % de
`ruido_gaussiano` sobre 100 muestras se producen 30 archivos extra, pasando de 100 a 130
muestras de entrenamiento sin necesidad de nuevas jornadas de campo.

---

### Permisos de acceso

| Acción | admin | desarrollador | investigador | anotador | consultor |
|---|:---:|:---:|:---:|:---:|:---:|
| Ver catálogo de técnicas | ✅ | ✅ | ✅ | ✅ | ✅ |
| Lanzar entrenamiento con augmentation | ✅ | ✅ | ✅ | ❌ | ❌ |
| Ver config de augmentation en experimento | ✅ | ✅ | ✅ | ✅ | ✅ |

---

### HU-AUG-01 — Consultar catálogo de técnicas disponibles

**Como** investigador o desarrollador, **quiero** ver todas las técnicas de augmentation
disponibles con sus parámetros y valores por defecto, **para** saber qué opciones tengo
antes de lanzar un experimento de entrenamiento.

**Criterios de aceptación:**
- La respuesta lista todas las técnicas con nombre, descripción y parámetros detallados.
- Cada técnica incluye: tipo de parámetro, rango válido (min/max), valor por defecto y descripción.
- La respuesta incluye un bloque `config_ejemplo` por técnica listo para copiar en `POST /entrenar/`.
- La respuesta incluye un `ejemplo_completo_para_entrenar` con todas las técnicas ya formateadas.
- El endpoint es de solo lectura y está disponible para cualquier usuario autenticado.

**Endpoint:** `GET /api/entrenamiento/dataset/augmentation/`  
**Autenticación requerida:** Sí — cualquier rol

```bash
curl http://localhost:8000/api/entrenamiento/dataset/augmentation/ \
  -H "Authorization: Token <token>"

# Respuesta 200
{
  "total_tecnicas": 6,
  "tecnicas_recomendadas": ["ruido_gaussiano", "cambio_velocidad", "cambio_tono", "reduccion_volumen"],
  "tecnicas": {
    "ruido_gaussiano": {
      "nombre": "Ruido Gaussiano",
      "descripcion": "Añade ruido blanco gaussiano al audio. Simula grabaciones en entornos con ruido ambiental...",
      "parametros": {
        "intensidad": {
          "tipo": "float",
          "min": 0.001,
          "max": 0.05,
          "default": 0.005,
          "descripcion": "Amplitud del ruido relativa a la señal. 0.005 = sutil, 0.03 = notable."
        }
      },
      "porcentaje_default": 30,
      "recomendado": true,
      "impacto_tiempo": "bajo",
      "requiere_gpu": false,
      "config_ejemplo": {
        "habilitado": true,
        "porcentaje": 30,
        "intensidad": 0.005
      }
    },
    "cambio_velocidad": {
      "nombre": "Cambio de Velocidad (Time Stretching)",
      "parametros": {
        "factor_min": { "tipo": "float", "min": 0.7, "max": 1.0, "default": 0.9, "descripcion": "..." },
        "factor_max": { "tipo": "float", "min": 1.0, "max": 1.3, "default": 1.1, "descripcion": "..." }
      },
      "porcentaje_default": 20,
      "recomendado": true,
      "impacto_tiempo": "medio",
      "config_ejemplo": { "habilitado": true, "porcentaje": 20, "factor_min": 0.9, "factor_max": 1.1 }
    },
    "cambio_tono": { "...": "ver respuesta completa en Swagger" },
    "reduccion_volumen": { "...": "ver respuesta completa en Swagger" },
    "recorte_tiempo": { "...": "ver respuesta completa en Swagger" },
    "eco": { "...": "ver respuesta completa en Swagger" }
  },
  "ejemplo_completo_para_entrenar": {
    "habilitado": true,
    "tecnicas": {
      "ruido_gaussiano":   { "habilitado": true, "porcentaje": 30, "intensidad": 0.005 },
      "cambio_velocidad":  { "habilitado": true, "porcentaje": 20, "factor_min": 0.9, "factor_max": 1.1 },
      "cambio_tono":       { "habilitado": true, "porcentaje": 20, "semitonos_min": -2, "semitonos_max": 2 },
      "reduccion_volumen": { "habilitado": true, "porcentaje": 20, "factor_min": 0.5, "factor_max": 0.9 },
      "recorte_tiempo":    { "habilitado": false, "porcentaje": 15, "max_porcentaje_clip": 10 },
      "eco":               { "habilitado": false, "porcentaje": 10, "delay_ms": 50, "decay": 0.2 }
    }
  }
}
```

---

### HU-AUG-02 — Lanzar entrenamiento con data augmentation activado

**Como** investigador, **quiero** habilitar el data augmentation al lanzar un experimento
eligiendo qué técnicas aplicar y en qué porcentaje del dataset, **para** aumentar el tamaño
efectivo del conjunto de entrenamiento sin necesitar nuevas grabaciones.

**Criterios de aceptación:**
- El campo `augmentation` es opcional — si se omite, el entrenamiento se ejecuta sin augmentation.
- Si `habilitado: false`, se ignoran todas las técnicas aunque estén definidas.
- Solo se aplican las técnicas que tienen `habilitado: true` dentro de `tecnicas`.
- Una técnica sin `porcentaje` explícito usa el valor por defecto del catálogo.
- El campo `porcentaje` controla qué fracción de las muestras de entrenamiento recibe esa transformación.
  Ej: 100 muestras + `ruido_gaussiano` al 30 % → 30 archivos nuevos → **130 muestras totales**.
- Los archivos generados se guardan en disco bajo `<uuid_experimento>/augmented/` y se cachean.
- En la respuesta aparece `config_usada.augmentation` confirmando qué quedó configurado.
- Las técnicas activas se registran en MLflow (`augmentation_habilitado`, `augmentation_tecnicas`).

**Endpoint:** `POST /api/entrenamiento/entrenar/`  
**Autenticación requerida:** Sí — rol `investigador`, `desarrollador` o `admin`

```bash
# Entrenamiento con augmentation — recomendado para datasets pequeños (< 500 muestras)
curl -X POST http://localhost:8000/api/entrenamiento/entrenar/ \
  -H "Authorization: Token <token-investigador>" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "arhuaco-wav2vec2-aug-v1",
    "lengua_id": 1,
    "modelo_audio_id": 2,
    "todos": true,
    "config": {
      "num_train_epochs": 30,
      "learning_rate": 0.0001,
      "use_peft": false
    },
    "augmentation": {
      "habilitado": true,
      "tecnicas": {
        "ruido_gaussiano":   { "habilitado": true, "porcentaje": 30, "intensidad": 0.005 },
        "cambio_velocidad":  { "habilitado": true, "porcentaje": 20 },
        "cambio_tono":       { "habilitado": true, "porcentaje": 20 },
        "reduccion_volumen": { "habilitado": true, "porcentaje": 20 },
        "recorte_tiempo":    { "habilitado": false },
        "eco":               { "habilitado": false }
      }
    }
  }'

# Respuesta 202 — entrenamiento iniciado
{
  "mensaje": "Entrenamiento iniciado.",
  "experimento_id": "3f8a1c2d-...",
  "task_id": "a9b2c3d4-...",
  "num_muestras": 87,
  "config_usada": {
    "num_train_epochs": 30,
    "learning_rate": 0.0001,
    "use_peft": false,
    "augmentation": {
      "habilitado": true,
      "tecnicas": {
        "ruido_gaussiano":   { "habilitado": true, "porcentaje": 30, "intensidad": 0.005 },
        "cambio_velocidad":  { "habilitado": true, "porcentaje": 20 },
        "cambio_tono":       { "habilitado": true, "porcentaje": 20 },
        "reduccion_volumen": { "habilitado": true, "porcentaje": 20 },
        "recorte_tiempo":    { "habilitado": false },
        "eco":               { "habilitado": false }
      }
    }
  },
  "advertencias_config": [],
  "estado_url": "/api/entrenamiento/experimentos/3f8a1c2d-.../estado/"
}
```

```bash
# Entrenamiento SIN augmentation (omitir el campo o habilitado: false)
curl -X POST http://localhost:8000/api/entrenamiento/entrenar/ \
  -H "Authorization: Token <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "arhuaco-baseline",
    "lengua_id": 1,
    "modelo_audio_id": 2,
    "todos": true,
    "config": { "num_train_epochs": 20 }
  }'
```

---

### HU-AUG-03 — Configurar cada técnica individualmente con sus parámetros

**Como** investigador, **quiero** controlar los parámetros específicos de cada técnica
(intensidad del ruido, rango de velocidad, semitonos, etc.), **para** adaptar el augmentation
al tipo de grabaciones y a las características fonológicas de la lengua.

**Criterios de aceptación:**
- Cada técnica acepta sus propios parámetros opcionales; si se omiten se usan los defaults del catálogo.
- Los parámetros son validados por la API: valores fuera de rango devuelven `400`.
- Se pueden activar/desactivar técnicas de forma granular sin eliminar su configuración.

**Referencia de parámetros por técnica:**

#### `ruido_gaussiano`
| Parámetro | Tipo | Rango | Default | Descripción |
|---|---|---|---|---|
| `habilitado` | bool | — | `false` | Activa la técnica |
| `porcentaje` | float | 1–100 | `30` | % de muestras que reciben la transformación |
| `intensidad` | float | 0.001–0.05 | `0.005` | Amplitud del ruido. `0.005` = sutil, `0.03` = notable |

```json
{ "habilitado": true, "porcentaje": 30, "intensidad": 0.005 }
```

#### `cambio_velocidad`
| Parámetro | Tipo | Rango | Default | Descripción |
|---|---|---|---|---|
| `habilitado` | bool | — | `false` | Activa la técnica |
| `porcentaje` | float | 1–100 | `20` | % de muestras |
| `factor_min` | float | 0.7–1.0 | `0.9` | Velocidad mínima (`0.9` = 10 % más lento) |
| `factor_max` | float | 1.0–1.3 | `1.1` | Velocidad máxima (`1.1` = 10 % más rápido) |

```json
{ "habilitado": true, "porcentaje": 20, "factor_min": 0.85, "factor_max": 1.15 }
```

#### `cambio_tono`
| Parámetro | Tipo | Rango | Default | Descripción |
|---|---|---|---|---|
| `habilitado` | bool | — | `false` | Activa la técnica |
| `porcentaje` | float | 1–100 | `20` | % de muestras |
| `semitonos_min` | int | -6–0 | `-2` | Desplazamiento mínimo (negativo = más grave) |
| `semitonos_max` | int | 0–6 | `2` | Desplazamiento máximo (positivo = más agudo) |

```json
{ "habilitado": true, "porcentaje": 20, "semitonos_min": -3, "semitonos_max": 3 }
```

#### `reduccion_volumen`
| Parámetro | Tipo | Rango | Default | Descripción |
|---|---|---|---|---|
| `habilitado` | bool | — | `false` | Activa la técnica |
| `porcentaje` | float | 1–100 | `20` | % de muestras |
| `factor_min` | float | 0.2–0.8 | `0.5` | Ganancia mínima (`0.5` = 50 % del volumen) |
| `factor_max` | float | 0.6–1.0 | `0.9` | Ganancia máxima |

```json
{ "habilitado": true, "porcentaje": 20, "factor_min": 0.4, "factor_max": 0.8 }
```

#### `recorte_tiempo`
| Parámetro | Tipo | Rango | Default | Descripción |
|---|---|---|---|---|
| `habilitado` | bool | — | `false` | Activa la técnica |
| `porcentaje` | float | 1–100 | `15` | % de muestras |
| `max_porcentaje_clip` | int | 5–30 | `10` | Máximo % del audio a silenciar |

```json
{ "habilitado": true, "porcentaje": 15, "max_porcentaje_clip": 10 }
```

#### `eco`
| Parámetro | Tipo | Rango | Default | Descripción |
|---|---|---|---|---|
| `habilitado` | bool | — | `false` | Activa la técnica |
| `porcentaje` | float | 1–100 | `10` | % de muestras |
| `delay_ms` | int | 10–200 | `50` | Retardo del eco en milisegundos |
| `decay` | float | 0.05–0.5 | `0.2` | Amplitud del eco (`0.2` = 20 % de la señal) |

```json
{ "habilitado": true, "porcentaje": 10, "delay_ms": 80, "decay": 0.25 }
```

**Errores de validación:**
```bash
# porcentaje fuera de rango → 400
{ "augmentation": { "tecnicas": { "ruido_gaussiano": { "porcentaje": ["Ensure this value is less than or equal to 100.0."] } } } }

# intensidad fuera de rango → 400
{ "augmentation": { "tecnicas": { "ruido_gaussiano": { "intensidad": ["Ensure this value is greater than or equal to 0.001."] } } } }
```

---

### HU-AUG-04 — Verificar el augmentation aplicado en un experimento

**Como** investigador, **quiero** ver en el detalle de un experimento completado
si se usó augmentation y con qué configuración exacta, **para** reproducir los resultados
o comparar dos experimentos (con y sin augmentation).

**Criterios de aceptación:**
- `GET /api/entrenamiento/experimentos/<id>/` incluye `config_entrenamiento.augmentation` si fue activado.
- En MLflow el run muestra los parámetros `augmentation_habilitado` y `augmentation_tecnicas`.
- Los archivos aumentados permanecen en disco en `<ruta_modelo_entrenado>/augmented/` como evidencia.

**Endpoint:** `GET /api/entrenamiento/experimentos/<id>/`  
**Autenticación requerida:** Sí — cualquier rol autenticado

```bash
curl http://localhost:8000/api/entrenamiento/experimentos/3f8a1c2d-.../ \
  -H "Authorization: Token <token>"

# Respuesta 200 — fragmento relevante de config_entrenamiento
{
  "id": "3f8a1c2d-...",
  "nombre": "arhuaco-wav2vec2-aug-v1",
  "estado": "completado",
  "num_muestras_train": 113,
  "num_muestras_eval": 13,
  "metricas": {
    "eval_wer": 0.312,
    "eval_cer": 0.189,
    "train_loss": 0.428,
    "estrategia": "split_simple"
  },
  "config_entrenamiento": {
    "num_train_epochs": 30,
    "augmentation": {
      "habilitado": true,
      "tecnicas": {
        "ruido_gaussiano":  { "habilitado": true, "porcentaje": 30, "intensidad": 0.005 },
        "cambio_velocidad": { "habilitado": true, "porcentaje": 20 },
        "cambio_tono":      { "habilitado": true, "porcentaje": 20 },
        "reduccion_volumen":{ "habilitado": true, "porcentaje": 20 },
        "recorte_tiempo":   { "habilitado": false },
        "eco":              { "habilitado": false }
      }
    }
  },
  "mlflow_run_id": "a1b2c3d4e5f6...",
  "mlflow_tracking_uri": "sqlite:///mlflow.db"
}
```

```bash
# Comparar dos experimentos — con y sin augmentation
curl http://localhost:8000/api/entrenamiento/experimentos/baseline-id/   # WER: 0.41
curl http://localhost:8000/api/entrenamiento/experimentos/aug-v1-id/     # WER: 0.31 → mejora de ~25 %
```

---

## Tabla resumen — endpoints de Data Augmentation

| # | Método | Endpoint | Auth | Roles | Descripción |
|---|---|---|---|---|---|
| 1 | GET | `/api/entrenamiento/dataset/augmentation/` | Sí | Todos | Ver catálogo de técnicas con parámetros y ejemplos |
| 2 | POST | `/api/entrenamiento/entrenar/` | Sí | `investigador`+ | Lanzar entrenamiento (con o sin augmentation) |
| 3 | GET | `/api/entrenamiento/experimentos/<id>/` | Sí | Todos | Ver config de augmentation aplicada al experimento |

---

## Flujo recomendado de trabajo con Data Augmentation

```
1. Consultar catálogo
   GET /api/entrenamiento/dataset/augmentation/
   → Copiar el bloque "ejemplo_completo_para_entrenar"

2. Ajustar técnicas según el dataset
   - Dataset muy pequeño (< 100 muestras): habilitar las 4 técnicas recomendadas al 30–40 %
   - Dataset mediano (100–500):            habilitar 2–3 técnicas al 20–30 %
   - Dataset grande (> 500):               augmentation tiene poco impacto; no es necesario

3. Lanzar experimento con augmentation
   POST /api/entrenamiento/entrenar/ → guardar experimento_id

4. Monitorear progreso
   GET /api/entrenamiento/experimentos/<id>/estado/

5. Comparar resultados en MLflow
   → Filtrar por augmentation_habilitado = true/false
   → Comparar WER entre runs con y sin augmentation
```

---

## Notas técnicas

| Aspecto | Detalle |
|---|---|
| Archivos originales | **Nunca se modifican** — las transformaciones se guardan como nuevos WAV |
| Caché | Si el archivo aumentado ya existe en disco, no se regenera (útil en K-Fold) |
| Transcripción | La muestra aumentada hereda la transcripción exacta del audio fuente |
| Ubicación en disco | `<ruta_experimento>/augmented/<stem>__<tecnica>.wav` |
| Split train/eval | El augmentation se aplica antes del split en modo normal, y por fold en K-Fold (`use_cv: true`) |
| MLflow | Parámetros `augmentation_habilitado` y `augmentation_tecnicas` se logean automáticamente |
| Tiempo extra | `ruido_gaussiano` y `reduccion_volumen`: < 1 s/muestra. `cambio_tono`: 2–5 s/muestra |
