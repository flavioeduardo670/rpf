from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from core.models import Andar, Comodo, LocalArmazenamento, Morador, Produto, Setor
from core.services.estoque import sincronizar_consumo_item


class EstoqueNegativosTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='estoque_user', password='123456')
        group, _ = Group.objects.get_or_create(name='Estoque')
        self.user.groups.add(group)

        self.setor = Setor.objects.create(nome='Estoque')
        self.andar = Andar.objects.create(nome='Terreo')
        self.comodo = Comodo.objects.create(nome='Deposito', andar=self.andar)
        self.local = LocalArmazenamento.objects.create(nome='Prateleira', comodo=self.comodo)
        self.produto = Produto.objects.create(
            nome='Parafuso',
            descricao='Bem de Uso',
            setor=self.setor,
            local=self.local,
            quantidade=2,
            estoque_minimo=1,
        )
        self.morador = Morador.objects.create(nome='Responsavel', ativo=True)

    def test_bloqueia_consumo_maior_que_estoque(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('registrar_consumo'),
            {
                'morador': self.morador.id,
                'data': '2026-04-08',
                'produto': self.produto.id,
                'quantidade': 3,
                'setor': 'infraestrutura',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.quantidade, 2)
        self.assertContains(response, 'Estoque insuficiente', html=False)

    def test_concorrencia_simulada_em_duas_baixas_do_mesmo_item(self):
        sincronizar_consumo_item(
            consumo_atual=None,
            produto_id=self.produto.id,
            quantidade=1,
            morador=self.morador,
            data='2026-04-08',
        )
        sincronizar_consumo_item(
            consumo_atual=None,
            produto_id=self.produto.id,
            quantidade=1,
            morador=self.morador,
            data='2026-04-08',
        )

        self.produto.refresh_from_db()
        self.assertEqual(self.produto.quantidade, 0)

    def test_fluxos_basicos_de_estoque_e_exportacoes(self):
        self.client.force_login(self.user)

        response_almox = self.client.get(reverse('almoxarifado'))
        self.assertEqual(response_almox.status_code, 200)

        response_novo = self.client.post(
            reverse('almoxarifado'),
            {
                'produto_submit': '1',
                'nome': 'Martelo',
                'descricao': 'Bem de Uso',
                'setor': self.setor.id,
                'comodo': self.comodo.id,
                'local': self.local.id,
                'quantidade': 5,
                'estoque_minimo': 1,
            },
        )
        self.assertEqual(response_novo.status_code, 302)
        produto_novo = Produto.objects.get(nome='Martelo')

        response_editar = self.client.post(
            reverse('editar_produto', args=[produto_novo.id]),
            {
                'nome': 'Martelo',
                'descricao': 'Bem de Uso',
                'setor': self.setor.id,
                'comodo': self.comodo.id,
                'local': self.local.id,
                'quantidade': 9,
                'estoque_minimo': 1,
            },
        )
        self.assertEqual(response_editar.status_code, 302)

        response_consumo_ok = self.client.post(
            reverse('registrar_consumo'),
            {
                'morador': self.morador.id,
                'data': '2026-04-08',
                'produto': self.produto.id,
                'quantidade': 1,
                'setor': 'infraestrutura',
            },
        )
        self.assertEqual(response_consumo_ok.status_code, 302)
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.quantidade, 1)

        self.assertEqual(self.client.get(reverse('consumo_historico')).status_code, 200)
        self.assertEqual(self.client.get(reverse('exportar_consumo_csv')).status_code, 200)
        self.assertEqual(self.client.get(reverse('exportar_estoque_csv')).status_code, 200)

    def test_editar_produto_exclusao(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('editar_produto', args=[self.produto.id]),
            {'excluir_submit': '1'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Produto.objects.filter(id=self.produto.id).exists())
