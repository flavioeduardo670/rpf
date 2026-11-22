import base64
import hashlib
import hmac
import json
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO, StringIO
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

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

    def test_reenvio_para_na_primeira_falha_e_respeita_limite(self):
        outros = []
        for i in range(3):
            m = Morador.objects.create(nome=f'M{i}', email=f'm{i}@example.com', ativo=True)
            outros.append(CobrancaAluguel.objects.create(
                morador=m, mes_referencia=date(2026, 5, 1), valor=Decimal('1.00'), txid=f'RPFALX{i}',
                status='pago', pago_em=timezone.now(),
            ))
        CobrancaAluguel.objects.filter(pk=self.cobranca.pk).update(status='pago', pago_em=timezone.now())
        with patch('core.views.financeiro.EmailMessage.send', side_effect=TimeoutError('smtp bloqueado')) as send:
            verificar_pagamentos_pendentes()
        self.assertEqual(send.call_count, 1)

        self.assertEqual(verificar_pagamentos_pendentes(limite_recibos=2)['comprovantes_enviados'], 2)
        self.assertEqual(verificar_pagamentos_pendentes()['comprovantes_enviados'], 2)

    def test_email_tem_timeout(self):
        from django.conf import settings
        self.assertGreater(settings.EMAIL_TIMEOUT, 0)

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

    @override_settings(MERCADOPAGO_ACCESS_TOKEN='APP_USR-de-usuario-de-teste')
    @patch('core.services.pix_gateway.request.urlopen')
    def test_token_de_usuario_de_teste_gera_pix_local_com_motivo(self, urlopen):
        # Situação real de produção: o Mercado Pago recusa o token com 401 e o
        # boleto sai com a chave da casa, que nunca é confirmada sozinha.
        corpo = json.dumps({'cause': [{'code': 7, 'description': 'Unauthorized use of live credentials'}], 'status': 401}).encode('utf-8')
        urlopen.side_effect = HTTPError('https://api.mercadopago.com/v1/payments', 401, 'Unauthorized', {}, BytesIO(corpo))
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        cobranca = CobrancaAluguel.objects.get(morador=self.morador)
        self.assertEqual(cobranca.status_gateway, 'erro_autorizacao_fallback_local')
        self.assertEqual(cobranca.provider_payload['detalhe'], 'Unauthorized use of live credentials')

        pagina = self.client.get(reverse('financeiro_aluguel') + '?mes=2026-05')
        self.assertContains(pagina, 'Unauthorized use of live credentials')
        self.assertContains(pagina, 'usuário de teste')
        self.assertContains(pagina, reverse('confirmar_pagamento_aluguel_morador', args=[self.morador.id]))

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


class ConfirmacaoManualTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='fin_manual', password='123456')
        self.user.groups.add(Group.objects.get_or_create(name='Financeiro')[0])
        self.client.force_login(self.user)
        self.morador = Morador.objects.create(nome='Duda', email='duda@example.com', ativo=True)
        ConfiguracaoFinanceira.objects.create(valor_aluguel=Decimal('500.00'), conta_recebimentos_pix='15998509135')
        self.url = reverse('confirmar_pagamento_aluguel_morador', args=[self.morador.id])

    def test_confirma_pix_local_quita_mensalidade_e_envia_recibo(self):
        cobranca = CobrancaAluguel.objects.create(
            morador=self.morador, mes_referencia=date(2026, 5, 1), valor=Decimal('500.00'),
            txid='RPFAL00000000000000000010', status='aguardando_pagamento',
            status_gateway='erro_autorizacao_fallback_local', provider_payload={'modo': 'local'},
        )
        response = self.client.post(self.url, {'mes_referencia': '2026-05'})
        self.assertRedirects(response, reverse('financeiro_aluguel') + '?mes=2026-05', fetch_redirect_response=False)
        cobranca.refresh_from_db()
        self.assertEqual((cobranca.status, cobranca.status_gateway), ('pago', 'confirmado_manual'))
        self.assertEqual(cobranca.provider_payload['confirmacao_manual']['usuario'], 'fin_manual')
        self.assertIsNotNone(cobranca.comprovante_enviado_em)
        self.assertTrue(Mensalidade.objects.get(morador=self.morador, mes_referencia=date(2026, 5, 1)).pago)
        self.assertEqual(mail.outbox[0].to, ['duda@example.com'])

        # Clicar de novo não duplica recibo.
        self.client.post(self.url, {'mes_referencia': '2026-05'})
        self.assertEqual(len(mail.outbox), 1)

        pagina = self.client.get(reverse('financeiro_aluguel') + '?mes=2026-05')
        self.assertNotContains(pagina, self.url)

    def test_cria_cobranca_quando_boleto_nao_foi_gerado(self):
        self.client.post(self.url, {'mes_referencia': '2026-05'})
        cobranca = CobrancaAluguel.objects.get(morador=self.morador, mes_referencia=date(2026, 5, 1))
        self.assertEqual(cobranca.status, 'pago')
        self.assertTrue(cobranca.txid.startswith('RPFAL'))
        self.assertGreater(cobranca.valor, Decimal('0.00'))

    @override_settings(MERCADOPAGO_ACCESS_TOKEN='TEST-123')
    @patch('core.services.aluguel.cancelar_pagamento_mercado_pago')
    @patch('core.services.aluguel.consultar_status_por_txid')
    def test_cancela_pix_pendente_no_mercado_pago(self, consultar, cancelar):
        CobrancaAluguel.objects.create(
            morador=self.morador, mes_referencia=date(2026, 5, 1), valor=Decimal('500.00'),
            txid='RPFAL00000000000000000011', payment_id='444', status='aguardando_pagamento', status_gateway='pending',
        )
        consultar.return_value = {'status': 'pending', 'provider_payload': {}}
        self.client.post(self.url, {'mes_referencia': '2026-05'})
        cancelar.assert_called_once_with('444')
        self.assertEqual(CobrancaAluguel.objects.get(payment_id='444').status, 'pago')

    @override_settings(MERCADOPAGO_ACCESS_TOKEN='TEST-123')
    @patch('core.services.aluguel.cancelar_pagamento_mercado_pago')
    @patch('core.services.aluguel.consultar_status_por_txid')
    def test_usa_pagamento_real_se_o_mercado_pago_ja_aprovou(self, consultar, cancelar):
        CobrancaAluguel.objects.create(
            morador=self.morador, mes_referencia=date(2026, 5, 1), valor=Decimal('500.00'),
            txid='RPFAL00000000000000000012', payment_id='445', status='aguardando_pagamento', status_gateway='pending',
        )
        consultar.return_value = {'status': 'pago', 'payment_id': '445', 'provider_payload': {'id': 445}}
        self.client.post(self.url, {'mes_referencia': '2026-05'})
        cancelar.assert_not_called()
        self.assertEqual(CobrancaAluguel.objects.get(payment_id='445').status_gateway, 'pago')

    def test_quem_nao_e_do_financeiro_nao_confirma(self):
        outro = User.objects.create_user(username='curioso', password='123456')
        self.client.force_login(outro)
        self.client.post(self.url, {'mes_referencia': '2026-05'})
        self.assertFalse(CobrancaAluguel.objects.filter(morador=self.morador, status='pago').exists())

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend', EMAIL_HOST='localhost')
    def test_avisa_quando_email_nao_esta_configurado(self):
        pagina = self.client.get(reverse('financeiro_aluguel') + '?mes=2026-05')
        self.assertContains(pagina, 'Email não configurado')


@override_settings(
    EMAIL_BACKEND='core.email_backends.BrevoEmailBackend', BREVO_API_KEY='xkeysib-teste',
    DEFAULT_FROM_EMAIL='República RPF <rpf@example.com>',
)
class BrevoEmailBackendTests(TestCase):
    @patch('core.email_backends.request.urlopen')
    def test_recibo_sai_pela_api_https_com_anexo(self, urlopen):
        urlopen.return_value = _resposta_json({'messageId': '<1@brevo>'})
        morador = Morador.objects.create(nome='Gil', email='gil@example.com', ativo=True)
        cobranca = CobrancaAluguel.objects.create(
            morador=morador, mes_referencia=date(2026, 5, 1), valor=Decimal('800.00'),
            txid='RPFAL00000000000000000030', status='aguardando_pagamento',
        )
        confirmar_pagamento_aluguel(cobranca)
        cobranca.refresh_from_db()
        self.assertIsNotNone(cobranca.comprovante_enviado_em)

        req = urlopen.call_args.args[0]
        self.assertEqual(req.full_url, 'https://api.brevo.com/v3/smtp/email')
        self.assertEqual(req.get_header('Api-key'), 'xkeysib-teste')
        self.assertEqual(urlopen.call_args.kwargs['timeout'], 10)
        enviado = json.loads(req.data)
        self.assertEqual(enviado['sender'], {'email': 'rpf@example.com', 'name': 'República RPF'})
        self.assertEqual(enviado['to'], [{'email': 'gil@example.com'}])
        self.assertTrue(enviado['attachment'][0]['name'].endswith('.pdf'))
        self.assertTrue(base64.b64decode(enviado['attachment'][0]['content']).startswith(b'%PDF'))

    @patch('core.email_backends.request.urlopen')
    def test_erro_da_api_deixa_recibo_pendente(self, urlopen):
        urlopen.side_effect = HTTPError(BREVO_URL, 401, 'Unauthorized', {}, BytesIO(b'{"message":"Key not found"}'))
        morador = Morador.objects.create(nome='Hil', email='hil@example.com', ativo=True)
        cobranca = CobrancaAluguel.objects.create(
            morador=morador, mes_referencia=date(2026, 5, 1), valor=Decimal('800.00'),
            txid='RPFAL00000000000000000031', status='aguardando_pagamento',
        )
        confirmar_pagamento_aluguel(cobranca)
        cobranca.refresh_from_db()
        self.assertEqual(cobranca.status, 'pago')
        self.assertIsNone(cobranca.comprovante_enviado_em)


BREVO_URL = 'https://api.brevo.com/v3/smtp/email'


@override_settings(DEBUG=False, MERCADOPAGO_WEBHOOK_SECRET='segredo-webhook', MERCADOPAGO_ACCESS_TOKEN='TEST-123')
class WebhookSemAssinaturaTests(TestCase):
    def setUp(self):
        self.morador = Morador.objects.create(nome='Eva', email='eva@example.com', ativo=True)
        self.cobranca = CobrancaAluguel.objects.create(
            morador=self.morador, mes_referencia=date(2026, 5, 1), valor=Decimal('800.00'),
            txid='RPFAL00000000000000000020', payment_id='900', status='aguardando_pagamento',
        )

    @patch('core.views.pix.consultar_evento_mercado_pago')
    def test_ipn_sem_assinatura_e_conferido_na_api(self, consultar):
        consultar.return_value = {'txid': self.cobranca.txid, 'payment_id': '900', 'status': 'pago', 'provider_payload': {'id': 900}}
        response = self.client.post(f"{reverse('webhook_pix_financeiro')}?topic=payment&id=900", data='{}', content_type='application/json', secure=True)
        self.assertEqual(response.status_code, 200)
        self.cobranca.refresh_from_db()
        self.assertEqual(self.cobranca.status, 'pago')

    @patch('core.views.pix.consultar_evento_mercado_pago')
    def test_corpo_sem_assinatura_nao_vale_mais_que_a_api(self, consultar):
        consultar.return_value = {'txid': self.cobranca.txid, 'payment_id': '900', 'status': 'pending', 'provider_payload': {}}
        corpo = json.dumps({'type': 'payment', 'data': {'id': '900'}, 'status': 'approved', 'txid': self.cobranca.txid})
        response = self.client.post(reverse('webhook_pix_financeiro'), data=corpo, content_type='application/json',
                                    HTTP_X_SIGNATURE='ts=1,v1=falsa', HTTP_X_REQUEST_ID='r', secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(consultar.call_args.args[2], {})
        self.cobranca.refresh_from_db()
        self.assertEqual(self.cobranca.status, 'aguardando_pagamento')

    def test_sem_assinatura_e_sem_id_continua_recusado(self):
        corpo = json.dumps({'txid': self.cobranca.txid, 'status': 'approved'})
        response = self.client.post(reverse('webhook_pix_financeiro'), data=corpo, content_type='application/json', secure=True)
        self.assertEqual(response.status_code, 400)

    @patch('core.views.pix.consultar_evento_mercado_pago')
    def test_assinatura_valida_continua_funcionando(self, consultar):
        consultar.return_value = {'txid': self.cobranca.txid, 'payment_id': '900', 'status': 'pago', 'provider_payload': {}}
        manifest = 'id:900;request-id:req-1;ts:1700000000;'
        v1 = hmac.new(b'segredo-webhook', manifest.encode(), hashlib.sha256).hexdigest()
        response = self.client.post(
            f"{reverse('webhook_pix_financeiro')}?data.id=900&type=payment",
            data=json.dumps({'type': 'payment', 'data': {'id': '900'}}), content_type='application/json',
            HTTP_X_SIGNATURE=f'ts=1700000000,v1={v1}', HTTP_X_REQUEST_ID='req-1', secure=True,
        )
        self.assertEqual(response.status_code, 200)
        self.cobranca.refresh_from_db()
        self.assertEqual(self.cobranca.status, 'pago')
