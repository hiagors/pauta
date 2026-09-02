# Pauta — Requisitos v1 (linguagem de negócio)

> Este documento descreve **o que** o sistema faz, em linguagem de negócio.
> O **como** está em [`spec.md`](spec.md), que é a fonte para implementação.
> Onde os dois divergirem, o `spec.md` vence e este documento deve ser corrigido.

Escopo da v1: planejar quais frentes de trabalho o time toca, em quais sprints, com
quais squads e com quais pessoas. Nada além disso.

O que a v1 substitui: a aba `Planejamento` da planilha (o Gantt) e o controle mental
de fila.
O que a v1 **não** substitui ainda: `Sprints.md`, `Sprint_XX.md`, dailies e
biblioteca de prompts. Continuam como arquivos soltos.

---

## 1. Vocabulário

| Termo no sistema | O que é |
|---|---|
| **Projeto** | o agrupador maior: CRM, BNPL, API PIX, MICROCRÉDITO… Não é alocável por si só |
| **Iniciativa** | a frente de trabalho de verdade, dentro de um projeto. É **ela** que ocupa sprints. Ex.: no CRM — "Reestruturação V1", "Dispatch Service", "Backlog V2" |
| **Camada** | rótulo livre de uma iniciativa, quando faz sentido separar por área de atuação |
| **Membro** | liderado do time |
| **Squad** | agrupamento temporário de membros para atuarem juntos em uma frente |
| **Representante** | o membro de uma squad que faz a ponte |
| **Sprint** | ciclo de duas semanas, numerado. Unidade de tempo do planejamento |
| **Alocação** | a barra colorida: iniciativa × sprint × (squad **ou** membro). Uma iniciativa tem **um** responsável por sprint |

Uma iniciativa não é uma tarefa. É uma frente que ocupa capacidade por uma ou mais
sprints.

**Nada é fixo no código.** Projetos, iniciativas, membros, squads e sprints são todos
cadastrados na interface. Os nomes acima são exemplos reais do time, não valores de
enum.

---

## 2. Estrutura do trabalho

### Por que projeto e iniciativa são coisas diferentes

O CRM não é uma frente única. Hoje ele tem a reestruturação da V1 em andamento, o
Dispatch Service (o serviço unificado de disparo de mensagens de recuperação) e um
backlog para as versões seguintes ao lançamento da V1. São três frentes com
prioridades e cronogramas próprios, dentro do mesmo produto.

Então:

- **Projeto** é o agrupador. Carrega nome, descrição, cor e a flag de reserva de
  capacidade. Não tem status nem prioridade nem alocação.
- **Iniciativa** é a unidade de trabalho. Carrega prioridade, tamanho estimado,
  status e as alocações. É a linha do Gantt.
- Todo projeto tem pelo menos uma iniciativa. Ao cadastrar um projeto simples, o
  sistema já cria a primeira iniciativa com o mesmo nome — quem só tem uma frente
  não precisa pensar nisso.

### Cor

Cor é opcional e puramente estética: serve para agrupar visualmente as barras do
Gantt. Fica no **projeto**, para que a leitura vertical agrupe. Iniciativa sem cor
herda a do projeto; projeto sem cor usa uma cor neutra padrão.

---

## 3. Modelo de dados (visão de negócio)

### Projeto
`nome`, `descrição`, `cor` (opcional), `é reserva de capacidade` (sim/não), `ativo`.

### Iniciativa
`projeto`, `nome`, `camada` (opcional, texto livre), `descrição`,
`prioridade` (Alta | Média | Baixa), `tamanho estimado em sprints` (opcional),
`status`, `data de entrada`.

### Membro
`nome`, `nome curto`, `papel`, `ativo`.

Membro nunca é apagado de verdade — apagar quebraria o histórico. "Excluir" apenas
marca como inativo: ele sai dos seletores e continua nas alocações passadas.

### Squad
`nome`, `representante` (opcional), `ativo`.

A squad **não tem uma lista fixa de membros**. Quem está nela é definido sprint a
sprint (veja §4).

### Sprint
`número`, `data de início`, `data de fim`.

### Alocação
`iniciativa`, `sprint`, e **ou** uma `squad` **ou** um `membro`.

Uma linha por sprint ocupada. A reestruturação do CRM indo da Sprint 18 à 22 gera
cinco linhas. Isso deixa o Gantt trivial de renderizar e permite pausar uma
iniciativa no meio sem gambiarra.

Frentes grandes vão para uma squad. Trabalho pequeno pode ser alocado direto a uma
pessoa, sem criar squad de uma pessoa só.

---

## 4. Squad é um agrupamento com prazo

Squad existe para eu não ter que alocar demanda pessoa por pessoa. Frentes grandes
precisam de squad para fluir; trabalho pequeno não precisa.

Mas quem está na squad **muda ao longo do tempo**, e o sistema precisa registrar isso
por sprint. O caso real:

> A Emilie está no BNPL até a Sprint 19. A partir da Sprint 20 ela vai para o CRM,
> que já tem gente atuando desde o começo. A squad do CRM ganha um membro novo a
> partir da 20.

Isso **não** é um conflito. Na Sprint 19 a Emilie está no BNPL; na Sprint 20 está no
CRM. O sistema tem que distinguir as duas situações pela sprint, não por uma lista
estática de membros.

A regra dura: **um membro nunca está em duas squads na mesma sprint.** Se estiver, é
conflito e o sistema avisa.

---

## 5. Status da iniciativa

Seis status, e a ordem importa:

| Status | Significado |
|---|---|
| **Backlog** | trabalho que em algum momento será executado. Não está priorizado, não está em andamento, **não entra em nenhuma conta de capacidade** |
| **Planejado** | tem alocação em sprint, mas não começou |
| **Em andamento** | começou |
| **Despriorizado** | começou e foi parado. Não volta para o backlog |
| **Concluído** | terminou |
| **Cancelado** | não será feito |

Regras de transição:

- Ao receber a primeira alocação, `Backlog` vira `Planejado` (automático).
- Ao perder todas as alocações, `Planejado` volta para `Backlog` (automático).
- `Em andamento` → `Concluído`, `Cancelado` ou `Despriorizado` (manual).
- **Nada volta para `Backlog` depois de começar.** Uma iniciativa `Em andamento` que
  perde as alocações continua `Em andamento`; se for para ser parada, vai para
  `Despriorizado`, à mão.
- `Despriorizado` pode ser retomado para `Planejado` ou `Em andamento`.
- `Concluído` e `Cancelado` são finais.

A **tela de backlog** mostra exatamente as iniciativas com status `Backlog`.
`Despriorizado` tem lugar próprio e não se mistura com backlog.

---

## 6. Sprints

Sprint é a unidade de tempo. Serve para medir a duração das frentes e para separar o
planejamento por trimestre.

- Uma sprint começa em uma segunda e termina na sexta da semana seguinte — duas
  semanas de calendário, 11 dias entre início e fim.
- `data de início` e `data de fim` são a referência de trabalho. A quantidade de dias
  úteis dentro do intervalo varia: feriado é feriado, e o sistema não tenta adivinhar.
- Uma sprint nova começa depois do fim da anterior, pulando o fim de semana.
- O botão "criar próxima sprint" propõe início e fim seguindo esse padrão; as datas
  ficam editáveis.
- **Sprint não é excluída.** Ela é uma marcação de tempo; apagar reescreveria o
  passado e abriria buraco na numeração.
- A **sprint atual** é a de início mais recente que já passou. Se hoje cai numa folga
  entre duas sprints, a anterior continua sendo a atual — uma sprint só termina de
  verdade quando a próxima começa.

---

## 7. Requisitos funcionais

### RF1 — Cadastrar projetos e iniciativas
CRUD de projeto. Ao criar, o sistema cria a primeira iniciativa com o mesmo nome.
Dentro do projeto, CRUD de iniciativas. Iniciativa nasce em `Backlog`.

### RF2 — Cadastrar membros
CRUD de membro. "Excluir" é inativar.

### RF3 — Cadastrar squads
CRUD de squad, com representante opcional. Squad sem membro em uma sprint é
permitida (planejar antes de contratar), mas o sistema sinaliza.

### RF4 — Compor squads por sprint
Definir quem está em qual squad em qual sprint, aceitando períodos parciais. É aqui
que o caso da Emilie se resolve, e é aqui que o conflito fica visível antes de virar
alerta.

### RF5 — Cadastrar sprints
CRUD de sprint sem exclusão. Validar que as datas não se sobrepõem e que a numeração
é sequencial. Botão "criar próxima sprint".

### RF6 — Alocar iniciativas em sprints
Selecionar iniciativa, o intervalo de sprints (de X até Y) e o responsável — uma
squad ou uma pessoa. O sistema cria uma linha de alocação por sprint.

Regras:
- Uma iniciativa tem **um** responsável por sprint. Se duas squads estão na mesma
  frente na mesma sprint, elas deveriam ser uma squad só.
- Uma iniciativa pode ter squads diferentes em sprints diferentes.
- Alocar a mesma squad em mais de uma frente na mesma sprint é permitido, **com
  aviso**. Às vezes é de propósito.
- Se o intervalo pedido passa da última sprint cadastrada, o sistema aloca o que
  cabe e diz quais sprints faltam criar.

### RF7 — Tela de backlog
Iniciativas com status `Backlog`, excluindo as de projetos de reserva de capacidade.

- Ordenável por prioridade, tamanho e data de entrada.
- Ação direta de alocar, abrindo o mesmo diálogo do RF6.
- Contador no topo: quantas iniciativas aguardando e quantas sprints de trabalho elas
  somam, com aviso de quantas estão sem estimativa.

### RF8 — Tela de planejados
Duas visualizações do mesmo dado, com alternador:

**Grade (o Gantt).** Linhas = iniciativas, agrupadas por projeto. Colunas = sprints.
Barra colorida cobre o intervalo, com o nome da squad (ou da pessoa) dentro. É a
planilha atual, gerada em vez de desenhada. A janela padrão é o **trimestre civil
corrente** (jan–mar, abr–jun, jul–set, out–dez), derivado da data de hoje.

**Lista.** Por iniciativa: projeto, camada, prioridade, responsável, sprint inicial,
sprint final, status.

Em ambas, filtro por squad e por sprint, persistido na URL.

---

## 8. Reserva de capacidade (o caso SUS)

O SUS é trabalho sob demanda: sustentação. Ele é cadastrado como um projeto normal,
mas com a flag **reserva de capacidade** ligada.

Um projeto com essa flag:

- aparece na grade com tratamento visual distinto (faixa hachurada, não bloco sólido);
- **não** trava a pessoa: quem está no SUS pode estar em outra frente na mesma sprint
  sem gerar sobrecarga nem conflito;
- não conta para o alerta de squad sobrecarregada nem para o de conflito de membro;
- não aparece no backlog nem soma nas contas de capacidade.

A flag é ligável e desligável no cadastro do projeto. Não é um caso especial escondido
no código — é configuração.

---

## 9. Alertas

O que justifica sair da planilha. São quatro, calculados, não configuráveis na v1.
**Alerta é aviso visual, nunca bloqueio** — às vezes eu vou querer sobrecarregar de
propósito.

| Alerta | Condição | Peso |
|---|---|---|
| **Squad sobrecarregada** | squad em mais de uma frente na mesma sprint | atenção |
| **Conflito de membro** | membro em duas squads na mesma sprint, em frentes diferentes | atenção |
| **Membro sem alocação** | membro ativo sem nenhuma frente numa sprint atual ou futura | informativo |
| **Squad sem membro** | squad com alocação numa sprint, mas sem ninguém dentro naquela sprint | informativo |

Frentes de projeto com reserva de capacidade são desconsideradas nos dois alertas de
atenção.

### Silenciar

O conflito conhecido e intencional (a Bianca em duas frentes) grita em toda sprint.
Sem silenciamento, o painel perde valor em uma semana.

Silenciar exige um motivo em texto, é reversível, e o painel mostra os silenciados
atrás de um contador expansível com o motivo visível. O silenciamento não se perde
quando um terceiro projeto entra na mesma sprint.

---

## 10. Persistência e sincronização

> Os requisitos não-funcionais numerados (`RNF1`…) vivem no `spec.md` §9. Aqui ficam
> em prosa de propósito, para as duas numerações não divergirem.

Como a v1 só tem dado estruturado, sem conteúdo narrativo, o banco é a fonte da
verdade e o Markdown é saída.

- SQLite local, arquivo único, fora da pasta sincronizada.
- A cada alteração, exportar um snapshot em texto para a pasta sincronizada:
  um `.json` por entidade e um `plan-sprint-XX.md` com a grade renderizada. Texto
  sincroniza sem conflito binário; o `.sqlite` não.
- Importar de volta a partir do snapshot, para reconstruir o banco em outra
  máquina ou após perda. Isso é restauração, não integração.
- Uso individual, offline, sem autenticação, sem chamada externa.
- **Sem importação de planilha ou CSV.** Todo dado entra pela interface do
  próprio sistema. Sem carga inicial automática e sem `seed`.

---

## 11. Fora do escopo da v1

Não é "nunca", é "não agora". Fica registrado para o modelo de dados não fechar a
porta:

- Dailies, reportes por pessoa e itens de acompanhamento (bloqueios, decisões, riscos).
- Planejamento semanal com Big Bets e Quick Wins.
- Vínculo com os `.md` de reunião e biblioteca de prompts.
- Demandas ou tarefas dentro da iniciativa, e board kanban.
- Capacidade em horas, férias e ausências.
- Calendário de feriados.
- Dependência entre iniciativas.
- Integrações com LLM para transformar relatório de reunião em tarefas.
- Importação de planilha.

O que a v1 deixa preparado: ID estável em projeto, iniciativa e sprint, para que
dailies e demandas possam referenciá-los depois sem migração.

---

## 12. O que ainda não está decidido

Três pontos menores, com a premissa que vale até haver decisão. A versão completa,
com o impacto de cada um, está no `spec.md` §16.

1. **Trimestre.** A grade abre no trimestre civil. Se o time usa trimestre fiscal
   deslocado, muda o default.
2. **Volume do alerta "membro sem alocação".** Hoje ele olha da sprint atual até a
   última cadastrada, sem teto. Pode virar ruído; o corte natural seria a sprint
   atual mais as duas seguintes.
3. **Membro inativado com composição em sprint futura.** Hoje ele simplesmente
   desaparece dos alertas e a composição fica no histórico. Não há aviso.
