# SPEC-005: Security Hardening & Compliance Architecture (ISO 27001, ISO 27701, SOC 2)

- **Estado:** IMPLEMENTED (Fases 1, 2, 3 y Fase 4 de Suficiencia de Controles completadas)
- **Fecha:** Noviembre 2026
- **Ámbito:** Frontend (Nginx/Astro), Backend (FastAPI), Base de Datos (PostgreSQL), Docker & Infraestructura
- **Objetivo:** Establecer los controles formales de seguridad técnica, privacidad de datos y endurecimiento operativo (hardening) en 2 Rodríguez Distribuidora, alineando la arquitectura con **ISO/IEC 27001:2022**, **ISO/IEC 27701:2019** (Privacidad / Ley 18.331 Uruguay) y **SOC 2 Type II** (Security, Confidentiality & Privacy).

---

## 1. Mapeo de Estándares y Controles

| Norma / Marco | Control Clave | Componente Afectado | Impacto en 2 Rodríguez Distribuidora |
| :--- | :--- | :--- | :--- |
| **ISO 27001:2022** | **A.8.26** Requisitos de seguridad en aplicaciones | Nginx / Frontend | Cabeceras HTTP estrictas: CSP, HSTS, X-Frame-Options, Permissions-Policy. |
| **ISO 27001:2022** | **A.8.5** Autenticación segura y control de accesos | Backend (FastAPI) | Rate Limiting contra fuerza bruta en `/auth/login`; hashing Argon2id. |
| **ISO 27001:2022** | **A.8.9** Gestión de configuración técnica | Docker / Servidor | Contenedores sin privilegios de root (`appuser`), descarte de tokens del servidor. |
| **ISO 27001:2022** | **A.8.15** Registro de eventos y auditoría | Backend (Logging) | Registro estructurado de cambios de precios, gastos y cargas masivas. |
| **ISO 27701:2019** | **PIMS 7.2.2** Consentimiento y base legal | Portal / Clientes | Consentimiento expreso de tratamiento de datos personales (Ley 18.331). |
| **ISO 27701:2019** | **PIMS 7.3.3** Minimización y confidencialidad | Base de Datos & DTOs | Aislamiento estricto de listas de costos de proveedores y márgenes de Mariana. |
| **SOC 2 (CC6.1)** | Control de acceso lógico perimetral | Nginx / API | Bloqueo de ataques automatizados y segregación de roles (RBAC: ADMIN vs CUSTOMER). |
| **SOC 2 (CC6.6)** | Protección contra vectores de inyección | Backend / Storage | Validación de tipos MIME, magic bytes y cuotas de subida en attachments. |

---

## 2. Fases de Implementación

```
┌─────────────────────────────────┐
│ Fase 1: Perímetro & Código     │ ──▶ Rate limiting, CSP, HSTS, eliminación credenciales default
└─────────────────────────────────┘
                 │
┌─────────────────────────────────┐
│ Fase 2: Docker & Contenedores   │ ──▶ Usuario no-root, aislamiento de red DB, resource limits
└─────────────────────────────────┘
                 │
┌─────────────────────────────────┐
│ Fase 3: Auditoría & Privacidad  │ ──▶ Logs inmutables de operaciones, consentimiento Ley 18.331
└─────────────────────────────────┘
```

---

## 3. Especificación Técnica por Fase

### Fase 1: Perímetro HTTP y Control de Fuerza Bruta (Inmediata)

#### 1.1. Cabeceras de Seguridad en Nginx (`frontend/nginx.conf`)
* **Content-Security-Policy (CSP):** Bloqueo de inyecciones de scripts de orígenes no autorizados.
  ```nginx
  add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data: blob: https://wa.me; connect-src 'self' https://wa.me; frame-ancestors 'none'; form-action 'self'; base-uri 'self';" always;
  ```
* **Strict-Transport-Security (HSTS):** Forzar HTTPS con preloading por 1 año (`max-age=31536000; includeSubDomains; preload`).
* **Permissions-Policy:** Deshabilitar APIs sensibles del navegador que la tienda no utiliza: `geolocation=(), microphone=(), camera=(), payment=(), usb=()`.
* **Server Tokens Off:** Ocultar la versión exacta de Nginx (`server_tokens off;`).

#### 1.2. Rate Limiting en Endpoint de Login (`backend`)
* **Problema:** `/api/v1/auth/login` permite intentos ilimitados.
* **Solución:** Limitar a un máximo de **5 intentos fallidos por minuto por IP**. Al superarse, retornar `HTTP 429 Too Many Requests` con cabecera `Retry-After`.
* **Protección adicional:** Retardo temporal constante para evitar ataques de temporización (timing attacks).

#### 1.3. Remoción de Credenciales Precargadas en Frontend
* En `frontend/src/pages/admin.astro`, eliminar los atributos `value="mariana@2rodriguez.uy"` y `value="Admin2Rodriguez!2026"` para evitar filtraciones de contraseñas por inspección DOM o captura de pantalla.

---

### Fase 2: Endurecimiento de Contenedores e Infraestructura

#### 2.1. Usuario no-root en Contenedores Docker
* En `backend/Dockerfile`, crear un usuario de sistema dedicado `appuser` (UID 10001) y cambiar de contexto con `USER appuser` antes del `ENTRYPOINT`.
* En caso de explotación de vulnerabilidad en una librería Python, el atacante no tiene acceso root al host.

#### 2.2. Aislamiento de Red y Puertos
* PostgreSQL (`postgres:16-alpine`) debe escuchar **únicamente** en la red virtual interna `web2r_internal`.
* En producción, no mapear `ports: ["5432:5432"]` al host ni a la interfaz pública de la Orange Pi.

#### 2.3. Límites de Recursos (Anti-Denegación de Servicio / DoS)
* Configurar cuotas en `docker-compose.prod.yml`:
  * Backend: Límite de 1.5 CPUs y 768 MB de RAM.
  * Frontend: Límite de 0.5 CPUs y 256 MB de RAM.
  * Postgres: Límite de 1.0 CPUs y 512 MB de RAM.

---

### Fase 3: Trazabilidad, Auditoría y Privacidad PII

#### 3.1. Registro de Auditoría de Acciones Administrativas (Audit Log)
* Toda mutación en backoffice debe generar un registro JSON estructurado:
  ```json
  {
    "timestamp": "2026-11-02T15:10:00Z",
    "actor_id": 1,
    "actor_email": "mariana@2rodriguez.uy",
    "action": "UPDATE_PRODUCT_PRICE",
    "target_entity": "product",
    "target_id": 105,
    "ip_address": "192.168.1.50",
    "details": { "cost_iva_inc": 150.00, "price_iva_inc": 225.00 }
  }
  ```
* Se guardan en archivo de rotación diaria con permisos de solo lectura (`/var/log/web2r/audit.log`).

#### 3.2. Cumplimiento de Privacidad (ISO 27701 / Ley 18.331)
* Consentimiento informado en formulario de registro de clientes B2B.
* Derecho de acceso, rectificación y supresión (ARCO).
* Almacenamiento exclusivo de datos necesarios para la facturación y entrega logística.

---

## 4. Checklist de Aceptación y Verificación

- [x] `curl -I https://2rodriguez.uy/` devuelve cabeceras `Content-Security-Policy`, `Strict-Transport-Security` y `X-Content-Type-Options: nosniff` (incluyendo bloques `location` con `Cache-Control`).
- [x] La versión de Nginx no figura en las cabeceras HTTP (`Server: nginx` sin versión).
- [x] 6 intentos consecutivos de login incorrecto en `/api/v1/auth/login` resultan en `HTTP 429 Too Many Requests` (resistente a spoofing de `X-Forwarded-For` y acotado en memoria).
- [x] El formulario de login de [admin.astro](file:///c:/Users/cerra/codigo/web_2R/frontend/src/pages/admin.astro) tiene inputs limpios sin valores por defecto.
- [x] El contenedor `web_2r_backend` corre bajo UID `10001` (no `root`).
- [x] La base de datos se publica únicamente en loopback local (`127.0.0.1:5446:5432`) para monitoreo de Guardian, inaccesible desde redes externas.
- [x] Los tokens JWT separan estrictamente `type: "access"` de `type: "password_reset"`, y los enlaces de recuperación son de un solo uso mediante firma HMAC del `password_hash` actual.
- [x] La subida de archivos adjuntos verifica la firma binaria real (Magic Bytes para JPG, PNG, WEBP y PDF) y sanitiza nombres de archivo.
- [x] El checkout público aísla las órdenes de invitados en una cuenta de consumidor final deshabilitada para login, sin exponer ni asociar órdenes a clientes B2B registrados.
- [x] Las rutas `/docs`, `/redoc` y `/openapi.json` se desactivan automáticamente cuando `ENVIRONMENT=production`.
