from django.urls import path
from . import views

app_name = 'cv_reviewer'

urlpatterns = [
    path('', views.index, name='index'),
    path('create/', views.create_review, name='create_review'),
    path('view/<int:review_id>/', views.view_review, name='view_review'),
    path('delete/<int:review_id>/', views.delete_review, name='delete_review'),
]