# Candidaturas

## Problema

O processo de candidatura a uma vaga e dinamico: passa por diversas etapas ao longo do tempo, envolve comunicacoes externas, exige acoes do candidato em momentos especificos e pode comecar por caminhos diferentes (manual, e-mail recebido, formulario externo). O sistema precisa representar esse processo de forma que o usuario saiba, a qualquer momento, onde cada candidatura esta e o que precisa fazer a seguir.

## Solucao

O modelo de candidatura representa o processo individual de um usuario em relacao a uma vaga. Cada usuario tem suas proprias candidaturas, completamente isoladas das de outros usuarios.

### Origem da candidatura

Uma candidatura pode entrar no sistema por tres caminhos:

- **Manual**: o usuario cria diretamente, informando a vaga e os dados do processo. Usado quando o usuario se candidatou por fora do sistema (LinkedIn, site da empresa, indicacao, telefone) ou quando quer registrar algo que ja aconteceu.
- **E-mail**: criada automaticamente pelo sistema quando um e-mail de recrutador ou empresa e detectado e classificado. O sistema cria a vaga e a candidatura em rascunho, vinculadas ao e-mail original.
- **Externo**: candidatura iniciada em plataforma externa sem e-mail correspondente no sistema. Funciona como manual, mas com a origem registrada para fins de rastreabilidade.

Esse campo de origem e imutavel apos a criacao — registra como o processo comeou, nao como esta.

### Ciclo de vida e status

Toda candidatura possui um status que reflete o momento atual do processo seletivo:

```
Rascunho → Candidatura enviada → Recebida pela empresa → Triagem →
Entrevista → Oferta → [fim: Rejeitada | Retirada | Arquivada]
```

O status pode ser avancado manualmente pelo usuario ou atualizado automaticamente pelo sistema quando um e-mail classificado confirma uma mudanca de etapa.

### Proxima acao

O usuario define o que precisa fazer a seguir em cada candidatura. Cada proxima acao tem:

- **Data e hora**: quando a acao deve ocorrer
- **Tipo**: categoria pre-definida que descreve a natureza da acao
  - Follow-up (retomar contato)
  - Entrevista (participar de entrevista agendada)
  - Enviar documento (enviar curriculo, portfolio, certificado, etc.)
  - Aguardar retorno (sem acao ativa, apenas monitorar)
  - Outro (para casos nao mapeados)
- **Descricao**: texto livre opcional para detalhar o que exatamente deve ser feito

Quando a data vence, o sistema gera uma notificacao urgente para o usuario. Apos concluir a acao, o usuario marca como realizada e o sistema registra automaticamente na linha do tempo.

### Linha do tempo

Toda candidatura tem uma linha do tempo cronologica de eventos. Cada evento registra o que aconteceu, quando aconteceu e como foi originado. Os tipos de evento sao:

- **Nota manual**: texto livre registrado pelo usuario
- **Atualizacao por e-mail**: e-mail recebido e vinculado a esta candidatura
- **Mudanca de status**: transicao de um status para outro, com o valor anterior e o novo
- **Lembrete**: proxima acao concluida ou dispensada
- **Evento de calendario**: integracao futura com agenda externa

A linha do tempo e append-only — eventos nao sao editados ou removidos, apenas adicionados.

## Entradas

**Para criar candidatura manual**:
- Vaga (obrigatorio)
- Status inicial (rascunho ou candidatura enviada)
- Data de envio (opcional)
- Proxima acao: data, tipo, descricao (opcional)
- Observacoes gerais (opcional)

**Para atualizar status**: novo status selecionado pelo usuario ou confirmado a partir de classificacao de e-mail

**Para registrar proxima acao**: data, tipo obrigatorio, descricao opcional

**Para concluir proxima acao**: confirmacao do usuario; descricao do que foi feito (opcional)

## Saidas

- Candidatura visivel apenas para o usuario dono
- Status atual sempre visivel no painel
- Proxima acao com data e tipo exibidos com destaque
- Notificacao gerada automaticamente quando proxima acao vence
- Entrada na linha do tempo criada automaticamente para cada evento relevante
- Candidatura com origem registrada e imutavel
