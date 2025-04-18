from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Quiz(models.Model):
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quizzes')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='medium')
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    original_file_name = models.CharField(max_length=255, blank=True, null=True)
    
    def __str__(self):
        return f"{self.title} ({self.get_difficulty_display()})"
    
    class Meta:
        verbose_name_plural = "Quizzes"
        ordering = ['-created_at']


class Question(models.Model):
    QUESTION_TYPES = [
        ('multiple_choice', 'Multiple Choice'),
        ('true_false', 'True/False'),
        ('fill_in_blank', 'Fill in the Blank'),
    ]
    
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES)
    explanation = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.question_text[:50]}..."


class Option(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    option_text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.option_text} ({'Correct' if self.is_correct else 'Incorrect'})"


class QuizAttempt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quiz_attempts')
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    def __str__(self):
        if self.score:
            return f"{self.user.username}'s attempt on {self.quiz.title} - Score: {self.score}"
        return f"{self.user.username}'s attempt on {self.quiz.title} - In progress"
    
    def calculate_score(self):
        if self.end_time:
            total_questions = self.quiz.questions.count()
            if total_questions == 0:
                return 0
                
            correct_answers = self.answers.filter(is_correct=True).count()
            score = (correct_answers / total_questions) * 100
            self.score = score
            self.save()
            return score
        return None


class Answer(models.Model):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_option = models.ForeignKey(Option, on_delete=models.CASCADE, null=True, blank=True)
    text_answer = models.CharField(max_length=255, blank=True, null=True)
    is_correct = models.BooleanField(default=False)
    
    def __str__(self):
        if self.question.question_type == 'multiple_choice':
            answer = self.selected_option.option_text if self.selected_option else "No answer"
        elif self.question.question_type == 'true_false':
            answer = "True" if self.selected_option and self.selected_option.is_correct else "False"
        else:
            answer = self.text_answer or "No answer"
            
        return f"Q: {self.question.question_text[:30]}... - A: {answer}"
    
    def check_correctness(self):
        if self.question.question_type == 'multiple_choice':
            if self.selected_option:
                self.is_correct = self.selected_option.is_correct
        elif self.question.question_type == 'true_false':
            if self.selected_option:
                self.is_correct = self.selected_option.is_correct
        elif self.question.question_type == 'fill_in_blank':
            correct_option = self.question.options.filter(is_correct=True).first()
            if correct_option and self.text_answer:
                # Case insensitive comparison
                self.is_correct = self.text_answer.lower().strip() == correct_option.option_text.lower().strip()
        self.save()
        return self.is_correct