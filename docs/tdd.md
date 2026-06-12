# TDD — Guia de Desenvolvimento por Testes

## Objetivo

O projeto adota **Test-Driven Development (TDD)** como paradigma de desenvolvimento. Toda funcionalidade, fluxo, ou mecanismo do sistema deve ter um teste correspondente escrito **antes** do código de produção. Isso garante:

- Estabilidade ao longo do desenvolvimento
- Detecção imediata de regressões quando funcionalidades anteriores quebram
- Confiança para refatorar sem medo de efeitos colaterais
- Documentação viva do comportamento esperado do sistema

---

## O Ciclo RED-GREEN-REFACTOR

Todo desenvolvimento neste projeto segue este ciclo, sem exceção:

```
1. RED    → Escreva um teste que falha descrevendo o comportamento desejado
2. GREEN  → Escreva o mínimo de código para o teste passar
3. REFACTOR → Limpe o código mantendo os testes verdes
4. REPITA → Nunca escreva código de produção sem um teste falhando antes
```

**Regra crítica:** Se está implementando uma feature ou corrigindo um bug, escreva o teste primeiro. O teste reprovado (`FAILED`) é a autorização para escrever código de produção.

---

## Conjunto canônico de testes por comportamento

> **Qualidade não é quantidade.** O valor de uma suíte não está em *quantos* testes
> existem, mas em *o que cada teste prova*. Uma montanha de testes redundantes dá
> falsa confiança e custa manutenção. Cada teste deve corresponder a uma
> **proposição distinta** sobre o comportamento — se dois testes provam a mesma
> coisa, um deles sobra.

Para cada comportamento que **recebe entrada e produz efeito** (um endpoint, um
método de domínio que valida, um formulário), o ponto de partida é um conjunto
canônico que cobre sucesso **e** falha. Não é um teto nem uma cota: é o mínimo que
responde *"a aplicação reage certo, e quando recusa, diz claramente por quê?"*.

### Os caminhos de sucesso (2)

1. **Entrada completa → sucesso.** Todos os campos (obrigatórios **e** opcionais)
   enviados corretamente. Assere o efeito esperado: registro criado/alterado,
   status correto, resposta de sucesso.
2. **Mínimo viável → sucesso.** Só os campos **obrigatórios**, omitindo os
   opcionais. Prova que o opcional é de fato opcional e que o caminho feliz não
   depende dele. (Quando o comportamento não tem campos opcionais, este caso se
   funde ao anterior — são 1, não 2.)

### Os caminhos de falha (3) — o coração da política

O objetivo dos testes de falha **não** é só ver que "deu erro". É verificar que a
aplicação **recusa de forma específica e legível**, identificando *o quê* e *por
quê* — e que **o efeito não aconteceu**. Cada teste de falha assere as duas coisas:

- **(a) Nada mudou.** A operação não teve efeito colateral (nada criado, status
  inalterado) — `Model.objects.count()` igual, `refresh_from_db()` sem mudança.
- **(b) A recusa é explícita e específica.** Status/código correto **e** uma
  mensagem que aponta o campo ou a regra violada. **Não** basta `assert
  response.status_code != 200`; é preciso assertar o *conteúdo* do erro.

Os três cenários de exemplo:

3. **Dados duplicados.** Tentar criar algo que viola unicidade (empresa de nome já
   existente, `message_id` repetido). A resposta deve dizer que é duplicado, não
   estourar 500 nem aceitar em silêncio.
4. **Dados incompatíveis / que quebram regra.** Valor fora do domínio (status
   inválido, transição proibida, tipo errado, e-mail malformado). A resposta deve
   nomear a regra violada.
5. **Campo obrigatório faltando.** Omitir um campo exigido. A resposta deve apontar
   *qual* campo falta.

### A regra do erro silencioso

> **Erro silencioso é bug.** Uma requisição problemática que retorna `200` e não faz
> nada, um `save()` que falha sem sinal, um endpoint HTMX que devolve o mesmo card
> sem explicar a recusa — todos são falhas de produto, não "comportamentos
> aceitáveis". Sempre que existir um caminho de recusa, **deve existir um teste que
> prova que a recusa é visível e específica**.

Esta política tem dente direto no projeto: a spec
[13-revisao-orientada-a-intencao.md](../.specs/13-revisao-orientada-a-intencao.md)
nasceu de um "clique sem efeito" (HTTP 200 que não fazia nada e não dava feedback).
O teste de falha correspondente não para em "o status não mudou": ele assere que o
card re-renderizado **contém a faixa de erro** explicando por que a confirmação foi
recusada.

### Exemplo aplicado — `email_confirm_apply` sem candidatura

```python
class TestEmailConfirmApply:
    # sucesso completo
    def test_confirma_com_candidatura_e_status_aplica_e_vincula(self, auth_client, user):
        ...  # assere status aplicado + e-mail vinculado + reviewed_at preenchido

    # falha: obrigatório faltando — recusa ESPECÍFICA, não silenciosa
    def test_confirma_sem_candidatura_recusa_com_erro_visivel(self, auth_client, user):
        email = InboundEmailFactory(email_account__user=user, application=None)
        resp = auth_client.post(reverse("email_ingestion:email_confirm", args=[email.pk]))
        # (a) nada mudou
        email.refresh_from_db()
        assert email.application_id is None
        assert email.processing_status == "needs_review"
        # (b) recusa explícita e específica — NÃO um 200 mudo
        assert b"Selecione uma candidatura" in resp.content
```

### Quando o conjunto canônico flexiona

- **Mais regras → mais testes de falha.** Se o comportamento tem 3 regras de
  validação distintas, são 3 testes de "regra quebrada", um por regra. O número 3
  acima é a *forma* (duplicado / incompatível / obrigatório), não um limite.
- **Sem entrada de usuário → sem os 5.** Um `__str__`, uma property derivada ou um
  manager não recebem entrada problemática: testam-se pelo seu propósito direto,
  sem inventar cenários de falha artificiais.
- **Fluxo de ponta a ponta** (`test_flows.py`) cobre a *sequência* (receber →
  classificar → confirmar); os 5 canônicos cobrem cada *passo* isoladamente. Os dois
  níveis se complementam, não se substituem.

---

## Setup do Ambiente de Testes

### Dependências necessárias

Adicionar ao projeto:

```
pytest
pytest-django
factory-boy
pytest-cov
```

### Configuração em `pyproject.toml`

```toml
[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings"
python_files = ["test_*.py"]
addopts = ["--reuse-db", "-ra"]
```

Se o projeto não tiver `pyproject.toml`, criar um arquivo `pytest.ini` na raiz:

```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
python_files = test_*.py
addopts = --reuse-db -ra
```

---

## Estrutura de Arquivos de Teste

Os testes são organizados em um diretório `tests/` centralizado, espelhando a estrutura dos apps:

```
tests/
├── conftest.py                    # Fixtures compartilhadas globais
├── factories.py                   # Factories de todos os models
├── applications/
│   ├── test_models.py             # Company, JobApplication, ApplicationTimelineEntry
│   ├── test_views.py              # Views de candidatura
│   └── test_flows.py              # Fluxos completos (ex: ciclo de vida de candidatura)
├── autofill/
│   ├── test_models.py             # AutofillFieldMapping, AutofillSuggestion
│   └── test_views.py
├── candidate_profile/
│   ├── test_models.py             # CandidateProfile, Experience, Education, Skill, SavedAnswer
│   └── test_views.py
├── email_ingestion/
│   ├── test_models.py             # EmailSenderRule, InboundEmail, EmailClassification
│   ├── test_classification.py     # Lógica de classificação de emails
│   └── test_flows.py              # Fluxo completo: receber → classificar → atualizar candidatura
└── notifications/
    ├── test_models.py             # ApplicationReminder, CalendarEvent
    └── test_flows.py              # Fluxo: criar reminder → disparar → marcar enviado
```

Os arquivos `tests.py` dentro de cada app devem ser **removidos** ou deixados vazios. Toda lógica de teste vai em `tests/`.

---

## Convenções de Nomenclatura

### Arquivos
- `test_models.py` — testa métodos, propriedades, e managers de models
- `test_views.py` — testa status codes, contexto, redirecionamentos, e autenticação
- `test_forms.py` — testa validação e comportamento de formulários
- `test_flows.py` — testa fluxos completos de ponta a ponta

### Classes e Métodos

```python
class TestJobApplicationStatusTransition:
    def test_mark_as_applied_changes_status(self): ...
    def test_reject_creates_timeline_entry(self): ...
    def test_archived_application_cannot_be_applied(self): ...
```

Padrão: `test_<ação>_<resultado_esperado>`

---

## Factories

Cada model deve ter uma factory correspondente em `tests/factories.py`. As factories são a única forma de criar dados de teste — nunca criar instâncias manualmente dentro dos testes.

```python
# tests/factories.py
import factory
from django.contrib.auth.models import User
from applications.models import Company, JobApplication
from candidate_profile.models import CandidateProfile

class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"usuario_{n}")
    email = factory.Faker("email")
    password = factory.PostGenerationMethodCall("set_password", "senha123")

class CandidateProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CandidateProfile

    user = factory.SubFactory(UserFactory)
    full_name = factory.Faker("name", locale="pt_BR")
    headline = factory.Faker("job", locale="pt_BR")

class CompanyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Company

    name = factory.Faker("company", locale="pt_BR")
    website = factory.Faker("url")

class JobApplicationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = JobApplication

    user = factory.SubFactory(UserFactory)
    company = factory.SubFactory(CompanyFactory)
    role = factory.Faker("job", locale="pt_BR")
    status = "draft"
```

---

## Fixtures em `conftest.py`

```python
# tests/conftest.py
import pytest
from tests.factories import UserFactory, CandidateProfileFactory

@pytest.fixture
def user(db):
    return UserFactory()

@pytest.fixture
def candidate_user(db):
    user = UserFactory()
    CandidateProfileFactory(user=user)
    return user

@pytest.fixture
def auth_client(client, user):
    client.force_login(user)
    return client

@pytest.fixture
def candidate_client(client, candidate_user):
    client.force_login(candidate_user)
    return client
```

---

## O Que Testar em Cada App

### `applications`

| O que testar | Exemplo |
|---|---|
| Transições de status de candidatura | `draft → applied → interview → offer` |
| Criação automática de `ApplicationTimelineEntry` em mudanças de status | Mudança de status cria entrada no timeline |
| Candidaturas pertencem ao usuário correto | Usuário A não vê candidaturas do Usuário B |
| Filtros e listagem de candidaturas | Filtrar por status, empresa |
| `__str__` dos models | `"Engenheiro na Empresa X"` |

### `email_ingestion`

| O que testar | Exemplo |
|---|---|
| Classificação de email pelo domínio do remetente | `@empresa.com` mapeia para candidatura correta |
| `InboundEmail` muda status após classificação | `pending → classified` |
| Emails sem regra vão para `needs_review` | Remetente desconhecido |
| Confiança de `EmailClassification` | Apenas ordena/rotula a fila — nada é aplicado automaticamente (emenda 12); tudo vai para revisão |

### `candidate_profile`

| O que testar | Exemplo |
|---|---|
| Um `User` só pode ter um `CandidateProfile` | Segundo profile lança erro |
| `Experience` e `Education` pertencem ao profile correto | |
| Níveis de `Skill` são válidos | Valor fora das opções levanta erro |
| `SavedAnswer` retorna a resposta certa por chave | |

### `notifications`

| O que testar | Exemplo |
|---|---|
| `ApplicationReminder` muda para `sent` após disparo | |
| `CalendarEvent` cancelado não pode ser agendado | |
| Reminder vinculado à candidatura correta | |

### `autofill`

| O que testar | Exemplo |
|---|---|
| `AutofillFieldMapping` mapeia campo corretamente | `"first_name"` → `profile.full_name` |
| `AutofillSuggestion` muda de `suggested` para `accepted` | |
| Sugestão `rejected` não é usada | |

---

## Exemplos de Teste

### Teste de Model

```python
# tests/applications/test_models.py
import pytest
from tests.factories import JobApplicationFactory

pytestmark = pytest.mark.django_db

class TestJobApplication:
    def test_str_returns_role_and_company(self):
        application = JobApplicationFactory(role="Engenheiro de Software")
        assert "Engenheiro de Software" in str(application)

    def test_initial_status_is_draft(self):
        application = JobApplicationFactory()
        assert application.status == "draft"
```

### Teste de View

```python
# tests/applications/test_views.py
import pytest
from tests.factories import JobApplicationFactory

pytestmark = pytest.mark.django_db

class TestJobApplicationListView:
    def test_anonymous_user_is_redirected(self, client):
        response = client.get("/candidaturas/")
        assert response.status_code == 302

    def test_user_sees_only_own_applications(self, auth_client, user):
        own = JobApplicationFactory(user=user)
        other = JobApplicationFactory()  # outro usuário
        response = auth_client.get("/candidaturas/")
        assert own in response.context["applications"]
        assert other not in response.context["applications"]
```

### Teste de Fluxo

```python
# tests/applications/test_flows.py
import pytest
from tests.factories import JobApplicationFactory

pytestmark = pytest.mark.django_db

class TestApplicationLifecycle:
    def test_applying_creates_timeline_entry(self, auth_client, user):
        application = JobApplicationFactory(user=user, status="draft")
        auth_client.post(f"/candidaturas/{application.pk}/aplicar/")
        application.refresh_from_db()
        assert application.status == "applied"
        assert application.timeline_entries.filter(event_type="status_change").exists()
```

---

## Como Executar os Testes

```bash
# Todos os testes
uv run pytest

# Parar no primeiro erro
uv run pytest -x

# Rodar só os que falharam antes
uv run pytest --lf

# Parar no primeiro + só os que falharam
uv run pytest -x --lf

# App específico
uv run pytest tests/applications/

# Teste específico por nome
uv run pytest -k "test_user_sees_only_own"

# Com relatório de cobertura
uv run pytest --cov=applications --cov=email_ingestion --cov=candidate_profile --cov=notifications --cov=autofill
```

---

## Regras do Projeto

1. **Nenhuma feature sem teste.** Código de produção só é escrito após um teste falhando.
2. **Nenhum bug fix sem teste.** A correção de um bug começa com um teste que reproduz o bug.
3. **Factories, nunca instâncias manuais.** Dados de teste são criados via factories.
4. **Testes independentes.** Cada teste limpa seu próprio estado. Não há dependência entre testes.
5. **Testes testam comportamento, não implementação.** Testa o que o sistema faz, não como ele faz.
6. **CI não passa sem testes verdes.** A suite completa deve passar antes de qualquer merge.
7. **Todo comportamento com entrada cobre sucesso e falha.** Aplica-se o conjunto canônico (ver seção acima): caminhos felizes (completo e mínimo) **e** falhas específicas. Cada teste prova uma proposição distinta — quantidade não substitui propósito.
8. **Erro silencioso é bug.** Toda recusa precisa de um teste que prove que ela é visível e específica (status correto + motivo legível), nunca um `200` mudo ou uma falha sem sinal.

---

## Referências

- [pytest-django](https://pytest-django.readthedocs.io/)
- [Factory Boy](https://factoryboy.readthedocs.io/)
- [TDD by Example — Kent Beck](https://www.oreilly.com/library/view/test-driven-development/0321146530/)
