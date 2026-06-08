"""Formularios da operacao manual (Etapa 2).

`user` e `origin` da candidatura sao definidos pela view, nunca pelo formulario.
Datas/horas usam o widget nativo ``datetime-local`` do navegador.
"""
from django import forms

from .models import Company, Job, JobApplication


class _DateTimeLocalInput(forms.DateTimeInput):
    input_type = 'datetime-local'

    def __init__(self, **kwargs):
        kwargs.setdefault('format', '%Y-%m-%dT%H:%M')
        super().__init__(**kwargs)


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ['name', 'website', 'careers_page', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 3})}


class JobForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = ['company', 'role_title', 'source_url', 'location', 'remote', 'directed_to']


class JobApplicationForm(forms.ModelForm):
    class Meta:
        model = JobApplication
        fields = ['job', 'status', 'applied_at', 'notes']
        widgets = {
            'applied_at': _DateTimeLocalInput(),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Candidatura manual comeca em rascunho ou enviada (spec 03).
        self.fields['status'].choices = [
            (JobApplication.Status.DRAFT, JobApplication.Status.DRAFT.label),
            (JobApplication.Status.APPLIED, JobApplication.Status.APPLIED.label),
        ]


class NextActionForm(forms.ModelForm):
    class Meta:
        model = JobApplication
        fields = ['next_action_at', 'next_action_type', 'next_action_description']
        widgets = {
            'next_action_at': _DateTimeLocalInput(),
            'next_action_description': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['next_action_at'].required = True
        self.fields['next_action_type'].required = True


class StatusForm(forms.Form):
    status = forms.ChoiceField(choices=JobApplication.Status.choices)


class TimelineNoteForm(forms.Form):
    text = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}))
