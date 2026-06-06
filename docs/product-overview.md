# Visao do produto

## Problema

Candidaturas de emprego geram muitas interacoes repetitivas: acompanhar e-mails, lembrar proximas etapas, atualizar status manualmente e preencher os mesmos dados pessoais/profissionais em varios sites.

## Solucao

A solucao tera dois blocos principais:

1. Gerenciamento de candidaturas: centraliza empresas, vagas, status, historico, e-mails recebidos, lembretes e eventos.
2. Auxilio de preenchimento de formularios: usa dados pre-salvos do curriculo para sugerir valores em campos repetitivos durante uma candidatura.

## Principios da primeira versao

- Priorizar funcionamento simples antes de interface sofisticada.
- Usar Django Admin como painel operacional inicial.
- Organizar o dominio para futura exposicao via API.
- Manter integracoes externas desacopladas para evoluir por etapas.

## Usuarios

O usuario principal e uma pessoa buscando emprego que quer acompanhar candidaturas e reduzir tarefas repetitivas.

## Resultado esperado

O usuario deve conseguir saber rapidamente onde esta cada candidatura, quais e-mails foram recebidos, qual a proxima acao e quais dados do curriculo podem ser reutilizados em formularios.
