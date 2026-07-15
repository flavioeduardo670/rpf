import json
from decimal import Decimal
from urllib import error
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from core.services.pix_gateway import criar_cobranca_pix_avulsa, consultar_evento_mercado_pago, consultar_pagamento_mercado_pago, consultar_status_por_txid, validar_assinatura_webhook


class PixGatewayMercadoPagoTests(SimpleTestCase):
    @override_settings(MERCADOPAGO_ACCESS_TOKEN='TEST-123')
    @patch('core.services.pix_gateway.request.urlopen')
    def test_criar_cobranca_pix_avulsa_usa_mercado_pago(self, urlopen):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({
            'id': 123456,
            'status': 'pending',
            'external_reference': 'RPFAL0001',
            'point_of_interaction': {
                'transaction_data': {
                    'qr_code': '000201br.gov.bcb.pix',
                    'qr_code_base64': 'QUJD',
                    'ticket_url': 'https://www.mercadopago.com.br/payments/123456/ticket',
                },
            },
        }).encode('utf-8')
        urlopen.return_value = response

        resultado = criar_cobranca_pix_avulsa(
            txid='RPFAL0001',
            valor=Decimal('123.45'),
            chave_pix='',
            nome_pagador='Morador Teste',
            categoria='Aluguel',
        )

        self.assertEqual(resultado['payment_id'], '123456')
        self.assertEqual(resultado['payload_pix'], '000201br.gov.bcb.pix')
        self.assertEqual(resultado['qr_code_base64'], 'QUJD')
        self.assertEqual(resultado['ticket_url'], 'https://www.mercadopago.com.br/payments/123456/ticket')
        self.assertEqual(resultado['status_gateway'], 'pending')
        req = urlopen.call_args.args[0]
        self.assertEqual(req.full_url, 'https://api.mercadopago.com/v1/payments')
        self.assertEqual(req.headers['Authorization'], 'Bearer TEST-123')



    @override_settings(MERCADOPAGO_ACCESS_TOKEN='Bearer TEST-123')
    @patch('core.services.pix_gateway.request.urlopen')
    def test_criar_cobranca_pix_avulsa_normaliza_token_com_bearer(self, urlopen):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({
            'id': 123456,
            'status': 'pending',
            'external_reference': 'RPFAL0001',
            'point_of_interaction': {'transaction_data': {'qr_code': 'pix-code'}},
        }).encode('utf-8')
        urlopen.return_value = response

        criar_cobranca_pix_avulsa(
            txid='RPFAL0001',
            valor=Decimal('123.45'),
            chave_pix='',
            nome_pagador='Morador Teste',
            categoria='Aluguel',
        )

        req = urlopen.call_args.args[0]
        self.assertEqual(req.headers['Authorization'], 'Bearer TEST-123')

    @override_settings(MERCADOPAGO_ACCESS_TOKEN='TEST-123')
    @patch('core.services.pix_gateway.request.urlopen')
    def test_criar_cobranca_pix_avulsa_usa_fallback_local_em_erro_autorizacao(self, urlopen):
        urlopen.side_effect = error.HTTPError('https://api.mercadopago.com/v1/payments', 401, 'Unauthorized', None, None)

        resultado = criar_cobranca_pix_avulsa(
            txid='RPFAL0002',
            valor=Decimal('123.45'),
            chave_pix='11999999999',
            nome_pagador='Morador Teste',
            categoria='Aluguel',
        )

        self.assertEqual(resultado['status_gateway'], 'erro_autorizacao_fallback_local')
        self.assertIn('br.gov.bcb.pix', resultado['payload_pix'])
        self.assertEqual(resultado['provider_payload']['http_status'], 401)
        self.assertEqual(resultado['provider_payload']['modo'], 'local')

    @override_settings(MERCADOPAGO_ACCESS_TOKEN='TEST-123')
    @patch('core.services.pix_gateway.request.urlopen')
    def test_consultar_status_por_txid_retorna_pagamento_aprovado(self, urlopen):
        search_response = MagicMock()
        payment_response = MagicMock()
        search_response.__enter__.return_value.read.return_value = json.dumps({
            'results': [{'id': 123456, 'status': 'approved', 'date_created': '2026-07-15T10:00:00Z'}],
        }).encode('utf-8')
        payment_response.__enter__.return_value.read.return_value = json.dumps({
            'id': 123456,
            'status': 'approved',
            'external_reference': 'RPFAL0001',
            'point_of_interaction': {'transaction_data': {'qr_code': 'pix-code'}},
        }).encode('utf-8')
        urlopen.side_effect = [search_response, payment_response]

        resultado = consultar_status_por_txid('RPFAL0001')

        self.assertEqual(resultado['status'], 'pago')
        self.assertEqual(resultado['payment_id'], '123456')
        self.assertEqual(resultado['txid'], 'RPFAL0001')


    @override_settings(MERCADOPAGO_ACCESS_TOKEN='TEST-123')
    @patch('core.services.pix_gateway.request.urlopen')
    def test_consultar_pagamento_ignora_404_mercado_pago(self, urlopen):
        urlopen.side_effect = error.HTTPError('https://api.mercadopago.com/v1/payments/123456', 404, 'Not Found', None, None)

        resultado = consultar_pagamento_mercado_pago('123456')

        self.assertEqual(resultado['status'], 'nao_encontrado')
        self.assertEqual(resultado['payment_id'], '123456')

    def test_consultar_evento_order_ignora_sem_chamar_api(self):
        resultado = consultar_evento_mercado_pago('123456', 'order')

        self.assertEqual(resultado['status'], 'ignorado')
        self.assertEqual(resultado['provider_payload'], {'tipo': 'order', 'id': '123456'})


    def test_consultar_evento_order_com_external_reference_processa_payload(self):
        resultado = consultar_evento_mercado_pago('123456', 'order', {
            'type': 'order',
            'data': {
                'external_reference': 'ext_ref_1234',
                'id': '123456',
                'status': 'processed',
                'status_detail': 'accredited',
                'transactions': {'payments': [{'id': 'PAY01', 'status': 'processed', 'status_detail': 'accredited'}]},
            },
        })

        self.assertEqual(resultado['txid'], 'ext_ref_1234')
        self.assertEqual(resultado['payment_id'], 'PAY01')
        self.assertEqual(resultado['status'], 'pago')

    @override_settings(MERCADOPAGO_WEBHOOK_SECRET='segredo')
    def test_validar_assinatura_webhook_mercado_pago(self):
        import hashlib
        import hmac

        manifest = 'id:123456;request-id:req-1;ts:1700000000;'
        assinatura = hmac.new(b'segredo', manifest.encode('utf-8'), hashlib.sha256).hexdigest()

        self.assertTrue(validar_assinatura_webhook(
            b'{}',
            f'ts=1700000000,v1={assinatura}',
            request_id='req-1',
            data_id='123456',
        ))
