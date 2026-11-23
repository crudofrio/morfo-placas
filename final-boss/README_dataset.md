# Cómo armar un set de placas para FINAL BOSS

Este juego no trae datos inventados. Cada placa (diagnóstico, nombres de estructuras, posiciones, fotos silenciada y con nombres) sale de las diapos oficiales del curso. Cuando tengas el **segundo parcial**, se arma otro set con el mismo procedimiento y aparece solo en el menú.

## Dónde vive cada set

```
final-boss/
  index.html                 # el juego (sirve para cualquier set)
  data/
    primer-parcial.js        # set actual (obligatorio)
    segundo-parcial.js       # aparece en el menú apenas exista este archivo
  img/
    sin/  con/               # fotos del primer parcial (ya publicadas)
    segundo-parcial/sin|con/ # fotos de un set nuevo
```

El menú siempre muestra **Primer parcial**. **Segundo parcial** se lista solo si `data/segundo-parcial.js` está en el servidor y define `window.FB_SET` / `window.FB_PLACAS`. No se crea un set vacío ni de relleno.

## Esquema (mínimo y el que usa el juego)

Cada archivo `data/<set>.js` asigna:

```js
window.FB_SET = { id, name, course, file };
window.FB_META = { title, course, uni, prof, exam, classes, total, passScore, gaps, footer? };
window.FB_PLACAS = [ /* placas */ ];
window.FB_STRUCTS = [ /* índice para el Mapa de los secretos, se puede generar */ ];
window.FB_COVER = { all: { label, totalPlacas, totalStructs, route, uniques } };
```

Cada placa:

| Campo | Obligatorio | Notas |
|---|---|---|
| `code` | sí | Id estable, p.ej. `08-03` |
| `cls` o `class` | sí | Id de la clase, p.ej. `"8"` |
| `diagnosis` | sí | Texto **exacto** de la diapo (sin “Sección N” si el profe no lo pregunta) |
| `imgSin` / `img_silenciada` | sí | Ruta a la foto sin nombres |
| `imgCon` / `img_con_nombres` | sí | Ruta a la foto con nombres |
| `elements` | recomendado | `[{id, name, poly}]` con `poly` en % de la imagen `[[x,y],…]` |
| `structures` | aceptado | Forma corta `[{n, label, x, y}]` (x,y en %). El juego la convierte a `elements` |
| `parts` | opcional | Trozos del Dx para el nivel “Por partes” |

El juego acepta las dos formas de estructuras. Si solo hay `{n,label,x,y}` arma un recuadro alrededor del punto para las flechas.

## Cómo generar un set nuevo desde PDFs

1. Junta solo las diapos de **práctica** (páginas que son placas, no portadas ni rúbricas).
2. Copia `tools/set.example.json` y llena `id`, `name`, `course` y, por cada clase, la ruta del PDF y el rango de páginas (`"17-22"` o `"2,5,8-11"`).
3. Primera pasada, sin escribir fotos, para ver qué detecta:

```bash
python3 tools/build_set.py --config mi-segundo-parcial.json --root . --dry-run
```

4. Revisa el reporte: códigos, diagnósticos y cuántas estructuras salieron. Si una página no es placa, sácala del rango. Si un nombre quedó mal cortado, corrígelo en el JSON de salida **después**, copiando el texto de la diapo: no inventes.
5. Genera fotos (alta resolución, máx. 2400 px) y el `data/<id>.js`:

```bash
python3 tools/build_set.py --config mi-segundo-parcial.json --root .
```

6. El script hace, por página:
   - render a escala alta (`dpi_scale`, por defecto 2.8);
   - lee el texto del PDF (código, diagnóstico, etiquetas y sus cajas);
   - guarda **con nombres** (`img/<set>/con/<code>.jpg`);
   - tapa solo el texto de las etiquetas para la **silenciada** (`img/<set>/sin/<code>.jpg`) y deja las flechas y los números;
   - escribe `data/<id>.js` con el esquema de arriba.
7. Abre el juego (o súbelo a GitHub Pages). En el menú debería aparecer el set nuevo. Revisa cada silenciada: que no quede texto de nombres y que las flechas coincidan.

Dependencias: `pip install pymupdf pillow`.

## Primer parcial (receta especial)

Las clases 2–4 tienen JPGs oficiales ya silenciadas y un JSON de etiquetas revisado. Las clases 5–6 se armáron desde las diapos, tapando el texto. Esa receta (rutas UCSG, erratas, “Sección N”, partes del Dx) está en `build_data.py`:

```bash
python3 build_data.py
```

No uses `build_set.py` para rehacer el primer parcial: perderías las fotos oficiales y las correcciones ya verificadas.

## Qué no hacer

- No rellenar un set con placas de ejemplo ni “TODO” inventado.
- No cambiar el wording del diagnóstico: va palabra por palabra como en la diapo (incluyendo erratas, si el profe las deja).
- No bajar de ~1400–2400 px de ancho: en desktop la placa se ve grande y se nota la pixelación.
