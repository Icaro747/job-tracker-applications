from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .forms import (
    CompanyForm,
    JobApplicationForm,
    JobForm,
    NextActionForm,
    StatusForm,
    TimelineNoteForm,
)
from .models import (
    Company,
    CompanyAuditLog,
    Job,
    JobApplication,
)


@login_required
def home(request):
    applications = JobApplication.objects.filter(user=request.user)
    context = {
        'total_applications': applications.count(),
        'active_applications': applications.exclude(
            status__in=[
                JobApplication.Status.REJECTED,
                JobApplication.Status.WITHDRAWN,
                JobApplication.Status.ARCHIVED,
            ],
        ).count(),
        'companies': Company.objects.count(),
        'recent_applications': applications.select_related('job__company')[:8],
    }
    return render(request, 'home.html', context)


# --------------------------------------------------------------------------- #
# Empresa — recurso global (qualquer autenticado cria/edita/exclui).          #
# --------------------------------------------------------------------------- #
class CompanyListView(LoginRequiredMixin, ListView):
    model = Company
    context_object_name = 'companies'


class CompanyDetailView(LoginRequiredMixin, DetailView):
    model = Company

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['audit_logs'] = self.object.audit_logs.select_related('user')
        context['jobs'] = self.object.jobs.all()
        return context


class CompanyCreateView(LoginRequiredMixin, CreateView):
    model = Company
    form_class = CompanyForm

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        CompanyAuditLog.record_create(self.object, self.request.user)
        return response


class CompanyUpdateView(LoginRequiredMixin, UpdateView):
    model = Company
    form_class = CompanyForm

    def form_valid(self, form):
        old_values = {
            field: getattr(self.get_object(), field)
            for field in CompanyAuditLog.AUDITED_FIELDS
        }
        response = super().form_valid(form)
        CompanyAuditLog.record_update(self.object, self.request.user, old_values)
        return response


class CompanyDeleteView(LoginRequiredMixin, DeleteView):
    model = Company
    success_url = reverse_lazy('applications:company_list')

    def form_valid(self, form):
        company = self.get_object()
        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                'Nao e possivel excluir esta empresa: existem vagas vinculadas a ela.',
            )
            return redirect('applications:company_detail', pk=company.pk)
        # Exclusao e hard delete: os logs de auditoria sao removidos em cascata
        # junto com a empresa, entao registramos apenas uma confirmacao na sessao.
        messages.success(self.request, f'Empresa "{company.name}" excluida.')
        return response


# --------------------------------------------------------------------------- #
# Vaga — recurso global.                                                       #
# --------------------------------------------------------------------------- #
class JobListView(LoginRequiredMixin, ListView):
    model = Job
    context_object_name = 'jobs'

    def get_queryset(self):
        return super().get_queryset().select_related('company', 'directed_to')


class JobDetailView(LoginRequiredMixin, DetailView):
    model = Job


class JobCreateView(LoginRequiredMixin, CreateView):
    model = Job
    form_class = JobForm

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class JobUpdateView(LoginRequiredMixin, UpdateView):
    model = Job
    form_class = JobForm


class JobDeleteView(LoginRequiredMixin, DeleteView):
    model = Job
    success_url = reverse_lazy('applications:job_list')

    def form_valid(self, form):
        job = self.get_object()
        try:
            return super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                'Nao e possivel excluir esta vaga: existem candidaturas vinculadas a ela.',
            )
            return redirect('applications:job_detail', pk=job.pk)


# --------------------------------------------------------------------------- #
# Candidatura — privada por usuario.                                          #
# --------------------------------------------------------------------------- #
class OwnedApplicationMixin(LoginRequiredMixin):
    """Restringe o queryset as candidaturas do usuario autenticado."""

    model = JobApplication

    def get_queryset(self):
        return JobApplication.objects.filter(user=self.request.user)


class ApplicationListView(OwnedApplicationMixin, ListView):
    context_object_name = 'applications'
    template_name = 'applications/application_list.html'

    def get_queryset(self):
        return super().get_queryset().select_related('job__company')


class ApplicationDetailView(OwnedApplicationMixin, DetailView):
    template_name = 'applications/application_detail.html'
    context_object_name = 'application'

    def get_queryset(self):
        return super().get_queryset().select_related('job__company')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['timeline'] = self.object.timeline.all()
        context['status_form'] = StatusForm(initial={'status': self.object.status})
        context['next_action_form'] = NextActionForm(instance=self.object)
        context['note_form'] = TimelineNoteForm()
        return context


class ApplicationCreateView(OwnedApplicationMixin, CreateView):
    form_class = JobApplicationForm
    template_name = 'applications/application_form.html'

    def get_initial(self):
        initial = super().get_initial()
        job_id = self.request.GET.get('job')
        if job_id:
            initial['job'] = job_id
        return initial

    def form_valid(self, form):
        form.instance.user = self.request.user
        form.instance.origin = JobApplication.Origin.MANUAL
        return super().form_valid(form)


class ApplicationUpdateView(OwnedApplicationMixin, UpdateView):
    form_class = JobApplicationForm
    template_name = 'applications/application_form.html'


class ApplicationDeleteView(OwnedApplicationMixin, DeleteView):
    template_name = 'applications/application_confirm_delete.html'
    context_object_name = 'application'
    success_url = reverse_lazy('applications:application_list')


# --------------------------------------------------------------------------- #
# Acoes HTMX da candidatura — retornam partials atualizados.                  #
# --------------------------------------------------------------------------- #
def _get_owned_application(request, pk):
    return get_object_or_404(JobApplication, pk=pk, user=request.user)


def _render_detail_panels(request, application):
    """Renderiza os tres paineis (status, proxima acao, timeline) de uma vez.

    HTMX faz swap do container; assim qualquer acao reflete em todos os blocos.
    """
    return render(
        request,
        'applications/_detail_panels.html',
        {
            'application': application,
            'timeline': application.timeline.all(),
            'status_form': StatusForm(initial={'status': application.status}),
            'next_action_form': NextActionForm(instance=application),
            'note_form': TimelineNoteForm(),
        },
    )


@login_required
@require_POST
def application_change_status(request, pk):
    application = _get_owned_application(request, pk)
    form = StatusForm(request.POST)
    if form.is_valid():
        application.change_status(form.cleaned_data['status'])
    return _render_detail_panels(request, application)


@login_required
@require_POST
def application_add_note(request, pk):
    application = _get_owned_application(request, pk)
    form = TimelineNoteForm(request.POST)
    if form.is_valid():
        application.add_note(form.cleaned_data['text'])
    return _render_detail_panels(request, application)


@login_required
@require_POST
def application_set_next_action(request, pk):
    application = _get_owned_application(request, pk)
    form = NextActionForm(request.POST, instance=application)
    if form.is_valid():
        application.set_next_action(
            at=form.cleaned_data['next_action_at'],
            action_type=form.cleaned_data['next_action_type'],
            description=form.cleaned_data['next_action_description'],
        )
    return _render_detail_panels(request, application)


@login_required
@require_POST
def application_complete_next_action(request, pk):
    application = _get_owned_application(request, pk)
    note = request.POST.get('note', '')
    application.complete_next_action(note=note)
    return _render_detail_panels(request, application)
