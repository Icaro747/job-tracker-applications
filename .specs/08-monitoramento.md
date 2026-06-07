# Monitoramento do pipeline

## Problema

O pipeline de e-mail roda em background, fora da visao do usuario. Sem nenhuma visibilidade, e impossivel saber se a varredura esta funcionando, se ha e-mails presos na fila, se o Ollama esta respondendo ou se algum passo falhou silenciosamente. Para um sistema que depende de processamento assincrono, algum nivel de observabilidade e indispensavel.

## Solucao

Um painel de monitoramento simples acessivel pelo Django Admin, sem ferramentas externas de observabilidade.

### O que o painel exibe

**Resumo do pipeline de e-mail**

- Contagem de e-mails por status: pendente, classificado, precisa revisao, ignorado
- Quantos e-mails foram processados nas ultimas 24 horas
- Quantos estao atualmente na fila de classificacao aguardando processamento

**Status das contas de e-mail**

- Para cada conta conectada: ultima execucao de varredura (data e hora), resultado (sucesso ou erro), proximo horario programado

**Fila do Django Q2**

- Tarefas pendentes: quantas aguardam execucao
- Tarefas em execucao: quantas estao sendo processadas agora
- Tarefas com falha: quantas falharam e aguardam retry ou intervencao
- Tarefas concluidas recentemente: historico das ultimas execucoes

**Saude do Ollama**

- Status de conectividade com o servico local do Ollama (acessivel ou inacessivel)
- Modelo ativo configurado

### Para que serve cada informacao

- **E-mails pendentes acumulados**: indica que a Fila 2 esta atrasada ou o Ollama esta offline
- **Tarefas com falha no Q2**: indica erro que precisa de atencao manual (ex: token expirado, Ollama fora do ar)
- **Ultima varredura ha muito tempo**: indica que o agendamento da Fila 1 nao esta executando
- **Ollama inacessivel**: explica por que e-mails estao presos em `pendente`

### Limitacoes intencionais

O painel de monitoramento nao e um sistema de APM completo. Nao ha graficos de series temporais, alertas por e-mail ou integracao com ferramentas como Grafana. O objetivo e apenas dar visibilidade minima suficiente para diagnosticar problemas evidentes sem sair do sistema.

## Entradas

- Estado atual do banco de dados (contagens de `InboundEmail` por status)
- Estado das tarefas no Django Q2
- Ping ao servico Ollama local

## Saidas

- Pagina no Django Admin com o resumo consolidado
- Numeros em tempo real (sem cache agressivo) para refletir o estado atual do pipeline
