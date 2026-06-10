# .specs — Especificacoes do sistema

Documentacao arquitetural do Gerenciador de Candidaturas. Cada arquivo descreve um dominio funcional: o problema que resolve, como funciona, entradas e saidas esperadas. Sem codigo — apenas comportamento e estrutura.

## Indice

| Arquivo | Conteudo |
|---|---|
| [00-visao-geral.md](00-visao-geral.md) | Visao do produto, principios, restricoes tecnicas, stack de decisoes e etapas de construcao |
| [01-usuarios-autenticacao.md](01-usuarios-autenticacao.md) | Multi-usuario, cadastro, login, Google OAuth, soft delete com exclusao seletiva |
| [02-empresas-vagas.md](02-empresas-vagas.md) | Recursos globais compartilhados, auditoria de empresa, vagas direcionadas, separacao vaga x candidatura |
| [03-candidaturas.md](03-candidaturas.md) | Ciclo de vida, status, origem, proxima acao, linha do tempo |
| [04-contas-email.md](04-contas-email.md) | Contas de e-mail por usuario, adaptadores de provedor, regras de varredura e logica de matching |
| [05-pipeline-email.md](05-pipeline-email.md) | Fila de varredura, fila de classificacao, tela de revisao, vinculacao retroativa, vaga potencial por e-mail |
| [06-llm-classificacao.md](06-llm-classificacao.md) | Ollama local, modelo recomendado, estrutura da classificacao, limiar de confianca, abstracao de LLM |
| [07-notificacoes.md](07-notificacoes.md) | 5 tipos de notificacao, prioridades, painel interno, tarefa periodica de lembretes |
| [08-monitoramento.md](08-monitoramento.md) | Dashboard de fila no Admin, saude do pipeline, status do Ollama |
| [09-perfil-candidato.md](09-perfil-candidato.md) | Dados do curriculo, experiencias, formacao, competencias, respostas salvas |
| [10-modelos-dados.md](10-modelos-dados.md) | Referencia completa de todos os modelos: campos, tipos, restricoes e proposito de cada campo |
| [11-integracao-google-gmail.md](11-integracao-google-gmail.md) | Configuracao burocratica do Google Cloud, Gmail API, OAuth, verificacao e seguranca |
| [12-melhorias-etapa-4.md](12-melhorias-etapa-4.md) | Emenda a Etapa 4: fim do auto-aplicar (tudo vira sugestao), painel de marcos da candidatura, datas/indicador na vaga, migracao de dados legados |

## Etapas de construcao

```
Etapa 1 — Base
  Usuarios, autenticacao (django-allauth), modelos de empresa/vaga/candidatura

Etapa 2 — Operacao manual
  CRUD via Django templates, timeline, proxima acao, notificacoes internas

Etapa 3 — E-mail
  Contas de e-mail, adaptador Gmail, regras de varredura, Fila 1

Etapa 4 — Classificacao LLM
  Ollama, Fila 2, tela de revisao, aplicacao de status

Etapa 5 — Automacao
  Tarefas periodicas Q2, lembretes automaticos, monitoramento

Etapa 6 — Autofill
  Consulta de perfil durante candidatura, interface de sugestao

Etapa 7 — API + React
  Django REST Framework, projeto React separado
```
