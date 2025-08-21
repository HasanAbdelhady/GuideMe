from django.urls import path

from . import views
from .views import (
    ChatRAGFilesView,
    ChatStreamView,
    ChatView,
    chat_quiz,
    clear_chat,
    create_chat,
    edit_message,
    generate_flashcards_view,
    get_quiz_html,
    serve_diagram_image,
    study_hub_view,
    update_chat_title,
    list_rag_files,
)

urlpatterns = [
    path("new/", ChatView.as_view(), name="new_chat"),
    path("create/", create_chat, name="create_chat"),
    path("<uuid:chat_id>/", ChatView.as_view(), name="chat_detail"),
    path("<uuid:chat_id>/stream/", ChatStreamView.as_view(), name="chat_stream"),
    path("<uuid:chat_id>/delete/", views.delete_chat, name="delete_chat"),
    path("<uuid:chat_id>/update-title/", update_chat_title, name="update_chat_title"),
    path("<uuid:chat_id>/clear/", clear_chat, name="clear_chat"),
    path("<uuid:chat_id>/quiz/", chat_quiz, name="chat_quiz"),
    path("<uuid:chat_id>/study/", study_hub_view, name="study_hub"),
    path("<uuid:chat_id>/rag-files/", list_rag_files, name="list_rag_files"),
    path(
        "<uuid:chat_id>/rag-files/apply_rag",
        ChatRAGFilesView.as_view(),
        name="list_rag_files",
    ),
    path(
        "<uuid:chat_id>/rag-files/<int:file_id>/delete/",
        ChatRAGFilesView.as_view(),
        name="delete_rag_file",
    ),
    path(
        "<uuid:chat_id>/message/<int:message_id>/edit/",
        edit_message,
        name="edit_message",
    ),
    path("flashcards/", generate_flashcards_view, name="flashcards_generator"),
    path(
        "diagram_image/<uuid:diagram_id>/",
        serve_diagram_image,
        name="serve_diagram_image",
    ),
    path("quiz_html/<int:message_id>/", get_quiz_html, name="get_quiz_html"),
]
