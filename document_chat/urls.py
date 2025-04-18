from django.urls import path
from . import views

app_name = 'document_chat'

urlpatterns = [
    path('', views.index, name='index'),
    path('upload/', views.upload_document, name='upload_document'),
    path('document/<int:document_id>/', views.view_document, name='view_document'),
    path('document/<int:document_id>/delete/', views.delete_document, name='delete_document'),
    path('document/<int:document_id>/create_chat/', views.create_chat_session, name='create_chat_session'),
    path('chat/<int:session_id>/', views.chat, name='chat'),
    path('chat/<int:session_id>/send/', views.send_message, name='send_message'),
    path('chat/<int:session_id>/delete/', views.delete_chat_session, name='delete_chat_session'),
]