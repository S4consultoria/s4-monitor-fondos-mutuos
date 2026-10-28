# Brief para Claude Code — Pestaña "Cartera S4" del Monitor FFMM

Repo: `S4consultoria/s4-monitor-fondos-mutuos` (público). Rama `main` + otra rama (revísala antes de tocar nada).
Hoy contiene solo `index.html` y `fondos.xlsx`. El sitio se despliega en Cloudflare Pages desde el repo y `index.html` lee `fondos.xlsx` vía raw.githubusercontent.com.
Idioma de todo lo que se muestre al usuario y de los commits: español. Steve (director de S4) prefiere respuestas directas y concisas.


> ## ⚠️ Entorno: Claude Code **en la web** (nube), no en la PC de Steve
> Steve trabaja desde claude.ai/code. Esto cambia lo siguiente respecto al resto del brief:
> - **Dónde viven estos archivos:** Steve subió esta carpeta al repo como `_handoff/`. Léela desde ahí. Al terminar, proponer borrar `_handoff/`.
> - **Ramas:** por defecto trabajas en una rama `claude/...`. Abre un Pull Request hacia `main` y avisa a Steve para que lo fusione (Cloudflare Pages despliega desde `main`). Solo empuja directo a `main` si Steve lo pide.
> - **Red:** el entorno "Default" usa acceso *Trusted* y **bloquea dominios fuera de su lista**. Para leer factsheets hacen falta: `www.credicorpcapital.com`, `bbvaamdocs.bbva.com`, `cdn.prod.website-files.com` (y `raw.githubusercontent.com`). Si un `curl` devuelve 403 con `x-deny-reason: host_not_allowed`, pedir a Steve que edite el entorno (Network access → Custom → Allowed domains, marcando también la lista por defecto).
> - **BBVA puede devolver 403 por otras razones** (su sitio bloquea clientes no-navegador; en el PC de Steve `requests` también recibe 403). Si pasa, probar WebFetch; si tampoco, pedir a Steve que descargue los 3 PDFs FINV de BBVA y los suba a `factsheets/manual/` (la URL de cada uno está en `factsheets/data/factsheets_s4.json`).
> - **Playwright/Chromium en la nube** puede no instalarse por red restringida. Si no se puede, validar la pestaña con una revisión estática del JS (`node --check`) y pedirle a Steve que la mire en su navegador antes del merge.
> - **Mismo repo que usa el workflow:** el GitHub Action (`.github/workflows/actualizar-factsheets.yml`) corre en GitHub, no en Claude Code. Claude Code no necesita ejecutarlo; solo leer su salida `factsheets/data/factsheets_s4.json` (la primera vez, Steve lo lanza a mano en Actions → Run workflow).
> - **Reemplaza** donde el brief diga "descargar con curl desde la máquina de Steve" por "descargar desde el entorno de la nube (ver Red)".

## Objetivo
Una pestaña **🎯 Cartera S4** con los 12 fondos mutuos donde S4 tiene posiciones vía clientes. Por fondo: cifras (del Excel), factsheet actualizado (link directo), **composición de cartera a la fecha del último factsheet**, descripción de en qué invierte y perspectiva a 12 meses. Debe actualizarse cada quincena con poca intervención.

## Qué ya existe (en esta carpeta)
- `index_con_pestana_cartera_v1.html`: el `index.html` del monitor con la pestaña ya construida (v1, probada con Playwright contra el `fondos.xlsx` real, sin errores de consola). **No lo copies encima del `index.html` del repo**: el del repo pudo cambiar después del 20-oct. Haz diff y aplica solo lo añadido (bloque CSS "Pestaña Cartera S4", tab `tab-cartera`, `view-cartera`, hook en `render()`, cambios en `setView()` y el bloque JS `MACRO_S4 / ARQ_S4 / CARTERA_S4 / renderCartera`).
- `subir_al_repo/factsheets/`: actualizador de links (v6 de ChatGPT + parches v7: URLs codificadas con `%20`, salida compacta `data/factsheets_s4.json`, campo `nombre_excel` y `fuente_estable` en `fondos.json`).
- `subir_al_repo/.github/workflows/actualizar-factsheets.yml`: corre días 12 y 26 (13:00 UTC), `working-directory: factsheets`, con `concurrency` y `git pull --rebase`.
- `referencia_factsheets_links_gpt_2026-10-28.json`: salida real de la última corrida local de Steve.

## Pasos (en este orden, confirmando con Steve cada fase)
1. **Inspeccionar el repo** (ramas, workflows existentes, configuración de Pages). Confirmar que `index.html` actual coincide con la base del v1.
2. **Subir `factsheets/` y el workflow.** Pedir a Steve que active Settings → Actions → General → Workflow permissions = Read and write (o hacerlo con `gh api` si hay permisos). Lanzar `gh workflow run` y revisar resultado.
   - Esperado: Blum y Credicorp `PDF_ENLACE_VALIDADO`; BBVA `ENLACE_DETECTADO_SIN_VALIDAR` por 403 en la re-verificación HTTP — **es normal** (la URL sí es correcta: en su PC el clic en Chrome funciona y los PDFs abren).
   - Riesgo abierto: desde IPs de GitHub, BBVA puede bloquear el navegador. Si falla, el fallback es `factsheets/registrar_pdf.py` (registro manual de la URL FINV).
3. **Leer los 12 PDFs** (usa `url_pdf` de `factsheets/data/factsheets_s4.json`; ya están codificadas). Descargar con curl desde la máquina de Steve. Para Credicorp el texto del PDF solo trae emisores y moneda; **los gráficos (tipo de instrumento, región, rating) hay que leerlos rasterizando la página a imagen**.
   - Confirmar el período **dentro del PDF** (Credicorp: "Al 30 de Septiembre del 2026"; BBVA/Blum: "Septiembre 2026"), no por el nombre del archivo.
4. **Crear `cartera.json`** (raíz del repo) con, por fondo: `id`, `nombre_excel`, `corte` (fecha del factsheet), `fuente_pdf`, `composicion` (items con %, top emisores, duración, patrimonio, split por moneda cuando exista), `metricas_factsheet` (YTD/3M/6M/12M fondo vs benchmark), `en_que_invierte`, `perspectiva_12m` {`base`, `riesgos`, `vigilar`}, `fecha_lectura`.
5. **Modificar la pestaña** para que: (a) cifras salgan del Excel; (b) links salgan de `factsheets/data/factsheets_s4.json`; (c) composición, descripción y perspectiva salgan de `cartera.json`; (d) un apartado **"Composición de cartera al [corte]"** por fondo; (e) si `corte` es de un mes anterior al último mes del Excel, mostrar la etiqueta "composición desactualizada". Los textos hoy hardcodeados en `CARTERA_S4`/`ARQ_S4` deben migrar a `cartera.json`. Cargar los JSON con la misma estrategia que ya usa el Excel (raw URL con fallback relativo).
6. **Probar** con Playwright (hay un ejemplo de arnés en el historial: interceptar CDN de xlsx/Chart.js, servir `fondos.xlsx` local, contraseña del lock `s4equipo`) y revisar capturas antes de commit.
7. **Commit y push** (mensajes en español). No tocar `fondos.xlsx`: lo sube Steve a mano cada mes.

## Mapeo de los 12 fondos (nombre exacto en `fondos.xlsx`, tal como los muestra el monitor)
| id | nombre_excel |
|---|---|
| bbva_renta_corto_plazo_pen | BBVA RENTA CORTO PLAZO S/. BBVA SAF |
| bbva_renta_corto_plazo_usd | BBVA RENTA CORTO PLAZO $ BBVA SAF |
| bbva_fdf_distributivo | **no está en la matriz** (se retiró con los distributivos). Factsheet: 95 % PIMCO Income Fund; mostrar cifras del factsheet y avisar |
| cc_conservador_corto_usd | CRED. CONSER. CORTO PLAZO $ SERIE A |
| cc_conservador_corto_pen | CRED. CONSER. CORTO PLAZO S/ SERIE A |
| cc_conservador_mediano_pen | CC CONSERV. MED. PLAZO S/. SERIE A |
| cc_deuda_corporativa_pen | CC DEUDA CORPORATIVA SOLES CREDICORP SAF |
| cc_duracion_objetivo_latam | FdF CC Duración Objetivo Latam CREDICORP SAF |
| cc_deuda_corporativa_latam_hy | CRED DEUDA CORP LATAM HY CREDICORP SAF |
| blum_money_market_usd | BLUM MONEY MARKET $ FM BLUM SAF |
| blum_bonos_globales | **no está en la matriz** (fondo institucional; Blum Renta Global FM Serie B es otro) |
| cc_latin_american_equity_i | **no está en la matriz**. Es el **FdF Credicorp Capital Acciones Latam FMIV (Perú)**, página ALP-FMIV.aspx; el id es heredado del fondo chileno. Renombrarlo a `cc_acciones_latam_pe` |

Nota: el parser del monitor quita el prefijo "CREDICORP SAF-" de los nombres; por eso los nombres de arriba no lo llevan. Idealmente añadir los 3 fondos faltantes a `fondos.xlsx` con su serie de valor cuota (Steve decide).

## Hallazgos de la lectura de septiembre 2026 (validar al leer; algunos números de BBVA tienen mapeo ambiguo entre etiquetas y valores)
- **BBVA FdF Distributivo Estratégico Global**: 95 % PIMCO Income Fund, duración 6,25, patrimonio US$132,7 MM. YTD −3,36 %, 12M −1,27 % vs benchmark −0,38 % / +0,57 %. Único de la cartera con 12M negativo.
- **Blum Bonos Globales** (Set-26): 12M 4,51 % vs benchmark −1,50 %; patrimonio US$54 MM; mezcla: HY 16 %, grado de inversión 15,9 %, emergentes 15,5 %, flexible 15,3 %, renta alternativa 11,7 %, arbitraje convertible 7,5 %, cat bonds 7,3 %.
- **Blum Money Market** (Set-26): 12M 3,78 % vs benchmark 2,55 %; patrimonio US$26 MM; 47,1 % financiero ex-USA, 30,4 % no financiero USA; YTW 5,45 %.
- **BBVA Renta CP Dólares**: patrimonio US$765 MM; depósitos a plazo ≈44 % y bonos corporativos ≈52 %; 10 principales emisores = 52,1 %.
- **BBVA Renta CP Soles**: patrimonio S/918 MM; bonos corporativos ≈51 %, depósitos a plazo ≈37 %; 10 principales emisores = 53,3 %.
- **CC Deuda Corporativa Soles** (Set-26): **48,6 % en USD / 51,4 % en PEN**, emisores incluyen Rep. del Perú 7,4 %, Primax, Alicorp, Rep. de Colombia, Santander México/Brasil; duración 3,46; 12M 3,20 % vs benchmark 6,78 %. (La descripción v1 "bonos corporativos peruanos en soles" es incorrecta: corregir.)
- **CC Conservador CP US$** (web): duración 90–360 días, 100 % renta fija. **CC Deuda Corp. Latam HY** (web): solo institucionales, duración flexible 0–10 años, distribución trimestral.
- Las cifras del factsheet y las del monitor difieren en centésimas (el monitor las calcula desde el valor cuota del Excel); es esperable.

## Contexto macro (para la tarjeta `MACRO_S4`, corte 20-oct-26; actualizar tras el FOMC del 28-oct)
Fed 3,75–4,00 % (alza de 25 pb el 16-sep, primera desde 2023; mediana SEP 4,1 % a fin de 2026). BCRP 4,25 % (13 meses sin cambios; inflación 4,5 % en septiembre; parte del mercado esperaba alza en octubre). Del comentario de Blum (Set-26): Brent > US$101 y bono del Tesoro a 10 años en 5,29 %.

## Reglas de contenido y diseño
- Lenguaje neutral y descriptivo; sin adjetivos fuertes ni juicios. Las perspectivas a 12M son escenarios cualitativos, **no proyecciones de retorno**.
- Diseño: nada cargado, más espacio entre tablas y tarjetas, letra algo más pequeña; menos texto, más elementos visuales (barras de composición, no párrafos).
- No inventar composición: si un dato no está en el factsheet, dejarlo vacío. Marcar siempre la fecha de corte.
- El repo es público (Steve lo aceptó): no guardar nada confidencial de clientes ni montos de posiciones.

## Automatización mensual (después de que el flujo manual funcione 1–2 ciclos)
Flujo objetivo: Action (días 12 y 26) actualiza links → Steve sube `fondos.xlsx` → Claude Code corre "actualiza la cartera" (pasos 3–5) → commit/push.
Para dejarlo sin intervención: crear una **tarea programada en la nube** (claude.ai/code/routines → New task, o `/schedule`) sobre este repo. Steve no usa Desktop, así que no hay opción local. Requisitos: (1) entorno con los dominios permitidos de la sección Red; (2) el prompt de la tarea debe ser autocontenido e indicar a qué rama empujar (por defecto `claude/...` y se abre PR; para publicar sin intervención, indicar `main` y verificar que no haya reglas de protección de rama que lo impidan); (3) programarla unos minutos después de la hora en punto (ej. 08:07) y un par de días después del Action (días 14 y 28 sugeridos); (4) si GitHub se desconecta, la tarea omite corridas hasta 72 h y luego se apaga. Cada corrida descuenta del uso de la suscripción de Steve. Revisar el historial de la tarea tras las primeras corridas.
