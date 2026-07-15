from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0064_conta_casa'),
    ]

    operations = [
        migrations.AddField(
            model_name='cobrancaaluguel',
            name='payment_id',
            field=models.CharField(blank=True, db_index=True, default='', max_length=80),
        ),
        migrations.AddField(
            model_name='cobrancaaluguel',
            name='qr_code',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='cobrancaaluguel',
            name='qr_code_base64',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='cobrancaaluguel',
            name='ticket_url',
            field=models.URLField(blank=True, default=''),
        ),
    ]
