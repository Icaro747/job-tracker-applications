# Revisao orientada a intencao — multiplas vagas por e-mail

> Este documento **emenda** as specs [05-pipeline-email.md](05-pipeline-email.md),
> [06-llm-classificacao.md](06-llm-classificacao.md) e
> [12-melhorias-etapa-4.md](12-melhorias-etapa-4.md). Onde houver conflito sobre o
> fluxo de revisao, **este documento prevalece**. Mantem o principio da emenda 12:
> *o sistema nunca aplica nem cria nada automaticamente*.

## Problema

A tela `Revisao de classificacoes` assume **um e-mail = uma intencao**: ela sempre
mostra o mesmo `select Candidatura` + `Aplicar status`, independentemente do que o
e-mail realmente e. Isso quebra em casos reais:

1. **Atualizacao sem candidatura para vincular.** Um e-mail "sua candidatura a
   Dev .NET na UDS foi rejeitada" chega para uma candidatura que existe no mundo
   real (o usuario se candidatou pelo site da empresa) mas **nao** esta no sistema.
   O botao `Confirmar e aplicar` retorna HTTP 200, nao faz nada e nao da feedback —
   um "clique sem efeito" (ver `docs/flow-issues/2026-06-11-revisao-sem-candidatura-vinculavel.md`).
2. **Varias vagas num unico e-mail.** Um e-mail de lista/newsletter (ex.: Gupy,
   "5 vagas para voce") traz varias vagas, de **uma ou varias empresas**. O modelo
   atual guarda **uma** vaga sugerida (`EmailClassification.suggested_company_name`
   / `suggested_role_title` / `suggested_source_url`); as demais nao tem onde
   existir.

A causa comum: o fluxo nao reconhece **a intencao** do e-mail nem suporta
**multiplas oportunidades** por e-mail.

## Principio que guia as mudancas

A classificacao do LLM continua sendo **sempre sugestao** (emenda 12). O que muda:
o LLM passa a sugerir tambem **qual a intencao** do e-mail e **uma lista** de
oportunidades. A intencao escolhe qual fluxo de revisao o usuario ve, mas o usuario
pode **corrigir a intencao** e nada se materializa sem confirmacao explicita.

A entrega e dividida em **tres fatias** independentes, cada uma testavel sozinha
(TDD obrigatorio, conforme `docs/tdd.md`).

---

## Conceitos

### As quatro intencoes

Todo e-mail em revisao pertence a **uma** destas intencoes (sugerida pelo LLM,
corrigivel pelo usuario):

| Intencao | O que e | Acao ao confirmar |
|---|---|---|
| **Atualizacao de candidatura** | Resposta de um processo (recebida, triagem, entrevista, rejeicao) | Vincula a candidatura e aplica o status |
| **Nova oportunidade unica** | Recrutador direciona **uma** vaga ao usuario | Cria Vaga + candidatura rascunho |
| **Lista de oportunidades** | Newsletter/lista com **N** vagas, de uma ou varias empresas | Cria, por item escolhido, **apenas a Vaga** |
| **Irrelevante / informativo** | Nao representa processo nem vaga | Marca o e-mail como ignorado |

> **A "lista" unifica o caso multi-empresa.** Nao ha intencao separada para "varias
> vagas da mesma empresa" vs "de varias empresas": cada vaga extraida carrega a
> **propria empresa**, entao um unico modelo cobre os dois. "Nova oportunidade
> unica" e, estruturalmente, uma lista de tamanho 1 com intencao distinta (vem
> direcionada e gera candidatura).

### Modelo de dados

**Nova tabela filha — uma linha por vaga detectada.**

`EmailDetectedOpportunity` representa **uma** vaga extraida de um e-mail. Um e-mail
de lista com 5 vagas gera 5 linhas; um e-mail de oportunidade unica gera 1 linha.

| Campo | Tipo | Proposito |
|---|---|---|
| `classification` | FK → `EmailClassification` | E-mail/classificacao de origem |
| `company_name` | char | Empresa sugerida (editavel na revisao) |
| `role_title` | char | Cargo sugerido (editavel) |
| `source_url` | url | Link da vaga (opcional) |
| `state` | choices | `pending` / `created` / `dismissed` |
| `job` | FK → `Job` (null) | Vaga materializada ao confirmar (reuso se ja existir) |
| `application` | FK → `JobApplication` (null) | Candidatura materializada, quando houver |

O **estado por linha** permite processar a lista aos poucos: criar 2 vagas, ignorar
1 e deixar 2 pendentes, com rastreabilidade de qual `Job`/candidatura nasceu de
cada item.

**Novo campo na classificacao — intencao confirmada.**

`EmailClassification.reviewed_intent` (char/choices, em branco ate a revisao) guarda
a intencao que o **usuario** confirmou no assistente. Distinto da intencao
*sugerida* pelo LLM — registra sugerido-vs-confirmado para auditoria e faz o cartao
reabrir no passo certo.

**Campos removidos.** `EmailClassification.suggested_company_name`,
`suggested_role_title`, `suggested_source_url` e `is_new_opportunity` saem do
modelo — seu conteudo migra para uma linha de `EmailDetectedOpportunity` (ver
Fatia 1, migracao). A vaga sugerida deixa de ser um campo unico e vira "a primeira
(e talvez unica) linha filha".

### Contrato do LLM

`ClassificationResult` (em `email_ingestion/classifiers/base.py`) passa a expor:

- `intent`: enum das quatro intencoes (sugestao);
- `opportunities`: `list[DetectedOpportunity]` (zero, uma ou varias).

Substitui `is_new_opportunity: bool` e `opportunity: DetectedOpportunity | None`.
`application_id` (candidatura existente identificada) permanece, usado pela intencao
de **atualizacao**. O classificador Ollama (`classifiers/ollama.py`) e seu prompt
sao atualizados para emitir a intencao e a lista; trocar de LLM continua sendo so
uma nova subclasse, sem tocar no pipeline.

### Assistente de revisao — duas etapas

O cartao de revisao deixa de ser um formulario unico e vira um assistente de **dois
passos** (parciais HTMX), que abre no palpite do LLM:

**Passo 1 — Confirmar a intencao.** Mostra a intencao sugerida e permite trocar
entre as quatro. Ao confirmar, grava `reviewed_intent` e avanca.

**Passo 2 — Acao da intencao confirmada:**

- **Atualizacao:** `select` de candidatura + `select` de status.
  - Quando **nenhuma candidatura casa**, oferece **"Criar candidatura a partir
    deste e-mail, ja com o status sugerido"** — materializa Empresa/Vaga/Candidatura
    (reusando se ja existir) com origem externa e aplica o status (ex.: rejeitada).
    Resolve o beco-sem-saida do caso UDS: e historia real, so nao estava registrada.
- **Nova oportunidade unica:** campos editaveis (Empresa, Cargo, Link) e o botao
  **Criar vaga e candidatura** — materializa **Vaga + candidatura rascunho**, como
  no fluxo atual da emenda 12.
- **Lista de oportunidades:** lista de sub-itens (uma vaga por linha) com selecao;
  **Criar marcadas** materializa **apenas a `Job`** de cada item (a candidatura nao
  e criada — ver regra abaixo), **Ignorar tudo** descarta os pendentes. Cada
  criacao roda o aviso de duplicacao por item (Fatia 4 da emenda 12 — reusar ou
  criar assim mesmo).
- **Irrelevante:** confirma e marca o e-mail como ignorado.

Reabrir um e-mail meio-processado cai direto no passo 2 da intencao gravada (nao
reconfirma a intencao a cada visita).

### Regras transversais

- **Lista cria so a Vaga; unica cria Vaga + candidatura.** Numa lista/newsletter o
  usuario normalmente ainda **nao** se candidatou a nada — criar candidaturas
  rascunho poluiria a lista de candidaturas com vagas apenas anotadas. Cada item de
  lista materializa so a `Job` (global); a tela da vaga ja mostra "Voce ainda nao se
  candidatou · [Candidatar-se]" (emenda 12, Fatia 3), e o usuario se candidata
  depois, so nas que interessam. Ja a oportunidade **unica direcionada** gera a
  candidatura rascunho.
- **Conclusao derivada.** O e-mail sai de `needs_review` **somente quando todas as
  suas linhas filhas estao em estado terminal** (`created` ou `dismissed`). Sobrou
  `pending` → continua na fila. Nao ha botao "concluir revisao": evita que um e-mail
  "concluido" esconda vagas que o usuario nem olhou. Para intencoes de candidatura
  unica (atualizacao / nova unica), a conclusao segue marcando `reviewed_at` como
  hoje.
- **Feedback inline, HTTP 200.** Quando uma acao nao pode ser executada (falta
  candidatura, falta empresa), o endpoint **mantem HTTP 200** e re-renderiza o
  cartao com uma **faixa de erro dentro dele**. Nao usa 400: o HTMX por padrao nao
  faz swap em respostas de erro, o que reintroduziria o "clique sem efeito". O
  framework de `messages` global do Django nao serve aqui porque o HTMX troca so o
  cartao.
- **Proveniencia.** Todo registro materializado pela revisao grava `source_email`
  (emenda 12, Fatia 4), inclusive as `Job` criadas a partir de itens de lista.

---

## Fatia 1 — Fim do beco-sem-saida + intencao unica

Entrega o esqueleto sem o multi-vaga, ja resolvendo a maior parte da dor.

- Modelo `EmailDetectedOpportunity` + campo `EmailClassification.reviewed_intent`.
- **Migracao de dados (sem re-classificar pelo LLM).** Para cada
  `EmailClassification` que tinha oportunidade sugerida (`is_new_opportunity`),
  cria **uma** linha filha carregando os `suggested_*`; o estado e derivado (ja ha
  candidatura ligada → `created`; senao → `pending`). `reviewed_intent` e inferido
  (tem `application` → atualizacao; tinha oportunidade → nova unica; senao em
  branco, decide-se na revisao). Em seguida remove os campos `suggested_*` e
  `is_new_opportunity`. E-mails antigos **nao** sao reenviados ao LLM — apenas
  reorganizados; o contrato novo vale daqui para frente.
- Assistente de duas etapas para as intencoes **atualizacao**, **nova unica** e
  **irrelevante** (tratando lista como tamanho 1).
- **Criacao retroativa** na intencao de atualizacao quando nao ha candidatura.
- **Erro inline** (HTTP 200) substituindo o `messages` global no fluxo parcial.

## Fatia 2 — Multiplas vagas por e-mail

- Contrato do LLM (`ClassificationResult`) passa a retornar `intent` + lista de
  `opportunities`; `classifiers/ollama.py` e o prompt atualizados.
- `classify_email` grava **N** linhas `EmailDetectedOpportunity` e o `reviewed_intent`
  sugerido.
- Passo 2 da intencao **lista**: sub-itens com selecao, **Criar marcadas** (so
  `Job`), **Ignorar tudo**, e o aviso de duplicacao por item.
- Conclusao derivada do e-mail a partir do estado das linhas filhas.

## Fatia 3 — Polimento

- Selos/rotulos de intencao na fila de revisao; ordenacao mantida por confianca
  (emenda 12, Fatia 1.3).
- Bloco de origem (emenda 12, Fatia 4) refletindo as `Job` criadas via item de
  lista.
- Ajustes finos de copy e estados vazios do assistente.

---

## Entradas

- **Fila 2 (going-forward):** e-mail + candidaturas abertas do usuario. Saida:
  `needs_review` + `EmailClassification` (intencao sugerida) + N linhas
  `EmailDetectedOpportunity`.
- **Revisao manual:** intencao confirmada (passo 1) + acao da intencao (passo 2):
  candidatura/status, campos de vaga editaveis, ou selecao de itens da lista.
- **Migracao:** reorganizacao dos dados existentes, sem entrada do usuario e sem LLM.

## Saidas

- Nenhuma alteracao de status ou criacao sem confirmacao explicita (mantido da
  emenda 12).
- Cartao de revisao que se adapta a intencao, sem "clique sem efeito".
- E-mails com varias vagas representados como N oportunidades, processaveis item a
  item.
- Vagas de lista materializadas sem candidatura; candidatura criada so na
  oportunidade unica ou pelo botao da vaga.
- E-mail resolvido apenas quando todos os itens estao em estado terminal.

## Fora de escopo

- Deteccao por similaridade fuzzy / merge de duplicatas (segue como na emenda 12:
  apenas aviso normalizado na criacao).
- Preenchimento automatico de candidaturas a partir de itens de lista.
- Notificacoes, agendamento periodico (Q2) e monitoramento — continuam na Etapa 5.
