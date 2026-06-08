from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Company, JobApplication


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
