# Specs do sistema

## Stack e infraestrutura

- Django 6.x, SQLite, deployment local (rede domestica)
- Django Q2 para fila de tarefas em background
- Ollama (LLM local) para classificacao de e-mails
- django-allauth para autenticacao (tradicional + Google OAuth)
- Django templates como interface funcional inicial
- React como camada de apresentacao futura (projeto separado consumindo DRF)

---

## Usuarios e acesso

- Sistema multi-usuario com isolamento de dados pessoais
- Registro por e-mail/senha ou OAuth Google
- Tela de cadastro e login propria (nao so Admin)

### Soft delete de usuario
- `User` ganha campo `deleted_at` (DateTimeField nullable)
- Manager customizado filtra automaticamente usuarios e dados com `deleted_at` preenchido
- No momento da exclusao, usuario escolhe:
  - **Excluir tudo**: `JobApplication`, `EmailAccount`, `CandidateProfile`, `Notification`, `EmailSenderRule` recebem soft delete em cascata; `Job.directed_to` e `Company.created_by` viram null
  - **Manter dados globais**: so o `User` e marcado como deletado; `Job` e `Company` continuam acessiveis

---

## Modelos

### Company (global, compartilhada)
- `name`, `website`, `careers_page`, `notes`
- `created_by` FK → User (SET_NULL)
- `created_at`, `updated_at`
- Qualquer usuario pode criar, editar ou excluir
- **CompanyAuditLog**: `company`, `user`, `action` (criado/atualizado/excluido), `field_name`, `old_value`, `new_value`, `changed_at`

### Job / Vaga (global, compartilhada)
- `company` FK → Company (PROTECT)
- `role_title`, `source_url`, `location`, `remote`
- `directed_to` FK → User nullable (SET_NULL) — vaga direcionada a um usuario especifico
- `created_by` FK → User (SET_NULL)
- `created_at`
- Visivel para todos os usuarios com tag "Direcionada para [nome]" quando `directed_to` estiver preenchido
- Vagas geradas por e-mail nascem com `directed_to` apontando para o dono da conta de e-mail

### JobApplication / Candidatura (privada por usuario)
- `user` FK → User (CASCADE)
- `job` FK → Job (PROTECT)
- `status` choices: `draft`, `applied`, `confirmed`, `screening`, `interview`, `offer`, `rejected`, `withdrawn`, `archived`
- `origin` choices: `manual`, `email`, `external`
- `applied_at`, `last_status_at`
- `next_action_at`, `next_action_type` (choices: `follow_up`, `interview`, `send_document`, `await_response`, `other`), `next_action_description` (opcional)
- `notes`, `created_at`, `updated_at`

### ApplicationTimelineEntry
- `application` FK → JobApplication (CASCADE)
- `entry_type` choices: `manual_note`, `email_update`, `status_change`, `reminder`, `calendar_event`
- `title`, `description`, `occurred_at`, `created_at`
- Criada automaticamente quando: status muda, lembrete concluido, e-mail confirmado

### EmailAccount (privada por usuario)
- `user` FK → User (CASCADE)
- `provider` choices: `gmail`, `outlook`, `imap` (extensivel)
- `email_address`
- `access_token`, `refresh_token`, `token_expiry`
- `is_active`
- `scan_times` JSONField — lista de horarios (ex: `["00:00"]`), padrao meia-noite
- Usuario pode ter multiplas contas, inclusive do mesmo provedor

### EmailSenderRule (privada por conta de e-mail)
- `email_account` FK → EmailAccount (CASCADE)
- `company` FK → Company nullable
- `name`, `sender_email`, `sender_domain`
- `subject_keywords` JSONField — lista de palavras-chave no assunto
- `is_active`, `created_at`
- Logica de matching:
  - Somente remetente configurado → filtra por remetente, ignora assunto
  - Somente palavras-chave → busca em todos os e-mails pelo assunto
  - Remetente + palavras-chave → AND (ambos precisam bater)

### InboundEmail
- `message_id` (unique), `sender`, `subject`, `received_at`, `body_text`
- `matched_rule` FK → EmailSenderRule (SET_NULL)
- `application` FK → JobApplication nullable (SET_NULL)
- `processing_status` choices: `pending`, `classified`, `ignored`, `needs_review`
- `inferred_application_status`
- `created_at`

### EmailClassification
- `email` OneToOne → InboundEmail
- `confidence` (0-100)
- `summary`, `suggested_status`, `rationale`
- `reviewed_at`, `created_at`

### Notification (privada por usuario)
- `user` FK → User (CASCADE)
- `notification_type` choices:
  - `reminder_due` — proximo passo venceu (urgente)
  - `email_classified` — novo e-mail classificado (info)
  - `email_needs_review` — classificacao com baixa confianca (urgente)
  - `directed_job_detected` — nova vaga direcionada ao usuario (info)
  - `status_changed` — status de candidatura mudou automaticamente (info)
- `priority` choices: `urgent`, `info`
- `title`, `body`
- `related_application` FK → JobApplication nullable
- `is_read`
- `created_at`

---

## Pipeline de e-mail (Django Q2)

### Fila 1 — Varredura
- Agendada conforme `EmailAccount.scan_times` de cada conta
- Autentica via adaptador do provedor (`BaseEmailProvider`)
- Busca novos e-mails, filtra por `EmailSenderRule`
- Cria registros `InboundEmail` com status `pending`
- Enfileira cada e-mail na Fila 2

### Fila 2 — Classificacao Ollama
- Processa cada `InboundEmail` via Ollama (modelo local: Phi-3 mini ou Llama 3.2 3B)
- Gera `EmailClassification` com resumo, status sugerido, confianca e racional
- Tenta vincular ao `JobApplication` correto via analise do conteudo
- Se ambiguidade ou baixa confianca: `processing_status = needs_review`, notificacao urgente
- Se confianca alta e unica candidatura identificada: vincula automaticamente, notificacao informativa

### Tela de revisao de classificacoes
- Lista todos os e-mails classificados com: resumo Ollama, status sugerido, link para e-mail original
- Usuario pode editar a classificacao
- Usuario pode vincular manualmente a uma candidatura (dropdown)
- Botao "Confirmar e aplicar" → atualiza `JobApplication.status` + cria `ApplicationTimelineEntry`

### Tarefa periodica — Lembretes
- Django Q2 verifica `next_action_at` vencidos
- Cria `Notification` do tipo `reminder_due` para o usuario

---

## Adaptadores de provedor de e-mail

Padrao Strategy com interface abstrata:

```
BaseEmailProvider
  authenticate()
  fetch_messages(since, rules) -> List[RawMessage]
  revoke_access()

GmailAdapter(BaseEmailProvider)    # Fase 3, primeiro a implementar
OutlookAdapter(BaseEmailProvider)  # futuro
ImapAdapter(BaseEmailProvider)     # futuro
```

Novos provedores sao adicionados sem alterar o pipeline existente.

---

## LLM local (Ollama)

- Runtime: Ollama (`localhost:11434`)
- Modelo padrao: Phi-3 mini 3.8B ou Llama 3.2 3B
- Tarefas: classificacao de e-mail, identificacao de candidatura correspondente
- Mesmo padrao de adaptador — troca por API externa e possivel sem mudar o pipeline

---

## Autenticacao

- django-allauth
- Fluxo 1: registro com e-mail e senha
- Fluxo 2: "Entrar com Google" (OAuth2)
- Google OAuth serve tambem para autorizar acesso ao Gmail no fluxo de email_ingestion

---

## Monitoramento

- View no Django Admin com:
  - Contagem de `InboundEmail` por `processing_status`
  - Tarefas pendentes, em execucao e com erro no Django Q2
  - Ultima execucao de varredura por `EmailAccount`

---

## Notificacoes

- Painel interno: sino com badge de nao lidas, prioridade visual para `urgent`
- Expansao futura: integracao com Google Calendar para lembretes de proxima acao

---

## Regras de negocio transversais

- `Company` e `Job` sao recursos globais sem dono exclusivo
- `JobApplication`, `CandidateProfile`, `EmailAccount`, `Notification` sao sempre filtrados pelo usuario logado
- Todos os modelos com dados de usuario usam Manager customizado que exclui registros de usuarios com `deleted_at` preenchido
- `CompanyAuditLog` e o unico historico completo de alteracoes de campo; outros modelos nao tem auditoria detalhada
- `JobApplication.origin` registra como a candidatura entrou no sistema (`manual`, `email`, `external`)
- E-mails podem ser vinculados retroativamente a candidaturas existentes na tela de revisao
