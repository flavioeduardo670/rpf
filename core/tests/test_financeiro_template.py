from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from core.models import AjusteMorador, ComprovantePagamentoMorador, ConfiguracaoFinanceira, Morador, PendenciaMensalItem


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

    def test_financeiro_exibe_campos_hidden_para_exclusao_de_ajustes_e_pendencias(self):
        response = self.client.get(reverse('financeiro') + '?mes=2026-05')
        self.assertEqual(response.status_code, 200)

        html = response.content.decode('utf-8')
        self.assertIn(f'name="ajuste-0-id" value="{self.ajuste.id}"', html)
        self.assertIn(f'name="pendencia-0-id" value="{self.pendencia.id}"', html)


    def test_financeiro_permite_salvar_ajuste_sem_motivo(self):
        response = self.client.post(
            reverse('financeiro'),
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
            reverse('financeiro'),
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
        response = self.client.get(reverse('financeiro') + '?mes=2026-05')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'input[name$="-DELETE"]')
        self.assertContains(response, 'input[name$="-id"]')
        self.assertContains(response, "ajusteTotalForms.value = ajusteBody.querySelectorAll('tr').length;")

    def test_financeiro_exibe_coluna_de_comprovante(self):
        response = self.client.get(reverse('financeiro') + '?mes=2026-05')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Comprovante')
        self.assertContains(response, 'name="comprovante"')
        self.assertContains(response, 'Status')

    def test_financeiro_marca_status_pago_quando_aluguel_zero(self):
        ConfiguracaoFinanceira.objects.create(valor_aluguel=Decimal('0.50'))
        response = self.client.get(reverse('financeiro') + '?mes=2026-05')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pago')

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
        response = self.client.get(reverse('financeiro') + '?mes=2026-05')
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
        self.assertIn(reverse('financeiro'), response.url)
