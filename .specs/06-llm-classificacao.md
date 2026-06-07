# Classificacao por LLM (Ollama)

## Problema

E-mails de processos seletivos chegam em formatos e linguagens muito variados. Identificar se um e-mail e uma rejeicao, um convite para entrevista, uma confirmacao de recebimento ou um pedido de documento exige compreensao de linguagem natural — algo que regras fixas por palavras-chave nao resolvem de forma confiavel. Ao mesmo tempo, usar uma API de LLM em nuvem geraria custo por e-mail processado e dependencia de servico externo.

## Solucao

Uso de um modelo de linguagem rodando localmente via **Ollama**, sem custo de API e sem envio de dados para servicos externos.

### Escolha do modelo

O modelo precisa ser leve o suficiente para rodar em hardware domestico comum (8GB de RAM ou mais), mas capaz de compreender portugues e classificar texto com contexto. Modelos recomendados:

- **Phi-3 mini (3.8B)**: muito leve, bom para classificacao de texto curto
- **Llama 3.2 3B**: alternativa leve com bom desempenho em portugues

O modelo usado e configuravel pelo usuario ou administrador da instancia.

### O que o LLM recebe

Para cada e-mail a ser classificado, o sistema monta um contexto contendo:

- Remetente do e-mail
- Assunto do e-mail
- Corpo do e-mail (texto plano)
- Lista de candidaturas abertas do usuario (empresa, cargo, status atual) — para ajudar na identificacao de qual processo aquele e-mail pertence

### O que o LLM deve retornar

O modelo e instruido a retornar uma resposta estruturada com:

- **Resumo**: descricao breve do conteudo do e-mail em linguagem clara para o usuario
- **Status sugerido**: qual etapa do processo seletivo aquele e-mail representa (`entrevista`, `rejeitada`, `confirmacao de recebimento`, `pedido de documento`, etc.)
- **Confianca**: nivel de certeza da classificacao, de 0 a 100
- **Racional**: explicacao curta do motivo da classificacao
- **Candidatura identificada**: qual das candidaturas abertas e a mais provavel destinataria deste e-mail (se identificavel)

### Limiar de confianca

O sistema usa o nivel de confianca para decidir o fluxo automatico:

- **Confianca alta** (acima do limiar configurado, padrao 80): o e-mail e vinculado automaticamente a candidatura identificada e o status e aplicado; o usuario recebe notificacao informativa.
- **Confianca baixa** (abaixo do limiar): o e-mail fica aguardando revisao manual; o usuario recebe notificacao urgente para revisar.

O limiar e configuravel. Isso permite que usuarios mais ou menos conservadores ajustem o comportamento do sistema sem alterar o codigo.

### Abstracao do LLM

O acesso ao Ollama segue o mesmo padrao de adaptadores usado para provedores de e-mail. O sistema nao conhece diretamente o Ollama — ele conhece um contrato de classificacao. Isso significa que substituir o Ollama por uma API externa (ex: Claude, OpenAI) no futuro e possivel sem alterar o pipeline, apenas trocando o adaptador de LLM.

### Falha do Ollama

Se o Ollama estiver offline ou retornar erro durante o processamento de um e-mail, o e-mail permanece com status `pendente` e uma nova tentativa e agendada. O pipeline nao trava — os demais e-mails da fila continuam sendo processados.

## Entradas

- E-mail (remetente, assunto, corpo)
- Lista de candidaturas abertas do usuario (contexto para identificacao)
- Limiar de confianca configurado

## Saidas

- Classificacao estruturada: resumo, status sugerido, confianca, racional, candidatura identificada
- Decisao automatica de vinculacao (alta confianca) ou encaminhamento para revisao (baixa confianca)
- Em caso de falha: reagendamento da tarefa, sem interrupcao do restante da fila
