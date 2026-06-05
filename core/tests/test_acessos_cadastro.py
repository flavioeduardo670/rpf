from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import AcessoUsuario, Morador


class CadastroAcessoUsuarioTests(TestCase):
    def test_criacao_de_usuario_garante_registro_de_acesso(self):
        user = User.objects.create_user(username='usuario_novo', password='123456')

        self.assertTrue(AcessoUsuario.objects.filter(user=user).exists())


class GerenciarAcessosTests(TestCase):
    def test_vincular_usuario_a_morador_copia_permissoes_para_morador(self):
        admin = User.objects.create_superuser(username='admin', password='123456', email='')
        usuario = User.objects.create_user(username='visitante', password='123456')
        acesso_usuario = usuario.acesso_usuario
        acesso_usuario.acesso_financeiro_visualizar = True
        acesso_usuario.acesso_compras_editar = True
        acesso_usuario.save(update_fields=['acesso_financeiro_visualizar', 'acesso_compras_editar'])
        morador = Morador.objects.create(nome='Morador Vinculado', ativo=True)

        self.client.force_login(admin)
        response = self.client.post(
            reverse('gerenciar_acessos'),
            {
                'form-TOTAL_FORMS': '1',
                'form-INITIAL_FORMS': '1',
                'form-MIN_NUM_FORMS': '0',
                'form-MAX_NUM_FORMS': '1000',
                'form-0-id': str(morador.id),
                'usuarios-TOTAL_FORMS': '1',
                'usuarios-INITIAL_FORMS': '1',
                'usuarios-MIN_NUM_FORMS': '0',
                'usuarios-MAX_NUM_FORMS': '1000',
                'usuarios-0-id': str(acesso_usuario.id),
                'usuarios-0-acesso_financeiro_visualizar': 'on',
                'usuarios-0-acesso_compras_editar': 'on',
                f'vinculo_morador_{usuario.id}': str(morador.id),
            },
        )

        self.assertEqual(response.status_code, 302)
        morador.refresh_from_db()
        self.assertEqual(morador.user, usuario)
        self.assertTrue(morador.acesso_financeiro_visualizar)
        self.assertTrue(morador.acesso_compras_editar)
