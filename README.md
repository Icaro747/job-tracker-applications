# Gerenciador de candidaturas a vagas

Projeto Django para gerenciar candidaturas de emprego, acompanhar atualizacoes recebidas por e-mail e centralizar dados do curriculo para reduzir preenchimento repetitivo em formularios.

## Objetivos iniciais

- Catalogar candidaturas, empresas, status e historico.
- Ler e classificar e-mails de remetentes configurados.
- Gerar lembretes e eventos relacionados a candidaturas.
- Armazenar perfil, experiencias, formacao, competencias e respostas padrao.
- Preparar uma base simples que pode evoluir para API Django + interface React.

## Como rodar localmente

Use sempre o ambiente virtual do projeto para evitar conflito com pacotes globais ou de outros projetos.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Acesse:

- Aplicacao: http://127.0.0.1:8000/
- Admin: http://127.0.0.1:8000/admin/

## Como atualizar dependencias

Depois de instalar ou remover pacotes com o ambiente virtual ativado, recrie o `requirements.txt` com:

```powershell
python -m pip freeze > requirements.txt
```

## Apps Django

- `applications`: empresas, candidaturas e linha do tempo.
- `email_ingestion`: regras de remetentes, e-mails recebidos e classificacao.
- `candidate_profile`: dados do candidato, curriculo e respostas salvas.
- `notifications`: lembretes e eventos de calendario.
- `autofill`: mapeamentos e sugestoes para preenchimento de formularios.

## Documentacao

- [Visao do produto](docs/product-overview.md)
- [Fluxos principais](docs/main-flows.md)
- [Arquitetura inicial](docs/architecture.md)
- [Roadmap](docs/roadmap.md)
