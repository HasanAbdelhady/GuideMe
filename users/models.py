from django.contrib.auth.models import AbstractUser
from django.db import models


class Interest(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    profile_image = models.ImageField(
        upload_to="profile_images/", blank=True, null=True
    )

    # Learning style preferences
    LEARNING_STYLE_CHOICES = [
        ("visual", "Visual"),
        ("auditory", "Auditory"),
        ("kinesthetic", "Kinesthetic"),
        ("reading_writing", "Reading/Writing"),
    ]

    STUDY_TIME_CHOICES = [
        ("short", "Short bursts"),
        ("medium", "Medium sessions"),
        ("long", "Long sessions"),
    ]

    QUIZ_PREFERENCE_CHOICES = [
        (1, "Not at all helpful"),
        (2, "Not very helpful"),
        (3, "Neutral"),
        (4, "Somewhat Helpful"),
        (5, "Very helpful"),
    ]

    # Survey fields
    learning_style_visual = models.BooleanField(default=False)
    learning_style_auditory = models.BooleanField(default=False)
    learning_style_kinesthetic = models.BooleanField(default=False)
    learning_style_reading = models.BooleanField(default=False)

    # Modified interests field with through model
    interests = models.ManyToManyField(
        Interest, through="UserInterest", related_name="users", blank=True
    )

    study_habits = models.TextField(blank=True, help_text="Describe your study habits")
    preferred_study_time = models.CharField(
        max_length=10, choices=STUDY_TIME_CHOICES, default="medium"
    )
    quiz_preference = models.IntegerField(choices=QUIZ_PREFERENCE_CHOICES, default=3)

    def __str__(self):
        return self.email

    def get_primary_learning_style(self):
        styles = {
            "visual": self.learning_style_visual,
            "auditory": self.learning_style_auditory,
            "kinesthetic": self.learning_style_kinesthetic,
            "reading_writing": self.learning_style_reading,
        }
        return max(styles, key=styles.get)

    def get_learning_preferences(self):
        return {
            "learning_styles": {
                "visual": bool(self.learning_style_visual),
                "auditory": bool(self.learning_style_auditory),
                "kinesthetic": bool(self.learning_style_kinesthetic),
                "reading": bool(self.learning_style_reading),
            },
            "study_time": self.preferred_study_time or "medium",
            "quiz_preference": bool(self.quiz_preference),
            "interests": [interest.name for interest in self.interests.all()],
        }

    def get_user_interests(self):
        return self.interests.all()


class UserInterest(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    interest = models.ForeignKey(Interest, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "interest")  # Prevents duplicate entries
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} - {self.interest.name}"
