import csv
import sys
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bbva_resolver import is_bbva_finv,fecha_archivo,choose,_controlled_visor_url
from registrar_pdf import save_entry

PDF = 'https://bbvaamdocs.bbva.com/documents/BBVA/382_FINV_20261009_PER_SPA_0.pdf'

class TestV5(unittest.TestCase):
    def test_pdf_bbva_382(self):
        self.assertTrue(is_bbva_finv(PDF,'382'))
        self.assertFalse(is_bbva_finv(PDF,'399'))
        self.assertEqual(fecha_archivo(PDF),'2026-10-09')
        self.assertEqual(choose([PDF],code='382'),PDF)
    def test_https_host(self):
        self.assertFalse(is_bbva_finv('https://bbvaamdocs.bbva.com.malicioso.com/documents/BBVA/382_FINV_20261009_PER_SPA_0.pdf'))
        self.assertFalse(_controlled_visor_url('https://producto.bbvaassetmanagement.com.malicioso.com/pe/index.html'))
    def test_manual_registrar_y_preservar(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            c=root/'fondos.json'
            c.write_text(json.dumps([{'id':'bbva_fdf_distributivo','saf':'BBVA','nombre':'BBVA Distributivo','fuente':'https://fondos.bbva.pe/a', 'codigo_bbva':'382'}]),encoding='utf8')
            data=root/'data'
            record=save_entry(c,data,'bbva_fdf_distributivo',PDF,'2026-09')
            self.assertEqual(record['periodo'],'2026-09')
            self.assertEqual(record['estado'],'CAPTURA_MANUAL_SIN_REVALIDAR')
            self.assertTrue((data/'factsheets_links.csv').exists())
            data_json=json.loads((data/'factsheets_links.json').read_text(encoding='utf8'))
            self.assertEqual(data_json['fondos'][0]['url_pdf'],PDF)
            with self.assertRaises(ValueError):
                save_entry(c,data,'bbva_fdf_distributivo','https://evil.org/382_FINV_20261009_PER_SPA_0.pdf','2026-09')
            with self.assertRaises(ValueError):
                save_entry(c,data,'bbva_fdf_distributivo',PDF,'2026-08')
    def test_unknown_id(self):
        with TemporaryDirectory() as tmp:
            c=Path(tmp)/'fondos.json'
            c.write_text('[]',encoding='utf8')
            with self.assertRaises(ValueError):
                save_entry(c,Path(tmp)/'data','no_existe',PDF,'2026-09')

if __name__ == '__main__':unittest.main()
