from django.core.management.base import BaseCommand

from core.services.aluguel import verificar_pagamentos_pendentes
from core.services.pix_gateway import mercado_pago_configurado


class Command(BaseCommand):
    help = (
        'Consulta no Mercado Pago os boletos PIX de aluguel ainda em aberto, confirma os '
        'que já foram pagos e envia os recibos que ficaram pendentes. Rode a cada '
        '15-30 minutos (cron) como garantia caso algum webhook não chegue.'
    )

    def handle(self, *args, **options):
        if not mercado_pago_configurado():
            self.stdout.write(self.style.WARNING(
                'MERCADOPAGO_ACCESS_TOKEN não configurado: só os recibos pendentes serão reenviados.'
            ))
        resultado = verificar_pagamentos_pendentes()
        self.stdout.write(self.style.SUCCESS(
            f"Pagamentos confirmados: {resultado['confirmadas']} | "
            f"Recibos enviados: {resultado['comprovantes_enviados']}"
        ))
