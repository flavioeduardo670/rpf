from datetime import datetime, time

from django.db import models, transaction
from django.db.models.signals import post_save, pre_save
from django.db.models import Q
from django.dispatch import receiver
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


# =====================================================
# MÓDULO: MORADORES E MENSALIDADES
# =====================================================



class Morador(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='morador'
    )

    nome = models.CharField(max_length=100)
    apelido = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    quarto = models.CharField(max_length=100, null=True, blank=True)
    codigo_quarto = models.CharField(max_length=10, null=True, blank=True)
    peso_quarto = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    curso = models.CharField(max_length=120, blank=True, null=True)
    funcoes = models.TextField(blank=True, null=True)
    foto_perfil = models.ImageField(upload_to='perfil_fotos/', null=True, blank=True)
    ordem_hierarquia = models.PositiveIntegerField(default=0)
    ativo = models.BooleanField(default=True)
    ultima_visualizacao_os = models.DateTimeField(blank=True, null=True)

    # Permissões internas do sistema
    acesso_financeiro_visualizar = models.BooleanField(default=False)
    acesso_financeiro_editar = models.BooleanField(default=False)
    acesso_compras_visualizar = models.BooleanField(default=False)
    acesso_compras_editar = models.BooleanField(default=False)
    acesso_estoque_visualizar = models.BooleanField(default=False)
    acesso_estoque_editar = models.BooleanField(default=False)
    acesso_manutencao_visualizar = models.BooleanField(default=False)
    acesso_manutencao_editar = models.BooleanField(default=False)
    acesso_rock_visualizar = models.BooleanField(default=False)
    acesso_rock_editar = models.BooleanField(default=False)
    acesso_reunioes_visualizar = models.BooleanField(default=False)
    acesso_reunioes_editar = models.BooleanField(default=False)

    class Meta:
        ordering = ['ordem_hierarquia', 'nome']

    def __str__(self):
        return self.nome



class AcessoUsuario(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='acesso_usuario')
    acesso_financeiro_visualizar = models.BooleanField(default=False)
    acesso_financeiro_editar = models.BooleanField(default=False)
    acesso_compras_visualizar = models.BooleanField(default=False)
    acesso_compras_editar = models.BooleanField(default=False)
    acesso_estoque_visualizar = models.BooleanField(default=False)
    acesso_estoque_editar = models.BooleanField(default=False)
    acesso_manutencao_visualizar = models.BooleanField(default=False)
    acesso_manutencao_editar = models.BooleanField(default=False)
    acesso_rock_visualizar = models.BooleanField(default=False)
    acesso_rock_editar = models.BooleanField(default=False)
    acesso_reunioes_visualizar = models.BooleanField(default=False)
    acesso_reunioes_editar = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username


class Mensalidade(models.Model):
    """
    Representa a mensalidade que cada morador deve pagar.
    """
    morador = models.ForeignKey(Morador, on_delete=models.CASCADE)
    # Se o morador for excluído, suas mensalidades também serão

    mes_referencia = models.DateField()  # Mês referente ao pagamento
    valor = models.DecimalField(max_digits=8, decimal_places=2)  # Valor da mensalidade

    pago = models.BooleanField(default=False)  # Indica se já foi pago
    data_pagamento = models.DateField(blank=True, null=True)  # Data em que foi pago

    def __str__(self):
        return f"{self.morador.nome} - {self.mes_referencia}"


# =====================================================
# MÓDULO: FINANCEIRO (NOTAS FISCAIS)
# =====================================================

class NotaFiscal(models.Model):
    """
    Representa despesas registradas no setor financeiro.
    Pode vir de compras, manutenção ou outros setores.
    """

    # Opções de status da nota
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('pago', 'Pago'),
    ]

    # Setores responsáveis pela nota
    SETOR_CHOICES = [
        ('compras', 'Compras'),
        ('manutencao', 'Manutenção'),
        ('outros', 'Outros'),
    ]

    setor = models.CharField(
        max_length=20,
        choices=SETOR_CHOICES,
        default='outros'
    )

    descricao = models.CharField(max_length=200)  # Descrição da despesa
    fornecedor = models.CharField(max_length=100)  # Nome do fornecedor
    setor_estoque = models.ForeignKey('Setor', on_delete=models.SET_NULL, null=True, blank=True)
    local_estoque = models.ForeignKey('LocalArmazenamento', on_delete=models.SET_NULL, null=True, blank=True)
    tipo_item = models.CharField(max_length=100, blank=True, null=True)
    quantidade = models.IntegerField(default=0)
    qualidade = models.CharField(max_length=100, blank=True, null=True)
    adicionar_estoque = models.BooleanField(default=True)
    cobrar_no_aluguel = models.BooleanField(default=True)
    parcelado = models.BooleanField(default=False)
    quantidade_parcelas = models.IntegerField(default=1)
    categoria_compra = models.CharField(max_length=20, default='geral')
    valor = models.DecimalField(max_digits=10, decimal_places=2)  # Valor total da nota

    data_emissao = models.DateField()  # Data em que foi emitida
    data_vencimento = models.DateField()  # Data limite para pagamento

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='pendente'
    )

    data_pagamento = models.DateField(blank=True, null=True)  # Data em que foi paga
    forma_pagamento = models.CharField(max_length=50, blank=True, null=True)
    observacao = models.TextField(blank=True, null=True)
    rock_evento = models.ForeignKey('RockEvento', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.descricao} - {self.fornecedor}"


class RockEvento(models.Model):
    TIPO_CHOICES = [
        ('nosso', 'Nosso Rock'),
        ('aluguel', 'Aluguel da Casa'),
    ]

    nome = models.CharField(max_length=200)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    quantidade_pessoas = models.IntegerField(default=0)
    horario_inicio = models.TimeField(null=True, blank=True)
    horario_fim = models.TimeField(null=True, blank=True)
    observacoes = models.TextField(blank=True, null=True)
    data = models.DateField()
    valor_arrecadado = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return self.nome




class NotaParcela(models.Model):
    """
    Parcelas vinculadas a uma nota fiscal.
    """

    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('pago', 'Pago'),
    ]

    nota = models.ForeignKey(NotaFiscal, on_delete=models.CASCADE, related_name='parcelas')
    numero = models.PositiveIntegerField()
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    vencimento = models.DateField()
    mes_referencia = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pendente')

    class Meta:
        ordering = ['vencimento', 'id']

    def __str__(self):
        return f"{self.nota.descricao} - Parcela {self.numero}"


class DescontoMensal(models.Model):
    mes_referencia = models.DateField()
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        unique_together = ('mes_referencia',)

    def __str__(self):
        return f"Desconto {self.mes_referencia.strftime('%m/%Y')}"


class PendenciaMensal(models.Model):
    mes_referencia = models.DateField()
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        unique_together = ('mes_referencia',)

    def __str__(self):
        return f"Pendencia {self.mes_referencia.strftime('%m/%Y')}"


class PendenciaMensalItem(models.Model):
    TIPO_CHOICES = [
        ('extra', 'Extra'),
        ('desconto', 'Desconto'),
    ]

    mes_referencia = models.DateField()
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='extra')
    motivo = models.CharField(max_length=200, default='')
    descricao = models.CharField(max_length=200, blank=True, default='')
    valor = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        ordering = ['id']

    def __str__(self):
        descricao = self.motivo or self.descricao or 'Sem motivo'
        return f"{descricao} ({self.mes_referencia.strftime('%m/%Y')})"


class ParcelaRateioExclusao(models.Model):
    parcela = models.ForeignKey(NotaParcela, on_delete=models.CASCADE, related_name='rateio_exclusoes')
    morador = models.ForeignKey(Morador, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('parcela', 'morador')

    def __str__(self):
        return f"Exclusao de {self.morador.nome} na parcela {self.parcela_id}"


class AjusteMorador(models.Model):
    TIPO_CHOICES = [
        ('extra', 'Extra'),
        ('desconto', 'Desconto'),
    ]

    morador = models.ForeignKey(Morador, on_delete=models.CASCADE)
    mes_referencia = models.DateField()
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    motivo = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.morador.nome} - {self.tipo}"


class ComprovantePagamentoMorador(models.Model):
    morador = models.ForeignKey(Morador, on_delete=models.CASCADE, related_name='comprovantes_pagamento')
    mes_referencia = models.DateField()
    arquivo = models.FileField(upload_to='comprovantes_pagamento/%Y/%m/')
    enviado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('morador', 'mes_referencia')
        ordering = ['-mes_referencia', '-enviado_em']

    def __str__(self):
        return f"{self.morador.nome} - {self.mes_referencia.strftime('%m/%Y')}"


class NotificacaoMorador(models.Model):
    TIPO_CHOICES = [
        ('lembrete_aluguel', 'Lembrete de aluguel'),
    ]

    morador = models.ForeignKey(Morador, on_delete=models.CASCADE, related_name='notificacoes')
    mes_referencia = models.DateField()
    tipo = models.CharField(max_length=40, choices=TIPO_CHOICES, default='lembrete_aluguel')
    titulo = models.CharField(max_length=120)
    mensagem = models.TextField(blank=True, default='')
    lida = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em']
        unique_together = ('morador', 'mes_referencia', 'tipo')

    def __str__(self):
        return f"{self.morador.nome} - {self.titulo}"


# =====================================================
# MÓDULO: ESTOQUE
# =====================================================


class ConfiguracaoFinanceira(models.Model):
    """
    Configuracao de valores base do financeiro.
    """

    valor_aluguel = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valor_agua = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valor_luz = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    conta_principal_pix = models.CharField(max_length=255, blank=True, default='')
    conta_recebimentos_pix = models.CharField(max_length=255, blank=True, default='')
    conta_pagamentos_pix = models.CharField(max_length=255, blank=True, default='')
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuracao Financeira'
        verbose_name_plural = 'Configuracoes Financeiras'

    def __str__(self):
        return f"Aluguel: R$ {self.valor_aluguel} | PIX recebimentos: {self.conta_recebimentos_pix or '-'}"


class ContaFixa(models.Model):
    nome = models.CharField(max_length=100)
    valor = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nome} - R$ {self.valor}"

class Setor(models.Model):
    """
    Representa um setor do sistema (Compras, Manutenção etc).
    """
    nome = models.CharField(max_length=100)

    def __str__(self):
        return self.nome



class Andar(models.Model):
    nome = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ['nome']

    def __str__(self):
        return self.nome


class Comodo(models.Model):
    nome = models.CharField(max_length=150)
    andar = models.ForeignKey(Andar, on_delete=models.CASCADE, related_name='comodos')

    class Meta:
        unique_together = ('nome', 'andar')
        ordering = ['andar__nome', 'nome']

    def __str__(self):
        return f"{self.nome} ({self.andar.nome})"




class LocalArmazenamento(models.Model):
    """
    Local físico onde os produtos ficam armazenados.
    """
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True, null=True)
    comodo = models.ForeignKey(Comodo, on_delete=models.SET_NULL, null=True, blank=True, related_name='locais')

    def __str__(self):
        return self.nome


class RockItem(models.Model):
    rock_evento = models.ForeignKey(RockEvento, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey('Produto', on_delete=models.SET_NULL, null=True, blank=True)
    quantidade = models.IntegerField(default=1)
    valor_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    observacao = models.TextField(blank=True, null=True)
    consumo = models.OneToOneField('ConsumoEstoque', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return (self.produto.nome if self.produto else 'Item')


class IngressoRock(models.Model):
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('pago', 'Pago'),
    ]

    rock_evento = models.ForeignKey(RockEvento, on_delete=models.CASCADE, related_name='ingressos')
    nome = models.CharField(max_length=150)
    telefone = models.CharField(max_length=30, blank=True, null=True)
    quantidade_ingressos = models.PositiveIntegerField(default=1)
    valor_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status_pagamento = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendente')
    observacao = models.CharField(max_length=200, blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    @property
    def valor_total(self):
        return self.quantidade_ingressos * self.valor_unitario

    def __str__(self):
        return f"{self.nome} - {self.rock_evento.nome}"


class LoteIngressoRock(models.Model):
    rock_evento = models.ForeignKey(RockEvento, on_delete=models.CASCADE, related_name='lotes')
    nome = models.CharField(max_length=100)
    quantidade_total = models.PositiveIntegerField(default=0)
    quantidade_vendida = models.PositiveIntegerField(default=0)
    preco = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    @property
    def quantidade_disponivel(self):
        disponivel = self.quantidade_total - self.quantidade_vendida
        return disponivel if disponivel > 0 else 0

    def __str__(self):
        return f"{self.rock_evento.nome} - {self.nome}"


class PedidoIngressoRock(models.Model):
    STATUS_CHOICES = [
        ('aguardando_pagamento', 'Aguardando pagamento'),
        ('pago', 'Pago'),
    ]

    rock_evento = models.ForeignKey(RockEvento, on_delete=models.CASCADE, related_name='pedidos_ingresso')
    lote = models.ForeignKey(LoteIngressoRock, on_delete=models.PROTECT, related_name='pedidos')
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    nome_comprador = models.CharField(max_length=150)
    telefone = models.CharField(max_length=30, blank=True, null=True)
    quantidade = models.PositiveIntegerField(default=1)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='aguardando_pagamento')
    txid = models.CharField(max_length=40, blank=True, default='')
    payload_pix = models.TextField(blank=True, default='')
    status_gateway = models.CharField(max_length=40, blank=True, default='')
    webhook_recebido_em = models.DateTimeField(blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    pago_em = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Pedido {self.id} - {self.nome_comprador}"


class FormFieldConfig(models.Model):
    form_key = models.CharField(max_length=100)
    field_name = models.CharField(max_length=100)
    label = models.CharField(max_length=200, blank=True)
    visible = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('form_key', 'field_name')
        ordering = ['form_key', 'order', 'field_name']

    def __str__(self):
        return f"{self.form_key}:{self.field_name}"


class ChoiceList(models.Model):
    key = models.CharField(max_length=100, unique=True)
    label = models.CharField(max_length=200)

    class Meta:
        ordering = ['label', 'key']

    def __str__(self):
        return self.label


class ChoiceOption(models.Model):
    choice_list = models.ForeignKey(ChoiceList, on_delete=models.CASCADE, related_name='options')
    value = models.CharField(max_length=100)
    label = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('choice_list', 'value')
        ordering = ['order', 'label']

    def __str__(self):
        return f"{self.choice_list.key}:{self.label}"


class EventoCalendario(models.Model):
    titulo = models.CharField(max_length=200)
    data = models.DateField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data', 'titulo']

    def __str__(self):
        return f"{self.data} - {self.titulo}"


class Reuniao(models.Model):
    TIPO_CHOICES = [
        ('geral', 'Geral'),
        ('setorial', 'Setorial'),
    ]
    STATUS_CHOICES = [
        ('marcada', 'Marcada'),
        ('realizada', 'Realizada'),
        ('cancelada', 'Cancelada'),
    ]
    SETOR_CHOICES = [
        ('administrativo', 'Administrativo'),
        ('compras', 'Compras'),
        ('infraestrutura', 'Infraestrutura'),
        ('hotelaria', 'Hotelaria'),
        ('manutencao', 'Manutenção'),
        ('rock', 'Rock'),
        ('financeiro', 'Financeiro'),
        ('outros', 'Outros'),
    ]

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='geral')
    setor = models.CharField(max_length=30, choices=SETOR_CHOICES, blank=True, null=True)
    data = models.DateField()
    horario_marcado = models.TimeField()
    local = models.CharField(max_length=150)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='marcada')

    class Meta:
        ordering = ['-data', '-horario_marcado']

    def clean(self):
        if self.tipo == 'setorial' and not self.setor:
            raise ValidationError({'setor': 'Informe o setor para reuniões setoriais.'})
        if self.tipo == 'geral':
            self.setor = None

    def __str__(self):
        return f"Reunião {self.get_tipo_display()} - {self.data:%d/%m/%Y}"


class AtaReuniao(models.Model):
    reuniao = models.OneToOneField(Reuniao, on_delete=models.CASCADE, related_name='ata')
    numero_sequencial = models.PositiveIntegerField(editable=False)
    ano = models.PositiveIntegerField(editable=False)
    escopo_numeracao = models.CharField(max_length=40, editable=False)
    identificador_formatado = models.CharField(max_length=80, editable=False)
    horario_inicio_real = models.TimeField(blank=True, null=True)
    horario_fim_real = models.TimeField(blank=True, null=True)
    texto_abertura = models.TextField(blank=True, default='')
    encerramento_texto = models.TextField(blank=True, default='')
    criado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-ano', '-numero_sequencial']
        unique_together = (('ano', 'escopo_numeracao', 'numero_sequencial'),)

    def _setor_identificador(self):
        if self.reuniao.tipo == 'setorial':
            return (self.reuniao.setor or 'setorial').upper()
        return self.reuniao.tipo.upper()

    def _escopo_numeracao(self):
        if self.reuniao.tipo == 'setorial':
            return f"setorial:{(self.reuniao.setor or 'setorial').lower()}"
        return self.reuniao.tipo

    def _proximo_numero(self):
        return (
            AtaReuniao.objects.filter(ano=self.ano, escopo_numeracao=self.escopo_numeracao)
            .exclude(pk=self.pk)
            .aggregate(max_num=models.Max('numero_sequencial'))
            .get('max_num') or 0
        ) + 1

    def _identificador(self):
        return f"ATA {self._setor_identificador()} {self.numero_sequencial:02d}/{self.ano}"

    def save(self, *args, **kwargs):
        if not self.ano:
            self.ano = self.reuniao.data.year

        self.escopo_numeracao = self._escopo_numeracao()

        if not self.numero_sequencial:
            self.numero_sequencial = self._proximo_numero()

        self.identificador_formatado = self._identificador()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.identificador_formatado


class AtaAcao5W2H(models.Model):
    ata_reuniao = models.ForeignKey(
        AtaReuniao,
        on_delete=models.CASCADE,
        related_name='acoes_5w2h',
    )
    o_que = models.TextField()
    por_que = models.TextField(blank=True, default='')
    quem = models.CharField(max_length=150)
    quando = models.DateField(blank=True, null=True)
    onde = models.CharField(max_length=200, blank=True, default='')
    como = models.TextField(blank=True, default='')
    quanto = models.CharField(max_length=120, blank=True, default='')
    observacao = models.TextField(blank=True, default='')
    gerou_os = models.BooleanField(default=False)
    ordem_servico = models.ForeignKey(
        'OrdemServico',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acoes_5w2h',
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em', '-id']

    def __str__(self):
        return f"Ação 5W2H #{self.pk} - {self.o_que[:60]}"

    def _observacao_os(self, extras=None):
        partes = []
        if self.por_que:
            partes.append(f"Por quê: {self.por_que}")
        if self.como:
            partes.append(f"Como: {self.como}")
        if self.quanto:
            partes.append(f"Quanto: {self.quanto}")
        if self.onde:
            partes.append(f"Onde: {self.onde}")
        if self.observacao:
            partes.append(f"Obs. ação: {self.observacao}")
        if extras:
            for extra in extras:
                if extra:
                    partes.append(str(extra))
        return "\n".join(partes).strip()

    def _resolver_executado_por(self):
        responsavel = (self.quem or '').strip()
        if not responsavel:
            return 'Não definido'

        morador = Morador.objects.filter(
            Q(nome__iexact=responsavel) | Q(apelido__iexact=responsavel)
        ).first()
        if morador:
            return morador.nome
        return responsavel

    def gerar_ordem_servico(self, *, setor='manutencao', extras_observacao=None):
        with transaction.atomic():
            acao = AtaAcao5W2H.objects.select_for_update().get(pk=self.pk)

            if acao.ordem_servico_id:
                if not acao.gerou_os:
                    acao.gerou_os = True
                    acao.save(update_fields=['gerou_os'])
                return acao.ordem_servico

            if acao.gerou_os:
                raise ValidationError('Ação 5W2H já marcada como geradora de OS.')

            data_inicio = timezone.now()
            data_fim = None
            if acao.quando:
                data_fim = timezone.make_aware(
                    datetime.combine(acao.quando, time(23, 59, 59)),
                    timezone.get_current_timezone(),
                )

            ordem_servico = OrdemServico.objects.create(
                setor=setor,
                descricao=acao.o_que,
                observacao=acao._observacao_os(extras=extras_observacao),
                executado_por=acao._resolver_executado_por(),
                data_inicio=data_inicio,
                data_fim=data_fim,
            )

            acao.ordem_servico = ordem_servico
            acao.gerou_os = True
            acao.save(update_fields=['ordem_servico', 'gerou_os'])
            return ordem_servico


class Produto(models.Model):
    """
    Produto controlado no estoque.
    """
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True, null=True)

    setor = models.ForeignKey(Setor, on_delete=models.CASCADE)
    # Se o setor for excluído, os produtos também serão

    local = models.ForeignKey(
        LocalArmazenamento,
        on_delete=models.SET_NULL,
        null=True
    )
    # Se o local for excluído, o produto não será apagado

    quantidade = models.IntegerField(default=0)  # Quantidade atual em estoque
    estoque_minimo = models.IntegerField(default=0)  # Quantidade mínima aceitável

    data_cadastro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome

    def estoque_baixo(self):
        """
        Retorna True se o estoque estiver abaixo ou igual ao mínimo.
        """
        return self.quantidade <= self.estoque_minimo


class MovimentacaoEstoque(models.Model):
    """
    Registra entradas e saídas de produtos.
    """

    TIPO_CHOICES = [
        ('entrada', 'Entrada'),
        ('saida', 'Saída'),
    ]

    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    quantidade = models.IntegerField()
    data = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.produto.nome} - {self.tipo}"


class ConsumoEstoque(models.Model):
    """
    Registra consumo de produtos do estoque.
    """

    SETOR_CHOICES = [
        ('infraestrutura', 'Infraestrutura'),
        ('rock', 'Rock'),
        ('outros', 'Outros'),
    ]

    morador = models.ForeignKey(Morador, on_delete=models.CASCADE)
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    quantidade = models.IntegerField()
    data = models.DateField()
    setor = models.CharField(max_length=20, choices=SETOR_CHOICES, default='infraestrutura')
    rock_evento = models.ForeignKey('RockEvento', on_delete=models.SET_NULL, null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.morador.nome} - {self.produto.nome}"


# =====================================================
# MÓDULO: MANUTENÇÃO
# =====================================================

class OrdemServico(models.Model):
    """
    Representa uma Ordem de Serviço (OS).
    """

    SETOR_CHOICES = [
        ('manutencao', 'Manutencao'),
        ('infraestrutura', 'Infraestrutura'),
        ('hotelaria', 'Hotelaria'),
        ('rock', 'Rock'),
        ('outros', 'Outros'),
    ]

    STATUS_CHOICES = [
        ('aberta', 'Aberta'),
        ('andamento', 'Em Andamento'),
        ('finalizada', 'Finalizada'),
    ]

    numero = models.AutoField(primary_key=True)
    setor = models.CharField(max_length=20, choices=SETOR_CHOICES, default='manutencao')
    descricao = models.TextField()
    observacao = models.TextField(blank=True, null=True)

    data_inicio = models.DateTimeField()
    data_fim = models.DateTimeField(blank=True, null=True)

    executado_por = models.CharField(max_length=150)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='aberta'
    )

    @property
    def executado_por_exibicao(self):
        executado_por = (self.executado_por or '').strip()
        if not executado_por:
            return '-'

        morador = Morador.objects.filter(nome=executado_por).only('apelido').first()
        if morador and morador.apelido:
            return morador.apelido
        return executado_por

    # Indica se já foi gerada despesa no financeiro
    despesa_gerada = models.BooleanField(default=False)

    @property
    def valor_total(self):
        """
        Soma o valor total de todos os materiais utilizados na OS.
        """
        return sum(material.valor_total for material in self.materiais.all())

    def __str__(self):
        return f"OS #{self.numero} - {self.status}"

    def gerar_despesa(self):
        """
        Gera automaticamente uma Nota Fiscal no financeiro
        com base nos materiais utilizados na OS.
        """
        NotaFiscal.objects.create(
            setor='manutencao',
            descricao=f"Manutenção OS #{self.numero}",
            fornecedor="Setor de Manutenção",
            valor=self.valor_total,
            data_emissao=timezone.now().date(),
            data_vencimento=timezone.now().date(),
            status='pago',
            data_pagamento=timezone.now().date(),
            forma_pagamento="Interno"
        )

        self.despesa_gerada = True
        self.save()


class MaterialUtilizado(models.Model):
    """
    Representa um material utilizado em uma Ordem de Serviço.
    """

    ordem_servico = models.ForeignKey(
        OrdemServico,
        on_delete=models.CASCADE,
        related_name='materiais'
    )

    nome_material = models.CharField(max_length=200, blank=True, null=True)
    produto = models.ForeignKey(Produto, on_delete=models.SET_NULL, null=True, blank=True)
    quantidade = models.IntegerField()
    morador = models.ForeignKey(Morador, on_delete=models.SET_NULL, null=True, blank=True)
    data_consumo = models.DateField(null=True, blank=True)
    consumo = models.OneToOneField('ConsumoEstoque', on_delete=models.SET_NULL, null=True, blank=True)

    valor_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    @property
    def valor_total(self):
        """
        Calcula automaticamente o valor total do material.
        """
        return self.quantidade * self.valor_unitario

    def __str__(self):
        return f"{self.nome_material} - OS {self.ordem_servico.numero}"


class AuditoriaEvento(models.Model):
    TIPO_CHOICES = [
        ('configuracao_financeira_pix', 'Configuracao financeira PIX'),
        ('vinculo_user_morador', 'Vinculo User/Morador'),
        ('pedido_ingresso_status', 'Status de pedido de ingresso'),
    ]

    tipo = models.CharField(max_length=60, choices=TIPO_CHOICES)
    descricao = models.CharField(max_length=255)
    entidade = models.CharField(max_length=80, blank=True, default='')
    entidade_id = models.PositiveIntegerField(null=True, blank=True)
    dados = models.JSONField(blank=True, default=dict)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em', '-id']

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.criado_em:%d/%m/%Y %H:%M}"


def _registrar_auditoria_evento(*, tipo, descricao, entidade='', entidade_id=None, dados=None):
    AuditoriaEvento.objects.create(
        tipo=tipo,
        descricao=descricao,
        entidade=entidade,
        entidade_id=entidade_id,
        dados=dados or {},
    )


@receiver(pre_save, sender=ConfiguracaoFinanceira)
def _cache_configuracao_financeira_pix(sender, instance, **kwargs):
    anterior = None
    if instance.pk:
        anterior = sender.objects.filter(pk=instance.pk).values(
            'conta_principal_pix',
            'conta_recebimentos_pix',
            'conta_pagamentos_pix',
        ).first()
    instance._auditoria_pix_anterior = anterior


@receiver(post_save, sender=ConfiguracaoFinanceira)
def _auditar_configuracao_financeira_pix(sender, instance, created, **kwargs):
    novo = {
        'conta_principal_pix': instance.conta_principal_pix,
        'conta_recebimentos_pix': instance.conta_recebimentos_pix,
        'conta_pagamentos_pix': instance.conta_pagamentos_pix,
    }
    anterior = getattr(instance, '_auditoria_pix_anterior', None)
    if created:
        _registrar_auditoria_evento(
            tipo='configuracao_financeira_pix',
            descricao='Configuracao financeira PIX criada.',
            entidade='ConfiguracaoFinanceira',
            entidade_id=instance.id,
            dados={'anterior': None, 'novo': novo},
        )
        return

    if anterior and anterior != novo:
        _registrar_auditoria_evento(
            tipo='configuracao_financeira_pix',
            descricao='Configuracao financeira PIX alterada.',
            entidade='ConfiguracaoFinanceira',
            entidade_id=instance.id,
            dados={'anterior': anterior, 'novo': novo},
        )


@receiver(pre_save, sender=Morador)
def _cache_vinculo_morador_user(sender, instance, **kwargs):
    user_id_anterior = None
    if instance.pk:
        user_id_anterior = sender.objects.filter(pk=instance.pk).values_list('user_id', flat=True).first()
    instance._auditoria_user_id_anterior = user_id_anterior


@receiver(post_save, sender=Morador)
def _auditar_vinculo_morador_user(sender, instance, created, **kwargs):
    if created:
        return

    user_id_anterior = getattr(instance, '_auditoria_user_id_anterior', None)
    user_id_novo = instance.user_id
    if user_id_anterior == user_id_novo:
        return

    username_anterior = User.objects.filter(id=user_id_anterior).values_list('username', flat=True).first()
    username_novo = User.objects.filter(id=user_id_novo).values_list('username', flat=True).first()

    if user_id_anterior and user_id_novo:
        descricao = 'Vinculo User/Morador alterado.'
    elif user_id_novo:
        descricao = 'User vinculado a morador.'
    else:
        descricao = 'User desvinculado de morador.'

    _registrar_auditoria_evento(
        tipo='vinculo_user_morador',
        descricao=descricao,
        entidade='Morador',
        entidade_id=instance.id,
        dados={
            'morador_id': instance.id,
            'morador_nome': instance.nome,
            'user_id_anterior': user_id_anterior,
            'username_anterior': username_anterior,
            'user_id_novo': user_id_novo,
            'username_novo': username_novo,
        },
    )


@receiver(pre_save, sender=PedidoIngressoRock)
def _cache_status_pedido_ingresso(sender, instance, **kwargs):
    status_anterior = None
    if instance.pk:
        status_anterior = sender.objects.filter(pk=instance.pk).values_list('status', flat=True).first()
    instance._auditoria_status_anterior = status_anterior


@receiver(post_save, sender=PedidoIngressoRock)
def _auditar_status_pedido_ingresso(sender, instance, created, **kwargs):
    if created:
        return

    status_anterior = getattr(instance, '_auditoria_status_anterior', None)
    status_novo = instance.status
    if not status_anterior or status_anterior == status_novo:
        return

    _registrar_auditoria_evento(
        tipo='pedido_ingresso_status',
        descricao='Status do pedido de ingresso alterado.',
        entidade='PedidoIngressoRock',
        entidade_id=instance.id,
        dados={
            'pedido_id': instance.id,
            'evento_id': instance.rock_evento_id,
            'status_anterior': status_anterior,
            'status_novo': status_novo,
        },
    )
