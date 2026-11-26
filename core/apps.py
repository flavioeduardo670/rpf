from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        from core.organizacao_atual import instalar_filtro_nos_formularios

        instalar_filtro_nos_formularios()
