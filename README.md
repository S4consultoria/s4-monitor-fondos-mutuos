# Monitores S4

Una sola web en Cloudflare Pages con los dos monitores:

| Ruta       | Monitor                     | Excel que lo alimenta |
|------------|-----------------------------|-----------------------|
| `/`        | Portada (elige el monitor)  | —                     |
| `/fondos/` | Fondos Mutuos               | `fondos/fondos.xlsx`  |
| `/etfs/`   | ETFs extranjeros            | `etfs/etfs.xlsx`      |

## Cómo se actualiza

1. Reemplaza el Excel en su carpeta (mismo nombre de archivo).
2. Commit y push a `main`.
3. Cloudflare Pages vuelve a publicar solo (~1 min). La página lee el Excel
   desde la misma web (`/fondos/fondos.xlsx`, `/etfs/etfs.xlsx`), ya no desde GitHub.

## Cloudflare Pages

- Framework preset: **None**. Build command: vacío. Output directory: `/`.
- Rama de producción: `main`. Otras ramas generan una URL de prueba (preview).
