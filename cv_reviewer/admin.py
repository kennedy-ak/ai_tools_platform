from django.contrib import admin
from .models import CVReview, CVDocument


class CVDocumentInline(admin.StackedInline):
    model = CVDocument
    can_delete = False
    fields = ('file', 'file_type', 'upload_date')
    readonly_fields = ('upload_date',)


class CVReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'original_filename', 'job_role', 'overall_score', 'created_at', 'email_sent')
    list_filter = ('created_at', 'email_sent')
    search_fields = ('user__username', 'original_filename', 'job_role', 'email_address')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'structure_score', 'content_score', 
                      'skills_score', 'experience_score', 'overall_score')
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'original_filename', 'job_role', 'email_address', 'email_sent', 'created_at')
        }),
        ('Scores', {
            'fields': ('overall_score', 'structure_score', 'content_score', 'skills_score', 'experience_score')
        }),
        ('Feedback', {
            'fields': ('structure_feedback', 'content_feedback', 'skills_feedback', 
                      'experience_feedback', 'improvement_suggestions')
        }),
    )
    inlines = [CVDocumentInline]


admin.site.register(CVReview, CVReviewAdmin)