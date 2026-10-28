#!/usr/bin/env python3
"""Agrega fondos editando SOLO el catálogo, sin tocar el resolvedor."""
import argparse
import json
import re
from pathlib import Path
from actualizar_links import ROOT, trusted


def add(catalog, new):
    if any(f['id'] == new['id'] for f in catalog):
        raise ValueError('El fondo_id ya existe. No se duplicó.')
    if not re.fullmatch(r'[a-z0-9]+(?:_[a-z0-9]+)*', new['id']):
        raise ValueError('Usa un id en minúsculas, números y guiones bajos.')
    if not trusted(new['fuente']):
        raise ValueError('La URL debe ser HTTPS de un dominio oficial permitido.')
    catalog.append(new)
    return catalog


def main():
    ap=argparse.ArgumentParser(description='S4: agregar un fondo a fondos.json')
    ap.add_argument('--catalogo',type=Path,default=ROOT/'fondos.json')
    ap.add_argument('--id',required=True)
    ap.add_argument('--nombre',required=True)
    ap.add_argument('--saf',choices=['BBVA','Credicorp','Blum'],required=True)
    ap.add_argument('--url',required=True,help='URL de ficha individual / página oficial')
    ap.add_argument('--texto-enlace',default='',help='Si BBVA URL es página general: texto exacto de «Ver fondo...»')
    ap.add_argument('--codigo-bbva',default='',help='Código exacto del PDF (si conocido), ej. 382')
    args=ap.parse_args()
    new={'id':args.id,'saf':args.saf,'nombre':args.nombre,'fuente':args.url,
         'metodo':'bbva_portal' if args.saf=='BBVA' else 'pagina', 'alias_pdf':[args.nombre.lower()]}
    if args.texto_enlace: new['texto_enlace']=args.texto_enlace
    if args.codigo_bbva: new['codigo_bbva']=args.codigo_bbva
    catalog=json.loads(args.catalogo.read_text(encoding='utf-8'))
    add(catalog,new)
    args.catalogo.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Agregado: {args.id}. Ejecuta py -3 actualizar_links.py --solo {args.id}')

if __name__=='__main__': main()
