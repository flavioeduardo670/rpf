# Checkup técnico — novembro/2026

Resultado: a suíte de testes saiu de **20 falhas em 94** (e banco de testes que
nem chegava a ser criado) para **108 testes passando**, tanto com
`DJANGO_DEBUG=True` quanto no modo da CI (`DEBUG=False`). O repositório caiu de
~89 MB para ~1,5 MB.

## ⚠️ Ações manuais necessárias

1. **Antes de dar `git pull` nesta mudança, faça backup do seu `db.sqlite3` e da
   pasta `media/`.** Eles deixaram de ser versionados, e o git apaga do disco os
   arquivos removidos do repositório quando você atualiza.
2. **Trocar a senha do usuário `Panda`**: ela ficou em texto puro no histórico
   do `anotações.txt` (commits de março/2026), e o repositório é público.
3. O `db.sqlite3` que estava publicado continha 14 usuários (com hash de senha) e
   sessões ativas. Se esse banco foi usado em algum servidor, trocar as senhas e
   a `DJANGO_SECRET_KEY` (que também invalida as sessões).
4. Para apagar esses dados também do **histórico** do GitHub é preciso reescrever
   o histórico (`git filter-repo`) e fazer force push — decisão do dono do repo.
5. Em produção, conferir se `MERCADOPAGO_WEBHOOK_SECRET` está configurada: sem
   ela, o webhook de pagamento agora é recusado (antes aceitava qualquer um).
6. Mídia local no Render é apagada a cada deploy (disco efêmero). Comprovantes e
   PDFs de atas só ficam seguros com `DJANGO_MEDIA_BACKEND=s3`.

## Bugs corrigidos

| Área | Problema | Correção |
| --- | --- | --- |
| Migrações | `models.py` e migrações fora de sincronia (`AtaTopico.texto` não existia no banco; colunas antigas obrigatórias bloqueavam gravação de participantes/tópicos) | Nova migração `0066`, idempotente, que copia `titulo_assunto`/`desenvolvimento` para `texto` sem perder dados |
| Migrações | `0057` usava SQL exclusivo do PostgreSQL (`ADD COLUMN IF NOT EXISTS`), quebrando SQLite e o banco de testes | Reescrita de forma portátil e idempotente |
| Migrações | `0021` criava 14 moradores reais em **qualquer** banco novo | Só roda em bancos que já têm moradores |
| Permissões | Membros de grupo (ex.: "Financeiro") entravam no módulo mas viam tudo em "somente visualização" e recebiam 403 em ações | `can_edit` passou a considerar o grupo, igual ao `setor_required` |
| PIX | Webhook recusava notificações legítimas: usava o id do corpo no manifesto da assinatura quando `data.id` não vinha na URL | Manifesto segue o padrão do Mercado Pago |
| PIX (segurança) | Sem `MERCADOPAGO_WEBHOOK_SECRET`, qualquer POST podia marcar aluguel/ingresso como pago | Recusado fora do `DEBUG` |
| Atas | "PDF" da ata era texto puro com extensão `.pdf` (não abria) | PDF real, com abertura, participantes, tópicos, 5W2H e encerramento |
| Atas | POST em ata já registrada → erro 500 | Mensagem e redirecionamento |
| Atas | Download de PDF ausente do disco → erro 500 | Mensagem e redirecionamento |
| Rock | PDF da lista de ingressos cortava tudo após ~47 nomes | Gerador com várias páginas e quebra de linha |
| Financeiro | `mes_referencia` ausente/inválido no POST → erro 500 | Leitura tolerante com fallback |
| Login | Não havia como sair do sistema | Rota `/logout/` e botão "Sair" na barra superior |
| Atas | PDF da ata registrada saía com "Status: Rascunho" | Status atualizado antes de gerar o PDF |
| Financeiro | Título "Financeiro" quase invisível (texto escuro na faixa escura) | Cor do título corrigida |
| Favicon | Apontava para um upload em `media/` (404 em produção e no S3) | Aponta para `core/brand/favicon.svg` |

## Testes e CI

- Testes quebravam por infraestrutura: storage com manifest exigia `collectstatic`, e o
  `SECURE_SSL_REDIRECT` transformava toda resposta em 301 no modo CI. Ambos
  ajustados só para `manage.py test`.
- Teste de "marcadores de conflito" acusava comentários `# =====`; agora só
  detecta marcadores reais.
- Três testes do financeiro tinham expectativas que nunca bateram com o código
  (verificado no histórico); foram alinhados à regra atual
  (aluguel + ajuste + pendência).
- Uploads dos testes iam para `media/` do projeto; agora vão para pasta temporária.
- Hash de senha rápido nos testes (suíte ~10× mais rápida).
- Novo `core/tests/test_checkup_correcoes.py` com testes de regressão.

## Infraestrutura

- `rpf/settings.py`: bloco de e-mail duplicado removido; Sentry só é importado
  quando há `SENTRY_DSN`; `RENDER_EXTERNAL_HOSTNAME` entra em `ALLOWED_HOSTS`;
  `/healthz` isento do redirect HTTPS; cabeçalhos `nosniff`, `Referrer-Policy` e
  `X-Frame-Options: DENY`; `conn_health_checks` no banco.
- CI (`.github/workflows/homologacao.yml`): variáveis mínimas para o `check`
  rodar; verificação de migrações faltando; cache do pip; `collectstatic` no
  deploy; reinício do serviço só **depois** do `migrate`; smoke test em `/healthz`.
- `requirements-dev.txt` separado (coverage fora da produção).
- `core/services/pdf.py`: gerador de PDF único para financeiro, rock e atas.
- README reescrito em UTF-8 (o anterior estava em UTF-16 e aparecia como
  binário no GitHub); `.env.example` e `README_PRODUCAO.md` atualizados.

## Arquivos removidos do repositório

`venv/` (ambiente virtual do Windows, 81 MB), `db.sqlite3`, `media/`, `logs/`,
`__pycache__/`, `anotações.txt`, `gestãorpf.txt` e
`scripts/generate_security_pdf.py` (gerador avulso de relatório, dependia de
reportlab, que não está nos requirements). A tabela legada `core_ataacao5w2h`
foi mantida no banco, só saiu do código.

## Novo visual (nov/2026)

Todas as páginas foram refeitas com a identidade do manual de redes sociais:
menu lateral preto com o boneco de cada seção, títulos no estilo dos stories,
roleta de imagens na página inicial e a transição do boneco entrando pela
porta. Detalhes em [`identidade-visual.md`](identidade-visual.md). Nova
migração `0067_slide_inicio` (imagens da roleta).
