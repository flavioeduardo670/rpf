from django.test import SimpleTestCase
from django.urls import resolve, reverse


class FinanceiroPrestacaoUrlsTests(SimpleTestCase):
    def test_resolve_prestacao_contas_url(self):
        match = resolve('/financeiro/prestacao-contas/')
        self.assertEqual(match.view_name, 'financeiro_prestacao_contas')

    def test_resolve_prestacao_contas_morador_url(self):
        match = resolve('/financeiro/prestacao-contas/morador/1/')
        self.assertEqual(match.view_name, 'financeiro_prestacao_contas_morador')

    def test_resolve_registros_mensais_url(self):
        match = resolve('/financeiro/registros/')
        self.assertEqual(match.view_name, 'financeiro_registros_mensais')

    def test_resolve_salvar_registro_url(self):
        match = resolve('/financeiro/registros/salvar/')
        self.assertEqual(match.view_name, 'salvar_registro_financeiro')

    def test_reverse_urls(self):
        self.assertEqual(reverse('financeiro_prestacao_contas'), '/financeiro/prestacao-contas/')
        self.assertEqual(
            reverse('financeiro_prestacao_contas_morador', kwargs={'morador_id': 7}),
            '/financeiro/prestacao-contas/morador/7/',
        )
        self.assertEqual(
            reverse('exportar_boleto_aluguel_morador_pdf', kwargs={'morador_id': 7}),
            '/financeiro/prestacao-contas/morador/7/boleto/',
        )
        self.assertEqual(reverse('financeiro_registros_mensais'), '/financeiro/registros/')
        self.assertEqual(reverse('salvar_registro_financeiro'), '/financeiro/registros/salvar/')
        self.assertEqual(reverse('webhook_pix_financeiro'), '/financeiro/pix/webhook/')
