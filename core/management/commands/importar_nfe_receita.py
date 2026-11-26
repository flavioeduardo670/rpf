from django.core.management.base import BaseCommand, CommandError

from core.organizacao_atual import na_organizacao, organizacao_da_instalacao
from core.services.nfe_distribuicao import ConfigDistribuicao, DistribuicaoErro, importar_distribuicao


class Command(BaseCommand):
    help = (
        'Busca na Receita (Distribuição de DF-e) as NF-e emitidas para o CNPJ da república, '
        'com o certificado A1 (NFE_CNPJ, NFE_CERTIFICADO_PFX_BASE64 ou NFE_CERTIFICADO_PFX_CAMINHO, '
        'NFE_CERTIFICADO_SENHA) e registra as compras. Rode no máximo de hora em hora (cron).'
    )

    def handle(self, *args, **options):
        config = ConfigDistribuicao.do_ambiente()
        if config is None:
            raise CommandError('Configure NFE_CNPJ e o certificado A1 (NFE_CERTIFICADO_PFX_BASE64 e NFE_CERTIFICADO_SENHA).')
        org = organizacao_da_instalacao()
        if org is None:
            raise CommandError('Nenhuma organização ativa.')
        try:
            # O certificado das variáveis do servidor é do cliente original da instalação.
            with na_organizacao(org):
                resultado = importar_distribuicao(config)
        except DistribuicaoErro as exc:
            raise CommandError(str(exc)) from exc
        for erro in resultado.erros:
            self.stdout.write(self.style.WARNING(erro))
        self.stdout.write(self.style.SUCCESS(
            f'Documentos lidos: {resultado.lidas} | Compras registradas: {resultado.registradas} | '
            f'Já existentes: {resultado.repetidas}'
        ))
