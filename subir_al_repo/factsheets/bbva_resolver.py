"""Captura la 'Ficha del inversionista' BBVA por el flujo oficial mostrado por S4.

1) Página fondos.bbva.pe => clicar 'Ver fondo ...'
2) Visor producto.bbvaassetmanagement.com => Documentación => Ficha del inversionista
3) Recuperar URL BBVA _FINV_ desde href, popup, descarga o eventos de red.

No se generan URLs por patrones de fechas ni se descargan PDFs completos.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

BBVA_DOC_HOST = "bbvaamdocs.bbva.com"
VISOR_HOST = "producto.bbvaassetmanagement.com"
FINV = re.compile(r"(?:^|/)[^/]+_FINV_\d{8}_PER_SPA_\d+\.pdf(?:\?.*)?$", re.I)
DOCUMENT_DATE = re.compile(r"/[^/]+_FINV_(20\d{6})_PER_SPA_", re.I)
LABEL = re.compile(r"ficha\s+(?:del?\s+)?inversionista", re.I)


def is_bbva_finv(url: str, expected_code: str = "") -> bool:
    p = urlparse(url or "")
    if p.scheme != "https" or p.hostname != BBVA_DOC_HOST or not FINV.search(p.path):
        return False
    if expected_code:
        match = re.search(r"/([^/]+)_FINV_", p.path, re.I)
        if not match or match.group(1).casefold() != str(expected_code).casefold():
            return False
    return True


def fecha_archivo(url: str) -> str:
    m = DOCUMENT_DATE.search(urlparse(url).path)
    if not m:
        return ""
    d = m.group(1)
    return f"{d[:4]}-{d[4:6]}-{d[6:]}"


def choose(candidates: list[str], code: str = "") -> str:
    urls = sorted({u for u in candidates if is_bbva_finv(u, code)},
                  key=lambda u: (fecha_archivo(u), u), reverse=True)
    if not code and len({re.search(r"/([^/]+)_FINV_", urlparse(u).path, re.I).group(1)
                         for u in urls}) > 1:
        return ""
    return urls[0] if urls else ""


def _controlled_visor_url(url: str) -> bool:
    p = urlparse(url or "")
    return p.scheme == "https" and p.hostname == VISOR_HOST


def _diagnostic(directory, logs, ctx, stage):
    if not directory:
        return
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    (out / "eventos.json").write_text(json.dumps(logs, ensure_ascii=False, indent=2), encoding="utf-8")
    for n, tab in enumerate(ctx.pages):
        try:
            tab.screenshot(path=str(out / f"{stage}_tab{n}.png"), full_page=False, timeout=7000)
            (out / f"{stage}_tab{n}.html").write_text(tab.content(), encoding="utf-8")
            frame_urls = [f.url for f in tab.frames]
            (out / f"{stage}_tab{n}_marcos.json").write_text(json.dumps(frame_urls,ensure_ascii=False,indent=2), encoding="utf-8")
        except Exception as exc:
            logs.append("diagnostico: " + type(exc).__name__ + ": " + str(exc)[:100])


def _link_from_control(control, base_url):
    """Busca href / data-url / ventana.open en ancestros del control, incluyendo Shadow DOM abierto."""
    try:
        u = control.evaluate("""el => {
          let n=el;
          while (n) {
            for (const key of ['href','data-href','data-url']) {
              let v=n.getAttribute?.(key);
              if (v) return v;
            }
            n=n.parentElement || n.getRootNode()?.host;
          }
          return '';
        }""")
        return urljoin(base_url, u) if u else ""
    except Exception:
        return ""


def _find_pdf_controls(ctx):
    """Búsqueda en todas las pestañas y marcos, incluido Shadow DOM abierto."""
    for tab in list(ctx.pages):
        for frame in list(tab.frames):
            for selector in [
                lambda f: f.get_by_role("link", name=LABEL).first,
                lambda f: f.get_by_text(LABEL).first,
                lambda f: f.locator("a:has-text('Ficha del inversionista')").first,
                lambda f: f.locator("text=/Ficha\\s+del\\s+inversionista/i").first,
            ]:
                try:
                    ctrl = selector(frame)
                    if ctrl.count() > 0:
                        yield tab, frame, ctrl
                except Exception:
                    pass


def _find_visor_link(page, portal_link_text):
    """Evita el texto completo exacto para tolerar cambios menores de BBVA."""
    if portal_link_text:
        matches = [page.get_by_role("link", name=portal_link_text, exact=True).first,
                   page.get_by_role("link", name=re.compile(re.escape(portal_link_text), re.I)).first]
    else:
        matches = []
    if not portal_link_text:
        matches.extend([page.locator("a[href*='producto.bbvaassetmanagement.com']").first,
                        page.get_by_role("link", name=re.compile(r"Ver fondo BBVA", re.I)).first])
    for ctrl in matches:
        try:
            if ctrl.count():
                href = _link_from_control(ctrl, page.url)
                if _controlled_visor_url(href):
                    return ctrl, href
        except Exception:
            pass
    return None, ""


def resolve_bbva_url(portal_url: str, *, code: str = "", portal_link_text: str = "",
                     show_browser: bool = False, timeout_ms: int = 35000,
                     fallback_portal: str = "", diagnostic_dir=None,
                     manual_assist: bool = False) -> tuple[str, str]:
    """Sigue el flujo real. En el modo asistido, la persona puede hacer clic en el navegador.

    Si no es posible abrir la página con Playwright, el usuario siempre puede
    registrar una URL obtenida con su Chrome normal usando registrar_pdf.py.
    """
    from playwright.sync_api import sync_playwright
    hits: list[str] = []
    logs: list[str] = []
    clicked_urls: list[str] = []

    def collect(url):
        if is_bbva_finv(url, code):
            hits.append(url)
            logs.append("URL_FINV: " + url)

    with sync_playwright() as p:
        # Chrome de sistema, si está disponible; de lo contrario Chromium de Playwright.
        browser = None
        if show_browser:
            try:
                browser = p.chromium.launch(channel="chrome", headless=False)
                logs.append("navegador: chrome del sistema")
            except Exception:
                pass
        if browser is None:
            browser = p.chromium.launch(headless=not show_browser,
                                        args=["--disable-dev-shm-usage"])
            logs.append("navegador: chromium playwright")
        ctx = browser.new_context(accept_downloads=True, locale="es-PE",
                                  viewport={"width":1440,"height":1050})
        ctx.on("request", lambda req: collect(req.url))
        ctx.on("response", lambda resp: collect(resp.url))
        def on_page(tab):
            logs.append("pestana_nueva: " + tab.url)
            tab.on("download", lambda download: collect(download.url))
        ctx.on("page", on_page)
        page = ctx.new_page()
        page.on("download", lambda download: collect(download.url))
        try:
            # ETAPA 1: Página de producto (o visor directo si se dispone de un identificador seguro).
            try:
                r = page.goto(portal_url, wait_until="domcontentloaded", timeout=timeout_ms)
                logs.append("pagina_inicial: " + str(r.status if r else "sin_response") + " " + page.url)
            except Exception as exc:
                logs.append("pagina_inicial_error: " + type(exc).__name__ + ": " + str(exc).splitlines()[0][:130])
            if not _controlled_visor_url(page.url):
                ctrl, href = _find_visor_link(page, portal_link_text)
                if href:
                    logs.append("enlace_ver_fondo: " + href)
                    # Hacer clic como en el flujo del usuario. Si la página bloquea el clic,
                    # abrir el href real que ya se extrajo del control oficial.
                    try:
                        ctrl.click(timeout=8000)
                        page.wait_for_timeout(1200)
                        clicked_urls.append(href)
                        logs.append("click_ver_fondo: ok")
                    except Exception as exc:
                        logs.append("click_ver_fondo_error: " + str(exc).splitlines()[0][:110])
                    if not any(_controlled_visor_url(t.url) for t in ctx.pages):
                        page.goto(href, wait_until="domcontentloaded", timeout=timeout_ms)
                elif _controlled_visor_url(fallback_portal):
                    logs.append("acceso_por_visor_configurado (pagina oficial no disponible)")
                    try:
                        page.goto(fallback_portal, wait_until="domcontentloaded", timeout=timeout_ms)
                    except Exception as exc:
                        logs.append("visor_error: " + type(exc).__name__ + ": " + str(exc).splitlines()[0][:110])
                else:
                    logs.append("NO_LOCALIZADO: link Ver fondo en pagina oficial")
            _diagnostic(diagnostic_dir, logs, ctx, "bbva_paso2_visor")
            # ETAPA 2: Sección Documentación => Ficha del inversionista.
            located = False
            import time
            until = time.monotonic() + min(timeout_ms / 1000, 35)
            while time.monotonic() < until and not hits:
                controls = list(_find_pdf_controls(ctx))
                if controls:
                    located = True
                    tab, frame, ctrl = controls[0]
                    u = _link_from_control(ctrl, tab.url)
                    if u:
                        logs.append("url_control: " + u)
                        collect(u)
                    if not hits:
                        try:
                            ctrl.scroll_into_view_if_needed(timeout=5000)
                            ctrl.click(timeout=8000)
                            logs.append("click_ficha_inversionista: ok")
                            clicked_urls.append(tab.url)
                            tab.wait_for_timeout(1800)
                        except Exception as exc:
                            logs.append("click_ficha_inversionista_error: " + str(exc).splitlines()[0][:110])
                    break
                page.wait_for_timeout(800)
            if not located:
                logs.append("NO_LOCALIZADO: control Ficha del inversionista, incluidos marcos")
            # ETAPA 3: PDF en enlace/pestaña/red. Buscar la URL solo después del control.
            for tab in ctx.pages:
                try:
                    collect(tab.url)
                    for u in tab.locator("a[href*='_FINV_']").evaluate_all("els=>els.map(a=>a.href)"):
                        collect(u)
                except Exception:
                    pass
            if not hits and manual_assist and show_browser:
                print("\nBBVA: si el visor abrió, pulsa Ficha del inversionista en la ventana mostrada.\n"
                      "Cuando el PDF se haya abierto, regresa aquí y pulsa ENTER.\n", flush=True)
                input("ENTER para recuperar el enlace capturado > ")
                for tab in ctx.pages:
                    try: collect(tab.url)
                    except Exception: pass
            _diagnostic(diagnostic_dir, logs, ctx, "bbva_resultado")
            out = choose(hits, code)
            if not out:
                if hits:
                    logs.append("FINV ambiguos: se detectaron más de un fondo; no se elige ninguno")
                else:
                    logs.append("No se capturó PDF FINV; si Chrome normal sí funciona, usar registrar_pdf.py")
            return out, "; ".join(logs)[-1900:]
        finally:
            ctx.close()
            browser.close()
