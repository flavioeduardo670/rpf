import json
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import Group, User
from django.core import mail
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import CobrancaAluguel, ConfiguracaoFinanceira, Mensalidade, Morador
from core.services.aluguel import confirmar_pagamento_aluguel, verificar_pagamentos_pendentes
from core.services.pix_gateway import consultar_status_por_txid, criar_cobranca_pix_avulsa


def _resposta_json(dados):
    resposta = MagicMock()
    resposta.__enter__.return_value.read.return_value = json.dumps(dados).encode('utf-8')
    return resposta


class GatewayAluguelTests(SimpleTestCase):
    @override_settings(MERCADOPAGO_ACCESS_TOKEN='TEST-123')
    @patch('core.services.pix_gateway.request.urlopen')
    def test_cobranca_envia_validade_e_email_do_morador(self, urlopen):
        urlopen.return_value = _resposta_json({'id': 1, 'status': 'pending', 'point_of_interaction': {'transaction_data': {'qr_code': 'pix'}}})
        validade = timezone.make_aware(timezone.datetime(2026, 5, 10, 23, 59, 59))
        criar_cobranca_pix_avulsa(
            txid='RPFAL1', valor=Decimal('10.00'), chave_pix='', nome_pagador='M', categoria='Aluguel',
            payer_email='morador@example.com', data_expiracao=validade,
        )
        enviado = json.loads(urlopen.call_args.args[0].data)
        self.assertEqual(enviado['payer']['email'], 'morador@example.com')
        self.assertEqual(enviado['date_of_expiration'], '2026-05-10T23:59:59.000-03:00')

    @override_settings(MERCADOPAGO_ACCESS_TOKEN='TEST-123')
    @patch('core.services.pix_gateway.request.urlopen')
    def test_status_por_txid_prefere_pagamento_aprovado_ao_mais_recente(self, urlopen):
        urlopen.side_effect = [
            _resposta_json({'results': [
                {'id': 2, 'status': 'pending', 'date_created': '2026-05-08T10:00:00Z'},
                {'id': 1, 'status': 'approved', 'date_created': '2026-05-02T10:00:00Z'},
            ]}),
            _resposta_json({'id': 1, 'status': 'approved', 'external_reference': 'RPFAL1'}),
        ]
        resultado = consultar_status_por_txid('RPFAL1')
        self.assertEqual(resultado['status'], 'pago')
        self.assertEqual(resultado['payment_id'], '1')
        self.assertTrue(urlopen.call_args.args[0].full_url.endswith('/v1/payments/1'))


class ConfirmacaoPagamentoTests(TestCase):
    def setUp(self):
        self.morador = Morador.objects.create(nome='Ana', email='ana@example.com', ativo=True)
        self.cobranca = CobrancaAluguel.objects.create(
            morador=self.morador, mes_referencia=date(2026, 5, 1), valor=Decimal('800.00'),
            txid='RPFAL00000000000000000001', status='aguardando_pagamento',
        )

    def test_confirma_uma_vez_e_envia_um_recibo(self):
        self.assertTrue(confirmar_pagamento_aluguel(self.cobranca, payment_id='99'))
        self.assertFalse(confirmar_pagamento_aluguel(self.cobranca, payment_id='99'))
        self.cobranca.refresh_from_db()
        self.assertEqual(self.cobranca.status, 'pago')
        self.assertIsNotNone(self.cobranca.comprovante_enviado_em)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['ana@example.com'])
        self.assertTrue(Mensalidade.objects.get(morador=self.morador, mes_referencia=date(2026, 5, 1)).pago)

    def test_falha_no_email_fica_pendente_e_e_reenviada(self):
        with patch('core.views.financeiro.EmailMessage.send', side_effect=OSError('smtp fora')):
            confirmar_pagamento_aluguel(self.cobranca)
        self.cobranca.refresh_from_db()
        self.assertEqual(self.cobranca.status, 'pago')
        self.assertIsNone(self.cobranca.comprovante_enviado_em)
        self.assertEqual(len(mail.outbox), 0)

        resultado = verificar_pagamentos_pendentes()
        self.assertEqual(resultado['comprovantes_enviados'], 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(verificar_pagamentos_pendentes()['comprovantes_enviados'], 0)

    def test_morador_sem_email_recebe_quando_cadastrar(self):
        self.morador.email = ''
        self.morador.save()
        confirmar_pagamento_aluguel(self.cobranca)
        self.assertEqual(len(mail.outbox), 0)
        self.morador.email = 'ana@example.com'
        self.morador.save()
        verificar_pagamentos_pendentes()
        self.assertEqual(len(mail.outbox), 1)

    def test_nao_reenvia_recibo_de_pagamento_antigo(self):
        CobrancaAluguel.objects.filter(pk=self.cobranca.pk).update(status='pago', pago_em=timezone.now() - timedelta(days=90))
        verificar_pagamentos_pendentes()
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(MERCADOPAGO_ACCESS_TOKEN='TEST-123')
    @patch('core.services.aluguel.consultar_status_por_txid')
    def test_comando_confirma_pagamento_sem_webhook(self, consultar):
        consultar.return_value = {'txid': self.cobranca.txid, 'status': 'pago', 'payment_id': '555', 'provider_payload': {}}
        saida = StringIO()
        call_command('verificar_pagamentos_aluguel', stdout=saida)
        self.cobranca.refresh_from_db()
        self.assertEqual(self.cobranca.status, 'pago')
        self.assertEqual(self.cobranca.payment_id, '555')
        self.assertIn('Pagamentos confirmados: 1', saida.getvalue())
        self.assertEqual(len(mail.outbox), 1)


@override_settings(MERCADOPAGO_WEBHOOK_SECRET='')
class WebhookAluguelTests(TestCase):
    def setUp(self):
        self.morador = Morador.objects.create(nome='Bia', email='bia@example.com', ativo=True)
        self.cobranca = CobrancaAluguel.objects.create(
            morador=self.morador, mes_referencia=date(2026, 5, 1), valor=Decimal('800.00'),
            txid='RPFAL00000000000000000002', payment_id='777', status='aguardando_pagamento',
        )

    @override_settings(DEBUG=True)
    def test_webhook_repetido_envia_um_recibo(self):
        corpo = json.dumps({'txid': self.cobranca.txid, 'status': 'approved'})
        for _ in range(3):
            response = self.client.post(reverse('webhook_pix_financeiro'), data=corpo, content_type='application/json')
            self.assertEqual(response.status_code, 200)
        self.cobranca.refresh_from_db()
        self.assertEqual(self.cobranca.status, 'pago')
        self.assertIsNotNone(self.cobranca.webhook_recebido_em)
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(DEBUG=True, MERCADOPAGO_ACCESS_TOKEN='TEST-123')
    @patch('core.views.pix.consultar_evento_mercado_pago')
    def test_webhook_ipn_com_topic_na_url(self, consultar):
        consultar.return_value = {'txid': self.cobranca.txid, 'payment_id': '777', 'status': 'pago', 'provider_payload': {}}
        response = self.client.post(f"{reverse('webhook_pix_financeiro')}?topic=payment&id=777", data='{}', content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(consultar.call_args.args[:2], ('777', 'payment'))
        self.cobranca.refresh_from_db()
        self.assertEqual(self.cobranca.status, 'pago')


class BoletoAluguelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='fin_boleto', password='123456')
        self.user.groups.add(Group.objects.get_or_create(name='Financeiro')[0])
        self.client.force_login(self.user)
        self.morador = Morador.objects.create(nome='Caio', email='caio@example.com', ativo=True)
        ConfiguracaoFinanceira.objects.create(valor_aluguel=Decimal('500.00'), conta_recebimentos_pix='15998509135')
        self.url = reverse('exportar_boleto_aluguel_morador_pdf', args=[self.morador.id]) + '?mes=2026-05'

    def test_boleto_de_cobranca_paga_devolve_recibo(self):
        CobrancaAluguel.objects.create(
            morador=self.morador, mes_referencia=date(2026, 5, 1), valor=Decimal('500.00'),
            txid='RPFAL00000000000000000003', status='pago', pago_em=timezone.now(),
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('comprovante_aluguel_caio_2026_05.pdf', response['Content-Disposition'])
        self.assertIn(b'Comprovante de Pagamento', response.content)

    @override_settings(MERCADOPAGO_ACCESS_TOKEN='TEST-123')
    @patch('core.views.financeiro.cancelar_pagamento_mercado_pago')
    @patch('core.views.financeiro.criar_cobranca_pix_avulsa')
    @patch('core.services.aluguel.consultar_status_por_txid')
    def test_pix_expirado_e_regerado_e_o_antigo_cancelado(self, consultar, criar, cancelar):
        CobrancaAluguel.objects.create(
            morador=self.morador, mes_referencia=date(2026, 5, 1), valor=Decimal('500.00'),
            txid='RPFAL00000000000000000004', payment_id='111', qr_code='pix-velho', payload_pix='pix-velho',
            status='aguardando_pagamento', status_gateway='pending',
            provider_payload={'date_of_expiration': (timezone.now() - timedelta(days=1)).isoformat()},
        )
        consultar.return_value = {'status': 'pending', 'provider_payload': {}}
        criar.return_value = {
            'txid': 'RPFAL00000000000000000004', 'payment_id': '222', 'payload_pix': 'pix-novo', 'qr_code': 'pix-novo',
            'qr_code_base64': '', 'ticket_url': '', 'status_gateway': 'pending', 'provider_payload': {'id': 222},
        }
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        criar.assert_called_once()
        self.assertEqual(criar.call_args.kwargs['payer_email'], 'caio@example.com')
        self.assertIsNotNone(criar.call_args.kwargs['data_expiracao'])
        cancelar.assert_called_once_with('111')
        cobranca = CobrancaAluguel.objects.get(morador=self.morador)
        self.assertEqual((cobranca.payment_id, cobranca.qr_code), ('222', 'pix-novo'))

    @override_settings(MERCADOPAGO_ACCESS_TOKEN='TEST-123')
    @patch('core.views.financeiro.criar_cobranca_pix_avulsa')
    @patch('core.services.aluguel.consultar_status_por_txid')
    def test_gerar_boleto_detecta_pagamento_que_o_webhook_perdeu(self, consultar, criar):
        CobrancaAluguel.objects.create(
            morador=self.morador, mes_referencia=date(2026, 5, 1), valor=Decimal('500.00'),
            txid='RPFAL00000000000000000005', payment_id='333', qr_code='pix', payload_pix='pix',
            status='aguardando_pagamento', status_gateway='pending',
        )
        consultar.return_value = {'status': 'pago', 'payment_id': '333', 'provider_payload': {}}
        response = self.client.get(self.url)
        criar.assert_not_called()
        self.assertIn('comprovante_aluguel_', response['Content-Disposition'])
        self.assertEqual(len(mail.outbox), 1)
