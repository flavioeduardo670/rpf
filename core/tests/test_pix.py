import hashlib
import hmac
import json
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import IngressoRock, PedidoIngressoRock, RockEvento, LoteIngressoRock
from core.services.rock import (
    confirmar_pagamento_pedido,
    criar_ingresso_rock,
    recalcular_quantidade_pessoas_evento,
    recalcular_quantidade_vendida_por_lote,
    remover_ingresso_rock,
)


@override_settings(PIX_WEBHOOK_SECRET='segredo-webhook')
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

    def _assinatura(self, body: bytes) -> str:
        return hmac.new(b'segredo-webhook', body, hashlib.sha256).hexdigest()

    def test_webhook_rejeita_assinatura_invalida(self):
        response = self.client.post(
            reverse('webhook_pix'),
            data=json.dumps({'txid': self.pedido.txid, 'status': 'pago'}),
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE='assinatura-invalida',
        )
        self.assertEqual(response.status_code, 400)

    def test_webhook_rejeita_payload_invalido(self):
        payload_invalido = b'{payload quebrado'
        response = self.client.post(
            reverse('webhook_pix'),
            data=payload_invalido,
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE=self._assinatura(payload_invalido),
        )
        self.assertEqual(response.status_code, 400)

    def test_webhook_rejeita_payload_sem_txid(self):
        body = json.dumps({'status': 'pago'}).encode('utf-8')
        response = self.client.post(
            reverse('webhook_pix'),
            data=body,
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE=self._assinatura(body),
        )
        self.assertEqual(response.status_code, 400)

    def test_webhook_ignora_txid_inexistente(self):
        body = json.dumps({'txid': 'RPF00000999', 'status': 'pago'}).encode('utf-8')
        response = self.client.post(
            reverse('webhook_pix'),
            data=body,
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE=self._assinatura(body),
        )
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'ok': True, 'detail': 'pedido_nao_encontrado'})

    def test_webhook_confirma_pagamento(self):
        body = json.dumps({'txid': self.pedido.txid, 'status': 'paid'}).encode('utf-8')
        response = self.client.post(
            reverse('webhook_pix'),
            data=body,
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE=self._assinatura(body),
        )
        self.assertEqual(response.status_code, 200)
        self.pedido.refresh_from_db()
        self.lote.refresh_from_db()
        self.assertEqual(self.pedido.status, 'pago')
        self.assertEqual(self.lote.quantidade_vendida, 2)

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
