# Contas de e-mail e adaptadores de provedor

## Problema

Para monitorar e-mails de processos seletivos, o sistema precisa acessar a caixa de entrada do usuario. Diferentes provedores de e-mail (Gmail, Outlook, IMAP) funcionam de formas tecnicamente distintas — cada um tem seu proprio protocolo de autenticacao e sua propria API de leitura de mensagens. Construir o sistema acoplado a um unico provedor criaria uma barreira para adicionar novos provedores no futuro.

Alem disso, um usuario pode ter multiplas contas de e-mail — ate mais de uma conta no mesmo provedor — e cada uma pode ter regras de filtragem independentes.

## Solucao

### Contas de e-mail

Cada usuario pode conectar uma ou mais contas de e-mail ao sistema. Uma conta de e-mail registra:

- A qual usuario pertence
- O provedor (Gmail, Outlook, IMAP, etc.)
- O endereco de e-mail da conta
- As credenciais de acesso (tokens OAuth ou credenciais IMAP), armazenadas de forma segura
- Se esta ativa para varredura
- Os horarios programados de varredura

Quando um usuario e excluido, todas as suas contas de e-mail sao removidas junto — as credenciais nao tem valor sem o dono.

### Horarios de varredura

Cada conta tem sua propria programacao de varredura independente. Por padrao, o sistema verifica novos e-mails uma vez por dia, a meia-noite. O usuario pode personalizar:

- Quantas vezes por dia a varredura ocorre
- Em quais horarios especificos ela acontece

Exemplos validos: so a meia-noite (padrao), tres vezes ao dia (08:00, 13:00, 19:00), uma vez ao meio-dia.

### Adaptadores de provedor

Para isolar o sistema dos detalhes tecnicos de cada provedor, todo acesso a caixa de e-mail passa por um **adaptador**. Cada adaptador implementa um contrato comum:

- Autenticar com o provedor usando as credenciais da conta
- Buscar mensagens novas desde um determinado momento, aplicando os filtros das regras configuradas
- Revogar o acesso (para desconectar a conta)

O sistema central nao sabe se esta falando com Gmail ou IMAP — ele so conhece o contrato. Isso significa que adicionar suporte a um novo provedor no futuro nao exige alterar o pipeline de processamento, apenas criar um novo adaptador que respeite o mesmo contrato.

**Provedor inicial**: Gmail (OAuth2 via Google API)

**Provedores futuros planejados**: Outlook (Microsoft Graph API), IMAP generico (para qualquer provedor que suporte o protocolo)

### Regras de varredura

Cada conta de e-mail tem suas proprias regras que determinam quais e-mails sao relevantes e devem ser capturados. Uma regra pode filtrar por:

- **Remetente especifico**: e-mail exato do remetente (ex: `recrutador@empresa.com`)
- **Dominio do remetente**: todos os e-mails de um dominio (ex: `@empresa.com`)
- **Palavras-chave no assunto**: termos que devem aparecer no titulo do e-mail (ex: `vaga`, `entrevista`, `oportunidade`)

A logica de matching funciona assim:

- Se a regra tem somente remetente → captura qualquer e-mail daquele remetente, independente do assunto
- Se a regra tem somente palavras-chave → captura qualquer e-mail de qualquer remetente que tenha aqueles termos no assunto
- Se a regra tem remetente e palavras-chave → captura somente e-mails daquele remetente E que tenham os termos no assunto (ambas as condicoes obrigatorias)

Uma regra pode ser opcionalmente vinculada a uma empresa cadastrada no sistema, o que facilita a classificacao posterior dos e-mails capturados.

## Entradas

**Para conectar uma conta**:
- Provedor selecionado (Gmail, IMAP, etc.)
- Fluxo de autorizacao OAuth ou credenciais IMAP
- Horarios de varredura (opcional, usa padrao se omitido)

**Para criar uma regra de varredura**:
- Conta de e-mail a qual a regra pertence
- Nome descritivo da regra
- Remetente ou dominio (opcional)
- Palavras-chave no assunto (opcional, lista)
- Empresa vinculada (opcional)
- Ao menos um dos campos de filtro deve ser preenchido

## Saidas

- Conta registrada e disponivel para varredura automatica nos horarios programados
- Regras ativas usadas pelo adaptador como criterio de filtragem durante a varredura
- E-mails que passam pelos filtros entram no pipeline de processamento como mensagens pendentes de classificacao
