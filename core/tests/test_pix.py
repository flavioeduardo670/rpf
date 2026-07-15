import hashlib
import hmac
import json
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import CobrancaAluguel, IngressoRock, Mensalidade, Morador, PedidoIngressoRock, RockEvento, LoteIngressoRock
from core.services.rock import (
    confirmar_pagamento_pedido,
    criar_ingresso_rock,
    recalcular_quantidade_pessoas_evento,
    recalcular_quantidade_vendida_por_lote,
    remover_ingresso_rock,
)


@override_settings(MERCADOPAGO_WEBHOOK_SECRET='segredo-webhook')
class PixWebhookTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='comprador_pix', password='123456')
        self.client.force_login(self.user)
        self.evento = RockEvento.objects.create(
            nome='Rock Teste',
            tipo='nosso',
            quantidade_pessoas=0,
            data='2026-04-08',
            valor_arrecadado=0,
        )
        self.lote = LoteIngressoRock.objects.create(
            rock_evento=self.evento,
            nome='Lote 1',
            quantidade_total=2,
            quantidade_vendida=0,
            preco=Decimal('25.00'),
        )
        self.pedido = PedidoIngressoRock.objects.create(
            rock_evento=self.evento,
            lote=self.lote,
            usuario=self.user,
            nome_comprador='Cliente',
            telefone='11999990000',
            quantidade=2,
            valor_total=Decimal('50.00'),
            txid='RPF00000001',
            status='pendente',
        )

    def _headers_assinatura(self, data_id: str = '') -> dict[str, str]:
        request_id = 'request-test'
        ts = '1700000000'
        manifest = ''
        if data_id:
            manifest += f'id:{data_id};'
        manifest += f'request-id:{request_id};ts:{ts};'
        assinatura = hmac.new(b'segredo-webhook', manifest.encode('utf-8'), hashlib.sha256).hexdigest()
        return {
            'HTTP_X_SIGNATURE': f'ts={ts},v1={assinatura}',
            'HTTP_X_REQUEST_ID': request_id,
        }

    def test_webhook_rejeita_assinatura_invalida(self):
        response = self.client.post(
            reverse('webhook_pix'),
            data=json.dumps({'txid': self.pedido.txid, 'status': 'pago'}),
            content_type='application/json',
            HTTP_X_SIGNATURE='ts=1700000000,v1=assinatura-invalida',
            HTTP_X_REQUEST_ID='request-test',
        )
        self.assertEqual(response.status_code, 400)

    def test_webhook_rejeita_payload_invalido(self):
        payload_invalido = b'{payload quebrado'
        response = self.client.post(
            reverse('webhook_pix'),
            data=payload_invalido,
            content_type='application/json',
            **self._headers_assinatura(),
        )
        self.assertEqual(response.status_code, 400)

    def test_webhook_rejeita_payload_sem_txid(self):
        body = json.dumps({'status': 'pago'}).encode('utf-8')
        response = self.client.post(
            reverse('webhook_pix'),
            data=body,
            content_type='application/json',
            **self._headers_assinatura(),
        )
        self.assertEqual(response.status_code, 400)

    def test_webhook_ignora_txid_inexistente(self):
        body = json.dumps({'txid': 'RPF00000999', 'status': 'pago'}).encode('utf-8')
        response = self.client.post(
            reverse('webhook_pix'),
            data=body,
            content_type='application/json',
            **self._headers_assinatura(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'ok': True, 'detail': 'pagamento_nao_encontrado'})


    def test_webhook_ignora_simulacao_order_mercado_pago(self):
        body = json.dumps({'type': 'order', 'data': {'id': '123456'}}).encode('utf-8')
        response = self.client.post(
            f"{reverse('webhook_pix')}?data.id=123456&type=order",
            data=body,
            content_type='application/json',
            **self._headers_assinatura('123456'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'ok': True, 'detail': 'ignorado'})

    def test_webhook_confirma_pagamento(self):
        body = json.dumps({'txid': self.pedido.txid, 'status': 'paid'}).encode('utf-8')
        response = self.client.post(
            reverse('webhook_pix'),
            data=body,
            content_type='application/json',
            **self._headers_assinatura(),
        )
        self.assertEqual(response.status_code, 200)
        self.pedido.refresh_from_db()
        self.lote.refresh_from_db()
        self.assertEqual(self.pedido.status, 'pago')
        self.assertEqual(self.lote.quantidade_vendida, 2)


    def test_webhook_confirma_pagamento_aluguel_e_mensalidade(self):
        morador = Morador.objects.create(nome='Morador Pix', email='morador.pix@example.com', ativo=True)
        cobranca = CobrancaAluguel.objects.create(
            morador=morador,
            mes_referencia='2026-05-01',
            valor=Decimal('850.00'),
            txid='RPFAL000000000000000000000000000001',
            status='aguardando_pagamento',
        )
        body = json.dumps({'txid': cobranca.txid, 'status': 'pago', 'valor': '850.00'}).encode('utf-8')
        response = self.client.post(
            reverse('webhook_pix'),
            data=body,
            content_type='application/json',
            **self._headers_assinatura(),
        )
        self.assertEqual(response.status_code, 200)
        cobranca.refresh_from_db()
        self.assertEqual(cobranca.status, 'pago')
        mensalidade = Mensalidade.objects.get(morador=morador, mes_referencia='2026-05-01')
        self.assertTrue(mensalidade.pago)
        self.assertEqual(mensalidade.valor, Decimal('850.00'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['morador.pix@example.com'])
        self.assertIn('Comprovante de pagamento do aluguel - 05/2026', mail.outbox[0].subject)
        self.assertIn('TXID: RPFAL000000000000000000000000000001', mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].attachments[0][0], 'comprovante_aluguel_morador-pix_2026_05.pdf')
        self.assertEqual(mail.outbox[0].attachments[0][2], 'application/pdf')
        self.assertTrue(mail.outbox[0].attachments[0][1].startswith(b'%PDF-1.4'))


    def test_webhook_order_processado_confirma_aluguel_e_envia_comprovante(self):
        morador = Morador.objects.create(nome='Morador Order', email='morador.order@example.com', ativo=True)
        cobranca = CobrancaAluguel.objects.create(
            morador=morador,
            mes_referencia='2026-06-01',
            valor=Decimal('1000.00'),
            txid='ext_ref_1234',
            status='aguardando_pagamento',
        )
        body = json.dumps({
            'action': 'order.processed',
            'api_version': 'v1',
            'data': {
                'external_reference': cobranca.txid,
                'id': '123456',
                'status': 'processed',
                'status_detail': 'accredited',
                'total_paid_amount': 100000,
                'transactions': {
                    'payments': [{
                        'amount': 100000,
                        'id': 'PAY01K7S9596QBWZRTY02NF',
                        'paid_amount': 100000,
                        'status': 'processed',
                        'status_detail': 'accredited',
                    }],
                },
                'type': 'point',
                'version': 3,
            },
            'type': 'order',
        }).encode('utf-8')

        response = self.client.post(
            reverse('webhook_pix'),
            data=body,
            content_type='application/json',
            **self._headers_assinatura(),
        )

        self.assertEqual(response.status_code, 200)
        cobranca.refresh_from_db()
        self.assertEqual(cobranca.status, 'pago')
        self.assertEqual(cobranca.status_gateway, 'pago')
        self.assertEqual(cobranca.payment_id, 'PAY01K7S9596QBWZRTY02NF')
        mensalidade = Mensalidade.objects.get(morador=morador, mes_referencia='2026-06-01')
        self.assertTrue(mensalidade.pago)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['morador.order@example.com'])

    def test_concorrencia_simulada_confirmacao_idempotente(self):
        confirmar_pagamento_pedido(self.pedido)
        confirmar_pagamento_pedido(self.pedido)

        self.pedido.refresh_from_db()
        self.lote.refresh_from_db()

        self.assertEqual(self.pedido.status, 'pago')
        self.assertEqual(self.lote.quantidade_vendida, 2)

    def test_inconsistencia_lote_sem_disponibilidade_bloqueia_pagamento(self):
        pedido_extra = PedidoIngressoRock.objects.create(
            rock_evento=self.evento,
            lote=self.lote,
            usuario=self.user,
            nome_comprador='Cliente 2',
            telefone='11999990001',
            quantidade=1,
            valor_total=Decimal('25.00'),
            txid='RPF00000002',
            status='pendente',
        )
        self.lote.quantidade_vendida = self.lote.quantidade_total
        self.lote.save(update_fields=['quantidade_vendida'])

        with self.assertRaises(PermissionDenied):
            confirmar_pagamento_pedido(pedido_extra)

        pedido_extra.refresh_from_db()
        self.assertEqual(pedido_extra.status, 'pendente')

    def test_criar_e_remover_ingresso_recalcula_lote_e_evento(self):
        ingresso = criar_ingresso_rock(
            evento=self.evento,
            lote=self.lote,
            nome='Pessoa Teste',
            telefone='11999998888',
            quantidade_ingressos=1,
            status_pagamento='pendente',
        )
        self.lote.refresh_from_db()
        self.evento.refresh_from_db()
        self.assertEqual(self.lote.quantidade_vendida, 1)
        self.assertEqual(self.evento.quantidade_pessoas, 1)

        remover_ingresso_rock(ingresso)
        self.lote.refresh_from_db()
        self.evento.refresh_from_db()
        self.assertEqual(self.lote.quantidade_vendida, 0)
        self.assertEqual(self.evento.quantidade_pessoas, 0)

    def test_recalculo_por_lote_e_pessoas(self):
        IngressoRock.objects.create(
            rock_evento=self.evento,
            nome='Cliente A',
            telefone='11911111111',
            quantidade_ingressos=1,
            valor_unitario=Decimal('25.00'),
            status_pagamento='pago',
            observacao='Lote: Lote 1',
        )
        recalcular_quantidade_vendida_por_lote(self.evento)
        total = recalcular_quantidade_pessoas_evento(self.evento)
        self.lote.refresh_from_db()
        self.assertEqual(self.lote.quantidade_vendida, 1)
        self.assertEqual(total, 1)
