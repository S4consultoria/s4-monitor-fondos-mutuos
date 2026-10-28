"""Navegación de Credicorp: recupera HTML del portal sin descargar fichas PDF.

Se utiliza si requests recibe 403/no encuentra una Hoja Informativa o cuando
se solicita forzar Chromium. Conserva los enlaces observados en la página
oficial, sin generar rutas de PDF cambiando meses.
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from urllib.parse import urlparse


def is_credicorp_peru(url: str) -> bool:
    p = urlparse(url)
    return p.scheme == 'https' and p.hostname in ('www.credicorpcapital.com', 'credicorpcapital.com') and p.path.startswith('/Peru/')


def fetch_credicorp_browser(url: str, *, show_browser: bool = False,
                             diagnostic_dir=None, timeout_ms: int = 30000) -> tuple[str, str]:
    """Devuelve (HTML de página, detalle). No almacena ni descarga PDF."""
    if not is_credicorp_peru(url):
        raise ValueError('Solo se permiten páginas oficiales de Credicorp Capital Perú')
    from playwright.sync_api import sync_playwright
    logs = []
    with sync_playwright() as p:
        browser = None
        try:
            browser = p.chromium.launch(channel='chrome', headless=not show_browser,
                                        args=['--disable-dev-shm-usage'])
            logs.append('chrome')
        except Exception:
            browser = p.chromium.launch(headless=not show_browser,
                                        args=['--disable-dev-shm-usage'])
            logs.append('chromium_playwright')
        context = browser.new_context(locale='es-PE', viewport={'width':1440,'height':970},
                                      extra_http_headers={'Cache-Control':'no-cache', 'Pragma':'no-cache'})
        page = context.new_page()
        try:
            resp = page.goto(url, wait_until='domcontentloaded', timeout=timeout_ms)
            status = resp.status if resp else None
            logs.append('pagina_http='+str(status))
            if status and status >= 400:
                raise RuntimeError('Página respondió HTTP '+str(status)+' en navegador')
            # Las hojas de Credicorp suelen estar en el HTML, aunque el acordeón esté cerrado.
            # Seleccionar Documentos en caso de una carga dinámica.
            for selector in ('a[href*="Hojas_Informativas"]', 'a[href*="Hojas%20Informativas"]'):
                try:
                    page.locator(selector).first.wait_for(state='attached', timeout=2400)
                    logs.append('enlace_html_presente')
                    break
                except Exception:
                    pass
            if not page.locator('a[href*="Hojas_Informativas"]').count():
                for target in ('Documentos', 'Documentos referentes al Fondo'):
                    try:
                        page.get_by_text(target, exact=True).first.click(timeout=1700)
                        logs.append('click_'+target)
                    except Exception:
                        pass
                page.wait_for_timeout(900)
            html = page.content()
            if diagnostic_dir:
                path = Path(diagnostic_dir)
                path.mkdir(parents=True,exist_ok=True)
                (path/'credicorp_pagina.html').write_text(html, encoding='utf-8')
                links = page.locator('a[href]').evaluate_all('els => els.map(a=>({label:a.innerText, href:a.href})).filter(x => /informativ|\\.pdf/i.test(x.label+" "+x.href))')
                (path/'credicorp_enlaces.json').write_text(json.dumps(links,ensure_ascii=False,indent=2), encoding='utf-8')
                try: page.screenshot(path=str(path/'credicorp_pagina.png'),timeout=7000)
                except Exception: pass
            return html, '; '.join(logs)
        finally:
            context.close()
            browser.close()
