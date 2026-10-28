#!/usr/bin/env python3
"""Resuelve enlaces de fichas de fondos S4 y publica JSON/CSV, sin almacenar PDFs.

Los metadatos de fecha por nombre de archivo se marcan como indicativos, no como
validación del contenido. Los enlaces fallidos anteriores se retienen con alerta.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

import requests
from bs4 import BeautifulSoup
from bbva_resolver import resolve_bbva_url, fecha_archivo, is_bbva_finv
from credicorp_resolver import fetch_credicorp_browser

ROOT = Path(__file__).resolve().parent
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
DOMAINS = ("miblum.com", "credicorpcapital.com", "cdn.prod.website-files.com", "bbva.pe", "bbvaassetmanagement.com", "bbvaamdocs.bbva.com")
BAD = re.compile(r"prospecto|reglamento|anexo|contrato|comisiones|bolet[ií]n|memoria|estado\s+financiero|kiid|politica", re.I)
GOOD = re.compile(r"hojas?\s+informativas?|fact\s*sheet|factsheet|ficha\s+(?:mensual|informativa|t[eé]cnica|del?\s+fondo)", re.I)
MONTHS = {"enero":1, "ene":1, "febrero":2, "feb":2, "marzo":3, "mar":3, "abril":4, "abr":4, "mayo":5, "may":5, "junio":6, "jun":6, "julio":7, "jul":7, "agosto":8, "ago":8, "septiembre":9, "setiembre":9, "sept":9, "sep":9, "set":9, "octubre":10, "oct":10, "noviembre":11, "nov":11, "diciembre":12, "dic":12}
MONTH_PATTERN = "|".join(sorted(MONTHS, key=len, reverse=True))
FIELDS = ["fondo_id", "saf", "fondo", "estado", "periodo", "metodo_fecha", "fecha_documento", "url_pdf", "url_pagina", "url_ficha_web", "url_respaldo", "tipo_respaldo", "tipo_documento", "validacion_http", "ultima_revision", "detalle"]


def norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    return " ".join("".join(c for c in s if not unicodedata.combining(c)).lower().split())


def period_from_url(u):
    name = norm(unquote(urlparse(u).path.rsplit("/", 1)[-1])).replace("%20", " ")
    m = re.search(rf"(?<![a-z])({MONTH_PATTERN})[\s_./-]*(?:de[\s_./-]*)?(20\d{{2}})\b", name)
    if m:
        return f"{m.group(2)}-{MONTHS[m.group(1)]:02d}"
    m = re.search(r"\b(20\d{2})[-_/](0?[1-9]|1[0-2])\b", name)
    return f"{m.group(1)}-{int(m.group(2)):02d}" if m else ""


def trusted(u):
    p = urlparse(u)
    host = (p.hostname or "").lower()
    return p.scheme == "https" and any(host == d or host.endswith("." + d) for d in DOMAINS)


@dataclass
class Candidate:
    url: str
    label: str
    period: str
    kind: str


def extract_candidates(html, base):
    soup = BeautifulSoup(html, "html.parser")
    out = {}
    for a in soup.select("a[href], [data-url], [data-href]"):
        href = a.get("href") or a.get("data-url") or a.get("data-href") or ""
        if not href or href.startswith(("javascript:", "#", "mailto:")):
            continue
        full_url = urljoin(base, href)
        if not trusted(full_url):
            continue
        label = " ".join([a.get_text(" ", strip=True), a.get("title", ""), a.get("aria-label", "")])
        mention = (label + " " + full_url).lower()
        # Un enlace genérico «Descargar» junto a un factsheet no demuestra que
        # el PDF concreto sea una ficha; exigir indicio en el propio enlace.
        if BAD.search(label + " " + href) or not GOOD.search(mention):
            continue
        if not (".pdf" in urlparse(full_url).path.lower() or "pdf" in label.lower()):
            # No registrar enlaces genéricos que llevan a un nuevo portal.
            continue
        kind = "hoja_informativa" if re.search(r"hojas?\s+informativas?", mention, re.I) else "factsheet"
        out[full_url] = Candidate(full_url, label.strip(), period_from_url(full_url), kind)
    return list(out.values())


def find_official_bbva_ficha(html, base, text):
    soup = BeautifulSoup(html, "html.parser")
    target = norm(text)
    if not target:
        return ""
    for a in soup.select("a[href]"):
        label = norm(a.get_text(" ", strip=True))
        url = urljoin(base, a.get("href"))
        if target == label and trusted(url) and "producto.bbvaassetmanagement.com" in url:
            return url
    return ""


def check_pdf_link(url, session):
    """Inspecciona solo bytes iniciales del PDF, no descarga ni guarda el documento."""
    try:
        if not trusted(url):
            return "DOMINIO_NO_PERMITIDO", ""
        with session.get(url, stream=True, timeout=(10, 20), allow_redirects=True, headers={"Range": "bytes=0-1023"}) as res:
            if not trusted(res.url):
                return "REDIRECCION_NO_PERMITIDA", ""
            res.raise_for_status()
            iterator = res.iter_content(chunk_size=1024)
            first = next(iterator, b"")
            if first.startswith(b"%PDF-"):
                return "PDF_CONFIRMADO", ""
            return "NO_PDF", f"Content-Type: {res.headers.get('Content-Type', '')}"
    except Exception as exc:
        return "HTTP_NO_CONFIRMADO", (type(exc).__name__ + ": " + str(exc))[:130]


def last_month():
    d = date.today().replace(day=1)
    if d.month == 1:
        return f"{d.year-1}-12"
    return f"{d.year}-{d.month-1:02d}"


def load_legacy(path):
    if not path or not Path(path).exists():
        return {}
    obj = json.loads(Path(path).read_text(encoding="utf8"))
    rows = obj.get("fondos", []) if isinstance(obj, dict) else obj
    return {r["fondo_id"]:r for r in rows}


def classify_period(period):
    if not period:
        return "SIN_FECHA"
    return "PERIODO_PREVIO" if period < last_month() else "PERIODO_RECIENTE"


def build(fund, get_page, session, offline=False, old=None, verify=True, mostrar_navegador=False, ayuda_manual=False, carpeta_diagnostico=None, credicorp_navegador=False):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = {"fondo_id":fund["id"], "saf":fund["saf"], "fondo":fund["nombre"],
              "estado":"", "periodo":"", "metodo_fecha":"", "fecha_documento":"", "url_pdf":"", "url_pagina":fund["fuente"],
              "url_ficha_web":"", "url_respaldo":"", "tipo_respaldo":"", "tipo_documento":"",
              "validacion_http":"NO_APLICA", "ultima_revision":now, "detalle":""}
    if fund.get("requiere_confirmacion"):
        record.update(estado="REVISAR_IDENTIDAD", detalle=fund.get("estado_fuente", ""))
        return record
    if fund.get("metodo") == "bbva_portal" or fund["saf"] == "BBVA":
        # Localiza el enlace del visor individual. No confundir boletines ni prospectos.
        portal = fund["fuente"] if "producto.bbvaassetmanagement.com" in fund["fuente"] else ""
        if not portal and not offline:
            try:
                html = get_page(fund["fuente"])
                portal = find_official_bbva_ficha(html, fund["fuente"], fund.get("texto_enlace", ""))
            except Exception as exc:
                record["detalle"] = "No se pudo consultar la pagina oficial: " + str(exc)[:120]
        # Si la pagina general es accesible solo en el navegador, el resolver
        # puede entrar por ella y pulsar «Ver fondo ...» antes de FINV.
        if not portal and fund.get("texto_enlace") and not offline:
            portal = fund["fuente"]
        # Un enlace proporcionado por el usuario puede servir de respaldo, pero no
        # usar BBVATSO-PE, pues existe duda fundada sobre su identidad.
        if not portal and not fund.get("fuente_usuario_dudosa"):
            portal = fund.get("fuente_usuario", "")
        record["url_ficha_web"] = portal
        code = fund.get("codigo_bbva", "")
        url, msg = "", ""
        if portal and not offline:
            try:
                url, msg = resolve_bbva_url(portal, code=code,
                                             portal_link_text=fund.get("texto_enlace", ""),
                                             show_browser=mostrar_navegador,
                                             fallback_portal=(fund.get("fuente_usuario", "") if not fund.get("fuente_usuario_dudosa") else ""),
                                             diagnostic_dir=(carpeta_diagnostico / fund["id"] if carpeta_diagnostico else None),
                                             manual_assist=ayuda_manual)
            except Exception as exc:
                msg = "Fallo visor BBVA: " + (type(exc).__name__ + ": " + str(exc))[:180]
        elif offline:
            msg = "Prueba offline sin visor BBVA disponible"
        else:
            msg = "No se localizo el visor del fondo en el origen oficial"
        used_fallback = False
        if not url:
            prior = old.get("url_pdf", "") if old else ""
            seed = fund.get("url_pdf_manual", "")
            for candidate in (prior,seed):
                if is_bbva_finv(candidate,code):
                    url=candidate
                    used_fallback = True
                    msg += "; Se conserva PDF conocido; NO se confirma que siga vigente"
                    break
        record["detalle"] = "; ".join(filter(None,[record["detalle"],msg]))
        if not url:
            record["estado"] = "NO_ENCONTRADO"
            return record
        # FINV identifica una ficha del inversionista. AAAAMMDD corresponde a fecha
        # del archivo, NO al mes de cierre del reporte; no inferir periodo = fecha.
        status, err = ("SIN_VERIFICAR", "") if not verify else check_pdf_link(url,session)
        record["url_pdf"] = url
        record["fecha_documento"] = fecha_archivo(url)
        record["tipo_documento"] = "ficha_del_inversionista"
        record["validacion_http"] = status
        known = fund.get("url_pdf_manual", "") == url
        if known and fund.get("periodo_pdf_manual"):
            record["periodo"] = fund["periodo_pdf_manual"]
            record["metodo_fecha"] = "CAPTURA_USUARIO"
        elif old and old.get("url_pdf") == url:
            record["periodo"] = old.get("periodo", "")
            record["metodo_fecha"] = old.get("metodo_fecha", "")
        else:
            record["metodo_fecha"] = "PERIODO_NO_VERIFICADO"
        if status == "PDF_CONFIRMADO":
            record["estado"] = "ENLACE_ANTERIOR_REVALIDADO" if used_fallback else "PDF_ENLACE_VALIDADO"
        elif url and not msg.startswith("No se localizo") and not msg.startswith("Fallo visor") and "Se conserva PDF conocido" not in msg:
            record["estado"] = "ENLACE_DETECTADO_SIN_VALIDAR"
        else:
            record["estado"] = "ENLACE_ANTERIOR_SIN_REVALIDAR"
        if err: record["detalle"] += "; " + err
        if not record["periodo"]:
            record["detalle"] += "; El periodo de cartera aun no ha sido verificado"
        return record
    # Credicorp: primer intento por HTML directo; si falla/está desactualizado,
    # segundo intento REAL desde Chrome/Chromium. Nunca omitir porque haya un PDF antiguo.
    candidates = []
    msgs = []
    is_cc = fund["saf"] == "Credicorp" and "/Peru/" in fund["fuente"]
    if not (is_cc and credicorp_navegador and not offline):
        try:
            html = get_page(fund["fuente"])
            candidates = extract_candidates(html, fund["fuente"])
            msgs.append(f"consulta_html: {len(candidates)} candidatos")
        except Exception as exc:
            msgs.append("consulta_html_fallo: " + (type(exc).__name__ + ": " + str(exc))[:150])
    # Un enlace de agosto en octubre no debe impedir que se busque septiembre.
    # En modo offline solo se usan diagnósticos; nunca se lanza Chromium.
    best_period = max((c.period for c in candidates), default="")
    browser_needed = is_cc and not offline and (credicorp_navegador or not candidates or best_period < last_month())
    if browser_needed:
        try:
            browser_html, browser_msg = fetch_credicorp_browser(
                fund["fuente"], show_browser=mostrar_navegador,
                diagnostic_dir=(carpeta_diagnostico / fund["id"] if carpeta_diagnostico else None))
            browser_candidates = extract_candidates(browser_html, fund["fuente"])
            msgs.append(f"navegador: {browser_msg}; {len(browser_candidates)} candidatos")
            # Si la web ofreció algo mejor, reemplazar candidatos previos;
            # un browser sin enlaces no invalida candidatos detectados por HTTP.
            if browser_candidates:
                old_best = max((c.period for c in candidates), default="")
                new_best = max((c.period for c in browser_candidates), default="")
                if new_best >= old_best:
                    candidates = browser_candidates
        except Exception as exc:
            msgs.append("navegador_fallo: " + (type(exc).__name__ + ": " + str(exc).splitlines()[0])[:170])
    record["detalle"] = "; ".join(msgs)
    # Elige el PDF de mayor periodo explícito. Sin fecha debe ser señalado para revisión.
    candidates.sort(key=lambda c:(bool(c.period),c.period, "hoja" in c.kind), reverse=True)
    if not candidates:
        if old and old.get("url_pdf"):
            record.update(estado="ENLACE_ANTERIOR_SIN_REVALIDAR", periodo=old.get("periodo", ""),
                metodo_fecha=old.get("metodo_fecha", ""), url_pdf=old["url_pdf"],
                tipo_documento=old.get("tipo_documento", ""),
                validacion_http="NO_REVALIDADO", detalle=(record["detalle"]+"; Se conserva enlace previo, NO confirmar vigencia").strip("; "))
        else:
            record["estado"] = "NO_ENCONTRADO"
        return record
    candidate = candidates[0]
    # Un HTML de caché más antiguo que el catálogo no debe reemplazar el último PDF.
    if old and old.get("url_pdf") and old.get("periodo") and candidate.period and candidate.period < old["periodo"]:
        record.update(estado="ENLACE_ANTERIOR_SIN_REVALIDAR", periodo=old.get("periodo", ""),
                      metodo_fecha=old.get("metodo_fecha", ""), url_pdf=old["url_pdf"],
                      tipo_documento=old.get("tipo_documento", ""), validacion_http="NO_REVALIDADO",
                      detalle=record["detalle"]+f"; Origen devolvio periodo {candidate.period}, anterior al ultimo registrado ({old['periodo']}); no se retrocede")
        return record
    status, err = ("SIN_VERIFICAR", "") if not verify else check_pdf_link(candidate.url, session)
    record.update(periodo=candidate.period, metodo_fecha="NOMBRE_ARCHIVO" if candidate.period else "SIN_FECHA",
                  url_pdf=candidate.url, tipo_documento=candidate.kind, validacion_http=status)
    record["estado"] = "PDF_ENLACE_VALIDADO" if status == "PDF_CONFIRMADO" else "ENLACE_DETECTADO_SIN_VALIDAR"
    if status == "HTTP_NO_CONFIRMADO" and "404" in err:
        record["estado"] = "URL_NO_DISPONIBLE"
    if status in ("NO_PDF", "DOMINIO_NO_PERMITIDO", "REDIRECCION_NO_PERMITIDA"):
        record["estado"] = "URL_REQUIERE_REVISION"
    record["detalle"] += ("; Fecha indicada por nombre, no validada dentro del PDF; " +
                          classify_period(candidate.period) + ("; " + err if err else ""))
    return record


def offline_getter(zf):
    names = set(zf.namelist())
    def getter(url):
        # Mapeo únicamente para las 6 páginas Credicorp Perú de los diagnósticos.
        paths = {
            "CPD.aspx":"cc_conservador_corto_usd", "CC-OL.aspx":"cc_duracion_objetivo_latam",
            "CC-DCHYL-FMIV.aspx":"cc_deuda_corporativa_latam_hy", "CPS.aspx":"cc_conservador_corto_pen",
            "CMPS-FMIV.aspx":"cc_conservador_mediano_pen", "CC-DCS-FMIV.aspx":"cc_deuda_corporativa_pen"
        }
        for key, code in paths.items():
            if key in url:
                filename=f"diagnostico/{code}.html"
                if filename in names:
                    return zf.read(filename).decode("utf-8", errors="replace")
        raise FileNotFoundError("Sin HTML en diagnóstico (esta fuente requiere ejecución en vivo)")
    return getter


def url_codificada(url):
    """Codifica espacios y tildes (%20, %C3%B3) para que cualquier cliente pueda abrir la URL."""
    from urllib.parse import quote
    return quote(url or "", safe=":/?=&%#;,+@~!*'()-._") if url else ""


def escribir_compacto(rows, catalog, destino):
    """data/factsheets_s4.json: 7 campos por fondo para el monitor y Claude.
    Determinista (sin marca de tiempo global) para no generar commits sin cambios."""
    meta = {f["id"]: f for f in catalog}
    fondos = []
    for r in rows:
        c = meta.get(r["fondo_id"], {})
        fondos.append({
            "fondo_id": r["fondo_id"],
            "fondo": r.get("fondo", c.get("nombre", "")),
            "nombre_excel": c.get("nombre_excel", ""),
            "saf": c.get("saf", ""),
            "url_pdf": url_codificada(r.get("url_pdf", "")),
            "url_pagina": c.get("fuente_estable") or r.get("url_pagina", ""),
            "periodo": r.get("periodo", ""),
            "estado": r.get("estado", ""),
            "ultima_revision": r.get("ultima_revision", ""),
        })
    (destino / "factsheets_s4.json").write_text(
        json.dumps({"fondos": fondos}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(args):
    catalog=json.loads(args.catalogo.read_text(encoding="utf-8"))
    previous=load_legacy(args.destino / "factsheets_links.json")
    args.destino.mkdir(parents=True, exist_ok=True)
    session=requests.Session()
    session.headers.update({"User-Agent":UA,"Accept":"text/html,application/pdf,*/*"})
    zf=zipfile.ZipFile(args.diagnostico_zip) if args.diagnostico_zip else None
    try:
        def online_getter(url):
            if not trusted(url):
                raise ValueError("Origen no autorizado")
            res=session.get(url,timeout=(10,22))
            res.raise_for_status()
            if not trusted(res.url):
                raise ValueError("Redirección fuera de los dominios oficiales")
            return res.text
        getter=offline_getter(zf) if zf else online_getter
        rows=[]
        for f in catalog:
            if args.gestora and f["saf"].casefold() != args.gestora.casefold():
                if f["id"] in previous:
                    rows.append(previous[f["id"]])
                continue
            if args.solo and f["id"] != args.solo:
                if f["id"] in previous:
                    rows.append(previous[f["id"]])
                continue
            row=build(f,getter,session,offline=bool(zf),old=previous.get(f["id"]),verify=not args.sin_verificar_http and not zf,
                      mostrar_navegador=args.mostrar_navegador, ayuda_manual=args.ayuda_manual,
                      carpeta_diagnostico=args.carpeta_diagnostico, credicorp_navegador=args.credicorp_navegador)
            rows.append(row)
            print(f"{f['id']}: {row['estado']} {row['periodo']}",flush=True)
        # Evita commits innecesarios en GitHub cuando no cambia ningún dato útil.
        stable_keys=[key for key in FIELDS if key not in ("ultima_revision",)]
        changed=False
        for row in rows:
            prior=previous.get(row["fondo_id"])
            if prior and all(row.get(k)==prior.get(k) for k in stable_keys):
                row["ultima_revision"]=prior.get("ultima_revision",row["ultima_revision"])
            else:
                changed=True
        escribir_compacto(rows, catalog, args.destino)
        if not changed and (args.destino/"factsheets_links.json").exists():
            print("No hubo cambios en los enlaces/estados; se conserva el catálogo anterior.")
            return rows
        output={"generado_utc":datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "advertencia":"Las fechas por URL son indicativas; verificar fuente antes de extraer métricas de inversión.",
                "fondos":rows}
        (args.destino/"factsheets_links.json").write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        with (args.destino/"factsheets_links.csv").open("w",newline="",encoding="utf-8-sig") as file:
            writer=csv.DictWriter(file,fieldnames=FIELDS,delimiter=";",extrasaction="ignore")
            writer.writeheader();writer.writerows(rows)
        return rows
    finally:
        if zf: zf.close()
        session.close()


def main():
    p=argparse.ArgumentParser(description="S4: catálogo de URLs de factsheets sin descargar PDFs")
    p.add_argument("--catalogo",type=Path,default=ROOT/"fondos.json")
    p.add_argument("--destino",type=Path,default=ROOT/"data")
    p.add_argument("--diagnostico-zip",type=Path,help="Modo offline de prueba con el ZIP de diagnóstico suministrado")
    p.add_argument("--solo",type=str,help="ID de un único fondo; conserva los demás si existen")
    p.add_argument("--gestora", choices=["Credicorp", "BBVA", "Blum"], help="Procesa una sola gestora; preserva las demás")
    p.add_argument("--credicorp-navegador",action="store_true",help="Revisar SIEMPRE Credicorp Peru desde navegador, incluso si requests devuelve enlaces")
    p.add_argument("--sin-verificar-http",action="store_true",help="No confirmar firma PDF: salida marcada sin validar")
    p.add_argument("--mostrar-navegador",action="store_true",help="Abre el navegador BBVA visiblemente (modo Windows)")
    p.add_argument("--ayuda-manual", action="store_true", help="Permite hacer clic en el visor abierto si falla el clic automatico")
    p.add_argument("--carpeta-diagnostico", type=Path, default=ROOT/"diagnostico_v5", help="Capturas y eventos por fondo BBVA")
    args=p.parse_args()
    if args.solo and args.gestora:
        p.error("Usa --solo o --gestora, no ambos")
    if args.ayuda_manual and not args.mostrar_navegador:
        p.error("--ayuda-manual requiere --mostrar-navegador")
    rows=run(args)
    n=sum(bool(r["url_pdf"]) for r in rows)
    print(f"RESULTADO: {len(rows)} fondos; {n} enlaces PDF individuales detectados. JSON + CSV en {args.destino}")
    return 0

if __name__=="__main__":
    sys.exit(main())
