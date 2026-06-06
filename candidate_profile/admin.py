from django.contrib import admin

from .models import CandidateProfile, Education, Experience, SavedAnswer, Skill


class ExperienceInline(admin.TabularInline):
    model = Experience
    extra = 0


class EducationInline(admin.TabularInline):
    model = Education
    extra = 0


class SkillInline(admin.TabularInline):
    model = Skill
    extra = 0


class SavedAnswerInline(admin.TabularInline):
    model = SavedAnswer
    extra = 0


@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'user', 'headline', 'email', 'updated_at')
    search_fields = ('full_name', 'headline', 'email', 'user__username')
    inlines = [ExperienceInline, EducationInline, SkillInline, SavedAnswerInline]
