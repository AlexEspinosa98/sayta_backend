# Planificación — Sistema de Roles Dinámico y Módulo de Administración

## Proyecto Sayta — Traductor de Lenguas Indígenas (Backend)

> **Estado:** Planificación aprobada, pendiente de implementación
> **Alcance:** Backend Django (`sayta_backend`)
> **Relacionado con:** `HISTORIAS_USUARIO_AUTH.md` (documenta el comportamiento actual, este documento define el rediseño)

---

## 1. Resumen ejecutivo

Hoy Sayta tiene 5 roles fijos (`admin`, `desarrollador`, `investigador`, `anotador`, `consultor`)
escritos en código, con permisos hardcodeados en 3 clases (`EsAdmin`, `EsInvestigador`, `EsAnotador`).
Cualquier cambio de "quién puede hacer qué" requiere tocar código y redesplegar.

Este documento planifica el reemplazo de ese esquema por un **sistema de roles y permisos
100% dinámico**, dividido por **secciones** (glosario, etiquetas/dataset de audio, entrenamiento,
embeddings, transcripción, traducción, usuarios), administrable desde un **módulo de admin
dinámico** vía API — sin tocar código para crear roles nuevos o cambiar qué puede hacer cada uno.

De paso, corrige dos huecos de seguridad reales encontrados durante el análisis (sección 3).

---

## 2. Objetivos

| # | Objetivo | Criterio de éxito |
|---|---|---|
| 1 | Roles dinámicos | Un admin puede crear un rol nuevo (ej. `editor_glosario`) desde la API, sin desplegar código |
| 2 | Permisos por sección y acción | Cada módulo (glosario, etiquetas, entrenamiento...) tiene su propio catálogo de acciones (`ver`, `crear`, `editar`, `eliminar`, acciones especiales) |
| 3 | Panel de administración dinámico | Endpoints API para gestionar módulos, permisos, roles y la matriz completa — sin editar `permissions.py` |
| 4 | Login robusto | Mantener y documentar el flujo actual de login por token, compatible con el nuevo modelo de roles |
| 5 | Seguridad real | Todo endpoint queda protegido por defecto; nada depende de que un desarrollador recuerde poner `permission_classes` |
| 6 | Cero downtime de datos | Los 5 roles y usuarios actuales migran sin perder su rol ni su acceso |

### Fuera de alcance (por ahora)

- Frontend / UI del panel de administración (este documento cubre el backend; el panel se puede construir después contra estos endpoints).
- Permisos a nivel de fila/objeto (ej. "solo puedo editar términos que yo mismo creé") — el diseño es por sección+acción, no por owner.
- SSO / OAuth externo — se mantiene autenticación por token.

---

## 3. Diagnóstico del estado actual

### 3.1 Lo que ya existe y se conserva

- App `usuarios`: login/logout por token (`rest_framework.authtoken`), perfil, registro, gestión de usuarios (`/api/auth/...`).
- `PerfilUsuario` (1:1 con `User`) con campo `rol`.
- Comando `python manage.py crear_admin` para el primer admin.
- Endpoint público `POST /api/auth/setup/` para crear el primer admin sin token.
- Matriz de permisos ya **documentada** (no aplicada en código) en `HISTORIAS_USUARIO_AUTH.md`.

### 3.2 Hallazgos críticos de seguridad (a corregir con este cambio)

| # | Hallazgo | Ubicación | Impacto |
|---|---|---|---|
| 1 | `DEFAULT_PERMISSION_CLASSES` está en `AllowAny` con un `TODO: volver a IsAuthenticated antes de producción` sin resolver | `sayta_backend/settings.py:113` | Todos los endpoints de `terminos` (glosario, lenguas, embeddings) y `entrenamiento` (dataset, modelos, experimentos) están abiertos sin autenticación |
| 2 | `translator_api` usa vistas planas de Django (`HttpRequest` / `JsonResponse`), no DRF | `translator_api/views.py` | El etiquetado real (`session_etiquetar_view`, `session_glosario_view`, `session_etiqueta_view`) y la traducción (`translate_view`) no pasan por el sistema de permisos de DRF aunque se active `IsAuthenticated` globalmente — necesitan su propio mecanismo |

Estos dos hallazgos significan que, **hoy**, la matriz de permisos documentada en
`HISTORIAS_USUARIO_AUTH.md` es aspiracional: describe cómo debería comportarse el sistema,
pero no está aplicada donde más importa (glosario, etiquetado, entrenamiento).

### 3.3 Roles y su jerarquía actual (se conservan como roles "de sistema")

```
admin
  └─ desarrollador       (= investigador + acceso a Django admin)
       └─ investigador   (lenguas, términos, embeddings, entrenamiento ASR)
            └─ anotador  (sube y etiqueta audios)
                 └─ consultor  (solo lectura + traducción)
```

---

## 4. Arquitectura propuesta

### 4.1 Vista general

```
┌─────────────────────────────────────────────────────────────────┐
│                         App: roles (nueva)                        │
│                                                                     │
│   Modulo ──┬── Permiso ──┬── RolPermiso ──── Rol                  │
│  (sección)  │  (acción)   │   (matriz)                             │
│             │             │                                        │
│   glosario  │  ver        │                          admin         │
│   etiquetas │  crear      │                          desarrollador │
│   entrenam. │  editar     │                          investigador  │
│   embeddings│  eliminar   │                          anotador      │
│   usuarios  │  entrenar   │                          consultor     │
│   ...       │  etiquetar  │                          (+ los que    │
│             │  ...        │                           cree el admin)│
└──────────────────────────┬──────────────────────────────────────┘
                           │
                 tiene_permiso(user, modulo, accion)
                           │
          ┌────────────────┴─────────────────┐
          │                                    │
   DRF: requiere_permiso(...)      Django plano: @requiere_permiso_django(...)
   (terminos, entrenamiento,        (translator_api: etiquetado, traducción,
    usuarios)                        grabaciones)
```

### 4.2 App nueva: `roles`

Motor de autorización + módulo de administración dinámico. No depende de `usuarios`;
es al revés — `usuarios.PerfilUsuario` pasa a tener FK a `roles.Rol`.

### 4.3 Modelo de datos

#### `Modulo` — una sección del sistema

| Campo | Tipo | Notas |
|---|---|---|
| `codigo` | `SlugField`, único | `'glosario'`, `'dataset_audio'`, ... |
| `nombre` | `CharField` | Nombre visible, ej. "Glosario y Términos" |
| `descripcion` | `TextField`, opcional | |
| `orden` | `PositiveIntegerField` | Para ordenar en un futuro panel |
| `activo` | `BooleanField` | Desactivar sin borrar |

#### `Permiso` — una acción concreta dentro de un módulo

| Campo | Tipo | Notas |
|---|---|---|
| `modulo` | FK → `Modulo` | |
| `codigo` | `SlugField` | `'ver'`, `'crear'`, `'editar'`, `'eliminar'`, `'entrenar'`, ... |
| `nombre` | `CharField` | Nombre visible |
| `descripcion` | `TextField`, opcional | |

`unique_together = ('modulo', 'codigo')`

#### `Rol`

| Campo | Tipo | Notas |
|---|---|---|
| `codigo` | `SlugField`, único | `'admin'`, `'investigador'`, ... o cualquier código nuevo |
| `nombre` | `CharField` | |
| `descripcion` | `TextField`, opcional | |
| `es_sistema` | `BooleanField` | `True` en los 5 roles semilla — protege contra borrado accidental |
| `activo` | `BooleanField` | |
| `created_at` / `updated_at` | `DateTimeField` | |

#### `RolPermiso` — la matriz

| Campo | Tipo | Notas |
|---|---|---|
| `rol` | FK → `Rol` | |
| `permiso` | FK → `Permiso` | |

`unique_together = ('rol', 'permiso')`

#### `PerfilUsuario` (modificado, en `usuarios`)

| Campo | Antes | Después |
|---|---|---|
| `rol` | `CharField(choices=ROL_CHOICES)` | `ForeignKey('roles.Rol', on_delete=models.PROTECT)` |

`on_delete=PROTECT` evita borrar un rol mientras tenga usuarios asignados (se debe reasignar primero).

### 4.4 Motor de chequeo de permisos

Función única, reutilizada por los dos mecanismos de aplicación (DRF y vistas planas):

```python
# roles/services.py
def tiene_permiso(user, modulo_codigo, accion_codigo) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:          # válvula de seguridad — nunca bloquea al superusuario
        return True
    try:
        rol = user.perfil.rol
    except Exception:
        return False
    if rol is None or not rol.activo:
        return False
    return RolPermiso.objects.filter(
        rol=rol,
        permiso__modulo__codigo=modulo_codigo,
        permiso__codigo=accion_codigo,
    ).exists()
```

**Aplicación en DRF** (`roles/permissions.py`) — factory de `BasePermission`:

```python
permission_classes = [requiere_permiso('glosario', 'editar')]
```

Para `ModelViewSet` (ej. `terminos`), se sobreescribe `get_permissions()` mapeando la acción DRF:

| Acción DRF | Permiso requerido |
|---|---|
| `list`, `retrieve` | `ver` |
| `create` | `crear` |
| `update`, `partial_update` | `editar` |
| `destroy` | `eliminar` |

**Aplicación en vistas planas de Django** (`roles/decorators.py`) — para `translator_api`,
que no usa DRF y por lo tanto no tiene `request.user` poblado por token automáticamente:

```python
@requiere_permiso_django('dataset_audio', 'etiquetar')
def session_etiquetar_view(request, community, session):
    ...
```

El decorador reutiliza `rest_framework.authentication.TokenAuthentication` internamente
para resolver el usuario desde el header `Authorization: Token ...`, y responde `401`/`403`
en `JsonResponse` si falla — sin duplicar lógica de parseo de tokens.

### 4.5 Nota sobre qué tan "dinámico" es el sistema

Crear un `Modulo` o `Permiso` nuevo desde la API **no activa control de acceso automáticamente**
— eso requiere que un desarrollador agregue el `requiere_permiso(...)` correspondiente en la
vista real. Lo que sí es 100% dinámico, sin tocar código:

- Crear un **rol nuevo** (ej. `editor_glosario`).
- Decidir qué combinación de permisos **ya existentes** tiene ese rol (ej. solo `glosario.ver` + `glosario.editar`, sin `glosario.eliminar`).
- Asignar ese rol a cualquier usuario.
- Activar/desactivar roles o revocar permisos de golpe.

Esto se documenta explícitamente en la respuesta de `GET /api/admin/modulos/` para que
quien administre no espere que "crear una sección" proteja código que aún no la chequea.

---

## 5. Catálogo completo de módulos y permisos (semilla)

| Módulo (`codigo`) | Cubre | Permisos (`codigo`) |
|---|---|---|
| `usuarios` | Cuentas, login, gestión de equipo | `ver`, `crear`, `editar`, `eliminar`, `gestionar_roles` |
| `glosario` | `Lengua`, `TerminoEs`, `TerminoLeng` (app `terminos`) | `ver`, `crear`, `editar`, `eliminar`, `carga_masiva` |
| `embeddings` | `EmbeddingVersion` (app `terminos`) | `ver`, `generar`, `activar` |
| `dataset_audio` | Grabaciones, sesiones, subida y etiquetado (`translator_api` + `entrenamiento/dataset`) | `ver`, `subir`, `etiquetar` |
| `modelos_asr` | Catálogo/descarga de modelos, experimentos, augmentation, memoria GPU (`entrenamiento`) | `ver`, `descargar_modelo`, `entrenar`, `activar_experimento`, `cancelar_experimento`, `liberar_memoria` |
| `transcripcion` | Transcribir / transcribir+traducir audio | `ejecutar` |
| `traduccion` | Traducir texto | `ejecutar` |

**Total: 7 módulos, 28 permisos** en la semilla inicial (el admin puede agregar más después).

---

## 6. Matriz de roles semilla (reproduce exactamente `HISTORIAS_USUARIO_AUTH.md`)

| Módulo.Acción | admin | desarrollador | investigador | anotador | consultor |
|---|:---:|:---:|:---:|:---:|:---:|
| `usuarios.ver/crear/editar/eliminar/gestionar_roles` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `glosario.ver` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `glosario.crear/editar/eliminar/carga_masiva` | ✅ | ✅ | ✅ | ❌ | ❌ |
| `embeddings.ver` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `embeddings.generar/activar` | ✅ | ✅ | ✅ | ❌ | ❌ |
| `dataset_audio.ver` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `dataset_audio.subir/etiquetar` | ✅ | ✅ | ✅ | ✅ | ❌ |
| `modelos_asr.ver` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `modelos_asr.descargar_modelo/entrenar/activar_experimento/cancelar_experimento/liberar_memoria` | ✅ | ✅ | ✅ | ❌ | ❌ |
| `transcripcion.ejecutar` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `traduccion.ejecutar` | ✅ | ✅ | ✅ | ✅ | ✅ |

Estos 5 roles se crean con `es_sistema=True` (no se pueden borrar desde la API; sí se pueden
desactivar o editarles nombre/descripción). Cualquier rol nuevo que cree un admin nace con
`es_sistema=False` y puede borrarse libremente si no tiene usuarios asignados.

---

## 7. Módulo de administración dinámico — API

Prefijo: `/api/admin/`. Todos los endpoints requieren `usuarios.gestionar_roles`
(solo lo tiene `admin` por semilla).

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/api/admin/modulos/` | Listar secciones, con nota de que crear una no activa control de acceso por sí sola |
| `POST` | `/api/admin/modulos/` | Crear sección nueva |
| `PATCH` / `DELETE` | `/api/admin/modulos/<id>/` | Editar / desactivar sección |
| `POST` | `/api/admin/modulos/<id>/permisos/` | Crear acción/permiso dentro de una sección |
| `GET` | `/api/admin/roles/` | Listar roles, con conteo de usuarios y permisos asignados |
| `POST` | `/api/admin/roles/` | Crear rol nuevo |
| `GET` / `PATCH` | `/api/admin/roles/<id>/` | Detalle / editar rol |
| `DELETE` | `/api/admin/roles/<id>/` | Eliminar rol (bloqueado si `es_sistema=True` o tiene usuarios asignados) |
| `GET` | `/api/admin/roles/<id>/permisos/` | Ver permisos asignados a un rol |
| `PUT` | `/api/admin/roles/<id>/permisos/` | Reemplazar el set completo de permisos de un rol (body: lista de `permiso_id`) |
| `GET` | `/api/admin/matriz/` | Módulos × roles × permisos completo — para pintar una tabla de administración en un futuro frontend |

Los endpoints de `/api/auth/` (login, logout, perfil, registro, gestión de usuarios) **no
cambian de forma** — solo el campo `rol` pasa de aceptar un valor de una lista fija en código
a validarse contra la tabla `Rol` (por `codigo`).

---

## 8. Mapeo de endpoints existentes → módulo.acción

| App | Vista / endpoint | Módulo.Acción requerido |
|---|---|---|
| `usuarios` | `POST /api/auth/registro/` | `usuarios.crear` |
| `usuarios` | `GET /api/auth/usuarios/` | `usuarios.ver` |
| `usuarios` | `PATCH /api/auth/usuarios/<id>/` | `usuarios.editar` |
| `usuarios` | `DELETE /api/auth/usuarios/<id>/` | `usuarios.eliminar` |
| `terminos` | `LenguaViewSet`, `TerminoEsViewSet`, `TerminoLengViewSet` | `glosario.ver/crear/editar/eliminar` según acción |
| `terminos` | `EmbeddingVersionViewSet` (listar/generar/activar) | `embeddings.ver/generar/activar` |
| `entrenamiento` | `DatasetEstadoView`, `DatasetComunidadView`, `DatasetSesionesView`, `EstadisticasGrabacionesView` | `dataset_audio.ver` |
| `entrenamiento` | `SubirAudioView` | `dataset_audio.subir` |
| `entrenamiento` | `ModeloListView`, `ModelosDisponiblesView` | `modelos_asr.ver` |
| `entrenamiento` | `ModeloDescargarView` | `modelos_asr.descargar_modelo` |
| `entrenamiento` | `EntrenarView` | `modelos_asr.entrenar` |
| `entrenamiento` | `ExperimentoActivarView` | `modelos_asr.activar_experimento` |
| `entrenamiento` | `ExperimentoCancelarView` | `modelos_asr.cancelar_experimento` |
| `entrenamiento` | `SistemaLiberarMemoriaView` | `modelos_asr.liberar_memoria` |
| `entrenamiento` | `TranscribirView`, `TranscribirTraducirView` | `transcripcion.ejecutar` |
| `translator_api` | `session_etiquetar_view`, `session_etiqueta_view` | `dataset_audio.etiquetar` |
| `translator_api` | `session_audios_view`, `recordings_*`, `session_glosario_view`, `session_estado_view` | `dataset_audio.ver` |
| `translator_api` | `translate_view` | `traduccion.ejecutar` |
| `traduccion` | `TraducirView` | `traduccion.ejecutar` |

---

## 9. Estrategia de migración de datos

1. Crear la app `roles` con sus modelos y migración inicial.
2. Data migration `roles/migrations/0002_seed_roles.py`:
   - Crea los 7 `Modulo` y sus 28 `Permiso` (sección 5).
   - Crea los 5 `Rol` semilla con `es_sistema=True`.
   - Puebla `RolPermiso` reproduciendo la matriz de la sección 6.
3. En `usuarios`, migración de esquema: `PerfilUsuario.rol` pasa de `CharField` a
   `ForeignKey('roles.Rol')`.
4. Data migration en `usuarios` que recorre los `PerfilUsuario` existentes y asigna el `Rol`
   correspondiente según el valor de texto que tenían (`'admin'` → `Rol(codigo='admin')`, etc.).
5. Actualizar `crear_admin` para usar `Rol.objects.get(codigo='admin')`.

Ningún usuario pierde su rol ni su acceso durante la migración — es un mapeo 1:1 de texto a FK.

---

## 10. Plan de implementación por fases

- [ ] **Fase 1 — Modelos y semilla.** Crear app `roles` (modelos, migraciones, data migration de
  módulos/permisos/roles). Migrar `PerfilUsuario.rol` a FK con su data migration. Verificar con
  `python manage.py migrate` que los usuarios existentes conservan su rol.
- [ ] **Fase 2 — Motor de permisos.** `roles/services.py`, `roles/permissions.py`,
  `roles/decorators.py`. Reemplazar `EsAdmin`/`EsInvestigador`/`EsAnotador` en `usuarios/views.py`.
- [ ] **Fase 3 — Cerrar el hueco de seguridad real.** `DEFAULT_PERMISSION_CLASSES` →
  `IsAuthenticated`. Cablear `terminos` y `entrenamiento` con `requiere_permiso(...)` según la
  tabla de la sección 8.
- [ ] **Fase 4 — `translator_api`.** Cablear `@requiere_permiso_django(...)` en las vistas
  planas de etiquetado/traducción (paso más delicado: hoy no hay ningún control de acceso ahí).
- [ ] **Fase 5 — Módulo de admin dinámico.** `roles/admin_views.py` + `roles/urls.py` bajo
  `/api/admin/`, con los 11 endpoints de la sección 7.
- [ ] **Fase 6 — Documentación.** Actualizar `HISTORIAS_USUARIO_AUTH.md` para reflejar que la
  matriz ahora es consultable en vivo vía `GET /api/admin/matriz/`.

---

## 11. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Un admin se queda sin acceso por error de configuración en la matriz | `is_superuser` siempre pasa el chequeo, sin importar la matriz (válvula de escape) |
| Cablear `IsAuthenticated` por defecto rompe integraciones que hoy llaman sin token | Comunicar el cambio antes de desplegar; revisar si hay algún cliente (frontend, scripts) que dependa del acceso abierto actual |
| Migrar `translator_api` a permisos reales cambia comportamiento visible para usuarios de campo (anotadores) | Verificar en Fase 4 con un token real de cada rol antes de dar por cerrada la fase |
| Borrar un `Rol` que sigue en uso | `PROTECT` en el FK de `PerfilUsuario.rol` lo impide a nivel de base de datos; además la API bloquea el borrado si `es_sistema=True` o tiene usuarios asignados |

---

## 12. Plan de verificación

- `python manage.py migrate` sin errores; confirmar en shell que cada `PerfilUsuario` existente
  quedó con el `Rol` correcto.
- `python manage.py crear_admin` sigue funcionando.
- Con un token de cada uno de los 5 roles, probar un endpoint representativo por módulo
  (`GET/POST /api/terminos/lenguas/`, `POST /api/entrenamiento/entrenar/`,
  `POST /api/grabaciones/<comunidad>/<sesion>/etiquetar/`, `/api/admin/roles/`) y confirmar
  `200`/`403` según la matriz de la sección 6.
- Crear un rol nuevo vía `POST /api/admin/roles/`, asignarle permisos vía
  `PUT /api/admin/roles/<id>/permisos/`, asignarlo a un usuario de prueba vía
  `PATCH /api/auth/usuarios/<id>/`, y confirmar que su acceso cambia sin reiniciar el servidor.
- Revisar `GET /api/docs/` (drf-spectacular) para que los nuevos endpoints de `/api/admin/`
  queden documentados.

---

## 13. Glosario

| Término | Significado |
|---|---|
| **Módulo** | Una sección funcional del sistema (glosario, etiquetas, entrenamiento...) |
| **Permiso** | Una acción concreta dentro de un módulo (ver, crear, editar, entrenar...) |
| **Rol** | Un conjunto con nombre de permisos, asignable a usuarios |
| **`es_sistema`** | Marca los roles semilla para protegerlos de borrado accidental |
| **Matriz** | La tabla completa rol × permiso, editable vía `/api/admin/roles/<id>/permisos/` |
