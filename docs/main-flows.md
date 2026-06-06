# Fluxos principais

## 1. Cadastro manual de candidatura

1. Usuario cadastra a empresa.
2. Usuario cadastra a vaga com titulo, link, localidade e observacoes.
3. Sistema cria a candidatura com status `Rascunho` ou `Candidatura enviada`.
4. Usuario registra a data de envio e proxima acao esperada.
5. Sistema passa a exibir a candidatura no painel e no admin.

## 2. Atualizacao por e-mail

1. Usuario cadastra regras de remetente por e-mail ou dominio.
2. Rotina futura busca mensagens na caixa de e-mail.
3. Sistema compara remetente com as regras ativas.
4. E-mail relevante vira um `InboundEmail`.
5. Classificador sugere resumo e status, por exemplo:
   - candidatura recebida;
   - convite para entrevista;
   - rejeicao;
   - pedido de informacao adicional.
6. Usuario revisa a classificacao quando necessario.
7. Candidatura recebe novo status e entrada na linha do tempo.

## 3. Lembretes e eventos

1. Usuario define uma proxima acao na candidatura.
2. Sistema cria lembrete ou evento relacionado.
3. Futuramente, uma rotina enviara notificacao por app/e-mail ou criara evento externo de calendario.
4. Lembrete muda para `Enviado` ou `Dispensado`.

## 4. Perfil e dados do curriculo

1. Usuario cria perfil do candidato.
2. Usuario cadastra contatos, resumo, experiencias, formacao, competencias e respostas salvas.
3. Esses dados viram a fonte de verdade para futuras sugestoes de preenchimento.

## 5. Sugestao de preenchimento de formulario

1. Usuario inicia candidatura em um site externo.
2. Sistema identifica dominio e campos comuns do formulario.
3. Sistema consulta mapeamentos de campo e dados do perfil.
4. Sistema gera sugestoes de preenchimento.
5. Usuario aceita, rejeita ou ajusta sugestoes.
6. O historico ajuda a melhorar os mapeamentos para o mesmo dominio.
