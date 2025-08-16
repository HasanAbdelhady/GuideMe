from django.contrib import admin

from .models import Chat, Message


class ChatAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "title",
        "created_at",
        "updated_at",
    )  # Customize fields as needed
    search_fields = ("title",)  # Add search functionality


class MessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "chat",
        "role",
        "content",
        "created_at",
    )  # Customize fields as needed
    list_filter = ("chat", "role")  # Add filters for easier navigation


# Register your models here.
admin.site.register(Chat, ChatAdmin)
admin.site.register(Message, MessageAdmin)
