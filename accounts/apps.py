from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

# # accounts/apps.py
# from django.apps import AppConfig


# class AccountsConfig(AppConfig):
#     default_auto_field = 'django.db.models.BigAutoField'
#     name = 'accounts'

#     def ready(self):
#         import accounts.signals  # noqa


# # quiz_generator/apps.py
# from django.apps import AppConfig


# class QuizGeneratorConfig(AppConfig):
#     default_auto_field = 'django.db.models.BigAutoField'
#     name = 'quiz_generator'


# # cv_reviewer/apps.py
# from django.apps import AppConfig


# class CvReviewerConfig(AppConfig):
#     default_auto_field = 'django.db.models.BigAutoField'
#     name = 'cv_reviewer'


# # document_chat/apps.py
# from django.apps import AppConfig


# class DocumentChatConfig(AppConfig):
#     default_auto_field = 'django.db.models.BigAutoField'
#     name = 'document_chat'