import os

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Cria um superusuario a partir de variaveis de ambiente, se ainda nao existir."

    def handle(self, *args, **options):
        username = os.getenv("DJANGO_ADMIN_USERNAME")
        email = os.getenv("DJANGO_ADMIN_EMAIL")
        password = os.getenv("DJANGO_ADMIN_PASSWORD")

        if not username or not password or not email:
            self.stdout.write("Variaveis DJANGO_ADMIN_USERNAME/EMAIL/PASSWORD nao definidas.")
            return

        User = get_user_model()
        if User.objects.filter(username=username).exists():
            self.stdout.write("Superusuario ja existe.")
            return

        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write("Superusuario criado com sucesso.")
