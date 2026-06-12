# Revisao de classificacao sem candidatura vinculavel

Data do registro: 2026-06-11

## Contexto

Na tela `Revisao de classificacoes`, o card do e-mail:

> Sua candidatura a Desenvolvedor .Net na UDS Tecnologia

aparece com status sugerido `rejected` e botao `Confirmar e aplicar`.

Ao clicar no botao, a requisicao HTMX retorna HTTP 200, mas a tela nao da
feedback visivel e nenhum registro e criado ou atualizado em candidatura, vaga
ou empresa.

## Comportamento observado

- O card envia `POST` para `/email/revisao/<id>/confirmar/`.
- O backend retorna `200`.
- O card permanece visualmente igual.
- Nenhuma candidatura, vaga ou empresa relacionada a UDS Tecnologia e criada.
- Nenhuma linha do tempo de candidatura e registrada.
- O usuario nao ve mensagem de erro na tela.

## Evidencias tecnicas

Estado local observado para o e-mail da UDS:

- `InboundEmail.id = 13`
- `processing_status = needs_review`
- `application_id = None`
- `inferred_application_status = rejected`
- `EmailClassification.suggested_status = rejected`
- `EmailClassification.is_new_opportunity = False`
- `EmailClassification.reviewed_at = None`
- usuario `clientadmin` sem candidaturas cadastradas
- nenhuma `Company`, `Job` ou `JobApplication` contendo `UDS`

Arquivos relevantes:

- `email_ingestion/templates/email_ingestion/_review_row.html`
  - O formulario `Confirmar e aplicar` usa `hx-post` para o endpoint
    `email_ingestion:email_confirm` e troca apenas o card.
  - O formulario sempre mostra o select `Candidatura`, mesmo quando nao ha
    candidatura disponivel.
- `email_ingestion/views.py`
  - `email_confirm_apply` so aplica a classificacao se houver uma candidatura
    selecionada ou ja vinculada ao e-mail.
  - Quando nao ha candidatura, a view registra a mensagem de erro "Selecione uma
    candidatura antes de confirmar." e retorna o mesmo parcial com HTTP 200.
- `templates/base.html`
  - As mensagens globais sao renderizadas no layout completo.
  - Como o HTMX substitui apenas o card, a mensagem global nao aparece no fluxo
    parcial.

## Diagnostico

O sistema esta tratando o e-mail como atualizacao de uma candidatura existente,
mas nao existe candidatura vinculada nem candidatura disponivel para selecao.

O endpoint nao falha tecnicamente. Ele recusa aplicar sem candidatura, registra a
mensagem de erro no framework de mensagens do Django e devolve o parcial com
HTTP 200. Como essa mensagem nao e renderizada dentro do card, a recusa fica
invisivel para o usuario.

## Problema de produto

O select de candidatura nao representa todos os tipos de e-mail que chegam ao
fluxo de revisao.

Hoje a tela mistura pelo menos quatro intencoes diferentes:

1. Atualizacao de candidatura existente.
2. Nova oportunidade unica.
3. Lista ou newsletter com varias vagas.
4. E-mail irrelevante ou informativo.

O card da UDS caiu em um estado sem saida visivel: foi classificado como
atualizacao de candidatura existente, mas nao havia nenhuma candidatura para
atualizar.

## Impacto

- O usuario entende que o botao nao funciona.
- O console mostra sucesso HTTP 200, o que dificulta o diagnostico.
- A classificacao permanece pendente em `needs_review`.
- O usuario nao sabe se deve criar uma candidatura, ignorar o e-mail ou corrigir
  a classificacao.
- E-mails com varias vagas ou oportunidades genericas podem ser forcados para um
  modelo de "uma candidatura alvo", mesmo quando essa relacao nao existe.

## Perguntas abertas

- A revisao deveria pedir primeiro a intencao do e-mail antes de mostrar campos
  especificos?
- Para e-mails sem candidatura vinculada, quais acoes devem aparecer?
  - Vincular a candidatura existente.
  - Criar candidatura a partir deste e-mail.
  - Criar apenas vaga/oportunidade sem candidatura.
  - Marcar como lista de oportunidades.
  - Ignorar.
- Como representar e-mails que contem varias vagas?
  - Uma classificacao com varias oportunidades extraidas?
  - Um registro de newsletter/lista separado de `JobApplication`?
  - Criacao manual assistida de varias `Job` sem criar candidaturas?
- Um e-mail de rejeicao sem candidatura previa deveria permitir criar uma
  candidatura retroativa ja como `rejected`?
- O endpoint de confirmacao deveria retornar erro HTTP 400 quando faltar
  candidatura, ou manter HTTP 200 com erro inline no card?

## Possiveis caminhos de solucao

### Curto prazo

- Mostrar erro inline no proprio card quando o usuario clicar em `Confirmar e
  aplicar` sem candidatura selecionada.
- Desabilitar ou esconder `Confirmar e aplicar` quando nao houver candidatura
  vinculada nem opcoes no select.
- Exibir uma mensagem clara: "Nao ha candidatura vinculada. Vincule uma
  candidatura, crie uma nova a partir deste e-mail ou ignore."

### Medio prazo

- Separar visualmente os fluxos de revisao por tipo de e-mail:
  - atualizar candidatura existente;
  - criar nova vaga/candidatura;
  - revisar lista de oportunidades;
  - ignorar.
- Permitir que o usuario altere a intencao sugerida pelo LLM dentro do card.

### Longo prazo

- Evoluir o contrato do classificador para retornar multiplas oportunidades
  quando o e-mail for uma lista de vagas.
- Criar um modelo ou fluxo proprio para "oportunidades recebidas" que ainda nao
  sao candidaturas.
- Revisar a nomenclatura da tela para deixar claro que nem toda revisao aplica
  status em uma candidatura.

## Criterio para considerar resolvido

O usuario nao deve conseguir cair em um clique sem efeito visivel. Para qualquer
e-mail em revisao, a tela precisa deixar claro:

- o que o sistema acha que o e-mail representa;
- qual acao sera executada ao confirmar;
- por que a acao nao pode ser executada, quando faltar informacao;
- quais alternativas existem para concluir ou descartar a revisao.
