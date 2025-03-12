from django.contrib.auth.models import AbstractUser
from django.db import models

class Subject(models.Model):
    name = models.CharField(max_length=100, unique=True)
    
    def __str__(self):
        return self.name

class Interest(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)
    
    # Predefined subjects
    SUBJECT_CHOICES = [
        ('ml', 'Machine Learning'),
        ('dl', 'Deep Learning'),
        ('nlp', 'Natural Language Processing'),
        ('cv', 'Computer Vision'),
        ('ai', 'Artificial Intelligence'),
        ('ds', 'Data Science'),
        ('py', 'Python Programming'),
        ('dsa', 'Data Structures & Algorithms'),
        ('db', 'Databases'),
        ('web', 'Web Development'),
        ('cloud', 'Cloud Computing'),
        ('sec', 'Cybersecurity'),
        ('rob', 'Robotics'),
        ('de', 'Data Engineering'),
    ]

    # Learning style preferences
    LEARNING_STYLE_CHOICES = [
        ('visual', 'Visual'),
        ('auditory', 'Auditory'),
        ('kinesthetic', 'Kinesthetic'),
        ('reading_writing', 'Reading/Writing'),
    ]
    
    STUDY_TIME_CHOICES = [
        ('short', 'Short bursts'),
        ('medium', 'Medium sessions '),
        ('long', 'Long sessions'),
    ]
    
    QUIZ_PREFERENCE_CHOICES = [
        (1, 'Very helpful'),
        (2, 'Somewhat helpful'),
        (3, 'Neutral'),
        (4, 'Not very helpful'),
        (5, 'Not at all helpful'),
    ]
    
    # Survey fields
    learning_style_visual = models.IntegerField(default=0)
    learning_style_auditory = models.IntegerField(default=0)
    learning_style_kinesthetic = models.IntegerField(default=0)
    learning_style_reading = models.IntegerField(default=0)
    
    interests = models.ManyToManyField(Interest, blank=True)
    custom_interests = models.TextField(blank=True, help_text="Additional subjects you're interested in")
    
    study_habits = models.TextField(blank=True, help_text="Describe your study habits")
    preferred_study_time = models.CharField(
        max_length=10,
        choices=STUDY_TIME_CHOICES,
        default='medium'
    )
    quiz_preference = models.IntegerField(
        choices=QUIZ_PREFERENCE_CHOICES,
        default=3
    )

    def __str__(self):
        return self.email

    def get_primary_learning_style(self):
        styles = {
            'visual': self.learning_style_visual,
            'auditory': self.learning_style_auditory,
            'kinesthetic': self.learning_style_kinesthetic,
            'reading_writing': self.learning_style_reading
        }
        return max(styles, key=styles.get)

    def get_learning_preferences(self):
        return {
            'learning_styles': {
                'visual': bool(self.learning_style_visual),
                'auditory': bool(self.learning_style_auditory),
                'kinesthetic': bool(self.learning_style_kinesthetic),
                'reading': bool(self.learning_style_reading)
            },
            'study_time': self.preferred_study_time or 'medium',
            'quiz_preference': bool(self.quiz_preference),
            'interests': [interest.name for interest in self.interests.all()]
        }