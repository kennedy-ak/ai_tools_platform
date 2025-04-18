from django.contrib import admin
from .models import Document, ChatSession, Message, DocumentEmbedding


class DocumentEmbeddingInline(admin.TabularInline):
    model = DocumentEmbedding
    extra = 0
    fields = ('chunk_index', 'chunk_text_preview')
    readonly_fields = ('chunk_index', 'chunk_text_preview')
    
    def chunk_text_preview(self, obj):
        return obj.chunk_text[:100] + '...' if len(obj.chunk_text) > 100 else obj.chunk_text
    chunk_text_preview.short_description = 'Chunk Preview'


class ChatSessionInline(admin.TabularInline):
    model = ChatSession
    extra = 0
    fields = ('title', 'created_at', 'last_activity', 'message_count')
    readonly_fields = ('created_at', 'last_activity', 'message_count')
    
    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description = 'Messages'


class DocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'user', 'created_at', 'embedding_count', 'chat_session_count')
    list_filter = ('created_at',)
    search_fields = ('title', 'user__username')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)
    inlines = [DocumentEmbeddingInline, ChatSessionInline]
    
    def embedding_count(self, obj):
        return obj.embeddings.count()
    embedding_count.short_description = 'Embeddings'
    
    def chat_session_count(self, obj):
        return obj.chat_sessions.count()
    chat_session_count.short_description = 'Chat Sessions'


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ('role', 'content_preview', 'timestamp')
    readonly_fields = ('role', 'content_preview', 'timestamp')
    
    def content_preview(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_preview.short_description = 'Content'


class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'user', 'document', 'created_at', 'last_activity', 'message_count')
    list_filter = ('created_at', 'last_activity')
    search_fields = ('title', 'user__username', 'document__title')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'last_activity')
    inlines = [MessageInline]
    
    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description = 'Messages'


class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'chat_session', 'role', 'content_preview', 'timestamp')
    list_filter = ('role', 'timestamp')
    search_fields = ('content', 'chat_session__title')
    date_hierarchy = 'timestamp'
    readonly_fields = ('timestamp',)
    
    def content_preview(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_preview.short_description = 'Content'


admin.site.register(Document, DocumentAdmin)
admin.site.register(ChatSession, ChatSessionAdmin)
admin.site.register(Message, MessageAdmin)