# Release Checklist Template (Go/No-Go)

> Copie este template para um arquivo de release (ex.: `docs/releases/release-YYYY-MM-DD.md`) e preencha **todas** as evidências.

## Metadados da release
- Release ID:
- Data/hora (UTC):
- Commit SHA:
- Responsável técnico:
- Aprovadores (mín. 2):
- Ambiente alvo para promoção: produção

## Gate 1 — CI/CD (homologação)
- [ ] Lint aprovado.
  - Evidência obrigatória (link run / print / log):
- [ ] Testes automatizados aprovados.
  - Evidência obrigatória:
- [ ] Deploy staging aprovado.
  - Evidência obrigatória:
- [ ] `python manage.py migrate --noinput` executado em staging sem erro.
  - Evidência obrigatória:
- [ ] Smoke tests em staging aprovados.
  - Evidência obrigatória:

## Gate 2 — Validação funcional e operacional
- [ ] Fluxos críticos validados (login, financeiro, compras/PIX, acessos/admin).
  - Evidência obrigatória:
- [ ] Métricas e logs sem erro crítico após deploy em staging.
  - Evidência obrigatória:
- [ ] Plano de rollback revisado para esta release.
  - Evidência obrigatória:
- [ ] Backup/snapshot de banco confirmado antes de produção.
  - Evidência obrigatória:

## Gate 3 — Aprovação Go/No-Go (obrigatória)
- [ ] **GO** aprovado por Engenharia.
  - Nome + data/hora + evidência:
- [ ] **GO** aprovado por Produto/Operações.
  - Nome + data/hora + evidência:
- [ ] Decisão final registrada como **GO** ou **NO-GO**.
  - Decisão:
  - Justificativa:

## Plano de rollback operacional desta release

### 1) Rollback de aplicação
- Tag/commit estável de retorno:
- Comando operacional:
- Responsável:
- Critério de acionamento:

### 2) Procedimento de banco de dados
- Tipo de rollback (restore snapshot / rollback lógico / reversão manual):
- Comando/procedimento:
- Janela máxima para execução:
- Risco de perda de dados e plano de mitigação:

### 3) Validação pós-rollback
- [ ] Aplicação retornou com healthcheck 200.
- [ ] Fluxos críticos executados com sucesso.
- [ ] Integridade de dados validada.
- Evidências:

## Evidências anexadas
- Links para logs da pipeline:
- Links para dashboards/monitoramento:
- Links para tickets/incidentes relacionados:
