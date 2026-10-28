import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from actualizar_links import period_from_url,extract_candidates,find_official_bbva_ficha, trusted

class TestLinks(unittest.TestCase):
    def test_fecha_blum_setiembre(self):
        self.assertEqual(period_from_url('https://cdn.prod.website-files.com/a/BMM%20-%20Set%202026.pdf'),'2026-09')
    def test_fecha_credicorp_agosto(self):
        self.assertEqual(period_from_url('https://www.credicorpcapital.com/Peru/Hojas_Informativas_Agosto_2026-CC.pdf'),'2026-08')
    def test_descartar_prospecto(self):
        h='<a href="a.pdf">Prospecto Simplificado</a><a href="b.pdf">Hoja Informativa</a>'
        c=extract_candidates(h,'https://www.credicorpcapital.com/Peru/test.html')
        self.assertEqual(len(c),1)
        self.assertTrue(c[0].url.endswith('b.pdf'))
    def test_bbva_seleccion_conservadora(self):
        h='<a href="https://producto.bbvaassetmanagement.com/pe/index.html#!/123">Ver fondo BBVA Renta Corto Plazo Soles FMIV</a>'
        self.assertIn('123',find_official_bbva_ficha(h,'https://fondos.bbva.pe/', 'Ver fondo BBVA Renta Corto Plazo Soles FMIV'))
    def test_ssrf(self):
        self.assertFalse(trusted('https://www.credicorpcapital.com.malicioso.com/f.pdf'))

if __name__=='__main__': unittest.main()
