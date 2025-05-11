from django.db import models
from django.conf import settings
from users.models import CustomUser
import uuid


class Chat(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(CustomUser,
                             on_delete=models.CASCADE, related_name='chats')
    title = models.CharField(max_length=100, default="New Chat")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['updated_at']


class Message(models.Model):
    chat = models.ForeignKey(
        Chat, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=[('user', 'User'), ('assistant', 'Assistant')])
    content = models.TextField(blank=True)  # For normal text
    type = models.CharField(
        max_length=20, default='text')  # 'normal' or 'quiz' or 'text' or 'mindmap'
    quiz_html = models.TextField(blank=True, null=True)  # For quiz HTML
    diagram_image_url = models.CharField(max_length=500, blank=True, null=True) # For diagram image path
    created_at = models.DateTimeField(auto_now_add=True)
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.role}: {self.content[:50]}... in Chat {self.chat.title}"

    class Meta:
        ordering = ['created_at']


# Helper function to define upload path for RAG files
def rag_file_upload_path(instance, filename):
    # file will be uploaded to MEDIA_ROOT/rag_files/user_<id>/chat_<id>/<sanitized_filename>
    # Consider adding filename sanitization here if needed
    return f'rag_files/user_{instance.user.id}/chat_{instance.chat.id}/{filename}'


class ChatRAGFile(models.Model):
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='rag_files')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    file = models.FileField(upload_to=rag_file_upload_path)
    original_filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    # indexed_at = models.DateTimeField(null=True, blank=True) # Consider adding later

    def __str__(self):
        return f"{self.original_filename} for Chat {self.chat.id} (User: {self.user.username})"

    class Meta:
        ordering = ['-uploaded_at']
        unique_together = [['chat', 'original_filename']] 
        verbose_name = "Chat RAG File"
        verbose_name_plural = "Chat RAG Files"

    def save(self, *args, **kwargs):
        # Ensure original_filename is set if not provided (e.g. from file.name)
        if not self.original_filename and self.file:
            self.original_filename = self.file.name
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Also delete the actual file from storage when the model instance is deleted
        if self.file:
            self.file.delete(save=False) # save=False to prevent saving the model again after file deletion
        super().delete(*args, **kwargs)
