# Guía Práctica para Mariana: Cómo Cargar Catálogos, Precios, Fotos y Fichas PDF con ChatGPT

Esta guía te explica paso a paso cómo subir productos nuevos, actualizar listas de precios de proveedores y cargar fotos o fichas técnicas en PDF desde el panel **`/admin`** de **2 Rodríguez**, ayudándote con **ChatGPT** y sin tener que armar planillas a mano ni recortar archivos uno por uno.

---

## Camino Rápido (Resumen en 3 situaciones)

| ¿Qué necesitás hacer hoy? | ¿Qué botón usás en `/admin`? | Truco rápido |
| :--- | :--- | :--- |
| **1. Cargar un catálogo o lista de precios entera de un proveedor** (varios productos a la vez) | Botón violeta **`✨ Cargar Catálogo (CSV / IA)`** | Pedile la tabla a ChatGPT, copiá el texto y **pegalo directo en el cuadro de texto** (no hace falta guardar archivos `.csv`). |
| **2. Ponerle la foto a un producto** sacándola de un catálogo PDF | Botón **`📷 + Foto`** en la fila del producto | Recortá la foto de la pantalla con **`Windows + Shift + S`** y presioná **`Ctrl + V`** adentro de la ventana de subida. ¡Se sube sola! |
| **3. Crear un solo producto nuevo** con costo, ganancia, stock y foto | Botón **`+ Nuevo Producto`** | Poné el **Costo (IVA inc.)** y el sistema calcula solo el **+50% redondeado hacia arriba** y te ofrece subir la foto y el PDF al instante. |

---

## Caso 1: Subir un Catálogo o Lista de Precios con ayuda de ChatGPT

Cuando un proveedor (por ejemplo, *Química Gabriel*, *Moizo*, *Dr. Beckmann*, etc.) te manda un PDF, una foto por WhatsApp o un listado de precios desordenado, **ChatGPT hace todo el trabajo pesado por vos**.

### Paso 1: Mandale la captura o el PDF a ChatGPT
1. Abrí **ChatGPT** en tu computadora.
2. Arrastrá el archivo PDF del proveedor o pegale las capturas de pantalla de la lista de precios.
3. Copiá y pegá exactamente este **mensaje (Prompt)** en ChatGPT:

```text
Hola ChatGPT. Actuá como mi asistente de catálogo para mi distribuidora (2 Rodríguez).
Te adjunto páginas/capturas del catálogo de nuestro proveedor.
Extraé todos los productos que veas y devolveme ÚNICAMENTE un bloque de código CSV separado por punto y coma (;) con estas columnas exactas en la primera línea:

Codigo;Nombre;Presentacion;Proveedor;Categoria;Costo_IVA_Inc;Precio_Venta_IVA_Inc;Stock;Alerta_Minima;Publicar

Reglas obligatorias:
1. Codigo: el código del artículo si aparece (si no aparece, dejalo vacío entre los punto y coma).
2. Nombre: nombre claro y prolijo del producto (sin la medida si ya va en Presentacion).
3. Presentacion: el envase o medida (ej: "5 L", "500 cc", "1 kg", "Caja x 12").
4. Proveedor: nombre de la empresa o marca (ej: "Química Gabriel").
5. Categoria: elegí la más adecuada (ej: "Automotriz", "Limpieza", "Hogar", "Piscinas", "Industrial").
6. Costo_IVA_Inc: el costo con IVA incluido usando punto para decimales y sin signo $ (ej: 150.00). Si el listado del proveedor está SIN IVA, multiplicalo por 1.22.
7. Precio_Venta_IVA_Inc: dejalo vacío (el sistema aplica automáticamente nuestra regla del +50% redondeado hacia arriba), a menos que yo te indique un precio de venta específico.
8. Stock: poné 20 por defecto (o el número que yo te diga).
9. Alerta_Minima: poné 5.
10. Publicar: poné SI si querés que quede visible en la web, o NO si preferís que quede en borrador para revisarlo antes.
```

### Paso 2: Copiá la respuesta de ChatGPT y pegala en `/admin`
1. ChatGPT te va a mostrar una cajita oscura con los productos ordenados. Hacé clic en el botón **"Copiar código"** arriba a la derecha de esa cajita en ChatGPT.
2. Entrá al panel **`/admin`** de la web y asegurate de estar en la pestaña **Catálogo & Stock**.
3. Hacé clic en el botón violeta **`✨ Cargar Catálogo (CSV / IA)`** (arriba a la derecha).
4. En el cuadro grande que dice **"Opción A (Más rápido): Pegar texto directo desde ChatGPT"**, hacé clic derecho -> **Pegar** (o **`Ctrl + V`**).
5. Hacé clic en **`Procesar e Importar`**.

> [!TIP]
> **¿Qué pasa si un producto ya existía en el sistema?**
> ¡No se duplica! Si el **Código** (o el **Nombre + Presentación**) ya existe en la web, el sistema **actualiza automáticamente su costo y su precio de venta** manteniendo la foto y la ficha PDF que ya tenía cargadas.

---

## Caso 2: Cómo Subir la Foto de un Producto en 5 Segundos (Sin guardar archivos)

Los catálogos de las empresas suelen venir en PDF con las fotos adentro. Para no tener que descargar imágenes, recortarlas, guardarlas en carpetas y después buscarlas:

1. Abrí el catálogo PDF del proveedor en tu pantalla y poné zoom para que la foto del producto se vea nítida.
2. Presioná en tu teclado las tres teclas: **`Windows + Shift + S`** (se oscurece la pantalla para hacer un recorte).
3. Dibujá un rectángulo alrededor de la foto del producto. *(¡Listo, ya quedó copiada en tu memoria/portapapeles!)*
4. Andá al panel **`/admin`**, buscá el producto en la tabla y hacé clic en el botón **`📷 + Foto`** (o **`📷 Cambiar`** si ya tenía una).
5. Con la ventanita abierta, simplemente presioná **`Ctrl + V`** en tu teclado.
6. ¡Listo! La foto se sube, se optimiza sola y ya aparece la miniatura en la fila del producto.

---

## Caso 3: Cómo Subir la Ficha Técnica en PDF

Cuando el proveedor te entrega la **Ficha Técnica** o la **Hoja de Seguridad (MSDS)** en formato PDF:

1. En la fila del producto dentro de **`/admin`**, hacé clic en el botón **`📄 + PDF`** (en la columna *Multimedia*).
2. Arrastrá el archivo `.pdf` adentro del recuadro punteado (o hacé clic para elegirlo de tu carpeta de Descargas).
3. Apenas termine de subir, vas a ver el botón **`📄 PDF`** en color verde: si le hacés clic, se abre la ficha en una pestaña nueva para que verifiques que sea la correcta, y los clientes ya podrán descargarla desde la tienda.

> [!NOTE]
> **¿Y si el proveedor me mandó un solo PDF gigante con 50 fichas técnicas juntas?**
> Si solo necesitás la página 14 de un PDF grande:
> 1. Abrí el PDF grande en tu navegador (Chrome o Edge) y andá a la página de ese producto.
> 2. Tocá el ícono de **Imprimir** (`Ctrl + P`).
> 3. En *Destino*, elegí **"Guardar como PDF"**.
> 4. En *Páginas*, elegí **Personalizado** y escribí el número de esa página (por ejemplo `14`).
> 5. Guardalo y subí ese PDF individual en el botón **`📄 + PDF`** del producto.

---

## Caso 4: Crear un Producto Individual Nuevo (`+ Nuevo Producto`)

Si solo querés agregar 1 o 2 productos sueltos sin usar ChatGPT:

1. Hacé clic en el botón oscuro **`+ Nuevo Producto`** arriba a la derecha.
2. Completá **Nombre**, **Código** (opcional), **Presentación** (ej. `5 L`), **Proveedor** y **Categoría**.
3. En **Costo c/IVA ($)**, escribí cuánto cuesta el artículo. Vas a ver abajo en vivo el **"Precio Venta final redondeado"** calculado automáticamente con el **+50% de ganancia** (podés cambiar el `%` si ese artículo lleva otro margen).
4. Si querés que ya se vea en la tienda, tildá **"Publicar inmediatamente en la tienda web"**.
5. Hacé clic en **`Crear Producto`**. El sistema te preguntará ahí mismo si querés pegarle la foto (`Ctrl + V`) en ese instante.

---

## Lista de Control (Checklist) antes de publicar un producto en la tienda

Para que un producto aparezca con el botón verde **`🟢 Visible en Web`** y los clientes lo puedan comprar en la tienda pública, el sistema verifica automáticamente 3 cosas por seguridad:

- [ ] **¿Tiene Precio de Venta mayor a `$ 0`?** (Si importaste el costo, el sistema ya le calculó el +50% automáticamente).
- [ ] **¿Tiene Nombre válido?** (Sin nombres vacíos o de prueba).
- [ ] **¿Activaste el botón de Estado?** Si el producto está en **`⚪ Borrador`**, hacé clic sobre ese botón en la última columna para pasarlo a **`🟢 Visible en Web`**.

---

## Preguntas Frecuentes y Solución de Problemas

**1. "Quise pasar un producto a `🟢 Visible en Web` y me salió un cartel rojo diciendo que no tiene precio asignado"**
* **Solución:** Mirá las columnas **Costo (IVA inc.)** y **Precio Venta** de ese producto. Escribí el costo en la casilla, presioná `Enter` o hacé clic afuera para que se calcule y guarde el precio en verde, y ahora sí tocá **`⚪ Borrador`** para publicarlo.

**2. "ChatGPT me dio los precios sin el +50% de ganancia"**
* **Solución:** ¡Mejor! Si en la columna `Precio_Venta_IVA_Inc` no hay nada escrito y solo está lleno `Costo_IVA_Inc`, el sistema de 2 Rodríguez **calcula automáticamente el +50% y lo redondea hacia arriba al próximo peso entero** al momento de importar.

**3. "Me equivoqué de foto en un producto"**
* **Solución:** Hacé clic en **`📷 Cambiar`** en ese producto y pegá (`Ctrl + V`) o subí la foto nueva; la anterior se reemplaza en el acto.
