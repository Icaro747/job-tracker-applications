"""Fase 2: atribuição determinística de links às vagas detectadas.

A 1a passada (classificação) recebe o corpo SEM links e devolve as vagas
(empresa/cargo). Aqui recuperamos os links do corpo original e os atribuímos à
vaga certa por casamento de texto — sem IA, sem alucinação.
"""
from email_ingestion.classifiers.base import DetectedOpportunity
from email_ingestion.classifiers.link_attribution import (
    attribute_source_urls,
    clean_url,
)

BODY = (
    'Seu alerta de vaga foi criado. Gerencie: '
    'https://www.linkedin.com/comm/jobs/alerts?lipi=3Durn\n\n'
    'Desenvolvedor (a) Backend Junior/Pleno - IT BSM\n'
    'BTG Pactual\n'
    'Sao Paulo, SP\n'
    'Melhor candidato\n'
    'Visualizar vaga: https://www.linkedin.com/comm/jobs/view/4404026219/?trk=3Dabc\n\n'
    '---------------------------------------------------------\n\n'
    'Engenharia de Software Senior\n'
    'Itau Unibanco\n'
    'Sao Paulo, SP\n'
    'Melhor candidato\n'
    'Visualizar vaga: https://www.linkedin.com/comm/jobs/view/4421208098/?trk=3Dxyz\n'
)


def test_clean_url_decodes_qp_and_soft_breaks():
    token = 'https://x.com/a?trk=3Deml_=\nfoo&t=3Dbar'

    assert clean_url(token) == 'https://x.com/a?trk=eml_foo&t=bar'


def test_attributes_correct_url_to_each_opportunity():
    opps = [
        DetectedOpportunity(company_name='BTG Pactual', role_title='Desenvolvedor Backend'),
        DetectedOpportunity(company_name='Itau Unibanco', role_title='Engenharia de Software'),
    ]

    attribute_source_urls(opps, BODY)

    assert '/jobs/view/4404026219/' in opps[0].source_url
    assert '/jobs/view/4421208098/' in opps[1].source_url


def test_does_not_attribute_non_job_urls():
    opps = [DetectedOpportunity(company_name='BTG Pactual', role_title='Backend')]

    attribute_source_urls(opps, BODY)

    assert 'jobs/alerts' not in opps[0].source_url
    assert '/jobs/view/4404026219/' in opps[0].source_url


def test_tolerates_company_typo_from_llm():
    # o modelo escreveu "BTG Patal" (typo) — ainda casa pelo bloco da BTG
    opps = [DetectedOpportunity(company_name='BTG Patal', role_title='Backend IT BSM')]

    attribute_source_urls(opps, BODY)

    assert '/jobs/view/4404026219/' in opps[0].source_url


def test_clears_hallucinated_url_when_no_match():
    opps = [
        DetectedOpportunity(
            company_name='Empresa Inexistente',
            role_title='Cargo Fantasma',
            source_url='https://alucinado.example/123',  # link inventado pela IA
        )
    ]

    attribute_source_urls(opps, BODY)

    assert opps[0].source_url == ''
