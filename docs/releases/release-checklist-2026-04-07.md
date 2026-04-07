# Release checklist — 2026-04-07

## Contexto
- Ambiente de execução local: `/workspace/rpf`.
- Objetivo: executar checklist de release, rodar suíte de testes, smoke manual em páginas críticas e gerar changelog com impacto por área + rollback.

## Execução do checklist

### 1) Aplicar migrations em staging
**Status:** ⚠️ Bloqueado (sem acesso ao ambiente staging neste container).

**Evidências técnicas no ambiente local:**
- Tentativa de rodar migration local com `python manage.py migrate --noinput` falhou por versão Python ausente no pyenv (`3.12.7`).
- Nova tentativa com `PYENV_VERSION=3.12.12 python manage.py migrate --noinput` falhou por ausência de dependências (`ModuleNotFoundError: django`).
- Tentativa de instalar dependências com `PYENV_VERSION=3.12.12 python -m pip install -r requirements.txt` bloqueada por proxy/rede (`403 Forbidden` em `pypi`).

### 2) Validar fluxo PIX ponta a ponta
**Status:** ⚠️ Parcial (análise de fluxo em código concluída; execução E2E em staging bloqueada).

**Fluxo identificado em código:**
1. Compra iniciada em `comprar_rocks` cria `PedidoIngressoRock` com status `aguardando_pagamento`.
2. Quando há conta PIX de recebimento configurada, payload PIX é gerado e QR code é montado.
3. Confirmação do pagamento (`confirmar_pagamento`) marca pedido como `pago`, incrementa `quantidade_vendida` do lote e gera `IngressoRock`.

**Arquivos relevantes:**
- `core/views/legacy.py` (função `comprar_rocks`).
- `core/models.py` (`ConfiguracaoFinanceira`, `LoteIngressoRock`, `PedidoIngressoRock`, `IngressoRock`).

### 3) Validar gestão de usuários/moradores no admin
**Status:** ⚠️ Parcial (validação de regras em código concluída; smoke funcional em staging/admin pendente).

**Regras verificadas:**
- Tela `gerenciar_acessos` restrita a superusuário.
- Edição de permissões via formsets para `Morador` e `AcessoUsuario`.
- Vínculo usuário↔morador via `vinculo_morador_<user_id>` no POST.

### 4) Validar compra de ingressos por lote
**Status:** ⚠️ Parcial (regra de negócio validada em código; execução manual ponta a ponta pendente).

**Regras verificadas:**
- Form de compra impede pedido acima do disponível do lote.
- Confirmação de pagamento revalida disponibilidade antes de baixar saldo do lote.
- Registro de ingresso e atualização de quantidade de pessoas no evento.

## Suíte de testes e smoke tests manuais

### Suíte automatizada
**Status:** ⚠️ Não executada por limitação de ambiente.

**Tentativas executadas:**
- `python manage.py migrate --noinput` (falha de versão Python no pyenv).
- `PYENV_VERSION=3.12.12 python manage.py migrate --noinput` (falha por falta do Django).
- `PYENV_VERSION=3.12.12 python -m pip install -r requirements.txt` (falha de rede/proxy para baixar dependências).

### Smoke tests manuais em páginas críticas
**Status:** ⚠️ Não executados (sem aplicação em execução + sem staging acessível).

**Páginas críticas sugeridas para execução imediata no staging:**
- `/financeiro/` (Financeiro)
- `/rock/`, `/rock/comprar/`, `/rock/<evento_id>/lotes/`, `/rock/<evento_id>/ingressos/` (Rock)
- `/acessos/`, `/moradores/` (Admin)

---

## Changelog de release (impacto por área)

### Financeiro
- Fluxo de configuração financeira contém campos de contas PIX (`conta_principal_pix`, `conta_recebimentos_pix`, `conta_pagamentos_pix`) usados para instrução de pagamento em compra de ingressos.
- Rateio mensal depende de `calcular_rateio_financeiro` e das entidades de ajuste/desconto/pendência.

**Risco:** médio (afeta cobrança/comunicação de pagamento).

### Rock
- Compra por lote com criação de pedido (`PedidoIngressoRock`) e confirmação de pagamento com baixa de disponibilidade no lote.
- Geração automática de ingresso (`IngressoRock`) após pagamento confirmado.

**Risco:** alto (afeta venda e controle de capacidade).

### Admin
- Gestão de permissões por morador e por usuário sem vínculo de morador na tela de acessos.
- Vínculo manual usuário↔morador via formulário.

**Risco:** médio (afeta autorização/segurança funcional).

### Acessos
- Decorator `setor_required` com validação por grupo e permissões de visualizar/editar.
- Diferenciação entre acesso por método HTTP (GET vs POST para editar).

**Risco:** médio-alto (afeta exposição de módulos e edição indevida).

## Plano de rollback
1. **Banco de dados**
   - Fazer backup snapshot antes do deploy.
   - Em caso de incidente, restaurar snapshot do banco anterior à release.
2. **Aplicação**
   - Reverter para o commit/tag anterior estável.
   - Reexecutar coleta de estáticos e restart de serviços.
3. **Dados operacionais de Rock (vendas)**
   - Conferir pedidos criados no intervalo da release.
   - Se houver inconsistência, conciliar `PedidoIngressoRock`, `LoteIngressoRock.quantidade_vendida` e `IngressoRock`.
4. **Validação pós-rollback**
   - Smoke rápido: login, financeiro, compra rock, acessos/admin.
   - Validar ausência de erro 500 e integridade de permissões.

## Go/No-Go
**Recomendação atual: NO-GO** até:
- Executar migrations em staging.
- Rodar suíte de testes com dependências instaladas.
- Concluir smoke manual E2E dos fluxos listados.
