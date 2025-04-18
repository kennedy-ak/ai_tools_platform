from django.urls import path
from . import views

app_name = 'quiz_generator'

urlpatterns = [
    path('', views.index, name='index'),
    path('create/', views.create_quiz, name='create_quiz'),
    path('view/<int:quiz_id>/', views.view_quiz, name='view_quiz'),
    path('take/<int:quiz_id>/', views.take_quiz, name='take_quiz'),
    path('submit_answer/<int:attempt_id>/', views.submit_answer, name='submit_answer'),
    path('finish/<int:attempt_id>/', views.finish_quiz, name='finish_quiz'),
    path('results/<int:attempt_id>/', views.quiz_results, name='quiz_results'),
    path('delete/<int:quiz_id>/', views.delete_quiz, name='delete_quiz'),
]