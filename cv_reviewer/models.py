from django.db import models
from django.contrib.auth.models import User


class CVReview(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cv_reviews')
    original_filename = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Review scores (0-100)
    structure_score = models.IntegerField(default=0)
    content_score = models.IntegerField(default=0)
    skills_score = models.IntegerField(default=0)
    experience_score = models.IntegerField(default=0)
    overall_score = models.IntegerField(default=0)
    
    # Review content
    structure_feedback = models.TextField(blank=True, null=True)
    content_feedback = models.TextField(blank=True, null=True)
    skills_feedback = models.TextField(blank=True, null=True)
    experience_feedback = models.TextField(blank=True, null=True)
    improvement_suggestions = models.TextField(blank=True, null=True)
    
    # Optional job role targeting
    job_role = models.CharField(max_length=255, blank=True, null=True)
    
    # Email notification
    email_sent = models.BooleanField(default=False)
    email_address = models.EmailField(blank=True, null=True)
    
    def __str__(self):
        return f"CV Review for {self.user.username} - {self.created_at.strftime('%Y-%m-%d')}"
    
    class Meta:
        ordering = ['-created_at']


class CVDocument(models.Model):
    review = models.OneToOneField(CVReview, on_delete=models.CASCADE, related_name='document')
    file = models.FileField(upload_to='cv_documents/')
    content_text = models.TextField(blank=True, null=True)
    file_type = models.CharField(max_length=10, choices=[('pdf', 'PDF'), ('docx', 'DOCX')])
    upload_date = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Document for {self.review}"