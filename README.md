# RPF — Gestão da República Portão dos Fundos

Sistema web (Django) para a gestão da república: moradores e acessos, financeiro
(rateio do aluguel, contas da casa, prestação de contas, cobranças PIX via
Mercado Pago), compras, almoxarifado, manutenção (ordens de serviço), rocks
(eventos, lotes e ingressos), reuniões com atas e calendário.

## Rodando localmente

Requisitos: Python 3.12.

```bash
python -m venv venv
# Linux/macOS: source venv/bin/activate
# Windows:     venv\Scripts\activate
pip install -r requirements-dev.txt

cp .env.example .env            # ajuste os valores (veja abaixo)
export DJANGO_DEBUG=True        # Windows PowerShell: $env:DJANGO_DEBUG="True"
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Com `DJANGO_DEBUG=True` o sistema usa SQLite (`db.sqlite3`) e uma chave de
desenvolvimento. Para acessar pela rede da casa no Windows há o script
`scripts/runserver-lan.ps1`.

> O banco `db.sqlite3`, a pasta `media/` e os logs **não** são versionados.
> Nunca faça commit de dados reais, senhas ou arquivos `.env`.

## Testes

```bash
python manage.py test
# com cobertura:
coverage run --rcfile=.coveragerc manage.py test && coverage report
```

Antes de abrir um PR, confira também se não faltam migrações:

```bash
python manage.py makemigrations --check --dry-run
```

## Estrutura

| Caminho | Conteúdo |
| --- | --- |
| `rpf/` | Configurações do projeto (settings, urls, logging) |
| `core/models.py` | Modelos de todos os módulos |
| `core/views/` | Views separadas por módulo (financeiro, rock, estoque, …) |
| `core/services/` | Regras de negócio reutilizáveis (rateio, PIX, PDF, estoque) |
| `core/templates/core/` | Templates HTML |
| `core/tests/` | Testes automatizados |
| `scripts/` | Utilitários (auditoria de mídia, Apps Script, servidor na LAN) |
| `docs/` | Operação, observabilidade e checklists de release |

## Identidade visual

O visual segue o manual de redes sociais e a apresentação de rebranding
(preto, branco e o dourado `#DEAB2C` do chopp; Montserrat; logo da porta com o
boneco de formatura; fundo cinza quadriculado e menu em pílulas no topo). O
boneco animado de cada seção, a transição pela porta e a página inicial estão
descritos em
[`docs/identidade-visual.md`](docs/identidade-visual.md).

## Produção

Variáveis de ambiente, segurança, estáticos/mídia e backup estão em
[`README_PRODUCAO.md`](README_PRODUCAO.md). Pipeline de homologação em
[`docs/releases/README.md`](docs/releases/README.md).
