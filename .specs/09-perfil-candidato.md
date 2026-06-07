# Perfil do candidato

## Problema

O usuario precisa preencher repetidamente os mesmos dados em formularios de candidatura de diferentes empresas: nome, telefone, endereco, resumo profissional, experiencias, formacao academica, competencias. Esses dados existem no curriculo, mas ficam dispersos em arquivos PDF ou documentos que o usuario precisa consultar manualmente a cada candidatura.

## Solucao

Um perfil centralizado que armazena todos os dados do curriculo do usuario de forma estruturada. Esse perfil e a fonte de verdade para sugestoes de preenchimento em candidaturas futuras.

### Dados do perfil

O perfil e organizado em secoes:

**Dados de contato**
- Nome completo
- Titulo profissional (headline)
- E-mail de contato
- Telefone
- Localizacao
- URL do LinkedIn
- URL do portfolio ou site pessoal

**Resumo profissional**
- Texto livre descrevendo o candidato em suas proprias palavras

**Experiencias profissionais**
Cada experiencia contem:
- Empresa
- Cargo
- Data de inicio e fim (ou "atual")
- Descricao das atividades e conquistas

**Formacao academica**
Cada formacao contem:
- Instituicao
- Curso
- Grau (bacharel, tecnologo, pos-graduacao, etc.)
- Periodo (inicio e fim)

**Competencias**
Lista de habilidades tecnicas e comportamentais, cada uma com nivel opcional (basico, intermediario, avancado, etc.)

**Respostas salvas**
Respostas pre-escritas para perguntas frequentes de formularios de candidatura. Cada resposta salva tem:
- Uma chave de identificacao (ex: `por_que_empresa`, `maior_desafio`)
- Um rotulo legivel (ex: "Por que voce quer trabalhar aqui?")
- O texto da resposta

Respostas salvas permitem que o usuario escreva uma vez e reutilize em diferentes candidaturas sem reescrever do zero.

### Relacao com autofill

O perfil e a base de dados que alimenta o modulo de preenchimento assistido (Etapa 7). Quando o usuario estiver em um formulario externo, o sistema consulta o perfil para sugerir valores nos campos detectados.

Manter o perfil atualizado e, portanto, um prerequisito para que o autofill funcione bem.

## Entradas

- Dados inseridos manualmente pelo usuario em cada secao do perfil
- Edicoes e atualizacoes ao longo do tempo

## Saidas

- Perfil estruturado disponivel para consulta pelo modulo de autofill
- Dados exibidos de forma organizada para o proprio usuario como referencia durante candidaturas
- Respostas salvas consultaveis rapidamente durante o preenchimento de formularios externos
