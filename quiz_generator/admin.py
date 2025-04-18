from django.contrib import admin
from .models import Quiz, Question, Option, QuizAttempt, Answer


class OptionInline(admin.TabularInline):
    model = Option
    extra = 0


class QuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'quiz', 'question_type', 'question_text_preview')
    list_filter = ('question_type', 'quiz')
    search_fields = ('question_text', 'quiz__title')
    inlines = [OptionInline]
    
    def question_text_preview(self, obj):
        return obj.question_text[:50] + '...' if len(obj.question_text) > 50 else obj.question_text
    question_text_preview.short_description = 'Question'


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    show_change_link = True
    fields = ('question_text_preview', 'question_type')
    readonly_fields = ('question_text_preview',)
    
    def question_text_preview(self, obj):
        return obj.question_text[:50] + '...' if len(obj.question_text) > 50 else obj.question_text
    question_text_preview.short_description = 'Question'


class QuizAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'user', 'difficulty', 'created_at', 'question_count')
    list_filter = ('difficulty', 'created_at')
    search_fields = ('title', 'user__username', 'description')
    date_hierarchy = 'created_at'
    inlines = [QuestionInline]
    
    def question_count(self, obj):
        return obj.questions.count()
    question_count.short_description = 'Questions'


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    fields = ('question', 'selected_option', 'text_answer', 'is_correct')
    readonly_fields = ('question', 'selected_option', 'text_answer', 'is_correct')


class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'quiz', 'start_time', 'end_time', 'score')
    list_filter = ('start_time', 'end_time')
    search_fields = ('user__username', 'quiz__title')
    date_hierarchy = 'start_time'
    inlines = [AnswerInline]
    readonly_fields = ('start_time', 'end_time', 'score')


admin.site.register(Quiz, QuizAdmin)
admin.site.register(Question, QuestionAdmin)
admin.site.register(QuizAttempt, QuizAttemptAdmin)