# Arquitetura inicial

## Stack

- Python 3.12
- Django 6
- SQLite em desenvolvimento
- Django Admin como interface inicial

## Ambiente virtual

O projeto deve rodar em um ambiente virtual local (`.venv`) para separar as dependencias deste projeto dos pacotes globais da maquina e de outros projetos.

Fluxo recomendado:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Quando novas dependencias forem instaladas no ambiente virtual, atualize o arquivo de dependencias com:

```powershell
python -m pip freeze > requirements.txt
```

## Organizacao

```text
config/              Configuracao Django
applications/        Empresas, candidaturas e linha do tempo
email_ingestion/     Regras, e-mails recebidos e classificacao
candidate_profile/   Perfil, curriculo e respostas salvas
notifications/       Lembretes e eventos
autofill/            Mapeamento e sugestoes de campos
docs/                Documentacao de produto e engenharia
templates/           Templates HTML simples
```

## Decisoes

- O admin sera usado na primeira fase para acelerar validacao do dominio.
- Os modelos foram separados por responsabilidade para facilitar uma futura API.
- Leitura real de e-mails ainda nao foi implementada; a base ja contempla regras, e-mails recebidos e classificacao.
- Automacao de preenchimento ainda nao foi implementada; a base ja contempla mapeamentos e sugestoes.

## Evolucao para API + React

Quando a interface precisar ficar mais rica:

1. Adicionar Django REST Framework.
2. Expor endpoints para candidaturas, perfil, notificacoes e sugestoes.
3. Criar frontend React consumindo a API.
4. Manter Django Admin como ferramenta operacional interna.

## Integracoes previstas

- Gmail/Outlook via OAuth para leitura de e-mails.
- Servico de classificacao de texto para interpretar atualizacoes.
- Google Calendar/Outlook Calendar para eventos.
- Extensao de navegador ou bookmarklet para sugestoes em formularios.
