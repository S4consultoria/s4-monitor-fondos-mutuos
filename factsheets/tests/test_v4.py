import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bbva_resolver import is_bbva_finv, fecha_archivo, choose
from actualizar_links import build, find_official_bbva_ficha
from agregar_fondo import add
import requests

PDF='https://bbvaamdocs.bbva.com/documents/BBVA/382_FINV_20261009_PER_SPA_0.pdf'

class TestV4(unittest.TestCase):
    def test_bbva_archivo(self):
        self.assertTrue(is_bbva_finv(PDF,'382'))
        self.assertFalse(is_bbva_finv(PDF,'999'))
        self.assertFalse(is_bbva_finv('https://evil.com/documents/BBVA/382_FINV_20261009_PER_SPA_0.pdf'))
        self.assertEqual(fecha_archivo(PDF),'2026-10-09')
    def test_no_inferir_periodo(self):
        fund={'id':'f_test','saf':'BBVA','nombre':'Test','metodo':'bbva_portal',
              'fuente':'https://producto.bbvaassetmanagement.com/pe/index.html#!/fichape/382',
              'codigo_bbva':'382'}
        with patch('actualizar_links.resolve_bbva_url',return_value=(PDF,'')):
            row=build(fund,lambda u:'',requests.Session(),verify=False)
        self.assertEqual(row['periodo'],'')
        self.assertEqual(row['fecha_documento'],'2026-10-09')
        self.assertEqual(row['tipo_documento'],'ficha_del_inversionista')
    def test_periodo_captura_usuario(self):
        fund={'id':'f_test','saf':'BBVA','nombre':'Test','metodo':'bbva_portal',
              'fuente':'https://producto.bbvaassetmanagement.com/pe/index.html#!/fichape/382',
              'codigo_bbva':'382','url_pdf_manual':PDF,'periodo_pdf_manual':'2026-09'}
        with patch('actualizar_links.resolve_bbva_url',return_value=(PDF,'')):
            row=build(fund,lambda u:'',requests.Session(),verify=False)
        self.assertEqual(row['periodo'],'2026-09')
    def test_solo_finv_y_mismo_fondo(self):
        other='https://bbvaamdocs.bbva.com/documents/BBVA/777_FINV_20261009_PER_SPA_0.pdf'
        self.assertEqual(choose([PDF,other],''),'')
        self.assertEqual(choose([PDF,other],'382'),PDF)
    def test_otra_ficha_bbva_configurable(self):
        c=[]
        f={'id':'bbva_mi_nuevo_fondo','nombre':'Nuevo','saf':'BBVA',
           'fuente':'https://producto.bbvaassetmanagement.com/pe/index.html#!/fichape/999'}
        self.assertEqual(len(add(c,f)),1)
        with self.assertRaises(ValueError): add(c,f)
    def test_no_asignar_fondo_erroneo(self):
        h='<a href="https://producto.bbvaassetmanagement.com/pe/index.html#!/fichape/12">Ver fondo A</a>'
        self.assertFalse(find_official_bbva_ficha(h,'https://fondos.bbva.pe/','Ver fondo B'))

if __name__=='__main__':unittest.main()
