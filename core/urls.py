from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('cadastro/', views.cadastro, name='cadastro'),
    path('acessos/', views.gerenciar_acessos, name='gerenciar_acessos'),
    path('', views.home, name='home'),
    path('perfil/', views.perfil, name='perfil'),
    path('moradores/', views.moradores, name='moradores'),
    path('financeiro/', views.financeiro, name='financeiro'),
    path('financeiro/exportar/', views.exportar_financeiro_csv, name='exportar_financeiro_csv'),
    path('financeiro/notas/<int:nota_id>/pagar/', views.pagar_nota, name='pagar_nota'),
    path('financeiro/parcelas/<int:parcela_id>/pagar/', views.pagar_parcela, name='pagar_parcela'),
    path('financeiro/parcelas/<int:parcela_id>/editar/', views.editar_parcela, name='editar_parcela'),
    path('compras/', views.compras, name='compras'),
    path('compras/editar/<int:nota_id>/', views.editar_nota_compra, name='editar_nota_compra'),
    path('compras/exportar/', views.exportar_compras_csv, name='exportar_compras_csv'),
    path('rock/', views.rock, name='rock'),
    path('almoxarifado/', views.almoxarifado, name='almoxarifado'),
    path('almoxarifado/editar/<int:produto_id>/', views.editar_produto, name='editar_produto'),
    path('almoxarifado/exportar/', views.exportar_estoque_csv, name='exportar_estoque_csv'),
    path('almoxarifado/consumo/', views.registrar_consumo, name='registrar_consumo'),
    path('almoxarifado/consumo/historico/', views.consumo_historico, name='consumo_historico'),
    path('almoxarifado/consumo/exportar/', views.exportar_consumo_csv, name='exportar_consumo_csv'),
    path('manutencao/', views.manutencao, name='manutencao'),
    path('manutencao/lista/', views.lista_os, name='lista_os'),
    path('manutencao/editar/<int:numero>/', views.editar_os, name='editar_os'),
]
