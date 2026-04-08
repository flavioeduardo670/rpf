# Processo de homologação e promoção para produção

## Objetivo
Padronizar a esteira de homologação antes de produção com gates obrigatórios de qualidade, segurança e operação.

## Pipeline CI/CD
Workflow versionado em `.github/workflows/homologacao.yml` com estágios:
1. `lint`
2. `testes`
3. `deploy_staging`
4. `migracoes_staging` (`migrate --noinput`)
5. `smoke_tests`

Também existe operação manual de `rollback_operacional` via `workflow_dispatch`.

## Variáveis e segredos obrigatórios
Configurar no repositório (GitHub Actions Secrets/Environment):
- `STAGING_SSH_HOST`
- `STAGING_SSH_USER`
- `STAGING_SSH_KEY`
- `STAGING_APP_PATH`
- `STAGING_VENV_ACTIVATE`
- `STAGING_APP_SERVICE`
- `STAGING_DJANGO_SETTINGS_MODULE`
- `STAGING_DJANGO_SECRET_KEY`
- `STAGING_DATABASE_URL`
- `STAGING_BASE_URL`
- `ROLLBACK_APP_COMMAND`
- `ROLLBACK_DB_COMMAND`

## Go/No-Go obrigatório
Antes de qualquer promoção para produção:
1. Criar arquivo da release a partir de `docs/releases/checklist-template.md`.
2. Anexar evidências obrigatórias de cada gate.
3. Coletar aprovações formais de Engenharia e Produto/Operações.
4. Registrar decisão final GO/NO-GO com data/hora.

Sem checklist preenchido + evidências, **não promover para produção**.
