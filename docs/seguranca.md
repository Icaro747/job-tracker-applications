# Segurança e Privacidade dos Dados do Usuário

Este documento registra as correções de segurança já aplicadas e os cuidados que devem
guiar o desenvolvimento daqui para frente. O sistema lida com **dados sensíveis**: tokens
de acesso ao Gmail do usuário e o conteúdo de e-mails pessoais. Proteger esses dados —
inclusive contra a própria infraestrutura e contra terceiros — é requisito, não opcional.

> **Princípio orientador:** colete o mínimo, guarde criptografado, retenha pelo menor tempo
> possível e nunca deixe credenciais ou conteúdo de e-mail saírem do controle do usuário.

---

## Parte 1 — Correções já aplicadas

Trabalho feito na branch `feature/seguranca-credenciais` (TDD; suíte completa verde,
`manage.py check --deploy` sem avisos).

### 1. Tokens OAuth criptografados em repouso (CRÍTICO)
- **Problema:** `access_token`/`refresh_token` ficavam em texto plano no banco. O refresh
  token é de longa duração e dá acesso de leitura a **toda** a caixa do Gmail.
- **Correção:** `EncryptedTextField` (Fernet) em
  [`email_ingestion/fields.py`](../email_ingestion/fields.py); criptografa ao salvar e
  descriptografa ao ler, de forma transparente ao ORM. A chave vem de
  `settings.FIELD_ENCRYPTION_KEY`.

### 2. Apagados os tokens legados em texto plano (CRÍTICO)
- **Correção:** migração `0003_apagar_tokens_legados` zerou todas as credenciais já
  gravadas. O usuário reconecta o Gmail uma vez — nenhum token plano remanesce.

### 3. Banco para fora de pasta sincronizada (CRÍTICO)
- **Problema:** o `db.sqlite3` ficava dentro do OneDrive → replicado para a nuvem da
  Microsoft, levando junto tokens e corpos de e-mail.
- **Correção (código):** caminho do banco configurável via `DJANGO_DB_PATH`.
- **Ação manual pendente (deploy):** mover o arquivo do banco para fora do OneDrive e
  apontar `DJANGO_DB_PATH` para o novo local.

### 4. Hardening de produção (ALTO)
- `SECRET_KEY` e `DJANGO_FIELD_ENCRYPTION_KEY` **obrigatórias** quando `DEBUG=False`
  (falha dura com `ImproperlyConfigured`).
- Bloco `if not DEBUG:` ativa `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`,
  `SECURE_SSL_REDIRECT`, HSTS (1 ano + subdomínios + preload), `SECURE_CONTENT_TYPE_NOSNIFF`
  e `SECURE_PROXY_SSL_HEADER`.

### 5. `.env.example` higienizado (ALTO)
- Removido `OAUTHLIB_INSECURE_TRANSPORT=1` (só seria seguro em dev; o `settings.py` já o
  ativa apenas sob `DEBUG`). Adicionadas `DJANGO_FIELD_ENCRYPTION_KEY` e `DJANGO_DB_PATH`.

### 6. Minimização: expurgo do corpo dos e-mails (MÉDIO)
- Comando `purge_email_bodies --days N` (padrão 90) limpa `body_text` de e-mails já
  processados. Deve ser agendado periodicamente (Django Q2, Etapa 5).

### 7. Revogação transparente (MÉDIO)
- `revoke()` agora retorna `bool`; se a revogação no Google falhar, a UI avisa
  (`messages.warning`) e orienta a remover o acesso em
  `myaccount.google.com/permissions`. Antes a falha era silenciosa.

### 8. Transparência do escopo na UI (MÉDIO/BAIXO)
- A tela de contas explica que o app terá acesso de **leitura** ao Gmail e que só os
  e-mails que casam com as regras são armazenados.

---

## Parte 2 — Cuidados contínuos no desenvolvimento

### 2.1 Credenciais e segredos
- **Nunca** versione segredos. Eles vivem só em `.env` (já no `.gitignore`) e no ambiente
  do servidor. O `.env.example` carrega apenas chaves vazias / placeholders.
- A `DJANGO_FIELD_ENCRYPTION_KEY` é tão sensível quanto o banco: quem tem a chave **e** o
  banco lê os tokens. Guarde-as em locais separados (idealmente um cofre de segredos).
- O fallback de chave em `DEBUG` é **inseguro e fixo** — jamais use em produção. Em
  produção a ausência da chave derruba o boot de propósito.
- Ao adicionar qualquer campo sensível novo (senhas de IMAP, chaves de API de terceiros,
  dados de currículo sensíveis), use `EncryptedTextField` em vez de `TextField`.

### 2.2 Princípio do menor privilégio (escopos OAuth)
- Mantenha o escopo do Gmail no mínimo necessário (`gmail.readonly`). **Não** peça escopos
  de escrita/envio/exclusão sem necessidade real — cada escopo extra aumenta o dano de um
  vazamento e dificulta a verificação OAuth do Google.
- Ao integrar novos provedores (Outlook/IMAP), replicar o padrão de adaptador
  ([`adapters/base.py`](../email_ingestion/adapters/base.py)) e pedir só leitura.

### 2.3 Minimização e retenção de dados
- Guarde o **mínimo** do e-mail necessário para a função. Avalie parar de salvar o corpo
  integral e reter só o resumo/classificação após processar.
- Garanta que `purge_email_bodies` rode de verdade (agendar na Etapa 5). Dados retidos sem
  uso são só risco.
- Ao criar o `CandidateProfile` (Etapa 6) e o autofill, trate currículo/CPF/telefone como
  PII: criptografe o que for sensível e exponha só ao próprio dono.

### 2.4 Isolamento por usuário (autorização)
- **Sempre** escopar consultas de recursos privados a `request.user`. Recursos privados:
  `JobApplication`, `CandidateProfile`, `EmailAccount` e tudo aninhado a eles.
  `Company`/`Job` são globais e compartilhados — não filtrar por dono é intencional.
- Em views novas, herdar os mixins de dono existentes (ex.: `OwnedEmailAccountMixin`) ou
  usar `get_object_or_404(Model, pk=..., user=request.user)`. Nunca confie só no `pk` da URL.
- Lembre do **soft delete**: `objects` esconde registros apagados; só use `all_objects`
  quando realmente precisar alcançar tudo.

### 2.5 Integrações com LLM e serviços externos (atenção redobrada)
- O conteúdo de e-mails é PII. Ao classificar via LLM, prefira **modelo local** (Ollama, já
  adotado na Etapa 4) a APIs externas. Enviar corpo de e-mail a uma API de terceiros é
  exportar dados do usuário — só com consentimento explícito e necessidade clara.
- Se algum dia usar serviço externo, mande o **mínimo** (resumo/trechos, não o e-mail
  inteiro), documente, e nunca registre o conteúdo em logs do provedor.
- **Nunca logar** tokens, corpos de e-mail ou PII. Cuidado com `logging` em nível DEBUG e
  com bibliotecas que logam payloads.

### 2.6 Web / superfície de ataque
- Manter `DEBUG=False` em produção (já garantido por config) e `ALLOWED_HOSTS` restrito ao
  domínio real.
- Servir **sempre** sob HTTPS atrás de proxy (o `SECURE_PROXY_SSL_HEADER` já está pronto).
- Não desativar a proteção CSRF do Django; em endpoints HTMX, manter o `{% csrf_token %}`.
- Confiar no escape automático dos templates Django; evitar `|safe`/`mark_safe` em conteúdo
  vindo de e-mail (o corpo é texto não confiável e pode conter HTML/scripts).
- Ao expor publicamente, considerar rate limiting no login e verificação de e-mail
  (`ACCOUNT_EMAIL_VERIFICATION` hoje é `none` por ser deploy doméstico — rever se abrir).

### 2.7 Dependências e operação
- Manter `requirements.txt` fixado em versões e atualizar com atenção a CVEs (Django,
  allauth, google-*, cryptography).
- Backups do banco herdam a sensibilidade dos dados: criptografe os backups e **não** os
  coloque em pastas sincronizadas (mesmo motivo do item 3).
- Rotação de chave de criptografia (re-encrypt em massa) ainda não existe — planejar antes
  de uma eventual troca de `FIELD_ENCRYPTION_KEY`.

### 2.8 Direitos do titular (privacidade / LGPD)
- O usuário deve conseguir **desconectar** uma conta (revoga + limpa credenciais — feito) e
  **excluir** seus dados. O soft delete com `keep_global_data` já cobre Opção A/B; garantir
  que exclusão de conta também revogue tokens OAuth ativos.
- Ser transparente sobre o que é coletado e por quê (a UI de conexão já explica o acesso ao
  Gmail). Manter essa transparência ao adicionar novas coletas.

---

## Checklist rápido para produção

- [ ] `DJANGO_DEBUG=false`
- [ ] `DJANGO_SECRET_KEY` definida (forte, única)
- [ ] `DJANGO_FIELD_ENCRYPTION_KEY` definida (gerada com `Fernet.generate_key()`)
- [ ] `DJANGO_DB_PATH` apontando para **fora** do OneDrive/Dropbox
- [ ] `DJANGO_ALLOWED_HOSTS` com o domínio real
- [ ] Servido sob HTTPS (proxy reverso)
- [ ] `manage.py check --deploy` sem avisos
- [ ] `purge_email_bodies` agendado
- [ ] Backups do banco criptografados e fora de pastas sincronizadas

---

*Documento vivo — atualizar a cada nova integração ou novo tipo de dado sensível coletado.
Referências: [`.specs/`](../.specs/) (comportamento por domínio), `CLAUDE.md` (padrões
transversais).*
