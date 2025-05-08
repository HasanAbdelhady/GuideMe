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
    path('<int:chat_id>/', ChatView.as_view(), name='chat_detail'),
    path('<int:chat_id>/stream/', ChatStreamView.as_view(), name='chat_stream'),
    path('<int:chat_id>/delete/', views.delete_chat, name='delete_chat'),
    path('<int:chat_id>/update-title/',
         views.update_chat_title, name='update_chat_title'),
    path('<int:chat_id>/clear/', views.clear_chat, name='clear_chat'),
    path('<int:chat_id>/quiz/', chat_quiz, name='chat_quiz'),
]
