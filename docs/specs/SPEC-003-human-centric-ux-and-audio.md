# SPEC-003: Human-Centric UX, Micro-Audios ("Mariana te cuenta") & Sinergia Comercial

- **Estado:** DRAFT / PROSPECTIVE (No bloqueante para MVP)
- **Fecha:** Octubre 2026
- **Ámbito:** Frontend (Astro), Static Assets & Integración de Canales
- **Objetivo:** Maximizar la tasa de conversión en adultos mayores y clientes comerciales B2B/B2C humanizando la web a través de la presencia de Mariana, reduciendo la fricción tecnológica y potenciando la confianza sin degradar el rendimiento en la Orange Pi.

---

## 1. Contexto y Justificación Comercial

En el mercado uruguayo de distribución y artículos de limpieza, los clientes finales (especialmente adultos mayores) y encargados de compras priorizan el trato humano sobre los flujos de autoservicio complejos. 
La empresa ya cuenta con una presencia activa en Instagram (`@2rodriguezdistribuidora`), donde Mariana Moreira comunica directamente los usos y bondades de los productos. 

Este documento especifica tres mejoras tácticas a implementar una vez consolidado el MVP funcional (imágenes base, checkout y fichas técnicas en PDF).

---

## 2. Pilares de la Especificación

### Pilar 1: Función "Mariana te cuenta" (Micro-Audios de Producto)
Frente a largas fichas técnicas de texto, se incorporan clips de audio breves y auténticos grabados por Mariana (15 a 30 segundos) explicando la dosificación, rendimiento o aplicación del producto destacado.

- **Políticas de Reproducción (Strict UX):**
  - **Zero Autoplay:** Prohibida la reproducción automática. El audio únicamente inicia ante un clic explícito del usuario (`onClick`).
  - **Ubicación:** Componente integrado junto al título y precio de la ficha (`AudioStoryPlayer.astro`).
- **Especificaciones de Medios:**
  - Formato de almacenamiento: `.webm` (Opus) y fallback en `.m4a` / `.aac`.
  - Peso objetivo: < 120 KB por audio (compresión para carga instantánea en redes 4G/móviles).
  - Almacenamiento: Directorio estático `public/audio/products/{sku}.webm` o bucket de assets sin cómputo de backend.
- **UI/UX:**
  - Botón circular con ícono de micrófono/play, etiqueta visible: *"Escuchar recomendación de Mariana"*, control de pausa y barra de progreso minimalista.

---

### Pilar 2: Enlace Directo "Pedir por WhatsApp" (Bypass de Carrito)
Para clientes que experimentan fricción con pasarelas de pago o formularios de checkout, cada ficha de producto ofrecerá un canal de compra asistida 1 a 1.

- **Comportamiento:**
  - Botón secundario junto a "Agregar al carrito": *"Pedir directo a Mariana por WhatsApp"*.
  - Generación de Deep Link codificado hacia `https://wa.me/59894151177`:
    ```text
    Hola Mariana, vi en la web el producto [Nombre Producto] (SKU: [SKU]) a $[Precio] y quiero coordinar el pedido contigo.
    ```
- **Trazabilidad:**
  - Disparo no bloqueante de analítica previo al redireccionamiento (`navigator.sendBeacon`) hacia el endpoint `lead_interactions` (documentado en arquitectura).

---

### Pilar 3: Sinergia Instagram (`@2rodriguezdistribuidora`) & Validación Social
Conectar la tienda digital con la actividad real del negocio para dar certeza de legitimidad y cercanía.

- **Header / Footer:**
  - Acceso directo destacado con badge dinámico o ícono oficial al perfil de Instagram (`https://www.instagram.com/2rodriguezdistribuidora/`).
- **Sección de Validación Social en Home (Fase Posterior):**
  - Grid liviano de reels o fotos incrustadas mostrando el galpón en Belvedere, despacho de pedidos y tips de limpieza de Mariana.
  - Implementación con placeholders estáticos para no cargar scripts pesados de terceros de Meta que ralenticen el render de Astro.

---

## 3. Modelo de Datos y Campos Futuros (Post-MVP)

Cuando se implemente este módulo, la entidad `Product` solo requerirá un campo opcional para habilitar el reproductor:

```python
# Adición futura en src/domain/catalog/entities.py
audio_guide_url: str | None = None  # Ej: "/audio/products/hipoclorito-5l.webm"
audio_duration_seconds: int | None = None
```

---

## 4. Criterios de Aceptación (DoD Futuro)

- El reproductor de audio no bloquea el hilo principal ni incrementa el bundle de JavaScript en más de 2 KB.
- Cumple al 100% las normativas de accesibilidad (etiquetas ARIA para lectores de pantalla).
- El botón de WhatsApp pre-rellena exactamente el contexto del producto visualizado.
- Las pruebas de navegación en dispositivos de gama media/baja mantienen una puntuación de performance de Lighthouse > 90.
