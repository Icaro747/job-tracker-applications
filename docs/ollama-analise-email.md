# Guia: rodar a IA local para analisar e-mails

Este guia explica como preparar o computador para a analise automatica de
e-mails do sistema usando o Ollama.

O Ollama e um programa que roda modelos de IA no seu proprio computador. Neste
projeto, ele e usado para ler um e-mail capturado, resumir o conteudo, sugerir o
status da candidatura e dizer se o sistema pode aplicar a mudanca sozinho ou se
voce precisa revisar.

## O que voce precisa ter

- Windows 10 ou superior.
- Internet para baixar o Ollama e o modelo de IA.
- O projeto Django funcionando.
- Uma conta de e-mail conectada no sistema.
- Pelo menos uma regra de captura de e-mail criada.

## Passo 1: instalar o Ollama

### Opcao A: instalacao pelo site

1. Acesse: <https://ollama.com/download/windows>
2. Baixe o instalador para Windows.
3. Abra o instalador baixado.
4. Siga os passos na tela.
5. Feche e abra de novo o PowerShell depois de instalar.

### Opcao B: instalacao pelo PowerShell

Abra o PowerShell e rode:

```powershell
winget install --id Ollama.Ollama -e --accept-source-agreements --accept-package-agreements
```

Se o Windows pedir permissao, aceite.

## Passo 2: confirmar que o Ollama foi instalado

Feche e abra o PowerShell. Depois rode:

```powershell
ollama --version
```

Se aparecer uma versao, o Ollama esta instalado.

Se aparecer uma mensagem dizendo que `ollama` nao e reconhecido, tente reiniciar
o computador. Se continuar igual, instale novamente pelo site oficial.

No Windows, tambem e possivel chamar o executavel pelo caminho completo:

```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" --version
```

## Passo 3: baixar o modelo de IA

O projeto usa `llama3.2` por padrao. Para baixar:

```powershell
ollama pull llama3.2
```

Esse download pode demorar. Ele tambem pode ocupar varios GB no disco.

Se o comando `ollama` ainda nao funcionar no PowerShell, use:

```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" pull llama3.2
```

## Passo 4: testar a IA fora do sistema

Rode:

```powershell
ollama run llama3.2
```

Quando abrir o chat, digite:

```text
Resuma em uma frase: recebi um convite para entrevista de emprego.
```

Se a IA responder, o modelo esta funcionando.

Para sair do chat, use:

```text
/bye
```

Se precisar usar o caminho completo:

```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" run llama3.2
```

## Passo 5: confirmar que a API local esta respondendo

O Django conversa com o Ollama pela API local na porta `11434`.

Rode:

```powershell
Invoke-RestMethod http://localhost:11434/api/tags
```

Se aparecer uma lista de modelos, esta tudo certo.

Se der erro de conexao, abra o Ollama pelo menu iniciar ou rode:

```powershell
ollama serve
```

Deixe essa janela aberta enquanto usa o sistema.

## Passo 6: configurar o projeto

No arquivo `.env`, estas configuracoes podem existir:

```env
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2
LLM_CONFIDENCE_THRESHOLD=80
```

O que cada uma significa:

- `OLLAMA_HOST`: endereco onde o Ollama esta rodando.
- `OLLAMA_MODEL`: modelo de IA usado para analisar os e-mails.
- `LLM_CONFIDENCE_THRESHOLD`: confianca minima para aplicar o status
  automaticamente. Com `80`, abaixo de 80% o e-mail vai para revisao manual.

Se essas linhas nao existirem, o sistema usa esses mesmos valores como padrao.

## Passo 7: conectar o e-mail no sistema

1. Rode o servidor Django:

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

2. Abra no navegador:

```text
http://localhost:8000/email/
```

3. Conecte sua conta Gmail.
4. Crie uma regra de captura.

Exemplos de regra:

- capturar e-mails vindos de `rh@empresa.com`;
- capturar e-mails do dominio `empresa.com`;
- capturar assuntos com palavras como `entrevista`, `processo seletivo`,
  `candidatura` ou `vaga`.

## Passo 8: fazer a varredura e a analise

Com o Ollama funcionando e o servidor Django configurado, rode:

```powershell
.\.venv\Scripts\python.exe manage.py scan_emails
```

Esse comando faz duas coisas:

1. Busca os e-mails que batem com as regras cadastradas.
2. Envia cada e-mail capturado para a IA analisar.

Depois disso, o sistema pode:

- aplicar automaticamente um status em uma candidatura;
- mandar o e-mail para revisao manual;
- criar uma vaga e candidatura em rascunho se detectar uma oportunidade nova.

## Passo 9: revisar os resultados

Abra:

```text
http://localhost:8000/email/revisao/
```

Nessa tela voce pode:

- confirmar a analise;
- trocar o status sugerido;
- vincular o e-mail a outra candidatura;
- ignorar o e-mail.

## Problemas comuns

### `ollama` nao e reconhecido

O Ollama nao foi instalado ou o PowerShell ainda nao atualizou o caminho do
programa. Feche e abra o PowerShell. Se nao resolver, reinicie o computador.

### A porta 11434 nao responde

O Ollama nao esta rodando. Abra o Ollama pelo menu iniciar ou rode:

```powershell
ollama serve
```

### O modelo demora para responder

Isso e normal em computadores sem placa de video dedicada. Modelos de IA podem
usar bastante memoria e processador.

### A varredura funciona, mas a analise nao

Confira:

```powershell
ollama --version
ollama list
Invoke-RestMethod http://localhost:11434/api/tags
```

Se `ollama list` nao funcionar, tente:

```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" list
```

Se esses comandos falharem, o problema esta no Ollama, nao no Django.

### O e-mail ficou como pendente

Isso acontece quando a IA nao estava disponivel, demorou demais ou retornou uma
resposta invalida. O comportamento e intencional: o sistema nao aplica mudancas
incertas quando a analise falha.

## Resumo rapido

```powershell
ollama --version
ollama pull llama3.2
ollama run llama3.2
.\.venv\Scripts\python.exe manage.py scan_emails
```

Depois revise em:

```text
http://localhost:8000/email/revisao/
```
