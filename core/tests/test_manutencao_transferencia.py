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

    def test_lista_os_mostra_status_finalizado_legado_em_finalizadas(self):
        OrdemServico.objects.create(
            setor='manutencao',
            descricao='Troca de fechadura',
            data_inicio='2026-04-16T10:00',
            executado_por='Mari',
            status='Finalizada',
            solicitante='João',
        )

        response = self.client.get(reverse('lista_os'))

        self.assertEqual(response.status_code, 200)
        ordens_finalizadas = list(response.context['ordens_finalizadas'])
        ordens_ativas = list(response.context['ordens_ativas'])

        self.assertEqual(len(ordens_finalizadas), 1)
        self.assertEqual(ordens_finalizadas[0].descricao, 'Troca de fechadura')
        self.assertEqual(len(ordens_ativas), 0)
        self.assertContains(response, 'Troca de fechadura')
        self.assertContains(response, 'Mostrar OSs finalizadas')
        self.assertNotContains(response, 'Nenhuma OS finalizada.')

    def test_lista_os_mantem_status_em_andamento_e_aguardando_como_ativas(self):
        OrdemServico.objects.create(
            setor='manutencao',
            descricao='OS aberta',
            data_inicio='2026-04-16T09:00',
            executado_por='Mari',
            status='aberta',
            solicitante='João',
        )
        OrdemServico.objects.create(
            setor='manutencao',
            descricao='OS em andamento',
            data_inicio='2026-04-16T10:00',
            executado_por='Mari',
            status='andamento',
            solicitante='João',
        )
        OrdemServico.objects.create(
            setor='manutencao',
            descricao='OS aguardando orçamento',
            data_inicio='2026-04-16T11:00',
            executado_por='Mari',
            status='aguardando_orcamento',
            solicitante='João',
        )

        response = self.client.get(reverse('lista_os'))

        self.assertEqual(response.status_code, 200)
        ordens_finalizadas = list(response.context['ordens_finalizadas'])
        ordens_ativas = list(response.context['ordens_ativas'])

        self.assertEqual(
            {os.descricao for os in ordens_ativas},
            {'OS aberta', 'OS em andamento', 'OS aguardando orçamento'},
        )
        self.assertEqual(ordens_finalizadas, [])

    def test_lista_os_nao_trata_data_fim_preenchida_como_finalizada_quando_status_aberta(self):
        OrdemServico.objects.create(
            setor='manutencao',
            descricao='OS aberta e ativa',
            data_inicio='2026-04-16T09:00',
            executado_por='Mari',
            status='aberta',
            solicitante='João',
        )
        OrdemServico.objects.create(
            setor='manutencao',
            descricao='OS aberta com data fim planejada',
            data_inicio='2026-04-16T10:00',
            data_fim='2026-04-16T12:00',
            executado_por='Mari',
            status='aberta',
            solicitante='João',
        )

        response = self.client.get(reverse('lista_os'))

        self.assertEqual(response.status_code, 200)
        ordens_finalizadas = list(response.context['ordens_finalizadas'])
        ordens_ativas = list(response.context['ordens_ativas'])

        self.assertEqual(
            {os.descricao for os in ordens_ativas},
            {'OS aberta e ativa', 'OS aberta com data fim planejada'},
        )
        self.assertEqual(ordens_finalizadas, [])

    def test_lista_os_normaliza_status_com_espacos(self):
        OrdemServico.objects.create(
            setor='manutencao',
            descricao='OS aberta com espaços',
            data_inicio='2026-04-16T09:00',
            executado_por='Mari',
            status='  aberta  ',
            solicitante='João',
        )

        response = self.client.get(reverse('lista_os'))

        self.assertEqual(response.status_code, 200)
        ordens_finalizadas = list(response.context['ordens_finalizadas'])
        ordens_ativas = list(response.context['ordens_ativas'])

        self.assertEqual({os.descricao for os in ordens_ativas}, {'OS aberta com espaços'})
        self.assertEqual(ordens_finalizadas, [])

    def test_manutencao_renderiza_tabela_de_finalizadas(self):
        OrdemServico.objects.create(
            setor='manutencao',
            descricao='OS já finalizada',
            data_inicio='2026-04-16T10:00',
            data_fim='2026-04-16T12:00',
            executado_por='Mari',
            status='finalizada',
            solicitante='João',
        )

        response = self.client.get(reverse('manutencao'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'OS já finalizada')
