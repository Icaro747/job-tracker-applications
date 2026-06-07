# Notificacoes

## Problema

O usuario nao fica o tempo todo com o sistema aberto. Eventos importantes acontecem em background — lembretes vencem, e-mails sao classificados, vagas direcionadas chegam — e o usuario precisa ser alertado sem precisar verificar manualmente. Ao mesmo tempo, nem todo evento tem a mesma urgencia: uma vaga nova e informativa, um lembrete vencido exige acao imediata.

## Solucao

Sistema de notificacoes internas com dois niveis de prioridade e cinco tipos de gatilho.

### Onde as notificacoes aparecem

As notificacoes sao exibidas em um **painel interno** acessivel de qualquer tela do sistema. Um badge numerico indica quantas notificacoes nao foram lidas. Notificacoes urgentes tem destaque visual diferente das informativas.

Expansao futura: integracao com **Google Calendar** para lembretes de proximas acoes, criando eventos diretamente na agenda do usuario.

### Niveis de prioridade

- **Urgente**: exige acao do usuario. Exibida com destaque visual (cor diferente, icone de alerta). O badge do sino nao diminui ate o usuario marcar como lida.
- **Informativa**: atualiza o usuario sobre algo que aconteceu. Exibida normalmente, sem alerta especial.

### Tipos de notificacao e seus gatilhos

**1. Lembrete vencido** (`reminder_due`) — prioridade: urgente
- Disparado por: tarefa periodica do Django Q2 que verifica candidaturas com `next_action_at` no passado e sem conclusao registrada
- Contexto: candidatura relacionada, tipo da acao vencida, data que passou
- Acao esperada do usuario: concluir ou remarcar a proxima acao

**2. E-mail classificado** (`email_classified`) — prioridade: informativa
- Disparado por: finalizacao bem-sucedida da Fila 2 com alta confianca
- Contexto: resumo do e-mail, candidatura atualizada, novo status aplicado
- Acao esperada: nenhuma obrigatoria; usuario pode revisar se quiser

**3. E-mail precisa revisao** (`email_needs_review`) — prioridade: urgente
- Disparado por: finalizacao da Fila 2 com baixa confianca ou candidatura ambigua
- Contexto: resumo do e-mail, status sugerido, link para tela de revisao
- Acao esperada: acessar tela de revisao, confirmar ou corrigir classificacao

**4. Vaga direcionada detectada** (`directed_job_detected`) — prioridade: informativa
- Disparado por: Ollama identificar nova oportunidade em e-mail recebido e criar vaga + candidatura rascunho
- Contexto: nome da empresa, titulo da vaga estimado, link para candidatura rascunho criada
- Acao esperada: avaliar a oportunidade e decidir se quer prosseguir

**5. Status de candidatura alterado** (`status_changed`) — prioridade: informativa
- Disparado por: confirmacao de classificacao de e-mail que atualiza o status de uma candidatura
- Contexto: candidatura afetada, status anterior, novo status
- Acao esperada: nenhuma obrigatoria; registro informativo do historico

### Ciclo de vida de uma notificacao

1. Sistema cria a notificacao com status **nao lida**
2. Badge do sino incrementa
3. Usuario acessa o painel e ve a notificacao
4. Usuario marca como lida (manualmente ou ao clicar na notificacao)
5. Badge decrementa

Notificacoes nao sao deletadas ao ser lidas — permanecem no historico para consulta futura.

### Tarefa periodica de lembretes

Uma tarefa agendada no Django Q2 executa regularmente (frequencia configuravel, padrao: a cada hora durante o dia). Ela verifica todas as candidaturas com `next_action_at` no passado e sem conclusao registrada e cria uma notificacao do tipo `reminder_due` para o usuario dono de cada candidatura afetada.

Para evitar spam de notificacoes, o sistema verifica se ja existe uma notificacao `reminder_due` nao lida para aquela candidatura antes de criar outra.

## Entradas

- Evento interno do sistema (finalizacao de tarefa Q2, confirmacao de classificacao, conclusao de acao)
- Execucao da tarefa periodica de verificacao de lembretes vencidos

## Saidas

- Registro de notificacao vinculado ao usuario e, quando aplicavel, a candidatura relacionada
- Badge atualizado no painel do usuario
- Destaque visual diferenciado para notificacoes urgentes
- Historico de notificacoes consultavel (incluindo as ja lidas)
