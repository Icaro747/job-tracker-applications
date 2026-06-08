# Modelos de dados

Referencia completa de todas as entidades do sistema: campos, tipos, restricoes e proposito de cada um. Nenhum campo e descrito aqui sem motivo — se existe, tem funcao.

---

## Usuario (`User`)

Extende o modelo padrao do Django (`AbstractUser`). Todos os campos originais do Django sao mantidos.

**Campos herdados do Django (mantidos sem alteracao)**

| Campo | Tipo | Observacao |
|---|---|---|
| `id` | inteiro auto | chave primaria |
| `username` | texto (150) | unico, usado no login tradicional |
| `email` | e-mail | obrigatorio neste sistema (ao contrario do padrao Django) |
| `password` | texto (hash) | gerenciado pelo Django |
| `first_name` | texto (150) | opcional |
| `last_name` | texto (150) | opcional |
| `is_active` | booleano | padrao: verdadeiro |
| `is_staff` | booleano | acesso ao Admin |
| `is_superuser` | booleano | permissoes totais |
| `date_joined` | data/hora | preenchido automaticamente no cadastro |
| `last_login` | data/hora | atualizado automaticamente |

**Campos adicionados pelo sistema**

| Campo | Tipo | Padrao | Proposito |
|---|---|---|---|
| `deleted_at` | data/hora (nulo) | nulo | marca o usuario como excluido (soft delete); nulo = ativo |

**Regras**
- `email` e obrigatorio e unico neste sistema, mesmo que o Django permita vazio por padrao.
- Registros com `deleted_at` preenchido sao automaticamente excluidos de todas as queries via Manager customizado.

---

## Empresa (`Company`)

Recurso global. Qualquer usuario autenticado pode ler, criar, editar ou excluir.

| Campo | Tipo | Obrigatorio | Proposito |
|---|---|---|---|
| `id` | inteiro auto | — | chave primaria |
| `name` | texto (180) | sim | nome da empresa; unico no sistema |
| `website` | URL | nao | site principal da empresa |
| `careers_page` | URL | nao | pagina de vagas ou recrutamento |
| `notes` | texto longo | nao | observacoes livres sobre a empresa |
| `created_by` | FK → Usuario | nao | quem cadastrou; vira nulo se o usuario for excluido |
| `created_at` | data/hora | — | preenchido automaticamente na criacao |
| `updated_at` | data/hora | — | atualizado automaticamente em cada edicao |

---

## Log de auditoria de empresa (`CompanyAuditLog`)

Registra toda operacao de criacao, edicao ou exclusao em uma empresa. Imutavel — nunca e editado apos criacao.

| Campo | Tipo | Obrigatorio | Proposito |
|---|---|---|---|
| `id` | inteiro auto | — | chave primaria |
| `company` | FK → Empresa | sim | empresa afetada |
| `user` | FK → Usuario (nulo) | nao | quem realizou a acao; nulo se o usuario foi excluido |
| `action` | escolha | sim | tipo de operacao: `created`, `updated`, `deleted` |
| `field_name` | texto (120) | nao | campo alterado (vazio para criacao e exclusao) |
| `old_value` | texto longo | nao | valor anterior do campo (vazio para criacao) |
| `new_value` | texto longo | nao | novo valor do campo (vazio para exclusao) |
| `changed_at` | data/hora | — | preenchido automaticamente no momento da operacao |

**Regra**: um registro de edicao (`updated`) e criado por campo alterado, nao por operacao. Se o usuario editar nome e site ao mesmo tempo, dois registros sao criados.

---

## Vaga (`Job`)

Recurso global. Representa uma posicao aberta em uma empresa.

| Campo | Tipo | Obrigatorio | Proposito |
|---|---|---|---|
| `id` | inteiro auto | — | chave primaria |
| `company` | FK → Empresa | sim | empresa que oferece a vaga; protegido contra exclusao |
| `role_title` | texto (220) | sim | titulo do cargo |
| `source_url` | URL | nao | link da publicacao original da vaga ou formulario de candidatura |
| `location` | texto (160) | nao | cidade, estado ou regiao |
| `remote` | booleano | — | padrao: falso; indica se a vaga aceita trabalho remoto |
| `directed_to` | FK → Usuario (nulo) | nao | usuario para quem a vaga foi enviada diretamente; nulo = vaga publica |
| `created_by` | FK → Usuario (nulo) | nao | quem cadastrou a vaga; vira nulo se o usuario for excluido |
| `created_at` | data/hora | — | preenchido automaticamente na criacao |

---

## Candidatura (`JobApplication`)

Privada por usuario. Representa o processo de um usuario especifico em relacao a uma vaga.

| Campo | Tipo | Obrigatorio | Proposito |
|---|---|---|---|
| `id` | inteiro auto | — | chave primaria |
| `user` | FK → Usuario | sim | dono da candidatura; exclusao em cascata |
| `job` | FK → Vaga | sim | vaga a qual o usuario se candidatou; protegido contra exclusao |
| `status` | escolha | sim | etapa atual do processo (ver lista abaixo); padrao: `draft` |
| `origin` | escolha | sim | como a candidatura entrou no sistema (ver lista abaixo) |
| `applied_at` | data/hora (nulo) | nao | quando o usuario enviou a candidatura |
| `last_status_at` | data/hora (nulo) | nao | quando o status mudou pela ultima vez |
| `next_action_at` | data/hora (nulo) | nao | data e hora da proxima acao programada |
| `next_action_type` | escolha (vazio) | nao | tipo da proxima acao (ver lista abaixo) |
| `next_action_description` | texto longo | nao | descricao livre da proxima acao |
| `notes` | texto longo | nao | observacoes gerais sobre a candidatura |
| `created_at` | data/hora | — | preenchido automaticamente na criacao |
| `updated_at` | data/hora | — | atualizado automaticamente em cada edicao |

**Opcoes de `status`**

| Valor | Rotulo |
|---|---|
| `draft` | Rascunho |
| `applied` | Candidatura enviada |
| `confirmed` | Recebida pela empresa |
| `screening` | Triagem |
| `interview` | Entrevista |
| `offer` | Oferta |
| `rejected` | Rejeitada |
| `withdrawn` | Retirada pelo candidato |
| `archived` | Arquivada |

**Opcoes de `origin`**

| Valor | Significado |
|---|---|
| `manual` | Criada diretamente pelo usuario |
| `email` | Gerada automaticamente a partir de e-mail recebido |
| `external` | Iniciada em plataforma externa sem e-mail no sistema |

**Opcoes de `next_action_type`**

| Valor | Rotulo |
|---|---|
| `follow_up` | Follow-up (retomar contato) |
| `interview` | Entrevista |
| `send_document` | Enviar documento |
| `await_response` | Aguardar retorno |
| `other` | Outro |

---

## Evento da linha do tempo (`ApplicationTimelineEntry`)

Historico imutavel de eventos de uma candidatura. Registros nunca sao editados, apenas adicionados.

| Campo | Tipo | Obrigatorio | Proposito |
|---|---|---|---|
| `id` | inteiro auto | — | chave primaria |
| `application` | FK → Candidatura | sim | candidatura a qual o evento pertence; exclusao em cascata |
| `entry_type` | escolha | sim | natureza do evento (ver lista abaixo) |
| `title` | texto (220) | sim | titulo curto do evento |
| `description` | texto longo | nao | detalhes adicionais |
| `occurred_at` | data/hora | sim | quando o evento ocorreu (pode ser retroativo) |
| `created_at` | data/hora | — | quando o registro foi criado no sistema |

**Opcoes de `entry_type`**

| Valor | Rotulo |
|---|---|
| `manual_note` | Nota manual |
| `email_update` | Atualizacao por e-mail |
| `status_change` | Mudanca de status |
| `reminder` | Lembrete concluido ou dispensado |
| `calendar_event` | Evento de calendario (integracao futura) |

---

## Conta de e-mail (`EmailAccount`)

Privada por usuario. Armazena uma conta de e-mail conectada e suas credenciais de acesso.

| Campo | Tipo | Obrigatorio | Proposito |
|---|---|---|---|
| `id` | inteiro auto | — | chave primaria |
| `user` | FK → Usuario | sim | dono da conta; exclusao em cascata |
| `provider` | escolha | sim | provedor de e-mail (ver lista abaixo) |
| `email_address` | e-mail | sim | endereco da conta conectada |
| `access_token` | texto longo | nao | token de acesso OAuth (criptografado em producao) |
| `refresh_token` | texto longo | nao | token de renovacao OAuth (criptografado em producao) |
| `token_expiry` | data/hora (nulo) | nao | quando o access token expira |
| `is_active` | booleano | — | padrao: verdadeiro; falso desativa a varredura sem remover a conta |
| `scan_times` | JSON (lista) | — | lista de horarios de varredura; padrao: `["00:00"]` |
| `last_scan_at` | data/hora (nulo) | nao | quando foi a ultima varredura bem-sucedida |
| `created_at` | data/hora | — | preenchido automaticamente na criacao |

**Opcoes de `provider`**

| Valor | Rotulo |
|---|---|
| `gmail` | Gmail |
| `outlook` | Outlook / Microsoft 365 |
| `imap` | IMAP generico |

---

## Regra de varredura (`EmailSenderRule`)

Define quais e-mails de uma conta devem ser capturados pelo sistema.

| Campo | Tipo | Obrigatorio | Proposito |
|---|---|---|---|
| `id` | inteiro auto | — | chave primaria |
| `email_account` | FK → Conta de e-mail | sim | conta a qual esta regra pertence; exclusao em cascata |
| `company` | FK → Empresa (nulo) | nao | empresa vinculada para facilitar classificacao posterior |
| `name` | texto (180) | sim | nome descritivo da regra (ex: "Google Recrutamento") |
| `sender_email` | e-mail | nao | e-mail exato do remetente a filtrar |
| `sender_domain` | texto (180) | nao | dominio do remetente a filtrar (ex: `@google.com`) |
| `subject_keywords` | JSON (lista) | nao | palavras-chave a buscar no assunto do e-mail |
| `is_active` | booleano | — | padrao: verdadeiro |
| `created_at` | data/hora | — | preenchido automaticamente na criacao |

**Restricao**: ao menos um dos campos `sender_email`, `sender_domain` ou `subject_keywords` deve estar preenchido.

---

## E-mail recebido (`InboundEmail`)

Registro de um e-mail capturado pela varredura. Um por mensagem, nunca duplicado.

| Campo | Tipo | Obrigatorio | Proposito |
|---|---|---|---|
| `id` | inteiro auto | — | chave primaria |
| `message_id` | texto (255) | sim | identificador unico da mensagem no provedor; unico no sistema (deduplicacao) |
| `email_account` | FK → Conta de e-mail (nulo) | nao | conta que recebeu o e-mail; nulo se a conta for removida |
| `sender` | e-mail | sim | endereco do remetente |
| `subject` | texto (255) | sim | assunto do e-mail |
| `received_at` | data/hora | sim | quando a mensagem foi recebida no provedor |
| `body_text` | texto longo | nao | corpo do e-mail em texto plano |
| `matched_rule` | FK → Regra (nulo) | nao | regra que capturou este e-mail; nulo se a regra for removida |
| `application` | FK → Candidatura (nulo) | nao | candidatura vinculada (manual ou automaticamente) |
| `processing_status` | escolha | sim | etapa atual no pipeline (ver lista abaixo); padrao: `pending` |
| `inferred_application_status` | texto (30) | nao | status inferido pelo LLM antes da confirmacao do usuario |
| `created_at` | data/hora | — | preenchido automaticamente na criacao |

**Opcoes de `processing_status`**

| Valor | Rotulo |
|---|---|
| `pending` | Pendente (aguardando classificacao) |
| `classified` | Classificado (confianca alta, processado automaticamente) |
| `needs_review` | Precisa revisao (confianca baixa ou candidatura ambigua) |
| `ignored` | Ignorado pelo usuario |

---

## Classificacao de e-mail (`EmailClassification`)

Resultado da analise do LLM para um e-mail. Um registro por e-mail, criado pela Fila 2.

| Campo | Tipo | Obrigatorio | Proposito |
|---|---|---|---|
| `id` | inteiro auto | — | chave primaria |
| `email` | OneToOne → E-mail recebido | sim | e-mail classificado; exclusao em cascata |
| `confidence` | decimal (5,2) | sim | confianca da classificacao de 0 a 100 |
| `summary` | texto longo | nao | resumo do e-mail gerado pelo LLM |
| `suggested_status` | texto (30) | nao | status de candidatura sugerido pelo LLM |
| `rationale` | texto longo | nao | justificativa do LLM para a classificacao |
| `reviewed_by` | FK → Usuario (nulo) | nao | usuario que revisou a classificacao; nulo se auto-aplicada |
| `reviewed_at` | data/hora (nulo) | nao | quando o usuario revisou |
| `created_at` | data/hora | — | preenchido automaticamente na criacao |

---

## Notificacao (`Notification`)

Privada por usuario. Alertas gerados pelo sistema sobre eventos relevantes.

| Campo | Tipo | Obrigatorio | Proposito |
|---|---|---|---|
| `id` | inteiro auto | — | chave primaria |
| `user` | FK → Usuario | sim | destinatario; exclusao em cascata |
| `notification_type` | escolha | sim | tipo do evento que originou a notificacao (ver lista abaixo) |
| `priority` | escolha | sim | `urgent` ou `info` |
| `title` | texto (220) | sim | titulo curto da notificacao |
| `body` | texto longo | nao | descricao detalhada |
| `related_application` | FK → Candidatura (nulo) | nao | candidatura relacionada ao evento |
| `related_email` | FK → E-mail recebido (nulo) | nao | e-mail relacionado ao evento |
| `is_read` | booleano | — | padrao: falso |
| `read_at` | data/hora (nulo) | nao | quando o usuario marcou como lida |
| `created_at` | data/hora | — | preenchido automaticamente na criacao |

**Opcoes de `notification_type`**

| Valor | Prioridade | Gatilho |
|---|---|---|
| `reminder_due` | urgente | Proxima acao vencida sem conclusao |
| `email_classified` | info | E-mail processado com alta confianca |
| `email_needs_review` | urgente | E-mail com baixa confianca ou candidatura ambigua |
| `directed_job_detected` | info | Nova vaga direcionada criada por e-mail |
| `status_changed` | info | Status de candidatura atualizado apos confirmacao |

---

## Perfil do candidato (`CandidateProfile`)

Privado por usuario. Um perfil por usuario (relacao 1:1).

| Campo | Tipo | Obrigatorio | Proposito |
|---|---|---|---|
| `id` | inteiro auto | — | chave primaria |
| `user` | OneToOne → Usuario | sim | dono do perfil; exclusao em cascata |
| `full_name` | texto (180) | sim | nome completo do candidato |
| `headline` | texto (220) | nao | titulo profissional curto (ex: "Desenvolvedor Backend Python") |
| `email` | e-mail | nao | e-mail de contato profissional (pode diferir do e-mail de login) |
| `phone` | texto (60) | nao | telefone de contato |
| `location` | texto (160) | nao | cidade e estado de residencia |
| `linkedin_url` | URL | nao | perfil no LinkedIn |
| `portfolio_url` | URL | nao | portfolio, GitHub ou site pessoal |
| `summary` | texto longo | nao | resumo profissional livre |
| `created_at` | data/hora | — | preenchido automaticamente na criacao |
| `updated_at` | data/hora | — | atualizado automaticamente em cada edicao |

---

## Experiencia profissional (`Experience`)

Vinculada ao perfil. Multiplas experiencias por perfil.

| Campo | Tipo | Obrigatorio | Proposito |
|---|---|---|---|
| `id` | inteiro auto | — | chave primaria |
| `profile` | FK → Perfil | sim | perfil ao qual a experiencia pertence; exclusao em cascata |
| `company` | texto (180) | sim | nome da empresa onde trabalhou |
| `title` | texto (180) | sim | cargo exercido |
| `start_date` | data | sim | inicio do periodo |
| `end_date` | data (nulo) | nao | fim do periodo; nulo se for o emprego atual |
| `is_current` | booleano | — | padrao: falso; indica se ainda esta neste emprego |
| `description` | texto longo | nao | atividades, responsabilidades e conquistas |

---

## Formacao academica (`Education`)

Vinculada ao perfil. Multiplas formacoes por perfil.

| Campo | Tipo | Obrigatorio | Proposito |
|---|---|---|---|
| `id` | inteiro auto | — | chave primaria |
| `profile` | FK → Perfil | sim | perfil ao qual a formacao pertence; exclusao em cascata |
| `institution` | texto (180) | sim | nome da instituicao de ensino |
| `course` | texto (180) | sim | nome do curso |
| `degree` | texto (120) | nao | grau academico (ex: Bacharelado, Tecnologo, Pos-graduacao) |
| `start_date` | data (nulo) | nao | inicio do periodo |
| `end_date` | data (nulo) | nao | fim do periodo; nulo se em andamento |

---

## Competencia (`Skill`)

Vinculada ao perfil. Multiplas competencias por perfil.

| Campo | Tipo | Obrigatorio | Proposito |
|---|---|---|---|
| `id` | inteiro auto | — | chave primaria |
| `profile` | FK → Perfil | sim | perfil ao qual a competencia pertence; exclusao em cascata |
| `name` | texto (120) | sim | nome da habilidade (ex: Python, Negociacao, SQL) |
| `level` | texto (80) | nao | nivel de dominio (ex: Basico, Intermediario, Avancado) |

---

## Resposta salva (`SavedAnswer`)

Vinculada ao perfil. Respostas pre-escritas para perguntas frequentes de formularios.

| Campo | Tipo | Obrigatorio | Proposito |
|---|---|---|---|
| `id` | inteiro auto | — | chave primaria |
| `profile` | FK → Perfil | sim | perfil ao qual a resposta pertence; exclusao em cascata |
| `key` | slug (120) | sim | identificador programatico unico dentro do perfil (ex: `por_que_empresa`) |
| `label` | texto (180) | sim | rotulo legivel da pergunta (ex: "Por que voce quer trabalhar aqui?") |
| `answer` | texto longo | sim | resposta pre-escrita pelo usuario |
| `updated_at` | data/hora | — | atualizado automaticamente em cada edicao |

**Restricao**: o par (`profile`, `key`) e unico — um perfil nao pode ter duas respostas com a mesma chave.
