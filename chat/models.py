import uuid

from django.conf import settings
from django.db import models

from pgvector.django import VectorField

from users.models import CustomUser


class Chat(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="chats")
    title = models.CharField(max_length=100, default="New Chat")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ["updated_at"]


class DiagramImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chat = models.ForeignKey(
        Chat, on_delete=models.CASCADE, related_name="diagram_images"
    )
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="diagram_images"
    )
    image_data = models.BinaryField()
    filename = models.CharField(max_length=255, default="diagram.png")
    content_type = models.CharField(max_length=50, default="image/png")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Diagram {self.filename} for Chat {self.chat.id} (User: {self.user.username})"

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Diagram Image"
        verbose_name_plural = "Diagram Images"


class Message(models.Model):
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(
        max_length=10, choices=[("user", "User"), ("assistant", "Assistant")]
    )
    content = models.TextField(blank=True)  # For normal text
    type = models.CharField(
        max_length=20,
        default="text",
        choices=[
            ("text", "Text"),
            ("quiz", "Quiz"),
            ("diagram", "Diagram"),
            ("youtube", "YouTube"),
            ("flashcard_update", "Flashcard Update"),
            ("background_process", "Background Process"),
            ("mixed", "Mixed Content"),  # New type for mixed content
        ],
    )
    # For structured data like YouTube links and mixed content
    structured_content = models.JSONField(null=True, blank=True)
    # Separate field specifically for mixed content metadata
    mixed_content_data = models.JSONField(null=True, blank=True)
    quiz_html = models.TextField(blank=True, null=True)  # For quiz HTML
    diagram_image = models.ForeignKey(
        DiagramImage,
        on_delete=models.SET_NULL,  # Or models.CASCADE if image is essential
        null=True,
        blank=True,
        related_name="messages",
    )
    # New fields to support mixed content
    has_diagram = models.BooleanField(default=False)
    has_youtube = models.BooleanField(default=False)
    has_quiz = models.BooleanField(default=False)
    has_code = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.role}: {self.content[:50]}... in Chat {self.chat.title}"

    class Meta:
        ordering = ["created_at"]

    def is_mixed_content(self):
        """Check if this message contains mixed content types"""
        return (
            self.type == "mixed"
            or sum([self.has_diagram, self.has_youtube, self.has_quiz, self.has_code])
            > 1
        )


# Helper function to define upload path for RAG files
def rag_file_upload_path(instance, filename):
    # file will be uploaded to MEDIA_ROOT/rag_files/user_<id>/chat_<id>/<sanitized_filename>
    # Consider adding filename sanitization here if needed
    return f"rag_files/user_{instance.user.id}/chat_{instance.chat.id}/{filename}"


class ChatRAGFile(models.Model):
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name="rag_files")
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    file = models.FileField(upload_to=rag_file_upload_path)
    original_filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    # indexed_at = models.DateTimeField(null=True, blank=True) # Consider adding later

    def __str__(self):
        return f"{self.original_filename} for Chat {self.chat.id} (User: {self.user.username})"

    class Meta:
        ordering = ["-uploaded_at"]
        unique_together = [["chat", "original_filename"]]
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
            # save=False to prevent saving the model again after file deletion
            self.file.delete(save=False)
        super().delete(*args, **kwargs)


class ChatFlashcard(models.Model):
    """Store flashcards for each chat"""

    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name="flashcards")
    term = models.CharField(max_length=200)
    definition = models.TextField()
    context = models.TextField(blank=True)  # Context from conversation
    auto_generated = models.BooleanField(default=False)  # AI-generated vs user-created
    created_at = models.DateTimeField(auto_now_add=True)
    last_reviewed = models.DateTimeField(null=True, blank=True)
    review_count = models.IntegerField(default=0)
    confidence_level = models.IntegerField(default=0)  # 0-5 scale for spaced repetition

    class Meta:
        unique_together = ["chat", "term"]
        ordering = ["-created_at"]
        verbose_name = "Chat Flashcard"
        verbose_name_plural = "Chat Flashcards"

    def __str__(self):
        return f"{self.term} - {self.chat.title[:30]}"


class ChatQuestionBank(models.Model):
    """Store quiz questions from each chat"""

    chat = models.ForeignKey(
        Chat, on_delete=models.CASCADE, related_name="question_bank"
    )
    question_html = models.TextField()  # The full quiz HTML
    question_text = models.TextField()  # Extracted question text for search
    correct_answer = models.CharField(max_length=10)  # A, B, C, D
    topic = models.CharField(max_length=300, blank=True)  # Topic/subject
    difficulty = models.CharField(
        max_length=20,
        default="medium",
        choices=[("easy", "Easy"), ("medium", "Medium"), ("hard", "Hard")],
    )
    times_answered = models.IntegerField(default=0)
    times_correct = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Chat Question Bank"
        verbose_name_plural = "Chat Question Banks"

    def __str__(self):
        return f"Q: {self.question_text[:50]}... - {self.chat.title[:30]}"

    @property
    def success_rate(self):
        if self.times_answered == 0:
            return 0
        return (self.times_correct / self.times_answered) * 100


class DocumentChunk(models.Model):
    """Store document chunks with their vector embeddings"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chat = models.ForeignKey(
        Chat, on_delete=models.CASCADE, related_name="document_chunks"
    )
    rag_file = models.ForeignKey(
        ChatRAGFile, on_delete=models.CASCADE, related_name="chunks"
    )

    # Text content
    content = models.TextField()
    chunk_index = models.IntegerField()

    # Vector embedding (384 dimensions for all-MiniLM-L6-v2)
    embedding = VectorField(dimensions=384)

    # Metadata
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "chat_document_chunks"
        indexes = [
            models.Index(fields=["chat", "chunk_index"]),
            models.Index(fields=["rag_file"]),
        ]


class ChatVectorIndex(models.Model):
    """Track vector index status for chats"""

    chat = models.OneToOneField(
        Chat, on_delete=models.CASCADE, related_name="vector_index"
    )
    total_chunks = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)
    embedding_model = models.CharField(max_length=100, default="all-MiniLM-L6-v2")

    class Meta:
        db_table = "chat_vector_index"
