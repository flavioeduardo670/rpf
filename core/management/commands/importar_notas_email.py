from django.core.management.base import BaseCommand, CommandError

from core.organizacao_atual import na_organizacao, organizacao_da_instalacao
from core.services.nfe_importacao import ConfigEmailNotas, importar_notas_do_email


class Command(BaseCommand):
    help = (
        'Lê os e-mails não lidos da caixa configurada (NFE_EMAIL_IMAP_HOST, NFE_EMAIL_USUARIO, '
        'NFE_EMAIL_SENHA) e registra no Compras as notas cujos XML vierem anexados. '
        'Rode a cada 15-30 minutos (cron).'
    )

    def handle(self, *args, **options):
        config = ConfigEmailNotas.do_ambiente()
        if config is None:
            raise CommandError('Configure NFE_EMAIL_IMAP_HOST, NFE_EMAIL_USUARIO e NFE_EMAIL_SENHA.')
        org = organizacao_da_instalacao()
        if org is None:
            raise CommandError('Nenhuma organização ativa.')
        # A caixa de email das variáveis do servidor é do cliente original da instalação.
        with na_organizacao(org):
            resultado = importar_notas_do_email(config)
        for erro in resultado.erros:
            self.stdout.write(self.style.WARNING(erro))
        self.stdout.write(self.style.SUCCESS(
            f'XML lidos: {resultado.lidas} | Compras registradas: {resultado.registradas} | '
            f'Já existentes: {resultado.repetidas}'
        ))
