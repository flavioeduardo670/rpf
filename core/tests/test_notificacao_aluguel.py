from datetime import date

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from core.models import Morador, NotificacaoMorador


class NotificacaoAluguelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='morador_notif', password='123456')
        self.morador = Morador.objects.create(nome='Morador Notificação', user=self.user, ativo=True)

    def test_command_force_cria_notificacao(self):
        call_command('notificar_pagamento_aluguel', '--force')
        self.assertEqual(NotificacaoMorador.objects.count(), 1)

    def test_perfil_exibe_notificacao(self):
        NotificacaoMorador.objects.create(
            morador=self.morador,
            mes_referencia=date(2026, 5, 1),
            tipo='lembrete_aluguel',
            titulo='Lembrete de aluguel',
            mensagem='Pague o aluguel e anexe o comprovante.',
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse('perfil'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Notificações de aluguel')
        self.assertContains(response, 'Lembrete de aluguel')
