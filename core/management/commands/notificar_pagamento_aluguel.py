from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Morador, NotificacaoMorador, Organizacao


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
        termos = Organizacao.atual().vocabulario
        titulo = f'Lembrete: pagar {termos["cobranca"]} {mes_referencia.strftime("%m/%Y")}'
        mensagem = f'{termos["Cobranca"]} pendente. Anexe o comprovante no seu perfil.'
        enviados = 0
        for morador in Morador.objects.filter(ativo=True):
            _, created = NotificacaoMorador.objects.get_or_create(
                morador=morador,
                mes_referencia=mes_referencia,
                tipo='lembrete_aluguel',
                defaults={'titulo': titulo, 'mensagem': mensagem},
            )
            if created:
                enviados += 1

        self.stdout.write(self.style.SUCCESS(f'Notificações criadas: {enviados}'))
