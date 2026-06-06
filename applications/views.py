from django.shortcuts import render

from .models import Company, JobApplication


def home(request):
    context = {
        'total_applications': JobApplication.objects.count(),
        'active_applications': JobApplication.objects.exclude(
            status__in=[
                JobApplication.Status.REJECTED,
                JobApplication.Status.WITHDRAWN,
                JobApplication.Status.ARCHIVED,
            ],
        ).count(),
        'companies': Company.objects.count(),
        'recent_applications': JobApplication.objects.select_related('company')[:8],
    }
    return render(request, 'home.html', context)
