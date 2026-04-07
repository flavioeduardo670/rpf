from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0048_merge_20260407_1515'),
    ]

    operations = [
        migrations.AddField(
            model_name='pedidoingressorock',
            name='payload_pix',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='pedidoingressorock',
            name='status_gateway',
            field=models.CharField(blank=True, default='', max_length=40),
        ),
        migrations.AddField(
            model_name='pedidoingressorock',
            name='txid',
            field=models.CharField(blank=True, default='', max_length=40),
        ),
        migrations.AddField(
            model_name='pedidoingressorock',
            name='webhook_recebido_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
