from django.test import SimpleTestCase
from django.urls import resolve, reverse


class FinanceiroPrestacaoUrlsTests(SimpleTestCase):
    def test_resolve_prestacao_contas_url(self):
        match = resolve('/financeiro/prestacao-contas/')
        self.assertEqual(match.view_name, 'financeiro_prestacao_contas')

    def test_resolve_prestacao_contas_morador_url(self):
        match = resolve('/financeiro/prestacao-contas/morador/1/')
        self.assertEqual(match.view_name, 'financeiro_prestacao_contas_morador')

    def test_resolve_exportar_rateio_prestacao_contas_pdf_url(self):
        match = resolve('/financeiro/prestacao-contas/rateio.pdf')
        self.assertEqual(match.view_name, 'exportar_rateio_prestacao_contas_pdf')

    def test_reverse_urls(self):
        self.assertEqual(reverse('financeiro_prestacao_contas'), '/financeiro/prestacao-contas/')
        self.assertEqual(reverse('exportar_rateio_prestacao_contas_pdf'), '/financeiro/prestacao-contas/rateio.pdf')
        self.assertEqual(
            reverse('financeiro_prestacao_contas_morador', kwargs={'morador_id': 7}),
            '/financeiro/prestacao-contas/morador/7/',
        )
