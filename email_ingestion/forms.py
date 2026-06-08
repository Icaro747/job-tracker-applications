"""Formularios das contas de e-mail e regras de varredura (Etapa 3).

`scan_times` e `subject_keywords` sao listas JSON no modelo, mas o usuario as
edita como texto simples (horarios/termos separados por virgula).
"""
import re

from django import forms

from .models import EmailAccount, EmailSenderRule

_TIME_RE = re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')


def _split_csv(value):
    """Quebra um texto separado por virgula numa lista limpa, sem vazios."""
    return [item.strip() for item in (value or '').split(',') if item.strip()]


class EmailAccountForm(forms.ModelForm):
    """Edita a programacao de varredura e o estado da conta.

    A conexao em si (provedor, e-mail, tokens) vem do fluxo OAuth, nao daqui.
    """

    scan_times = forms.CharField(
        label='Horarios de varredura',
        help_text='Horarios HH:MM separados por virgula. Ex: 08:00, 13:00, 19:00',
        required=True,
    )

    class Meta:
        model = EmailAccount
        fields = ['is_active', 'scan_times']
        labels = {'is_active': 'Ativa para varredura'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial['scan_times'] = ', '.join(self.instance.scan_times or [])

    def clean_scan_times(self):
        times = _split_csv(self.cleaned_data['scan_times'])
        if not times:
            raise forms.ValidationError('Informe ao menos um horario.')
        for value in times:
            if not _TIME_RE.match(value):
                raise forms.ValidationError(f'Horario invalido: "{value}". Use o formato HH:MM.')
        return times


class EmailSenderRuleForm(forms.ModelForm):
    subject_keywords = forms.CharField(
        label='Palavras-chave no assunto',
        help_text='Termos separados por virgula. Ex: vaga, entrevista, oportunidade',
        required=False,
    )

    class Meta:
        model = EmailSenderRule
        fields = [
            'name',
            'company',
            'sender_email',
            'sender_domain',
            'subject_keywords',
            'is_active',
        ]
        labels = {
            'name': 'Nome da regra',
            'company': 'Empresa vinculada',
            'sender_email': 'E-mail do remetente',
            'sender_domain': 'Dominio do remetente',
            'is_active': 'Ativa',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial['subject_keywords'] = ', '.join(self.instance.subject_keywords or [])

    def clean_subject_keywords(self):
        return _split_csv(self.cleaned_data['subject_keywords'])

    def clean(self):
        cleaned = super().clean()
        if not (
            cleaned.get('sender_email')
            or cleaned.get('sender_domain')
            or cleaned.get('subject_keywords')
        ):
            raise forms.ValidationError(
                'Preencha ao menos um filtro: remetente, dominio ou palavras-chave no assunto.'
            )
        return cleaned
