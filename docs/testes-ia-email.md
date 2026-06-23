# Testes da IA de leitura de e-mails

Guia direto para **preparar o ambiente, rodar e ler os resultados** dos testes que
avaliam (1) a transformação do e-mail em texto e (2) a classificação por IA.

> Você escreve e-mails de teste em um único arquivo YAML; os testes leem dele
> automaticamente. Não precisa mexer em código Python.

---

## O que cada camada testa

| Camada | Arquivo | Precisa do Ollama? | Roda no dia a dia? |
|---|---|---|---|
| **Transformação** (HTML/texto → texto que a IA vê; mede perda de informação) | `tests/email_ingestion/test_email_extraction.py` | Não | Sim |
| **IA mockada** (valida o pipeline com resposta canônica) | `tests/email_ingestion/test_llm_eval_mocked.py` | Não | Sim |
| **IA real** (chama o Ollama de verdade e mede confiabilidade) | `tests/email_ingestion/test_llm_eval_real.py` | **Sim** | Não (opt-in) |

A camada de IA real é **só-relatório**: ela nunca falha quando o modelo erra — só
mede e imprime os percentuais de acerto. Assim dá para acompanhar a confiabilidade
sem deixar a suíte vermelha.

---

## 1. Preparar o ambiente

### 1.1 Dependências do projeto (uma vez)

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Isso já instala o `PyYAML`, necessário para ler os casos de teste.

### 1.2 Ollama — só para a camada de IA real

As camadas de **transformação** e **IA mockada** rodam sem nada extra. Para rodar a
**IA real** você precisa do Ollama no ar com o modelo configurado:

```powershell
# Em um terminal separado, deixe o servidor rodando:
ollama serve

# Baixe o modelo configurado (padrão: llama3.2). Veja qual está em uso:
#   OLLAMA_MODEL no .env, ou o padrão em config/settings.py
ollama pull llama3.2
```

Variáveis de ambiente relevantes (opcionais; têm padrão sensato):

| Variável | Padrão | Para quê |
|---|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` | Endereço do servidor Ollama |
| `OLLAMA_MODEL` | `llama3.2` | Modelo usado na classificação |
| `LLM_TIMEOUT` | `60` | Timeout (s) por requisição |
| `LLM_TEMPERATURE` | `0` | Temperatura do sampling (0 = determinístico/reprodutível) |
| `LLM_SEED` | `42` | Seed fixo do sampling (junto com temperatura 0, fixa a saída) |
| `LLM_EVAL_LABEL` | `` | Rótulo opcional do run no histórico (ex.: `baseline`, `temp0`) |

Para testar **outro modelo**, baixe-o (`ollama pull <modelo>`) e defina
`OLLAMA_MODEL=<modelo>` no `.env` antes de rodar.

> Se o Ollama estiver desligado, a camada de IA real é **pulada** automaticamente
> (não falha) — basta ligar o `ollama serve` quando quiser avaliá-la.

---

## 2. Escrever seus e-mails de teste

Edite **`tests/email_ingestion/llm_cases.yaml`**. Cada item é um e-mail. Exemplo:

```yaml
- id: convite-entrevista            # identificador único (vira o id do teste)
  sender: rh@acme.com
  subject: "Vamos agendar sua entrevista"
  body_text: |                       # corpo em TEXTO PURO (opcional)
    Olá! Queremos agendar sua entrevista para a vaga de Backend.
  body_html: |                       # corpo em HTML BRUTO (opcional)
    <p>Olá! Queremos agendar sua <b>entrevista</b>...</p>
  # Trechos que DEVERIAM sobreviver à transformação (mede perda):
  expect_extraction:
    contains: ["entrevista", "Backend"]
  # Candidaturas abertas que a IA "vê" como contexto (opcional):
  open_applications:
    - key: acme
      company: ACME
      role: Desenvolvedora Backend
      status: applied
  # Gabarito da IA:
  expect:
    intent: atualizacao              # atualizacao | nova_unica | lista | irrelevante
    suggested_status: interview      # ver lista de status abaixo, ou "" 
    application: acme                # qual open_application a IA deve apontar (opcional)
    opportunities: []               # vagas esperadas: lista de {company, role}
    min_confidence: 50              # piso de confiança esperado (opcional)
```

Regras rápidas:

- Informe **`body_text` e/ou `body_html`** (ao menos um). Os dois juntos simulam um
  e-mail multipart real (texto + HTML), como a maioria dos e-mails de verdade.
- Para colar o **HTML cru de um e-mail real** e ver se a transformação perde algo,
  use só `body_html` e liste em `expect_extraction.contains` o que não pode sumir
  (nome da empresa, link da vaga, prazo, etc.).
- `intent` válidos: `atualizacao`, `nova_unica`, `lista`, `irrelevante`.
- `suggested_status` válidos: `draft`, `applied`, `confirmed`, `screening`,
  `interview`, `offer`, `rejected`, `withdrawn`, `archived` (ou `""`).

---

## 3. Rodar os testes

Sempre pelo interpretador do `.venv`.

**Transformação + IA mockada (sem Ollama):**

```powershell
.\.venv\Scripts\python.exe -m pytest -s tests/email_ingestion/test_email_extraction.py tests/email_ingestion/test_llm_eval_mocked.py
```

**IA real (com o Ollama no ar):**

```powershell
.\.venv\Scripts\python.exe -m pytest -m llm -s tests/email_ingestion/test_llm_eval_real.py
```

> O `-m llm` é obrigatório: por padrão a suíte exclui a camada real
> (`addopts = -m "not llm"` no `pytest.ini`). O `-s` é o que faz o **relatório
> aparecer** no terminal.

**Suíte completa do app de e-mail (a IA real fica de fora):**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/email_ingestion/
```

Dica: para rodar **um caso só**, use o `id` dele: `... -k convite-entrevista`.

---

## 4. Ler os resultados

Ao fim da sessão (com `-s`), aparecem dois relatórios.

> **Acentos saindo errados no terminal?** Rode com UTF-8:
> `$env:PYTHONUTF8=1; .\.venv\Scripts\python.exe -m pytest ...`

### 4.1 Transformação do e-mail (o que ENTRA → o que SAI p/ a IA)

Sai da camada de extração (`test_email_extraction.py`). Mostra, **por e-mail**, o
formato de entrada e o **corpo exato que é enviado à IA**:

```
=== Transformacao do e-mail: o que ENTRA -> o que SAI p/ a IA ===
casos com perda de marcadores : 1/6

[newsletter-html-only]  (entrada: HTML)
  corpo extraido p/ IA: (vazio)
  PERDIDO na transformacao: Globex, Initech, Umbrella, https://jobs.globex.com/123, 30/06

[newsletter-multipart]  (entrada: texto+HTML)
  corpo extraido p/ IA: Vagas da semana: - Backend Python na Globex (...) Prazo: 30/06.
  perda de informacao: nenhuma
```

- `corpo extraido p/ IA` = o texto que efetivamente chega ao modelo. `(vazio)` quer
  dizer que **nada do corpo chegou** — típico de e-mail HTML-only hoje (não há
  conversor HTML→texto).
- `PERDIDO na transformacao` = trechos de `expect_extraction.contains` que sumiram.

### 4.2 Resposta da IA (corpo enviado → resultado), por e-mail

Sai da camada de IA real (`test_llm_eval_real.py`). Primeiro o placar agregado,
depois o **detalhe de cada e-mail**: o corpo enviado e tudo que a IA devolveu
(intent, status, **confiança = probabilidade 0–100**, vagas, resumo, justificativa):

```
=== Confiabilidade da IA (Ollama: llama3.2) ===
intent           : 4/6  (67%)
suggested_status : 1/6  (17%)
opportunities    : 0/3  (0%)
casos perfeitos  : 1/6
confianca media  : 33.3

--- Resposta da IA por e-mail (corpo enviado -> resultado) ---

[vaga-unica-recrutador]
  ENVIADO -> assunto: Oportunidade de Engenheiro de Plataforma na Initech
             corpo  : Oi! Encontrei seu perfil e tenho uma vaga de Engenheiro...
  IA -> intent          : nova_unica [OK] (esperado: nova_unica)
        suggested_status: draft [X] (esperado: (vazio))
        confianca       : 50
        application_id  : None
        vaga            : Initech / Engenheiro de Plataforma <https://initech.io/vaga/42>
        resumo          : Vaga de Engenheiro de Plataforma no Initech, modelo remoto
        justificativa   : O e-mail é uma oferta direta de uma vaga...

[newsletter-html-only]
  ENVIADO -> assunto: 3 vagas de Python para você
             corpo  : (vazio)
  IA -> intent          : irrelevante [X] (esperado: lista)
        ...
```

Como interpretar:

- **ENVIADO** = exatamente o que a IA recebeu (assunto + corpo já transformado). Quando
  o corpo está `(vazio)`, a IA decide só pelo assunto — veja o `newsletter-html-only`
  virar `irrelevante`: é a perda na transformação contaminando a interpretação da IA.
- **IA →** cada campo da resposta, com `[OK]`/`[X]` comparando ao gabarito `expect`:
  - `intent` — a categoria (atualizacao / nova_unica / lista / irrelevante);
  - `suggested_status` — o status sugerido;
  - `confianca` — a **probabilidade (0–100)** que o modelo atribuiu;
  - `vaga` — cada oportunidade extraída (empresa / cargo / link);
  - `resumo` e `justificativa` — texto livre do modelo.
- O placar agregado resume os acertos por dimensão, casos 100% corretos e a confiança
  média. A camada **passa mesmo com acertos baixos** — é medição, não verde/vermelho.
  Com `LLM_TEMPERATURE=0` + `LLM_SEED` fixo (padrão), o mesmo e-mail tende a dar a
  **mesma resposta** entre execuções; antes (temperatura 0.8) variava bastante.

### 4.3 Pontuação da execução + histórico (comparar ao longo do tempo)

Depois do detalhe por e-mail, sai um bloco com a **pontuação 0–100 desta execução** e
o **delta vs a execução anterior** — é o que permite ver se uma mudança (modelo, prompt,
determinismo, schema) melhorou ou piorou:

```
=== Pontuacao desta execucao [temp0] ===
config           : modelo=llama3.2 temp=0.0 seed=42 format=schema
confiabilidade   : 58.3/100  (acuracia vs gabarito)
completude       : 71.4/100  (campos respondidos)
SCORE GERAL      : 62.2/100
vs run anterior [baseline]: 49.0 -> 62.2  (+13.2)
```

- **confiabilidade** = quanto a IA **acertou** contra o gabarito `expect` (intent,
  status, vagas, candidatura). É a "confiabilidade real".
- **completude** = quantos dos 7 campos pedidos a IA **respondeu** (mais campos
  respondidos → maior). Uma resposta vazia/alucinada pontua baixo aqui.
- **SCORE GERAL** = blend `0.7 × confiabilidade + 0.3 × completude` (pesos em
  `RELIABILITY_WEIGHT`/`COMPLETENESS_WEIGHT` em `llm_cases.py`).
- Cada execução é **anexada** a `tests/email_ingestion/llm_eval_history.json` (artefato
  local, fora do git), registrando data, modelo, config (temperatura/seed/format) e os
  três números. Use `LLM_EVAL_LABEL=baseline` (ou `temp0`, `schema`, …) para rotular
  cada run e facilitar a comparação no histórico.

**Fluxo de avaliação sugerido:** rode um **baseline** → aplique uma melhoria → rode de
novo e leia o delta. Como a saída é determinística (temperatura 0 + seed), a diferença
entre runs reflete a mudança, não o ruído do sampling.

---

## 5. O que acontece com o corpo antes/depois da IA (Fases 1 e 2)

Para e-mails ruidosos (ex.: alertas do LinkedIn, cheios de URLs de tracking
gigantes em quoted-printable), o pipeline faz duas passadas:

- **Fase 1 — classificação com corpo enxuto** (`body_for_classification`,
  em `email_ingestion/classifiers/body_normalization.py`): antes de enviar à IA,
  decodifica quoted-printable, **remove as URLs**, colapsa espaços e trunca o texto.
  Sem isso, modelos pequenos se perdem no ruído (chegavam a devolver um JSON com
  schema inventado). Com o corpo limpo, a classificação volta a funcionar.
- **Saída estruturada por JSON Schema** (`OllamaClassifier.RESPONSE_FORMAT`): a chamada
  envia um JSON Schema completo no `format` (com `enum` em `intent`/`suggested_status`),
  em vez de só `format: 'json'`. Isso restringe a forma da resposta na origem e reduz
  alucinação de schema. A chamada também fixa `options` determinísticas (temperatura 0
  + seed), tornando a saída reprodutível.
- **Validação de alucinação** (`OllamaClassifier`): se o modelo ainda assim devolve um
  JSON que **não contém nenhuma** das chaves esperadas (`intent`, `summary`,
  `opportunities`, …) ou um não-objeto, isso é tratado como falha
  (`ClassifierError`) em vez de virar uma classificação vazia silenciosa. No
  relatório da IA real, esses casos aparecem como **"respostas fora do schema
  (alucinacao)"** e pontuam zero.
- **Fase 2 — atribuição determinística de links** (`link_attribution.py`): como a
  Fase 1 tira os links, depois recuperamos do corpo original o link de cada vaga e
  o atribuímos por **casamento de texto** (tolera typos do modelo; descarta URLs
  que a IA tenha inventado). Sem IA nessa etapa.
  - *Limitação conhecida:* duas vagas quase idênticas da **mesma empresa** podem
    ter os links trocados entre si (o casamento por texto não as distingue bem).

## Notas

- **E-mail HTML-only ainda sai vazio.** A extração (`GmailAdapter._extract_body`)
  só aproveita a parte `text/plain`; não há conversor HTML→texto. A camada de
  transformação **mede** essa perda. (A limpeza da Fase 1 atua sobre o texto já
  extraído — não recupera conteúdo de um corpo HTML-only que chegou vazio.)
- **Trocar de modelo:** baixe outro (`ollama pull <modelo>`), defina
  `OLLAMA_MODEL=<modelo>` no `.env` e rode a camada de IA real de novo para comparar.
