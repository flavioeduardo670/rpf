from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Morador, NotificacaoMorador


class Command(BaseCommand):
    help = 'Cria notificações de lembrete de pagamento do aluguel para moradores ativos no dia 5.'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Executa mesmo fora do dia 5.')

    def handle(self, *args, **options):
        hoje = timezone.localdate()
        if hoje.day != 5 and not options['force']:
            self.stdout.write(self.style.WARNING('Hoje não é dia 5. Nada foi enviado. Use --force para forçar.'))
            return

        mes_referencia = hoje.replace(day=1)
        enviados = 0
        for morador in Morador.objects.filter(ativo=True):
            _, created = NotificacaoMorador.objects.get_or_create(
                morador=morador,
                mes_referencia=mes_referencia,
                tipo='lembrete_aluguel',
                defaults={
                    'titulo': f'Lembrete: pagar aluguel {mes_referencia.strftime("%m/%Y")}',
                    'mensagem': 'Seu aluguel está pendente. Anexe o comprovante no seu perfil.',
                },
            )
            if created:
                enviados += 1

        self.stdout.write(self.style.SUCCESS(f'Notificações criadas: {enviados}'))
