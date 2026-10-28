#!/usr/bin/env python3
"""Registro local y explícito de un PDF BBVA capturado en Chrome normal.

Uso:
py -3 registrar_pdf.py --fondo bbva_fdf_distributivo --url https://...pdf --periodo 2026-09

No descarga documentos ni requiere acceder a la web. Preserva los otros fondos.
"""
import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from bbva_resolver import fecha_archivo, is_bbva_finv
from actualizar_links import ROOT, FIELDS


def save_entry(config_file, data_dir, fund_id, url, period):
    catalog = json.loads(Path(config_file).read_text(encoding="utf-8"))
    mapping = {x['id']:x for x in catalog}
    if fund_id not in mapping:
        raise ValueError("El id del fondo no figura en fondos.json")
    fund = mapping[fund_id]
    if fund['saf'] != 'BBVA':
        raise ValueError("El registro manual de esta version está limitado a fichas BBVA")
    if not is_bbva_finv(url, fund.get('codigo_bbva','')):
        raise ValueError("El enlace no corresponde a una ficha FINV de BBVA con el código esperado")
    if not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", period):
        raise ValueError("Periodo inválido. Usar AAAA-MM según el MES IMPRESO dentro del PDF")
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    json_path = data_dir / "factsheets_links.json"
    if json_path.exists():
        obj = json.loads(json_path.read_text(encoding="utf-8"))
        rows = obj.get('fondos', [])
    else:
        rows = []
    keyed = {x['fondo_id']:x for x in rows}
    prev = keyed.get(fund_id,{})
    if prev.get('periodo') and period < prev['periodo']:
        raise ValueError("El periodo nuevo es más antiguo que el almacenado; revisa si es la ficha correcta")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = dict(prev)
    record.update({
        'fondo_id':fund_id, 'saf':fund['saf'], 'fondo':fund['nombre'],
        'estado':'CAPTURA_MANUAL_SIN_REVALIDAR', 'periodo':period,
        'metodo_fecha':'LECTURA_MANUAL_DOCUMENTO',
        'fecha_documento':fecha_archivo(url), 'url_pdf':url,
        'url_pagina':fund['fuente'], 'url_ficha_web':fund.get('fuente_usuario',''),
        'tipo_documento':'ficha_del_inversionista',
        'validacion_http':'NO_VERIFICADO_EN_SCRIPT', 'ultima_revision':now,
        'detalle':'URL capturada manualmente desde Chrome. Periodo informado por persona; verificar antes de análisis.'
    })
    keyed[fund_id] = record
    # Mantiene el orden del catálogo y las entradas aún no procesadas.
    out=[]
    for f in catalog:
        if f['id'] in keyed:
            out.append(keyed[f['id']])
    obj={'generado_utc':now,'advertencia':'Los enlaces capturados manualmente no están validados por HTTP.','fondos':out}
    json_path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    with (data_dir/'factsheets_links.csv').open('w',newline='',encoding='utf-8-sig') as csvf:
        writer=csv.DictWriter(csvf,fieldnames=FIELDS,delimiter=';',extrasaction='ignore')
        writer.writeheader()
        for row in out:writer.writerow(row)
    return record


def main():
    p=argparse.ArgumentParser(description="Registra manualmente enlace directo BBVA de la Ficha del inversionista")
    p.add_argument('--fondo',required=True,help='ID de fondos.json')
    p.add_argument('--url',required=True,help='URL PDF FINV copiada desde la barra de Chrome')
    p.add_argument('--periodo',required=True,help='AAAA-MM, tal como se muestra en la portada del PDF')
    p.add_argument('--catalogo',type=Path,default=ROOT/'fondos.json')
    p.add_argument('--destino',type=Path,default=ROOT/'data')
    args=p.parse_args()
    try:
        result=save_entry(args.catalogo,args.destino,args.fondo,args.url,args.periodo)
    except ValueError as exc:
        p.error(str(exc))
    print(f"REGISTRADO: {result['fondo']} => {result['periodo']}\n{result['url_pdf']}")
    print('JSON y CSV actualizados; no se ha descargado el PDF.')

if __name__=='__main__':main()
