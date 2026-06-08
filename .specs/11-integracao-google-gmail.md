# Integracao Google e Gmail

## Objetivo

Este documento descreve a parte operacional, burocratica e de configuracao externa necessaria para conectar o sistema ao Google, principalmente para permitir que usuarios autorizem o acesso a suas contas Gmail.

Ele cobre o que precisa ser feito fora do codigo: projeto no Google Cloud, Gmail API, tela de consentimento OAuth, credenciais, usuarios de teste, publicacao, verificacao do app e possivel avaliacao de seguranca.

## Escopo desta integracao

Na etapa 3, o sistema precisa:

- permitir que um usuario conecte uma conta Gmail;
- receber permissao explicita do usuario para acessar dados do Gmail;
- armazenar tokens OAuth de forma segura;
- usar esses tokens para buscar mensagens novas;
- aplicar regras de varredura por remetente, dominio e palavras-chave no assunto;
- enviar os e-mails capturados para a Fila 1 do pipeline.

O Google OAuth pode servir para duas coisas diferentes:

- **Login com Google**: identifica o usuario no sistema.
- **Acesso ao Gmail**: autoriza o sistema a ler dados da caixa de entrada.

Essas duas funcoes podem ser combinadas no mesmo fluxo, mas precisam de escopos diferentes. Login usa escopos basicos de identidade. Gmail exige escopos especificos e consentimento adicional.

## Decisao de escopos

O app deve pedir o menor conjunto de permissoes possivel.

### Escopos basicos de login

Usados apenas para autenticar o usuario:

- `openid`
- `email`
- `profile`

Esses escopos nao dao acesso a e-mails do Gmail.

### Escopos Gmail candidatos

Para a etapa 3, existem duas opcoes principais:

| Escopo | Uso | Categoria Google | Quando usar |
|---|---|---|---|
| `https://www.googleapis.com/auth/gmail.metadata` | Le metadados, labels, historico e headers, mas nao corpo nem anexos | Restricted | Se a etapa 3 so precisar de remetente, assunto, data e headers |
| `https://www.googleapis.com/auth/gmail.readonly` | Le mensagens e metadados, sem alterar nada | Restricted | Se o sistema precisar ler corpo do e-mail para classificacao posterior |

Para o produto descrito nas specs, a escolha mais provavel e `gmail.readonly`, porque a etapa 4 de classificacao LLM pode precisar do conteudo do e-mail. Se a classificacao for feita apenas por assunto/remetente, `gmail.metadata` reduz a exposicao de dados, mas ainda e um escopo restrito.

Evitar inicialmente:

- `https://www.googleapis.com/auth/gmail.modify`, porque permite alteracoes na caixa;
- `https://mail.google.com/`, porque da acesso amplo demais e e muito mais dificil de justificar.

## Consequencia importante dos escopos Gmail

Escopos como `gmail.readonly`, `gmail.metadata` e `gmail.modify` sao classificados pelo Google como **Restricted**.

Isso significa:

- em desenvolvimento, o app pode funcionar com usuarios de teste;
- em producao publica, o app precisa passar pela verificacao OAuth do Google;
- dependendo do caso, o Google pode exigir uma avaliacao de seguranca externa baseada em CASA;
- apps com escopos restritos podem precisar de reverificacao anual.

Se o sistema for usado apenas por voce durante desenvolvimento, a configuracao em modo de teste e suficiente para validar a implementacao. Para uso real por outros usuarios, trate a verificacao como uma etapa obrigatoria de lancamento.

## Pre-requisitos antes de configurar o Google

Antes de enviar o app para verificacao, prepare:

- nome publico do sistema;
- e-mail de suporte ao usuario;
- e-mail de contato tecnico do projeto;
- dominio oficial do sistema, quando houver;
- URL da pagina inicial;
- URL da politica de privacidade;
- URL dos termos de uso, recomendavel;
- URL ou instrucao clara para exclusao de conta/dados;
- explicacao objetiva de por que o app precisa ler Gmail;
- video demonstrando o fluxo OAuth e o uso dos dados;
- ambiente de producao acessivel publicamente, se for submeter verificacao.

Para desenvolvimento local, dominio publico, politica de privacidade e video ainda nao sao obrigatorios, mas serao necessarios antes do uso publico.

## Passo a passo no Google Cloud

### 1. Criar ou escolher um projeto

1. Acesse o Google Cloud Console.
2. Crie um projeto novo ou escolha um projeto existente.
3. Use um nome claro, por exemplo `Gerenciador de Candidaturas`.
4. Confirme se a conta Google usada tem permissao de owner/editor no projeto.

Recomendacao:

- use um projeto separado para desenvolvimento/teste;
- crie outro projeto para producao quando o app for publicado.

Isso evita que mudancas experimentais em escopos ou URLs quebrem uma integracao ja aprovada.

### 2. Ativar a Gmail API

1. No projeto do Google Cloud, va em **APIs & Services**.
2. Abra **Library**.
3. Procure por **Gmail API**.
4. Clique em **Enable**.

Sem essa etapa, as credenciais OAuth existem, mas chamadas para Gmail falham.

### 3. Configurar a tela de consentimento OAuth

No Google Cloud, abra a area da **Google Auth Platform** ou **OAuth consent screen**.

Configure:

- **App name**: nome que o usuario vera na tela de consentimento.
- **User support email**: e-mail para suporte.
- **Audience/User type**:
  - `External`, se usuarios comuns com contas Google pessoais poderao usar;
  - `Internal`, apenas se for uma organizacao Google Workspace e o app for restrito a ela.
- **Developer contact information**: e-mails que receberao avisos do Google.
- **Authorized domains**: dominio do app, quando houver producao.
- **Homepage URL**: pagina inicial publica do app.
- **Privacy Policy URL**: politica de privacidade.
- **Terms of Service URL**: recomendavel para publicacao.

Durante desenvolvimento local, deixe o app em estado de teste e adicione apenas usuarios conhecidos.

### 4. Adicionar os escopos

Na area de acesso a dados/scopes, adicione:

- `openid`
- `email`
- `profile`
- `https://www.googleapis.com/auth/gmail.readonly`

Ou, se for decidido que a etapa 3 nao precisa do corpo das mensagens:

- `https://www.googleapis.com/auth/gmail.metadata`

Depois de adicionar escopos sensiveis ou restritos, o Console mostra a categoria de cada um. Use essa informacao para saber qual verificacao sera exigida.

### 5. Criar credenciais OAuth

1. Va em **APIs & Services > Credentials**.
2. Clique em **Create Credentials**.
3. Escolha **OAuth client ID**.
4. Em tipo de aplicacao, escolha **Web application**.
5. Defina um nome, por exemplo `Django Web App - Dev`.
6. Configure os redirects autorizados.

URLs comuns para desenvolvimento:

- `http://localhost:8000/accounts/google/login/callback/`
- `http://127.0.0.1:8000/accounts/google/login/callback/`

Se o sistema usar uma rota propria para conectar Gmail, tambem cadastrar:

- `http://localhost:8000/email/gmail/callback/`
- `http://127.0.0.1:8000/email/gmail/callback/`

Em producao, cadastrar a URL HTTPS real:

- `https://seudominio.com/accounts/google/login/callback/`
- `https://seudominio.com/email/gmail/callback/`

O valor da URL precisa bater exatamente com o que o sistema envia no OAuth: protocolo, dominio, porta, caminho e barra final.

### 6. Guardar Client ID e Client Secret

Depois de criar a credencial, o Google fornece:

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`

Esses valores devem ir para variaveis de ambiente, nunca para o repositorio.

Exemplo esperado no ambiente local:

```env
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_OAUTH_SCOPES=openid email profile https://www.googleapis.com/auth/gmail.readonly
```

Se django-allauth for usado com configuracao pelo admin, esses dados tambem podem ser cadastrados como `SocialApp` no Django Admin. Ainda assim, para ambientes reais, preferir variaveis de ambiente ou secret manager.

### 7. Adicionar usuarios de teste

Enquanto o app estiver em modo de teste:

1. Abra a tela de consentimento OAuth.
2. Va ate a area de usuarios de teste.
3. Adicione os e-mails Google que poderao autorizar o app.

Contas que nao estiverem nessa lista podem receber erro de acesso negado.

Observacao importante: em apps externos com status de teste, refresh tokens para escopos alem de `openid`, `email` e `profile` podem expirar em 7 dias. Para varredura automatica real e persistente, o app precisa estar em producao.

## Verificacao para uso publico

### Quando a verificacao e necessaria

A verificacao e necessaria quando:

- o app sera usado por usuarios externos reais;
- o app pede escopos sensiveis ou restritos;
- o app precisa remover o aviso de "app nao verificado";
- o app precisa funcionar de forma confiavel para mais usuarios;
- o app precisa manter refresh tokens de longa duracao em producao.

Como Gmail `readonly` e `metadata` sao escopos restritos, assumir que havera verificacao antes de lancar publicamente.

### O que preparar para a verificacao OAuth

O Google normalmente solicita:

- tela de consentimento completa;
- dominio verificado;
- politica de privacidade publica;
- justificativa para cada escopo;
- explicacao de como os dados do Google sao usados;
- video demonstrativo do fluxo de login/autorizacao;
- video ou demonstracao mostrando onde os dados do Gmail aparecem no produto;
- usuario de teste para revisores, se necessario;
- confirmacao de que o app segue a politica de dados do Google API Services.

### Justificativa sugerida para `gmail.readonly`

Usar uma justificativa simples e direta:

> O app le mensagens do Gmail autorizadas pelo usuario para identificar comunicacoes relacionadas a processos seletivos, como convites de entrevista, respostas de recrutadores e atualizacoes de candidaturas. O acesso e somente leitura; o sistema nao envia, altera, exclui nem encaminha e-mails.

Se a implementacao realmente usar apenas remetente, assunto e headers, a justificativa deve ser ajustada e o escopo deve ser `gmail.metadata`.

### Video demonstrativo

Prepare um video curto mostrando:

1. usuario acessando o sistema;
2. usuario clicando para conectar Gmail;
3. tela de consentimento do Google com os escopos solicitados;
4. retorno ao sistema apos consentimento;
5. conta Gmail conectada;
6. execucao ou simulacao da varredura;
7. e-mails capturados aparecendo como itens pendentes no pipeline;
8. opcao de desconectar a conta Gmail;
9. opcao de excluir dados/conta, se aplicavel.

O video precisa deixar claro por que o escopo pedido e necessario.

### Politica de privacidade

A politica de privacidade deve explicar, em linguagem simples:

- quais dados do Google sao acessados;
- por que o sistema acessa esses dados;
- como os dados sao armazenados;
- por quanto tempo sao mantidos;
- quem pode acessar esses dados;
- como o usuario revoga o acesso;
- como o usuario solicita exclusao dos dados;
- que o sistema nao vende dados do Gmail;
- que o sistema nao usa dados do Gmail para publicidade;
- que os dados sao usados apenas para funcionalidades relacionadas a candidaturas.

### Avaliacao de seguranca CASA

Como escopos Gmail de leitura sao restritos, o Google pode exigir uma avaliacao de seguranca.

Na pratica, isso pode envolver:

- revisao de seguranca por avaliador autorizado;
- evidencias de armazenamento seguro de tokens;
- HTTPS em producao;
- controle de acesso por usuario;
- isolamento de dados entre usuarios;
- logs e auditoria;
- processo de exclusao de dados;
- protecao contra vazamento de credenciais;
- correcao de vulnerabilidades encontradas.

Essa etapa pode gerar custo e prazo externo. Por isso, para MVP, e prudente validar o produto com usuarios de teste antes de iniciar verificacao publica.

## Checklist de seguranca interna antes da submissao

Antes de enviar para verificacao, confirmar que o sistema:

- usa HTTPS em producao;
- nao commita `GOOGLE_CLIENT_SECRET`;
- criptografa tokens OAuth no banco ou usa armazenamento seguro equivalente;
- associa cada conta Gmail a exatamente um usuario dono;
- filtra todos os dados de e-mail por usuario autenticado;
- permite desconectar Gmail e revogar tokens;
- permite excluir dados do usuario;
- registra `last_history_id` ou outro marcador para evitar reprocessamento indevido;
- limita o volume de dados lidos ao necessario;
- nao armazena anexos sem necessidade;
- nao solicita escopos que nao usa;
- possui politica de privacidade coerente com o comportamento real do app.

## Variaveis e informacoes que o codigo vai precisar

O resultado da configuracao burocratica deve fornecer ao sistema:

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- lista de escopos OAuth
- URL de callback autorizada
- status do app: teste ou producao
- lista de usuarios de teste, enquanto estiver em teste

Tambem e necessario decidir:

- se o login Google e a conexao Gmail serao um fluxo unico ou separado;
- qual escopo Gmail sera usado no MVP;
- se havera projeto Google separado para desenvolvimento e producao;
- onde os tokens serao criptografados/armazenados;
- qual URL publica sera usada para politica de privacidade.

## Problemas comuns

### `redirect_uri_mismatch`

O redirect enviado pelo sistema nao bate exatamente com o cadastrado no Google Cloud.

Verificar:

- `localhost` vs `127.0.0.1`;
- `http` vs `https`;
- porta;
- caminho;
- barra final;
- dominio de producao.

### `access_denied`

Possiveis causas:

- usuario nao esta na lista de usuarios de teste;
- usuario recusou o consentimento;
- app esta restrito a uma organizacao Workspace;
- admin do Google Workspace bloqueou escopos Gmail.

### `invalid_grant`

Possiveis causas:

- refresh token expirou;
- app externo ainda esta em modo de teste;
- usuario revogou permissao;
- escopos mudaram e o usuario precisa autorizar novamente;
- horario do servidor esta incorreto.

### Aviso de app nao verificado

Esperado quando o app usa escopos sensiveis/restritos e ainda nao passou pela verificacao. Para uso publico, submeter o app para verificacao.

## Sequencia recomendada para este projeto

1. Criar projeto Google Cloud de desenvolvimento.
2. Ativar Gmail API.
3. Configurar tela OAuth em modo teste.
4. Criar OAuth Client ID web.
5. Cadastrar callbacks locais.
6. Adicionar sua conta Google como usuario de teste.
7. Implementar e validar conexao Gmail com `gmail.readonly` ou `gmail.metadata`.
8. Validar varredura e Fila 1 com poucos e-mails reais.
9. Criar pagina de politica de privacidade antes de pensar em usuarios externos.
10. Criar projeto Google Cloud de producao.
11. Configurar dominio, callbacks HTTPS e credenciais de producao.
12. Preparar justificativas e video.
13. Publicar app como producao no Google Cloud.
14. Submeter para verificacao OAuth.
15. Realizar avaliacao de seguranca se o Google exigir.

## Referencias oficiais

- Gmail API Python quickstart: https://developers.google.com/workspace/gmail/api/quickstart/python
- Escopos da Gmail API: https://developers.google.com/workspace/gmail/api/auth/scopes
- OAuth 2.0 para apps web: https://developers.google.com/identity/protocols/oauth2/web-server
- Uso de OAuth 2.0 para Google APIs: https://developers.google.com/identity/protocols/oauth2
- Verificacao OAuth: https://support.google.com/cloud/answer/13463073
- Envio do app para verificacao: https://support.google.com/cloud/answer/13461325
- Escopos minimos: https://support.google.com/cloud/answer/13807380
- Avaliacao de seguranca: https://support.google.com/cloud/answer/13465431
- Apps nao verificados: https://support.google.com/cloud/answer/7454865
