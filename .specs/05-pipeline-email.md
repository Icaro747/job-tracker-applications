# Pipeline de processamento de e-mail

## Problema

Varrer uma caixa de e-mail, classificar mensagens e atualizar candidaturas sao operacoes que nao podem acontecer durante uma requisicao web — sao lentas, dependem de servicos externos (Gmail, Ollama) e precisam rodar em momentos programados, nao sob demanda do usuario. Alem disso, o fluxo tem etapas distintas que podem falhar independentemente: a varredura pode funcionar mas o Ollama estar offline, por exemplo. Essas etapas precisam ser separadas e rastreadas individualmente.

## Solucao

O pipeline de e-mail e dividido em duas filas sequenciais, executadas em background pelo Django Q2.

---

### Fila 1 — Varredura

**Quando executa**: nos horarios programados de cada conta de e-mail (`scan_times`).

**O que faz**:

1. Para cada conta de e-mail ativa, autentica no provedor usando o adaptador correspondente.
2. Busca mensagens novas desde a ultima execucao bem-sucedida.
3. Para cada mensagem recebida, verifica se ela corresponde a alguma regra de varredura ativa da conta.
4. Mensagens que passam nos filtros sao registradas no sistema com status **pendente**.
5. Cada e-mail registrado e imediatamente enfileirado na Fila 2 para classificacao.

**Deduplicacao**: o identificador unico da mensagem no provedor e armazenado. Se a mesma mensagem for encontrada em varreduras futuras, ela e ignorada — nunca registrada duas vezes.

---

### Fila 2 — Classificacao por LLM

**Quando executa**: imediatamente apos cada e-mail ser registrado pela Fila 1.

**O que faz**:

1. Envia o conteudo do e-mail (remetente, assunto, corpo) para o Ollama.
2. O Ollama retorna:
   - Um **resumo** do e-mail em linguagem clara
   - Um **status sugerido** para a candidatura (ex: entrevista marcada, candidatura rejeitada, pedido de documento)
   - Um nivel de **confianca** na classificacao (0 a 100)
   - Um **racional** explicando o motivo da classificacao
3. O sistema tenta identificar a qual candidatura do usuario aquele e-mail pertence, analisando o conteudo em busca de mencoes ao cargo ou empresa.
4. Com base no nivel de confianca e na clareza da correspondencia com uma candidatura:

   - **Alta confianca + candidatura identificada com clareza**: e-mail e vinculado automaticamente, status `classificado`. Uma notificacao informativa e enviada ao usuario.
   - **Baixa confianca ou ambiguidade na candidatura**: e-mail fica com status `precisa revisao`. Uma notificacao urgente e enviada ao usuario para revisao manual.

---

### Tela de revisao de classificacoes

Apos o pipeline rodar, o usuario tem acesso a uma tela que lista todos os e-mails processados. Para cada e-mail, a tela exibe:

- O resumo gerado pelo Ollama
- O status sugerido
- O link para o e-mail original no provedor
- A candidatura identificada automaticamente (se houver) ou um campo para vinculacao manual

O usuario pode:

- **Aceitar** a classificacao como esta
- **Editar** o status sugerido para um diferente
- **Vincular manualmente** o e-mail a uma candidatura existente (quando o sistema nao identificou ou identificou errado)
- **Ignorar** o e-mail (marcar como irrelevante)

Ao clicar em **"Confirmar e aplicar"**, o sistema:

1. Atualiza o status da candidatura vinculada para o status confirmado
2. Cria uma entrada na linha do tempo da candidatura do tipo `atualizacao por e-mail`
3. Marca o e-mail como `classificado`

---

### Vaga potencial criada por e-mail

Quando o Ollama identifica que um e-mail traz uma **nova oportunidade de emprego** (e nao uma atualizacao de processo ja existente), o sistema:

1. Cria automaticamente uma **vaga** com os dados extraidos (empresa, titulo estimado, link do formulario ou e-mail de contato encontrado no corpo)
2. Preenche o campo `directed_to` com o dono da conta que recebeu o e-mail
3. Cria uma **candidatura rascunho** vinculada a essa vaga para aquele usuario, com origem `email`
4. Envia notificacao do tipo `directed_job_detected`

O usuario pode entao decidir se quer purseguir a oportunidade, editar os dados ou descartar a candidatura rascunho.

---

### Vinculacao retroativa

Candidaturas criadas manualmente (antes de qualquer e-mail) podem receber e-mails retroativamente. Na tela de revisao, o usuario simplesmente escolhe a candidatura correta no dropdown de vinculacao. O sistema aceita esse vinculo mesmo que a candidatura seja anterior ao e-mail.

## Entradas

- Execucao programada da Fila 1 (por horario configurado na conta de e-mail)
- E-mails retornados pelo adaptador do provedor
- Resposta do Ollama com classificacao, confianca e racional
- Acao do usuario na tela de revisao (confirmar, editar, vincular, ignorar)

## Saidas

- Registros de `InboundEmail` com status rastreado (`pendente` → `classificado` ou `precisa revisao`)
- `EmailClassification` com resumo, status sugerido, confianca e racional para cada e-mail
- Candidatura com status atualizado apos confirmacao
- Entrada na linha do tempo da candidatura
- Vaga e candidatura rascunho criadas automaticamente quando e-mail traz nova oportunidade
- Notificacoes geradas conforme resultado do processamento
