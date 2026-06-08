# Visao geral do sistema

## Problema

Pessoas em processo de busca de emprego enfrentam tres problemas recorrentes:

1. Perda de controle sobre candidaturas abertas — nao sabem em qual etapa estao, o que foi enviado e quando agir novamente.
2. Retrabalho de preenchimento — os mesmos dados pessoais e profissionais sao digitados repetidamente em diferentes formularios.
3. Volume de comunicacao por e-mail — e-mails de RH e recrutadores chegam dispersos, sem contexto da candidatura correspondente.

## Solucao

Um sistema centralizado de gerenciamento de candidaturas com dois blocos funcionais principais:

**Bloco 1 — Gerenciamento de candidaturas**
Centraliza empresas, vagas, status, historico, e-mails recebidos, lembretes e proximas acoes em um unico lugar.

**Bloco 2 — Auxilio de preenchimento**
Usa dados pre-salvos do curriculo do candidato para sugerir valores em campos de formularios externos durante uma candidatura.

## Principios arquiteturais

- Funcionamento correto antes de interface sofisticada.
- Integrações externas desacopladas via padrão Adapter — cada provedor e substituivel sem alterar o nucleo.
- Dados pessoais estritamente isolados por usuario; dados publicos (empresas, vagas) compartilhados globalmente.
- LLM como ferramenta de apoio, nao de decisao — o usuario sempre tem a palavra final.
- Sem dependencias externas obrigatorias de infraestrutura; tudo deve rodar localmente.

## Restricoes tecnicas

- Deployment local em rede domestica (sem cloud).
- LLM roda na mesma maquina (Ollama); sem custo de API por e-mail processado.
- Banco de dados SQLite — suficiente para o volume esperado (poucos usuarios, centenas de candidaturas).
- Interface inicial em Django templates; migracao futura para React sem reescrever a logica de negocio.

## Stack de decisoes

| Camada | Escolha | Motivo |
|---|---|---|
| Backend | Django 6.x | ORM, Admin, ecosistema maduro |
| Banco | SQLite | Local, zero configuracao |
| Fila de tarefas | Django Q2 | Usa o proprio banco, sem Redis |
| LLM | Ollama local | Sem custo, privacidade, baixo volume |
| Auth | django-allauth | Suporte a social login nativo |
| Frontend inicial | Django templates | Funcional rapido, sem build pipeline |
| Frontend futuro | React (projeto separado) | Consumira a mesma API DRF |

## Etapas de construcao

```
Etapa 1 — Base: usuarios, autenticacao, modelos de empresa/vaga/candidatura
Etapa 2 — Operacao manual: CRUD completo via templates, timeline, lembretes
Etapa 3 — E-mail: contas, regras de varredura, adaptador Gmail, pipeline de processamento
Etapa 4 — LLM: classificacao Ollama, fila de classificacao, tela de revisao
Etapa 5 — Notificacoes: painel interno, tarefas periodicas de lembrete
Etapa 6 — Monitoramento: dashboard de fila e saude do pipeline
Etapa 7 — Autofill: consulta de dados do curriculo durante candidatura
Etapa 8 — API + React: exposicao via DRF, migracao do frontend
```
