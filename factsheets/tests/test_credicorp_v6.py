import unittest
from unittest.mock import patch
import actualizar_links as al
from credicorp_resolver import is_credicorp_peru

FUND = dict(id='cc_conservador_corto_usd', saf='Credicorp',
            nombre='CC Conservador Corto Plazo Dólares',
            fuente='https://www.credicorpcapital.com/Peru/Fondos/FonMut/Loc/Paginas/CPD.aspx?t=3')
OLD = dict(url_pdf='https://www.credicorpcapital.com/Peru/Fondos/FonMut/Loc/Fondos/Hojas_Informativas_Agosto_2026-Conservador_Corto_Plazo_Dolares.pdf',
           periodo='2026-08', metodo_fecha='NOMBRE_ARCHIVO', tipo_documento='hoja_informativa')
NEW = '<html><body><div>Documentos referentes al Fondo</div><a class="docm" href="/Peru/Fondos/FonMut/Loc/Fondos/Hojas_Informativas_Setiembre_2026-Conservador_Corto_Plazo_Dolares.pdf">Hoja Informativa</a></body></html>'
AUG = NEW.replace('Setiembre_2026','Agosto_2026')

class TestCredicorpV6(unittest.TestCase):
    def test_no_permite_fondo_chile(self):
        self.assertTrue(is_credicorp_peru(FUND['fuente']))
        self.assertFalse(is_credicorp_peru('https://www.credicorpcapital.com/Chile/Neg/GestAct/p.pdf'))

    @patch('actualizar_links.fetch_credicorp_browser',return_value=(NEW,'html navegador'))
    def test_requests_403_navegador_recupera_septiembre(self,web):
        def fail(_): raise RuntimeError('403 Forbidden')
        row=al.build(FUND,fail,None,old=OLD,verify=False,carpeta_diagnostico=None)
        self.assertEqual(row['periodo'],'2026-09')
        self.assertIn('Setiembre_2026',row['url_pdf'])
        self.assertEqual(row['estado'],'ENLACE_DETECTADO_SIN_VALIDAR')
        self.assertIn('consulta_html_fallo',row['detalle'])
        web.assert_called_once()

    @patch('actualizar_links.last_month', return_value='2026-09')
    @patch('actualizar_links.fetch_credicorp_browser',return_value=(NEW,'html navegador'))
    def test_cuando_html_antiguo_vuelve_buscar(self,web,_period):
        row=al.build(FUND,lambda _: AUG,None,old=OLD,verify=False)
        self.assertEqual(row['periodo'],'2026-09')
        web.assert_called_once()

    @patch('actualizar_links.fetch_credicorp_browser',side_effect=RuntimeError('navegador no disponible'))
    def test_enlace_antiguo_solo_retenido_como_respaldo(self,web):
        row=al.build(FUND,lambda _: '<html/>',None,old=OLD,verify=False)
        self.assertEqual(row['estado'],'ENLACE_ANTERIOR_SIN_REVALIDAR')
        self.assertEqual(row['periodo'],'2026-08')
        self.assertIn('navegador_fallo',row['detalle'])
        web.assert_called_once()

if __name__=='__main__': unittest.main()
