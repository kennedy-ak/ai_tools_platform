from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import UserProfile, UsageLog


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'User Profile'
    fk_name = 'user'


class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_usage_credits')
    list_select_related = ('profile',)
    
    def get_usage_credits(self, instance):
        return instance.profile.usage_credits
    get_usage_credits.short_description = 'Credits'
    

class UsageLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'service', 'timestamp', 'credits_used')
    list_filter = ('service', 'timestamp')
    search_fields = ('user__username', 'user__email')
    date_hierarchy = 'timestamp'


# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
admin.site.register(UsageLog, UsageLogAdmin)