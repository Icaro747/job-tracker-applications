# Empresas e vagas

## Problema

Candidaturas precisam de contexto: a qual empresa e a qual vaga se referem. Esses dados sao neutros — nao pertencem a nenhum usuario especificamente. Se dois usuarios da mesma instancia se candidatam ao Google, nao faz sentido existirem dois registros de "Google" no sistema.

Ao mesmo tempo, uma vaga pode ter sido enviada diretamente para um usuario especifico por um recrutador, enquanto outra e uma publicacao aberta encontrada por qualquer pessoa. Essa distincao e importante para que o usuario filtre o que e relevante para ele.

## Solucao

Dois modelos globais e compartilhados: **Empresa** e **Vaga**.

### Empresa

Representa uma organizacao. Qualquer usuario pode criar, editar ou excluir uma empresa. Como e um recurso global de uso coletivo, nao ha controle de propriedade — qualquer usuario age sobre qualquer empresa.

Para garantir rastreabilidade das mudancas (quem alterou o que), toda operacao sobre uma empresa gera um registro de auditoria completo contendo: quem fez a acao, qual acao foi (criacao, edicao ou exclusao), qual campo foi alterado, o valor anterior e o valor novo, e o momento exato da mudanca.

Esse historico de auditoria existe exclusivamente para empresas. Outros modelos nao tem esse nivel de rastreabilidade.

### Vaga

Representa uma posicao aberta em uma empresa. E vinculada a uma empresa e pode ser criada por qualquer usuario.

Vagas tem um campo opcional **"direcionada para"** que indica se aquela oportunidade foi enviada especificamente para um usuario (por exemplo, um recrutador que entrou em contato diretamente). Quando preenchido:

- A vaga aparece para todos os usuarios com uma tag indicando para quem foi direcionada.
- O usuario alvo pode filtrar a listagem para ver apenas as vagas direcionadas a ele.

Vagas criadas automaticamente pelo sistema a partir de e-mails recebidos nascem com esse campo preenchido com o dono da conta de e-mail que recebeu o contato.

Vagas criadas manualmente nao tem esse campo preenchido por padrao — sao consideradas vagas publicas na instancia.

### Separacao entre vaga e candidatura

Vaga e candidatura sao conceitos distintos e separados:

- A **vaga** descreve a oportunidade: empresa, titulo, localizacao, link.
- A **candidatura** descreve o processo de um usuario especifico em relacao a essa vaga: status, data de envio, historico de interacoes.

A mesma vaga pode ter multiplas candidaturas de usuarios diferentes, cada uma com seu proprio historico e status independente.

## Entradas

**Para criar empresa**: nome, site, pagina de carreiras (opcional), observacoes (opcional)

**Para criar vaga**: empresa, titulo do cargo, link da vaga, localizacao, modalidade (presencial/remoto), campo "direcionada para" (opcional)

**Para auditoria de empresa**: qualquer edicao ou exclusao dispara automaticamente — sem entrada adicional do usuario

## Saidas

- Empresa disponivel globalmente para vinculacao com vagas
- Vaga disponivel globalmente para candidaturas de qualquer usuario
- Vagas direcionadas exibidas com tag visual para identificacao rapida
- Historico completo de alteracoes em empresa disponivel para consulta
