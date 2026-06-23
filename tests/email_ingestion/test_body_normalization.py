from email_ingestion.classifiers.body_normalization import (
    body_for_classification,
    normalize_body_for_llm,
)


def test_normalize_body_decodes_quoted_printable_text():
    raw = 'BTG Pactual · S=C3=A3o Paulo, SP'

    assert normalize_body_for_llm(raw) == 'BTG Pactual · São Paulo, SP'


def test_normalize_body_decodes_soft_line_breaks_in_text():
    raw = 'Gerencie=\r\n seus alertas de vaga'

    assert normalize_body_for_llm(raw) == 'Gerencie seus alertas de vaga'


def test_normalize_body_preserves_url_literal_while_decoding_text():
    url = (
        'https://www.linkedin.com/comm/jobs/alerts?lipi=3Durn'
        '%3Ali%3Apage%3Aemail&midToken=3DAQECvilt1_KaCw'
    )
    raw = f'S=C3=A3o Paulo: {url} pr=C3=B3xima vaga'

    assert normalize_body_for_llm(raw) == f'São Paulo: {url} próxima vaga'


def test_normalize_body_keeps_clean_text_readable():
    raw = 'Senior Software Engineer, Quality Platform\nAirbnb · Brasil (Remoto)'

    assert normalize_body_for_llm(raw) == raw


def test_normalize_body_preserves_multiple_urls_in_order():
    first = 'https://example.com/a?x=3D1'
    second = 'http://jobs.example.com/b?token=3Dabc&next=%3D'
    raw = f'Primeira: {first} S=C3=A3o Paulo Segunda: {second} remoto'

    assert (
        normalize_body_for_llm(raw)
        == f'Primeira: {first} São Paulo Segunda: {second} remoto'
    )


def test_normalize_body_preserves_quoted_printable_wrapped_url():
    url = 'https://example.com/jobs?trk=3Deml-email_job_=\nalert&token=3Dabc'
    raw = f'S=C3=A3o Paulo {url}\nPr=C3=B3xima vaga'

    assert normalize_body_for_llm(raw) == f'São Paulo {url}\nPróxima vaga'


# --- body_for_classification: corpo enxuto p/ a 1a passada de classificacao --- #
def test_classification_body_removes_urls_keeping_text():
    url = 'https://www.linkedin.com/comm/jobs/view/123?trk=3Dabc&token=3Dxyz'
    raw = f'Desenvolvedor Backend na BTG Pactual {url} fim'

    out = body_for_classification(raw)

    assert 'http' not in out
    assert 'BTG Pactual' in out
    assert 'Desenvolvedor Backend' in out


def test_classification_body_removes_quoted_printable_wrapped_url():
    url = 'https://example.com/jobs?trk=3Deml-email_job_=\nalert&token=3Dabc'
    raw = f'Visualizar vaga: {url}\nBTG Pactual'

    out = body_for_classification(raw)

    assert 'http' not in out
    assert 'BTG Pactual' in out


def test_classification_body_decodes_quoted_printable_text():
    out = body_for_classification('Engenharia de Software S=C3=AAnior')

    assert 'Sênior' in out
    assert '=C3=AA' not in out


def test_classification_body_truncates_oversized_input():
    raw = 'BTG Pactual ' + ('lorem ' * 5000)

    out = body_for_classification(raw, max_chars=200)

    assert len(out) <= 220
    assert 'BTG Pactual' in out
