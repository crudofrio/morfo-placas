# morfo-placas

Sitio de práctica de **Morfogénesis III** (UCSG, Medicina).

- `/` — app de estudio de las clases 2–4.
- `/final-boss/` — **FINAL BOSS**, el juego de práctica a ritmo de examen (placas silenciadas, lápiz y papel, y modos de calentamiento).

## Final Boss

Entra en https://crudofrio.github.io/morfo-placas/final-boss/

- **Examen simulado**, con tres modos que guardan récord por separado:
  - *Solo diagnósticos* (30 s y su propia escalera),
  - *Solo estructuras* (4 flechas, parte en 60 s),
  - *Completo* (Dx + 4, escalera 80→60 s, como el parcial).
- Juego por niveles, aprender estructuras, mapa de los secretos.
- Diseño para iPhone y para desktop (placa grande a la izquierda).

Los datos del **primer parcial** están en `final-boss/data/primer-parcial.js`. Cuando exista `final-boss/data/segundo-parcial.js` (armado desde las diapos del segundo parcial, sin relleno), el menú mostrará el set solo.

Cómo armar un set nuevo desde PDFs de clase: [`final-boss/README_dataset.md`](final-boss/README_dataset.md).
