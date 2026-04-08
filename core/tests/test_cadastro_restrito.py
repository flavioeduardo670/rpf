from django.contrib.auth.models import User
from django.test import TestCase


class CadastroRestritoTests(TestCase):
    def test_usuario_anonimo_nao_consegue_criar_conta_via_cadastro_publico(self):
        total_antes = User.objects.count()

        response = self.client.post(
            '/cadastro/',
            {
                'username': 'novo_usuario',
                'password1': 'SenhaSegura@123',
                'password2': 'SenhaSegura@123',
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(User.objects.count(), total_antes)
