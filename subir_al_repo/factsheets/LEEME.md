# S4 — Factsheets Links v6 · Credicorp vuelve a buscar en cada ejecución

**Propósito:** mantener las URL directas a las fichas de los 12 fondos sin guardar PDF. El catálogo sigue en `data/factsheets_links.json` y `data/factsheets_links.csv`, compatible con el monitor y Claude.

## ¿Qué se corrigió?

La **v5 sí intentaba consultar los seis fondos de Credicorp**, pero usaba `requests`; ante un 403 o una página sin enlaces volvía directamente al PDF histórico de agosto (`ENLACE_ANTERIOR_SIN_REVALIDAR`). No había navegador de rescate para Credicorp. La **v6 ahora intenta Chromium/Chrome** cuando `requests` falla o devuelve un documento anterior al mes más reciente cerrado. También puedes exigir navegador para todos los fondos de Credicorp con `--credicorp-navegador`.

El fondo antes identificado como `CC Latin American Equity I` se vincula ahora al **Fondo de Fondos Credicorp Capital Acciones Latam FMIV (Perú)**, página `.../Int/Paginas/ALP-FMIV.aspx?t=2`, tal como muestran las capturas. El ID interno `cc_latin_american_equity_i` se mantiene por compatibilidad.

No se fabrican enlaces reemplazando “Agosto” por “Setiembre”. Siempre se extrae la URL indicada en la sección **Documentos → Documentos referentes al Fondo → Hoja Informativa**.

## Instalar / usar

1. Descomprime `S4_Factsheets_Links_v6.zip` y abre la carpeta `S4_Factsheets_Links_v6` en el Explorador de Windows.
2. Escribe `powershell` en la barra de ruta de esa carpeta y pulsa Enter.
3. Si ya corriste v5, normalmente no tienes que instalar nada. Si no, ejecuta:

```powershell
py -3 -m pip install -r requirements.txt
py -3 -m playwright install chromium
```

**Prueba recomendada — únicamente Credicorp (7 fondos, incluyendo Acciones Latam Perú):**

```powershell
py -3 actualizar_links.py --gestora Credicorp --credicorp-navegador --mostrar-navegador
```

**Revisar TODOS los fondos (12):**

```powershell
py -3 actualizar_links.py --credicorp-navegador --mostrar-navegador
```

**Alternativa automática** sin forzar Chrome: `py -3 actualizar_links.py`. Credicorp abrirá Chrome/Chromium por sí solo si la lectura directa falla o parece desactualizada.

Cuando termina: 

```powershell
explorer .\data
```

Para diagnosticar bloqueos, comprime la carpeta `diagnostico_v5` (se conserva ese nombre por compatibilidad) y comparte `data/factsheets_links.csv`.

## Cómo interpretar los estados

- `PDF_ENLACE_VALIDADO`: se localizó el enlace y se verificó el encabezado de PDF.
- `ENLACE_DETECTADO_SIN_VALIDAR`: se encontró el enlace actual en la web, pero su URL no pudo verificarse directamente (p.ej. HTTP 403); requiere confirmación manual si es crítico.
- `ENLACE_ANTERIOR_SIN_REVALIDAR`: se conserva como referencia histórica, **NO equivale a una ficha actual**.
- `URL_NO_DISPONIBLE`: el documento localizado respondió 404 en la comprobación HTTP.
- `NO_ENCONTRADO`: tampoco existe enlace anterior.

Las fechas obtenidas del nombre del archivo son indicativas. Claude debe confirmar el mes dentro de la hoja antes de presentar métricas.

## Cambios técnicos

- Nuevo `credicorp_resolver.py`: navegación real en Chrome/Chromium, extracción desde HTML publicado por Credicorp; sin descargar PDFs completos.
- Nuevos parámetros `--gestora Credicorp` y `--credicorp-navegador`.
- Se conserva el histórico sin confundirlo con éxito y se evita reemplazar un periodo más reciente por una página en caché de periodo anterior.
- La carpeta inicial `data` incluye el CSV que compartió S4 al cierre de v5, para no perder las capturas de BBVA.
- 19 tests locales superados (incluyen simulación de 403, apertura del navegador y recuperación de septiembre). **No se ha podido realizar una prueba de navegación en vivo desde este entorno**, por restricciones de conectividad externa.

## Integración futura

El workflow `.github/workflows/actualizar-factsheets.yml` sigue siendo una opción para ejecución programada. En GitHub Actions el navegador intentará ejecutarse en modo headless; la navegación en vivo debe validarse primero en Windows. Para añadir fondos nuevos, agrega otra entrada a `fondos.json` (el motor de Credicorp sirve para nuevas páginas con el mismo diseño).
