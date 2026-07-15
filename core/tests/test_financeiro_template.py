from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from core.models import AjusteMorador, CobrancaAluguel, ComprovantePagamentoMorador, ConfiguracaoFinanceira, Morador, PendenciaMensalItem


class FinanceiroTemplateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='financeiro_template', password='123456')
        financeiro_group, _ = Group.objects.get_or_create(name='Financeiro')
        self.user.groups.add(financeiro_group)
        self.client.force_login(self.user)

        self.mes = date(2026, 5, 1)
        self.morador = Morador.objects.create(nome='Morador Teste', ativo=True)

        self.ajuste = AjusteMorador.objects.create(
            morador=self.morador,
            mes_referencia=self.mes,
            tipo='extra',
            valor=Decimal('123.45'),
            motivo='Extra de teste',
        )
        self.pendencia = PendenciaMensalItem.objects.create(
            mes_referencia=self.mes,
            tipo='extra',
            valor=Decimal('54.32'),
            motivo='Pendência de teste',
        )

    def test_financeiro_home_exibe_submodulos(self):
        response = self.client.get(reverse('financeiro'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Financeiro')
        self.assertContains(response, 'Aluguel')
        self.assertContains(response, reverse('financeiro_aluguel'))

    def test_financeiro_exibe_campos_hidden_para_exclusao_de_ajustes_e_pendencias(self):
        response = self.client.get(reverse('financeiro_aluguel') + '?mes=2026-05')
        self.assertEqual(response.status_code, 200)

        html = response.content.decode('utf-8')
        self.assertIn(f'name="ajuste-0-id" value="{self.ajuste.id}"', html)
        self.assertIn(f'name="pendencia-0-id" value="{self.pendencia.id}"', html)


    def test_financeiro_exclui_ajuste_por_botao_dedicado(self):
        response = self.client.post(
            reverse('financeiro_aluguel'),
            data={
                'mes_referencia': '2026-05-01',
                'delete_ajuste_id': str(self.ajuste.id),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(AjusteMorador.objects.filter(id=self.ajuste.id).exists())

    def test_financeiro_permite_salvar_ajuste_sem_motivo(self):
        response = self.client.post(
            reverse('financeiro_aluguel'),
            data={
                'mes_referencia': '2026-05-01',
                'ajuste_submit': '1',
                'ajuste-TOTAL_FORMS': '1',
                'ajuste-INITIAL_FORMS': '1',
                'ajuste-MIN_NUM_FORMS': '0',
                'ajuste-MAX_NUM_FORMS': '1000',
                'ajuste-0-id': str(self.ajuste.id),
                'ajuste-0-morador': str(self.morador.id),
                'ajuste-0-tipo': 'extra',
                'ajuste-0-valor': '123.45',
                'ajuste-0-motivo': '',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.ajuste.refresh_from_db()
        self.assertEqual(self.ajuste.motivo, '')

    def test_financeiro_permite_salvar_pendencia_sem_motivo(self):
        response = self.client.post(
            reverse('financeiro_aluguel'),
            data={
                'mes_referencia': '2026-05-01',
                'pendencia_submit': '1',
                'pendencia-TOTAL_FORMS': '1',
                'pendencia-INITIAL_FORMS': '1',
                'pendencia-MIN_NUM_FORMS': '0',
                'pendencia-MAX_NUM_FORMS': '1000',
                'pendencia-0-id': str(self.pendencia.id),
                'pendencia-0-tipo': 'extra',
                'pendencia-0-valor': '54.32',
                'pendencia-0-motivo': '',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.pendencia.refresh_from_db()
        self.assertEqual(self.pendencia.motivo, '')

    def test_financeiro_template_configura_exclusao_de_ajuste_para_itens_novos_e_existentes(self):
        response = self.client.get(reverse('financeiro_aluguel') + '?mes=2026-05')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'input[name$="-DELETE"]')
        self.assertContains(response, 'input[name$="-id"]')
        self.assertContains(response, 'name="delete_ajuste_id"')
        self.assertContains(response, "ajusteTotalForms.value = ajusteBody.querySelectorAll('tr').length;")

    def test_financeiro_exibe_coluna_de_comprovante(self):
        response = self.client.get(reverse('financeiro_aluguel') + '?mes=2026-05')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Comprovante')
        self.assertContains(response, 'name="comprovante"')
        self.assertContains(response, 'Status')

    def test_financeiro_marca_status_pago_quando_aluguel_zero(self):
        ConfiguracaoFinanceira.objects.create(valor_aluguel=Decimal('0.50'))
        response = self.client.get(reverse('financeiro_aluguel') + '?mes=2026-05')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pago')

    def test_financeiro_marca_status_pago_quando_cobranca_pix_paga(self):
        CobrancaAluguel.objects.create(
            morador=self.morador,
            mes_referencia=self.mes,
            valor=Decimal('123.45'),
            txid='RPFAL0000000000000001',
            status='pago',
        )
        response = self.client.get(reverse('financeiro_aluguel') + '?mes=2026-05')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pago')

    def test_extrato_morador_exibe_botao_pdf(self):
        response = self.client.get(reverse('financeiro_prestacao_contas_morador', args=[self.morador.id]) + '?mes=2026-05')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Gerar PDF')
        self.assertContains(response, 'Gerar boleto de aluguel')
        self.assertContains(response, reverse('exportar_extrato_morador_pdf', args=[self.morador.id]))
        self.assertContains(response, reverse('exportar_boleto_aluguel_morador_pdf', args=[self.morador.id]))

    def test_exportar_extrato_morador_pdf(self):
        response = self.client.get(reverse('exportar_extrato_morador_pdf', args=[self.morador.id]) + '?mes=2026-05')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('extrato_pessoal_morador-teste_2026_05.pdf', response['Content-Disposition'])
        self.assertTrue(response.content.startswith(b'%PDF-1.4'))
        self.assertIn(b'Extrato pessoal', response.content)
        self.assertIn(b'Data', response.content)
        self.assertIn('Descrição'.encode('cp1252'), response.content)
        self.assertIn('Pendência'.encode('cp1252'), response.content)
        self.assertIn(b'Detalhamento por categoria', response.content)
        self.assertIn('R$ 123,45'.encode('cp1252'), response.content)
        self.assertNotIn(b'!', response.content)


    def test_exportar_boleto_aluguel_morador_pdf_cria_cobranca_pix(self):
        ConfiguracaoFinanceira.objects.create(
            valor_aluguel=Decimal('1000.00'),
            conta_recebimentos_pix='15998509135',
        )
        response = self.client.get(reverse('exportar_boleto_aluguel_morador_pdf', args=[self.morador.id]) + '?mes=2026-05')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('boleto_aluguel_morador-teste_2026_05.pdf', response['Content-Disposition'])
        self.assertTrue(response.content.startswith(b'%PDF-1.4'))
        self.assertIn('Boleto PIX'.encode('cp1252'), response.content)
        self.assertIn(b'Aluguel', response.content)
        self.assertIn(b'PIX copia e cola', response.content)
        self.assertIn('Tipo de cobrança: Aluguel'.encode('cp1252'), response.content)
        self.assertIn(b'Chave PIX: +5515998509135', response.content)
        self.assertIn(b'Vencimento: 10/05/2026', response.content)
        self.assertNotIn(b'Vencimento sugerido', response.content)
        self.assertNotIn(b'Status no ERP', response.content)
        cobranca = CobrancaAluguel.objects.get(morador=self.morador, mes_referencia=self.mes)
        self.assertEqual(cobranca.valor, Decimal('123.45'))
        self.assertTrue(cobranca.txid.startswith('RPFAL'))
        self.assertLessEqual(len(cobranca.txid), 25)
        self.assertIn('br.gov.bcb.pix', cobranca.payload_pix)
        self.assertIn('+5515998509135', cobranca.payload_pix)

    def test_anexar_comprovante_pagamento(self):
        arquivo = SimpleUploadedFile('comprovante.pdf', b'%PDF-1.4 teste', content_type='application/pdf')
        response = self.client.post(
            reverse('anexar_comprovante_pagamento', args=[self.morador.id]),
            data={
                'mes': '2026-05',
                'comprovante': arquivo,
            },
        )
        self.assertEqual(response.status_code, 302)
        comprovante = ComprovantePagamentoMorador.objects.get(morador=self.morador, mes_referencia=self.mes)
        self.assertTrue(comprovante.arquivo.name.endswith('.pdf'))

    def test_financeiro_marca_status_pago_quando_tem_comprovante(self):
        ComprovantePagamentoMorador.objects.create(
            morador=self.morador,
            mes_referencia=self.mes,
            arquivo=SimpleUploadedFile('anexo.pdf', b'pdf', content_type='application/pdf'),
        )
        response = self.client.get(reverse('financeiro_aluguel') + '?mes=2026-05')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pago')

    def test_ver_comprovante_pagamento_retorna_arquivo(self):
        comprovante = ComprovantePagamentoMorador.objects.create(
            morador=self.morador,
            mes_referencia=self.mes,
            arquivo=SimpleUploadedFile('anexo.pdf', b'pdf', content_type='application/pdf'),
        )
        response = self.client.get(reverse('ver_comprovante_pagamento', args=[comprovante.id]))
        self.assertEqual(response.status_code, 200)

    def test_ver_comprovante_pagamento_redireciona_quando_arquivo_sumiu(self):
        comprovante = ComprovantePagamentoMorador.objects.create(
            morador=self.morador,
            mes_referencia=self.mes,
            arquivo=SimpleUploadedFile('anexo.pdf', b'pdf', content_type='application/pdf'),
        )
        with patch.object(comprovante.arquivo.storage, 'exists', return_value=False):
            response = self.client.get(reverse('ver_comprovante_pagamento', args=[comprovante.id]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('financeiro_aluguel'), response.url)
