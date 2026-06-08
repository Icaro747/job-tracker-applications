"""Os formularios da operacao manual devem rotular os campos em portugues."""
from applications.forms import (
    CompanyForm,
    JobApplicationForm,
    JobForm,
    NextActionForm,
    StatusForm,
    TimelineNoteForm,
)


def _labels(form):
    return {name: field.label for name, field in form.fields.items()}


def test_company_form_labels_in_portuguese():
    labels = _labels(CompanyForm())
    assert labels['name'] == 'Nome'
    assert labels['website'] == 'Site'
    assert labels['careers_page'] == 'Pagina de carreiras'
    assert labels['notes'] == 'Observacoes'


def test_job_form_labels_in_portuguese():
    labels = _labels(JobForm())
    assert labels['company'] == 'Empresa'
    assert labels['role_title'] == 'Cargo'
    assert labels['source_url'] == 'Link da vaga'
    assert labels['location'] == 'Localizacao'
    assert labels['remote'] == 'Remoto'
    assert labels['directed_to'] == 'Direcionada a'


def test_application_form_labels_in_portuguese():
    labels = _labels(JobApplicationForm())
    assert labels['job'] == 'Vaga'
    assert labels['status'] == 'Status'
    assert labels['applied_at'] == 'Data da candidatura'
    assert labels['notes'] == 'Observacoes'


def test_next_action_form_labels_in_portuguese():
    labels = _labels(NextActionForm())
    assert labels['next_action_at'] == 'Data e hora'
    assert labels['next_action_type'] == 'Tipo'
    assert labels['next_action_description'] == 'Descricao'


def test_action_form_labels_in_portuguese():
    assert StatusForm().fields['status'].label == 'Novo status'
    assert TimelineNoteForm().fields['text'].label == 'Nota'
