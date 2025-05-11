from django.urls import path
from .views import (
    ChatListView,
    ChatView,
    ChatStreamView,
    chat_quiz,
)
from . import views

urlpatterns = [
    path('', ChatListView.as_view(), name='chat_list'),
    path('new/', ChatView.as_view(), name='new_chat'),
    path('create/', views.create_chat, name='create_chat'),
    path('<uuid:chat_id>/', ChatView.as_view(), name='chat_detail'),
    path('<uuid:chat_id>/stream/', ChatStreamView.as_view(), name='chat_stream'),
    path('<uuid:chat_id>/delete/', views.delete_chat, name='delete_chat'),
    path('<uuid:chat_id>/update-title/',
         views.update_chat_title, name='update_chat_title'),
    path('<uuid:chat_id>/clear/', views.clear_chat, name='clear_chat'),
    path('<uuid:chat_id>/quiz/', chat_quiz, name='chat_quiz'),
    path('<uuid:chat_id>/rag-files/', views.ChatRAGFilesView.as_view(), name='list_rag_files'),
    path('<uuid:chat_id>/rag-files/<int:file_id>/delete/', views.ChatRAGFilesView.as_view(), name='delete_rag_file'),
    path('<uuid:chat_id>/message/<int:message_id>/edit/', views.edit_message, name='edit_message'),
]
