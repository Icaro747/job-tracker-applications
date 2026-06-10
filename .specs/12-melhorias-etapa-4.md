# Melhorias da Etapa 4 — Confianca, Controle e Visibilidade

> Este documento **emenda** as specs [05-pipeline-email.md](05-pipeline-email.md) e
> [06-llm-classificacao.md](06-llm-classificacao.md). Onde houver conflito, **este
> documento prevalece** — em especial sobre o "limiar de confianca" da spec 06, cujo
> comportamento de aplicacao automatica e aqui revogado.

## Problema

A Etapa 4 foi construida e colocada em uso, e tres deficiencias de usabilidade
apareceram:

1. **A classificacao automatica presume verdade.** A partir de um nivel de
   confianca, o sistema tratava a inferencia do LLM como fato: aplicava o status
   da candidatura e ate criava empresa/vaga/candidatura sozinho, sem o usuario
   confirmar. Essa informacao "presumida" se propagava para outras telas como se
   fosse confirmada, corroendo a sensacao de controle.
2. **As telas de empresa e vaga escondem datas e o estado da candidatura.** Ao
   navegar empresa -> vaga, nao da para saber quando a vaga foi anunciada nem se
   (e quando) o proprio usuario se candidatou a ela.
3. **A candidatura nao mostra seus marcos.** A linha do tempo e uma lista
   achatada; falta enxergar de relance os momentos-chave: quando comecou, quando
   o anuncio chegou, quando a candidatura foi enviada e quando houve retorno (ou
   se esta aguardando).

## Principio que guia todas as mudancas

**O sistema nunca aplica nem cria nada automaticamente.** A classificacao do LLM
e sempre uma *sugestao*. "Status aplicado" e "vaga criada" passam a significar,
por definicao, *"o usuario confirmou"*. A confianca deixa de ser gatilho de acao
e vira apenas apoio visual para priorizar a revisao.

A entrega e dividida em **tres fatias** independentes, cada uma testavel e
revisavel sozinha (TDD obrigatorio, conforme `docs/tdd.md`).

---

## Fatia 1 — Fim do auto-aplicar + migracao + fila de revisao

### 1.1 Nada e aplicado automaticamente

A Fila 2 (`classify_email`) deixa de decidir o fluxo pela confianca. Toda
classificacao bem-sucedida:

- grava a `EmailClassification` (resumo, status sugerido, confianca, racional)
  **apenas como apoio**;
- marca o e-mail como `needs_review` (precisa revisao);
- **nunca** altera o status da candidatura nem chama `register_email_update`.

O ramo de "alta confianca" que vinculava e aplicava status sozinho e removido.

**Exemplo.** Chega um e-mail da Acme: *"Recebemos sua candidatura para Backend."*
O LLM classifica com 95% de confianca, status sugerido "Recebida pela empresa",
candidatura identificada = "Backend na Acme".

- **Antes:** o status da candidatura virava "Recebida pela empresa"
  automaticamente; um evento aparecia na timeline sem o usuario ter feito nada.
- **Agora:** o e-mail aparece na fila de revisao com a sugestao ("Recebida pela
  empresa", 95%, candidatura "Backend na Acme" ja pre-selecionada). O status so
  muda quando o usuario clica em **Confirmar e aplicar**.

### 1.2 Vaga nova detectada vira sugestao, nao registro

Quando o LLM detecta uma oportunidade nova (e-mail de recrutador sobre uma vaga
que ainda nao esta cadastrada), `_create_directed_job` **deixa de criar**
Empresa/Vaga/Candidatura. Isso e critico porque `Company` e `Job` sao recursos
**globais compartilhados** — criar a partir de um palpite do LLM poluiria os
dados de todos os usuarios.

Em vez disso, o e-mail aparece na fila de revisao como **"possivel vaga nova"**,
com os campos sugeridos pelo LLM pre-preenchidos (nome da empresa, cargo, link da
vaga). Apenas ao confirmar e que Empresa (reusada se ja existir), Vaga e
Candidatura rascunho sao criadas — vinculadas ao e-mail original.

**Exemplo.** Um recrutador escreve: *"Temos uma vaga de Designer na Globex, da uma
olhada: globex.com/jobs/123."* O LLM marca como oportunidade nova.

- **Antes:** o sistema ja criava a empresa "Globex" (global), a vaga "Designer" e
  uma candidatura rascunho — tudo sem revisao.
- **Agora:** aparece um cartao de revisao "Possivel vaga nova" com os campos
  *Empresa: Globex*, *Cargo: Designer*, *Link: globex.com/jobs/123* editaveis. O
  botao **Criar vaga e candidatura** materializa os registros so depois da
  confirmacao. Se o LLM errou, o usuario corrige os campos ou ignora.

### 1.3 Papel da confianca: ordenar e rotular

Como nada mais e aplicado automaticamente, a confianca passa a ter papel
puramente visual:

- a fila de revisao e **ordenada por confianca** (maior primeiro);
- cada item recebe um **selo** de faixa: alta / media / baixa (derivado do limiar
  configurado, que vira referencia visual, nao gatilho);
- **nada e escondido** — e-mails de baixa confianca continuam aparecendo, apenas
  no fim da lista.

**Exemplo.** A fila mostra, de cima para baixo: "Entrevista agendada" (92%, selo
*alta*), "Confirmacao de recebimento" (74%, selo *media*), "Newsletter de vagas"
(31%, selo *baixa*). O usuario prioriza pelo topo, mas ainda ve o item de 31%.

### 1.4 Migracao dos dados legados

Como a Etapa 4 ja rodou, existem dados criados/aplicados pelo comportamento
antigo. A identificacao e confiavel: **qualquer `InboundEmail` com
`processing_status = classified` e `classification.reviewed_at` nulo** veio do
caminho automatico (a confirmacao manual sempre preenche `reviewed_at`).

A migracao reabre esses e-mails na fila de revisao, com dois tratamentos:

**a) Status aplicado automaticamente em candidatura existente — manter e sinalizar.**
O status que ja foi gravado **nao e revertido** (nao reescrevemos historico). O
e-mail volta para `needs_review` com um aviso *"aplicado automaticamente —
confirme ou corrija"*.

> **Exemplo.** A candidatura "Backend na Acme" esta em "Recebida pela empresa"
> porque o sistema antigo aplicou sozinho. A migracao **mantem** "Recebida pela
> empresa", mas o e-mail correspondente reaparece na fila pedindo confirmacao. Se
> estiver certo, o usuario confirma; se errado, corrige o status manualmente.

**b) Vaga/candidatura criada do zero pelo LLM — manter e sinalizar para confirmar.**
Os registros (empresa, vaga, candidatura rascunho) **sao mantidos**, mas a
candidatura aparece marcada como *"criada automaticamente — confirme que e real
ou descarte"*. Um botao **Descartar** remove o rascunho da candidatura e, se
ficarem orfas (sem nenhuma outra candidatura apontando para elas), tambem a vaga
e a empresa criadas junto.

> **Exemplo.** O sistema antigo criou empresa "Globex" + vaga "Designer" +
> candidatura rascunho a partir de um e-mail. A migracao mantem tudo, mas exibe na
> candidatura o selo *"criada automaticamente — confirme ou descarte"*. Se o
> usuario descartar, a candidatura some; se "Globex" e "Designer" nao forem usadas
> por mais ninguem, somem tambem.

**Nota de implementacao.** O estado "candidatura nao confirmada" e *derivado*, sem
campo novo no modelo: e uma candidatura com `origin = email` + `status = draft`
ligada a um `InboundEmail` em `needs_review` com `reviewed_at` nulo.

---

## Fatia 2 — Candidatura: painel de marcos + avisos de pendencia

### 2.1 Painel de marcos

No topo da tela de detalhe da candidatura, acima da linha do tempo detalhada (que
permanece), um bloco **"Marcos"** mostra as datas-chave rotuladas. Quando um marco
ainda nao aconteceu, exibe "—" ou um texto de estado ("aguardando"):

| Marco | Fonte do dado | Quando nao ha |
|---|---|---|
| **Criada em** | `created_at` da candidatura | sempre existe |
| **Anuncio recebido em** | `received_at` do e-mail **mais antigo** vinculado a candidatura | oculto em candidaturas manuais (sem e-mail) |
| **Candidatura enviada em** | `applied_at` | "aguardando envio" |
| **Ultimo retorno em** | `occurred_at` do **ultimo evento de atualizacao por e-mail** | ver regra abaixo |
| **Proximo passo** | proxima acao ja existente (`next_action_*`) | "nenhum proximo passo definido" |

**Regra do retorno.** "Retorno" significa **resposta real da empresa**, ou seja,
um evento de atualizacao por e-mail (`email_update`). Se a candidatura esta em um
status aberto (enviada, recebida, triagem, entrevista) e **nenhum e-mail de
resposta** chegou depois do envio, o marco exibe *"Aguardando retorno desde
{data de envio}"*.

**Exemplo 1 (origem e-mail, com resposta).** Candidatura "Backend na Acme":

```
Marcos
  Criada em ............... 02/06/2026
  Anuncio recebido em ..... 01/06/2026   (e-mail "vaga aberta na Acme")
  Candidatura enviada em .. 02/06/2026
  Ultimo retorno em ....... 05/06/2026   (e-mail "agendamento de entrevista")
  Proximo passo ........... Entrevista em 12/06/2026 14:00
```

**Exemplo 2 (origem manual, aguardando).** Candidatura "Dados na Initech",
cadastrada a mao, status "Candidatura enviada", sem e-mail vinculado:

```
Marcos
  Criada em ............... 03/06/2026
  (Anuncio recebido — oculto, candidatura manual)
  Candidatura enviada em .. 03/06/2026
  Ultimo retorno em ....... Aguardando retorno desde 03/06/2026
  Proximo passo ........... nenhum proximo passo definido
```

### 2.2 Aviso de pendencia na candidatura

Quando existe um e-mail em `needs_review` ligado a candidatura, a tela de detalhe
exibe um aviso no topo — *"1 atualizacao de e-mail aguardando revisao"* — com acao
direta para a fila/cartao de revisao. Assim a pendencia aparece **tanto na fila
quanto no contexto da candidatura** onde ela importa.

**Exemplo.** O usuario abre "Backend na Acme" e ve, antes dos marcos, uma faixa:
*"1 atualizacao de e-mail aguardando revisao — Revisar agora"*. Ao clicar, vai
direto ao cartao de revisao daquele e-mail.

---

## Fatia 3 — Vaga: datas de anuncio + indicador "candidatei?"

### 3.1 Data de anuncio da vaga

O modelo `Job` ganha um campo opcional **`published_at`** ("data de anuncio /
publicacao") — quando a vaga foi anunciada no mundo real. Por ser propriedade
objetiva da vaga, e global (compartilhada), como o restante de `Job`. Pode ser
preenchida manualmente ou vir do e-mail no futuro.

A tela de detalhe da vaga passa a mostrar:

- **"Anunciada em {published_at}"** quando conhecida;
- **sempre** "Cadastrada no sistema em {created_at}", separando o mundo real do
  registro interno.

**Exemplo.**

```
Designer — Globex
  Anunciada em ............ 28/05/2026
  Cadastrada no sistema em  02/06/2026
  Local: Remoto · Link: globex.com/jobs/123
```

Se `published_at` nao estiver preenchida, a linha "Anunciada em" e omitida e
apenas "Cadastrada no sistema em" aparece.

### 3.2 Indicador "voce se candidatou?"

Na tela de detalhe da vaga, um indicador **por usuario** (a partir das
`JobApplication` do usuario para aquela vaga):

- **Se ja se candidatou:** *"Voce se candidatou em {applied_at ou created_at},
  status atual: {status}"*, com link para a candidatura. O botao "Candidatar-se"
  da lugar a esse link (nao oferece duplicar a candidatura).
- **Se ainda nao:** *"Voce ainda nao se candidatou"* + botao **Candidatar-se**.

Havendo mais de uma candidatura do usuario para a mesma vaga, considera-se a mais
recente.

**Exemplo (ja candidatado).**

```
Designer — Globex
  Voce se candidatou em 02/06/2026 · status atual: Triagem  [ver candidatura]
```

**Exemplo (nao candidatado).**

```
Designer — Globex
  Voce ainda nao se candidatou.  [ Candidatar-se ]
```

> **Escopo decidido.** O indicador aparece **somente na tela da vaga aberta**. A
> lista de vagas dentro da empresa continua exibindo apenas os titulos (sem selo
> por vaga). Caso a navegacao empresa -> lista de vagas se mostre confusa no uso,
> reavaliar a inclusao de um selo "candidatado / nao candidatado" por item.

---

## Entradas

- **Fila 2 (going-forward):** e-mail (remetente, assunto, corpo) + candidaturas
  abertas do usuario. Saida sempre `needs_review` + classificacao de apoio.
- **Confirmacao manual:** candidatura selecionada + status a aplicar (ja existente
  na tela de revisao); para "vaga nova", os campos pre-preenchidos editaveis.
- **Migracao:** identificacao automatica via `processing_status = classified` +
  `classification.reviewed_at` nulo. Sem entrada do usuario.
- **Vaga:** novo campo opcional `published_at`.

## Saidas

- Nenhuma alteracao de status ou criacao de empresa/vaga/candidatura sem
  confirmacao explicita do usuario.
- Fila de revisao ordenada por confianca, com selos de faixa.
- Dados legados reabertos na fila, sinalizados conforme o caso (status mantido /
  candidatura auto-criada com opcao de descartar).
- Tela de candidatura com painel de marcos e aviso de pendencia.
- Tela de vaga com datas de anuncio/cadastro e indicador de candidatura do
  usuario.

## Fora de escopo (continuam adiados para a Etapa 5)

- Notificacoes (modelo `Notification` e painel) — o gancho `notify` permanece
  no-op.
- Agendamento periodico (Django Q2) e monitoramento de fila.
- Preenchimento automatico de `published_at` a partir do e-mail.
