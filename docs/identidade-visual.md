# Identidade visual do sistema

O visual segue o **Manual Completo de Redes Sociais** e a **apresentação de
rebranding** ("Insta da Portão"):

- **Logo:** a porta e o boneco de formatura correndo para ela com o chopp na
  mão (pictograma de "saída de emergência"). Assinatura: "REPÚBLICA" em peso
  leve e "PORTÃO DOS FUNDOS" em negrito.
- **Cores:** preto `#000000` e branco `#FFFFFF` como base; destaque dourado
  `#DEAB2C` (o chopp). O dourado aparece pouco: botão principal, item ativo do
  menu, subtítulos e os objetos do boneco.
- **Tipografia:** **Montserrat** (fonte oficial) em todo o sistema. Os
  subtítulos usam um itálico serifado (Crimson Text), no papel da fonte
  "Elegant" dos stories.
- **Estilo dos stories:** título de cada página em blocos pretos com letra
  branca e subtítulo logo abaixo.
- **Layout limpo:** títulos curtos, espaço em branco, painéis com contorno
  preto fino e sem sombras.
- **Fundo dos slides:** cinza-claro `#F0F0F0` com a grade quadriculada
  (`#DEDEDE`), como na apresentação. Menu em pílulas com contorno no topo,
  etiquetas pequenas em caixa alta espaçada e rodapé com "✦ RPF ✦" e a data.

As fontes estão em `core/static/core/fonts/` (licença OFL, arquivos `OFL-*.txt`).

## O boneco animado (vídeos)

O cabeçalho de cada seção mostra o boneco do logo fazendo a ação da seção, em
loop, a partir dos vídeos feitos no Canva. Os arquivos ficam em
`core/static/core/boneco/loop-<seção>.webp`: boneco **preto**, caneca com as
cores do chopp e **fundo transparente**, sem cartão nem camada, direto sobre o
quadriculado.

| Seção | Loop |
| --- | --- |
| Início | corre e passa pelo portão dos fundos |
| Moradores | três moradores chegam pela porta e acenam |
| Financeiro | conta as notas e joga uma moeda |
| Compras | empurra o carrinho de compras |
| Almoxarifado | empilha as caixas |
| Ordens de serviço | martela o prego na bancada |
| Rocks | dança com o chopp entre as notas musicais |
| Reuniões | fala na mesa da reunião |
| Calendário | vira a folha e marca o dia |
| Meu perfil | faz pose com o chopp |

Acessos e Configurações ainda não têm vídeo e continuam com a ação em SVG
(abaixo). Para trocar um loop, gere um WebP animado com fundo transparente e o
mesmo nome, e atualize largura e altura em `LOOPS`
(`core/context_processors.py`). Seções fora de `LOOPS` usam o SVG.

## O boneco em SVG

É o boneco do logo, redesenhado como um **esqueleto articulado** (quadril,
tronco, cabeça, ombros, cotovelos e joelhos), sempre virado para a esquerda,
para a porta. Assim ele muda de pose de verdade, e os objetos ficam presos às
mãos na posição certa.

Ele é usado nos ícones do menu e dos atalhos, na troca de página e no
cabeçalho das seções sem vídeo.

| Seção | O que ele faz na ação em SVG |
| --- | --- |
| Início | corre para a porta com o chopp (o logo) |
| Moradores | chega de mochila e acena para a casa |
| Financeiro | anda com o saco de dinheiro e joga uma moeda |
| Compras | empurra o carrinho, que vai na frente |
| Almoxarifado | carrega uma caixa com as duas mãos |
| Ordens de serviço | ajoelhado, de capacete, bate no cano com a chave inglesa |
| Rocks | vira o chopp, inclinando a cabeça a cada gole |
| Reuniões | sentado, escreve a ata na prancheta |
| Calendário | aponta para o calendário |
| Meu perfil | tira uma selfie (com flash) |
| Acessos | encaixa a chave e o cadeado abre |
| Configurações | empurra uma engrenagem, que gira |

Cada seção tem quatro desenhos em `core/static/core/boneco/`:

- `acao-<seção>-preto.svg`: a ação animada do cabeçalho. Toca três vezes ao
  abrir a página e para na pose final. Passar o mouse ou clicar repete.
- `icone-<seção>-{preto,branco}.svg`: o boneco correndo com o objeto, usado no
  menu e nos atalhos da página inicial.
- `corrida-<seção>.svg`: a cena da troca de página (abaixo).

Os desenhos **não são editados à mão**: eles saem do gerador
`scripts/boneco/` (`esqueleto.py` = proporções e articulações, `poses.py` =
objetos, `cenas.py` = pose de cada seção e ciclo de corrida). Para mudar uma
pose ou um objeto, edite esses arquivos e rode:

```bash
python3 scripts/boneco/gerar_boneco.py
```

O gerador também cria a marca (`marca-preto.svg`, `marca-branco.svg`), o
favicon e as ilustrações padrão da roleta.

## Troca de página: o boneco entra pela porta

Ao clicar num link interno, o boneco da página de destino entra correndo pela
direita (ciclo de corrida de 8 quadros, com pernas, braços e quadril em
movimento), levando o objeto da seção, e entra pela porta, que se fecha atrás
dele. Na página nova, a porta abre e a página aparece. A ida leva menos de um
segundo.

- Cenas: `core/static/core/boneco/corrida-*.svg` e `porta-abrindo.svg`
  (animações dentro do próprio SVG, pré-carregadas quando o navegador está
  ocioso).
- Código: `core/static/core/ui/rpf.shell.js` e `rpf.boneco.css`.
- Downloads, PDFs, exportações e o admin não animam.
- Quem ativa **"reduzir movimento"** no sistema operacional não vê a animação.
- Para um link específico não animar, use o atributo `data-sem-transicao`.

## Página inicial

A página inicial abre com a saudação ("Bom dia", "Boa tarde" ou "Boa noite"
e o nome da pessoa), a data, o próximo rock e a próxima reunião, os botões
"Abrir financeiro" e "Ver calendário" (para quem tem acesso) e o boneco do
início em loop. Abaixo, "Por onde a gente começa?" mostra as seções em blocos
numerados: Financeiro em dourado, Rocks em preto e Calendário em branco
ocupam dois espaços.

> A roleta de fotos saiu da página inicial. O cadastro *Imagens da roleta*
> continua no Admin, com as fotos guardadas, mas elas não aparecem mais.
