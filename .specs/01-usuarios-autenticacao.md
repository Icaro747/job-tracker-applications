# Usuarios e autenticacao

## Problema

O sistema precisa atender multiplos usuarios na mesma instancia com dados completamente isolados entre eles. Um usuario nao pode ver candidaturas, e-mails ou notificacoes de outro. Ao mesmo tempo, recursos compartilhados como empresas e vagas precisam ser acessiveis a todos sem duplicacao.

Alem disso, o fluxo de conexao com Gmail exige autenticacao OAuth com o Google, o que abre a possibilidade de unificar o login social com a autorizacao de acesso ao e-mail.

## Solucao

Sistema de autenticacao com dois caminhos de entrada e um mecanismo de exclusao segura e auditavel.

### Cadastro e login

O usuario pode se registrar e autenticar de duas formas:

**Forma 1 — Tradicional**: formulario de cadastro com e-mail e senha. Independente de qualquer servico externo.

**Forma 2 — Google OAuth**: botao "Entrar com Google". Ao usar essa opcao, o mesmo fluxo OAuth que autentica o usuario no sistema tambem pode ser reutilizado para autorizar o acesso ao Gmail na configuracao de contas de e-mail — evitando que o usuario precise passar por dois fluxos de autorizacao separados.

Ambas as formas coexistem. Um usuario pode ter cadastro tradicional sem nunca conectar o Google.

### Isolamento de dados

Todo dado pessoal — candidaturas, contas de e-mail, regras de varredura, notificacoes, perfil — e sempre filtrado pelo usuario autenticado. O sistema nunca expoe dados de um usuario para outro.

Recursos globais — empresas e vagas — sao acessiveis a todos os usuarios autenticados sem restricao de propriedade.

### Soft delete

Quando um usuario solicita exclusao de sua conta, o sistema nao apaga imediatamente. O campo `deleted_at` e preenchido com a data e hora da solicitacao. A partir desse momento, todos os filtros automaticos do sistema excluem esse usuario e seus dados de qualquer resultado.

O usuario escolhe entre duas opcoes no momento da exclusao:

**Opcao A — Excluir tudo que e meu**: todos os dados diretamente vinculados ao usuario (candidaturas, contas de e-mail, regras, notificacoes, perfil) tambem recebem soft delete em cascata. Vagas e empresas que ele criou permanecem, mas o vinculo `created_by` e removido (vira nulo).

**Opcao B — Manter dados globais**: apenas o usuario e marcado como excluido. Vagas e empresas que ele criou continuam integras e associadas a ele como referencia historica, mas sem impacto para outros usuarios.

## Entradas

- Formulario de cadastro: e-mail, senha, confirmacao de senha
- Formulario de login: e-mail + senha ou redirecionamento OAuth Google
- Solicitacao de exclusao: escolha entre opcao A ou B

## Saidas

- Sessao autenticada com identidade do usuario
- Token OAuth do Google armazenado para uso futuro no fluxo de e-mail (quando aplicavel)
- Conta marcada como excluida com timestamp; dados filtrados automaticamente de todas as queries
