from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import EventoCalendario


class CalendarioEventosManuaisTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username='admin', password='123456', email='admin@rpf.local')
        self.client.force_login(self.user)

    def test_cria_evento_manual(self):
        response = self.client.post(
            reverse('calendario'),
            {
                'acao': 'criar_manual',
                'titulo': 'Reunião especial',
                'data': '2026-04-16',
                'cor': '#00ff00',
                'dia_todo': 'on',
                'recorrente': 'on',
            },
        )
        self.assertEqual(response.status_code, 302)
        evento = EventoCalendario.objects.get(titulo='Reunião especial')
        self.assertEqual(evento.cor, '#00ff00')
        self.assertTrue(evento.dia_todo)
        self.assertTrue(evento.recorrente)

    def test_edita_evento_manual(self):
        evento = EventoCalendario.objects.create(titulo='Evento antigo', data='2026-04-16')
        response = self.client.post(
            reverse('calendario') + '?mes=2026-04',
            {
                'acao': 'editar_manual',
                'evento_id': str(evento.id),
                'titulo': 'Evento atualizado',
                'data': '2026-04-17',
                'cor': '#112233',
                'horario': '15:30',
            },
        )
        self.assertEqual(response.status_code, 302)
        evento.refresh_from_db()
        self.assertEqual(evento.titulo, 'Evento atualizado')
        self.assertEqual(str(evento.data), '2026-04-17')
        self.assertEqual(evento.cor, '#112233')
        self.assertFalse(evento.dia_todo)
        self.assertEqual(str(evento.horario), '15:30:00')

    def test_exclui_evento_manual(self):
        evento = EventoCalendario.objects.create(titulo='Evento excluir', data='2026-04-16')
        response = self.client.post(
            reverse('calendario') + '?mes=2026-04',
            {
                'acao': 'excluir_manual',
                'evento_id': str(evento.id),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(EventoCalendario.objects.filter(pk=evento.id).exists())

    def test_bloqueia_evento_sem_horario_quando_nao_for_dia_todo(self):
        response = self.client.post(
            reverse('calendario') + '?mes=2026-04',
            {
                'acao': 'criar_manual',
                'titulo': 'Evento inválido',
                'data': '2026-04-16',
                'cor': '#abcdef',
                'dia_todo': '',
                'horario': '',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Informe o horário ou marque')
