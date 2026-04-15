from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from core.models import Morador, OrdemServico


class ManutencaoTransferenciaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='manutencao_user', password='123456')
        group, _ = Group.objects.get_or_create(name='Manutencao')
        self.user.groups.add(group)
        self.morador = Morador.objects.create(nome='João da Silva', apelido='João', user=self.user, ativo=True)
        self.executor = Morador.objects.create(nome='Maria Pereira', apelido='Mari', ativo=True)
        self.client.force_login(self.user)

    def test_criacao_os_grava_solicitante_com_apelido(self):
        response = self.client.post(
            reverse('manutencao'),
            {
                'setor': 'manutencao',
                'descricao': 'Trocar lâmpada do corredor',
                'observacao': 'Urgente',
                'data_inicio': '2026-04-15T18:00',
                'data_fim': '2026-04-15T19:00',
                'executado_por': self.executor.nome,
                'status': 'aberta',
            },
        )
        self.assertEqual(response.status_code, 302)
        os_obj = OrdemServico.objects.latest('numero')
        self.assertEqual(os_obj.solicitante, 'João')

    def test_transferir_situacao_permite_atualizar_campos_relevantes(self):
        os_obj = OrdemServico.objects.create(
            setor='manutencao',
            descricao='Ajustar porta',
            data_inicio='2026-04-15T10:00',
            executado_por='-',
            status='aberta',
            solicitante='João',
        )

        response = self.client.post(
            reverse('transferir_situacao_os', args=[os_obj.numero]),
            {
                'executado_por': 'Mari',
                'data_inicio': '2026-04-15T11:00',
                'data_fim': '2026-04-15T12:00',
                'status': 'andamento',
            },
        )
        self.assertEqual(response.status_code, 302)
        os_obj.refresh_from_db()
        self.assertEqual(os_obj.executado_por, 'Mari')
        self.assertEqual(os_obj.status, 'andamento')
        self.assertIsNotNone(os_obj.data_fim)
