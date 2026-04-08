from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from core.models import Andar, Comodo, LocalArmazenamento, Morador, NotaFiscal, Setor


class ComprasFluxoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='compras_user', password='123456')
        group, _ = Group.objects.get_or_create(name='Compras')
        self.user.groups.add(group)
        Morador.objects.create(nome='Comprador', user=self.user, ativo=True, acesso_compras_editar=True)

        setor = Setor.objects.create(nome='Infraestrutura')
        andar = Andar.objects.create(nome='Terreo')
        comodo = Comodo.objects.create(nome='Deposito', andar=andar)
        self.local = LocalArmazenamento.objects.create(nome='Prateleira A', comodo=comodo)
        self.setor = setor

    def test_rejeita_payload_invalido_sem_campos_obrigatorios(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('compras'),
            {
                'descricao': '',
                'fornecedor': '',
                'valor': '',
                'data_emissao': '',
                'data_vencimento': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Este campo é obrigatório.', html=False)
        self.assertEqual(NotaFiscal.objects.count(), 0)

    def test_rejeita_inconsistencia_estoque_sem_local_quando_adicionar_estoque(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('compras'),
            {
                'descricao': 'Luva',
                'fornecedor': 'Fornecedor',
                'categoria_compra': 'geral',
                'tipo_item': 'Bem de Consumo',
                'adicionar_estoque': 'on',
                'setor_estoque': self.setor.id,
                'comodo_estoque': '',
                'local_estoque': '',
                'quantidade': 5,
                'valor': '10.00',
                'data_emissao': '2026-04-01',
                'data_vencimento': '2026-04-10',
                'status': 'pendente',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(NotaFiscal.objects.count(), 0)
        self.assertContains(response, 'Este campo é obrigatório.', html=False)
