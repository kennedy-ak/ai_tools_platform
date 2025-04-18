from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(max_length=500, blank=True)
    usage_credits = models.IntegerField(default=10)
    date_joined = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"


class UsageLog(models.Model):
    SERVICE_CHOICES = [
        ('quiz_generator', 'Quiz Generator'),
        ('cv_reviewer', 'CV Reviewer'),
        ('document_chat', 'Document Chat'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='usage_logs')
    service = models.CharField(max_length=20, choices=SERVICE_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    credits_used = models.IntegerField(default=1)
    
    def __str__(self):
        return f"{self.user.username} used {self.service} on {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()