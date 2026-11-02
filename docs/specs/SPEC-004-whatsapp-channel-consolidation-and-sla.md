# SPEC-004: Consolidación del Canal WhatsApp, Horarios de Atención y SLA de Despacho

- **Estado:** APPROVED / IMPLEMENTATION READY
- **Fecha:** Octubre 2026
- **Ámbito:** Frontend (Astro), UX/UI, Comunicación Comercial
- **Objetivo:** Reducir la saturación de llamadas a la acción (CTAs) de WhatsApp en el frontend, consolidar el canal de atención personalizada con Mariana, fijar horarios transparentes para evitar falsas expectativas y comunicar con claridad el tiempo de entrega (~24 hs).

---

## 1. Contexto y Diagnóstico Arquitectural

Una auditoría realizada con Ego Lite detectó **9 puntos de contacto independientes de WhatsApp en la página de inicio (Home)**, además de botones repetidos en cada tarjeta del catálogo. Esta dispersión genera tres problemas graves:

1. **Canibalización de objetivos:** Múltiples botones verdes compiten visualmente con el flujo principal del sitio (*Explorar Catálogo* e *Ingreso al Portal*).
2. **Falsa expectativa de inmediatez:** La presencia de indicadores visuales activos (`animate-ping`) sugiere atención en vivo las 24 horas, frustrando a los usuarios fuera de horario.
3. **Dispersión de números y mensajes:** Desalineación entre teléfonos de contacto y falta de un punto único de verdad para la configuración comercial.

---

## 2. Matriz de Decisiones por Componente

| Componente | Estado Actual | Decisión Arquitectural | Justificación |
| :--- | :--- | :--- | :--- |
| **Header** (`BaseLayout.astro`) | Botón verde prominente con pulso | **ELIMINAR**. Reemplazar solo por accesos de navegación (*Catálogo*, *Nosotros*, *Acceso Clientes*). | El header debe guiar al usuario a navegar el catálogo, no forzar una salida a WhatsApp antes de ver productos. |
| **Hero** (`index.astro`) | Botón "Pedir Cotización al 095..." | **REDEFINIR**. Mantener botón secundario neutro o dirigirlo prioritariamente al catálogo/portal. | Reducir la sobrecarga en el primer viewport. |
| **Tarjetas de Producto** (`index` y `catalogo`) | Botón "Consultar Precio" en cada card | **MANTENER CONTEXTUAL**. Un solo botón por producto con mensaje estructurado: SKU, nombre y solicitud de cotización. | Facilita la consulta asistida para el usuario que necesita un producto específico. |
| **Botón Flotante (FAB)** (`BaseLayout.astro`) | Burbuja fija con pulso 24/7 sin horario | **CONSOLIDAR COMO CANAL ÚNICO**. Incorporar estado de horario y mensaje transparente de atención. | Centraliza el contacto general en una sola ubicación conocida y predecible. |
| **Footer** (`BaseLayout.astro`) | Texto estático de horarios y teléfono | **ACTUALIZAR**. Reflejar los horarios comerciales oficiales de Uruguay y el tiempo de entrega estimado. | Soporte informativo al pie para clientes corporativos. |

---

## 3. Reglas de Negocio, Horarios y SLA

### 3.1. Ventanas de Atención Personalizada (Hora de Uruguay)
- **Lunes a Viernes:** 09:00 a 18:00 hs.
- **Sábados:** 09:00 a 14:00 hs.
- **Domingos y Feriados:** Cerrado.

### 3.2. SLA y Plazos de Despacho (Transparencia Comercial)
- **Tiempos de entrega:** Los pedidos coordinados demoran aproximadamente **24 horas hábiles** en prepararse y despacharse/retirarse.
- **Retiro en depósito:** Retiro inmediato en Paso Molino (Ángel Salvo 56) previa coordinación de stock.

### 3.3. Experiencia Fuera de Horario
Cuando el usuario interactúa con los puntos de contacto fuera de la ventana operativa:
1. **Mensaje honesto:** *"Mariana te responderá a primera hora del próximo día hábil"*.
2. **Alternativa de autoservicio:** *"¿Querés consultar precios ahora? [Ingresá a tu cuenta mayorista](/portal) o [revisá el catálogo completo](/catalogo)"*.

---

## 4. Configuración Centralizada (Single Source of Truth)

Para evitar discrepancias entre números telefónicos (`095 250 673` vs `094 151 177`), la información de contacto se centraliza en un archivo de configuración del frontend:

```typescript
// src/lib/contact.ts
export const CONTACT_CONFIG = {
  phone: "095 250 673",
  phoneRaw: "59895250673",
  address: "Ángel Salvo 56, Montevideo (Paso Molino)",
  email: "dosrodriguezdistribuidora@gmail.com",
  schedule: {
    weekdays: "09:00 a 18:00 hs",
    saturdays: "09:00 a 14:00 hs",
    deliveryTime: "Entregas en aprox. 24 hs hábiles"
  }
};
```

---

## 5. Criterios de Aceptación (Checklist de Implementación)

- [ ] **Limpieza de Header:** Removido el botón duplicado de WhatsApp del navbar principal.
- [ ] **Configuración Unificada:** Creado `src/lib/contact.ts` con los datos oficiales de contacto y horarios.
- [ ] **FAB Inteligente:** El botón flotante muestra horario de atención explícito y desactiva el pulso de inmediatez fuera de horario.
- [ ] **Manejo Fuera de Horario:** El tooltip del FAB invita a dejar la consulta o a ingresar al `/portal` cuando el local está cerrado.
- [ ] **Transparencia en Footer:** Incorporado el texto indicando *"Despacho y entregas en aprox. 24 hs hábiles"*.
- [ ] **Sin desborde horizontal:** Verificación visual mediante Ego Lite confirmando `hasOverflow: false` en móviles (390px) y escritorio (1440px).
