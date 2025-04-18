from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib import messages
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

import os
import re
import json
import uuid
import pickle
import numpy as np
from pathlib import Path
import tempfile
import PyPDF2
from groq import Groq
from sentence_transformers import SentenceTransformer
import faiss

from .models import Document, ChatSession, Message, DocumentEmbedding
from accounts.models import UsageLog


class FAISSIndex:
    def __init__(self, dimension=384):
        self.dimension = dimension
        self.index = faiss.IndexFlatL2(dimension)
        
    def add_embeddings(self, embeddings):
        if len(embeddings) > 0:
            self.index.add(embeddings)
    
    def search(self, query_embedding, top_k=5):
        if self.index.ntotal == 0:
            return None, None
        
        if len(query_embedding.shape) == 1:
            query_embedding = query_embedding.reshape(1, -1)
            
        distances, indices = self.index.search(query_embedding, min(top_k, self.index.ntotal))
        return distances, indices


def load_embedding_model():
    """Load the sentence transformer model for embeddings."""
    return SentenceTransformer("all-MiniLM-L6-v2")


def extract_text_from_pdf(file_path):
    """Extract text from a PDF file."""
    text = ""
    with open(file_path, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        for page in reader.pages:
            text += page.extract_text()
    
    # Clean up text
    text = re.sub(r"\n", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    
    return text


def chunk_text(text, chunk_size=1000, overlap=100):
    """Split text into chunks with overlap."""
    words = text.split()
    chunks = []
    
    if len(words) <= chunk_size:
        return [text]
    
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i+chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    
    return chunks


def create_embeddings(document, chunks):
    """Create embeddings for document chunks."""
    model = load_embedding_model()
    embeddings = []
    
    # Delete existing embeddings for this document
    DocumentEmbedding.objects.filter(document=document).delete()
    
    # Create new embeddings
    for i, chunk in enumerate(chunks):
        embedding = model.encode(chunk)
        
        # Save embedding to database
        DocumentEmbedding.objects.create(
            document=document,
            chunk_text=chunk,
            embedding_data=pickle.dumps(embedding),
            chunk_index=i
        )
        
        embeddings.append(embedding)
    
    return np.array(embeddings)


def search_document(document, query, top_k=3):
    """Search the document for relevant chunks based on query."""
    model = load_embedding_model()
    query_embedding = model.encode(query)
    
    # Get all embeddings for this document
    db_embeddings = DocumentEmbedding.objects.filter(document=document).order_by('chunk_index')
    
    if not db_embeddings:
        return []
    
    # Create a FAISS index
    embeddings = np.array([pickle.loads(e.embedding_data) for e in db_embeddings])
    index = FAISSIndex(dimension=embeddings.shape[1])
    index.add_embeddings(embeddings)
    
    # Search for similar chunks
    distances, indices = index.search(query_embedding, top_k)
    
    if indices is None:
        return []
    
    # Get the relevant chunks
    # results = []
    # for idx in indices[0]:
    #     results.append(db_embeddings[idx].chunk_text)
        
    results = []
    for idx in indices[0]:
        # Convert int64 to regular int before indexing
        idx = int(idx)  # This line fixes the error
        results.append(db_embeddings[idx].chunk_text)
    
    return results


def generate_response(query, context, chat_history):
    """Generate a response using Groq API based on context and chat history."""
    try:
        api_key = settings.GROQ_API_KEY
        if not api_key:
            return "API key not found. Please check your configuration."
        
        client = Groq(api_key=api_key)
        
        # Format chat history
        history_text = ""
        if chat_history:
            history_text = "Previous conversation:\n"
            for msg in chat_history:
                history_text += f"User: {msg['user']}\nAssistant: {msg['assistant']}\n\n"
        
        # Create prompt
        prompt = f"""
{history_text}
Context from document: {context}

User: {query}
Assistant:"""
        
        # Generate completion
        completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a helpful assistant answering questions about documents."},
                {"role": "user", "content": prompt}
            ],
            model="gemma2-9b-it",
            max_tokens=350
        )
        
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Error generating response: {str(e)}")
        return f"Error: {str(e)}"


@login_required
def index(request):
    """Main page for document chat app."""
    # Get all user documents
    documents = Document.objects.filter(user=request.user).order_by('-created_at')
    
    # Get recent chat sessions
    chat_sessions = ChatSession.objects.filter(user=request.user).order_by('-last_activity')[:5]
    
    context = {
        'documents': documents,
        'chat_sessions': chat_sessions,
    }
    
    return render(request, 'document_chat/index.html', context)


@login_required
def upload_document(request):
    """Upload a new document and create embeddings."""
    if request.method == 'POST':
        # Check if user has enough credits
        if request.user.profile.usage_credits < 1:
            messages.error(request, "You don't have enough credits to upload a document. Please contact support to get more credits.")
            return redirect('document_chat:index')
        
        # Get form data
        uploaded_file = request.FILES.get('document_file')
        title = request.POST.get('title') or uploaded_file.name
        
        if not uploaded_file:
            messages.error(request, "Please upload a PDF file.")
            return redirect('document_chat:upload_document')
        
        # Check file extension
        file_extension = uploaded_file.name.split('.')[-1].lower()
        if file_extension != 'pdf':
            messages.error(request, "Only PDF files are supported at this time.")
            return redirect('document_chat:upload_document')
        
        try:
            # Save the file temporarily
            unique_filename = f"{uuid.uuid4().hex}.pdf"
            file_path = default_storage.save(f"documents/{unique_filename}", ContentFile(uploaded_file.read()))
            
            # Extract text from PDF
            text = extract_text_from_pdf(default_storage.path(file_path))
            
            if not text:
                messages.error(request, "Could not extract text from the uploaded file. Please try a different file.")
                default_storage.delete(file_path)
                return redirect('document_chat:upload_document')
            
            # Create document record
            document = Document.objects.create(
                user=request.user,
                title=title,
                file=file_path,
                content_text=text
            )
            
            # Process the document - create chunks and embeddings
            chunks = chunk_text(text)
            create_embeddings(document, chunks)
            
            # Log the usage
            UsageLog.objects.create(
                user=request.user,
                service='document_chat',
                credits_used=1
            )
            
            # Deduct credits
            request.user.profile.usage_credits -= 1
            request.user.profile.save()
            
            messages.success(request, f"Document '{title}' uploaded and processed successfully!")
            return redirect('document_chat:view_document', document_id=document.id)
            
        except Exception as e:
            messages.error(request, f"Error processing document: {str(e)}")
            return redirect('document_chat:upload_document')
    
    return render(request, 'document_chat/upload_document.html')


@login_required
def view_document(request, document_id):
    """View document details and start a chat session."""
    document = get_object_or_404(Document, id=document_id, user=request.user)
    
    # Get or create a chat session
    chat_sessions = ChatSession.objects.filter(document=document, user=request.user).order_by('-last_activity')
    
    context = {
        'document': document,
        'chat_sessions': chat_sessions,
    }
    
    return render(request, 'document_chat/view_document.html', context)


@login_required
def delete_document(request, document_id):
    """Delete a document and its associated chat sessions."""
    document = get_object_or_404(Document, id=document_id, user=request.user)
    
    if request.method == 'POST':
        # Delete the file
        if document.file:
            document.file.delete(False)
        
        # Delete the document (this will cascade delete embeddings and chat sessions)
        document.delete()
        
        messages.success(request, f"Document '{document.title}' deleted successfully.")
        return redirect('document_chat:index')
    
    return render(request, 'document_chat/delete_document.html', {'document': document})


@login_required
def create_chat_session(request, document_id):
    """Create a new chat session for a document."""
    document = get_object_or_404(Document, id=document_id, user=request.user)
    
    if request.method == 'POST':
        title = request.POST.get('title') or f"Chat about {document.title}"
        
        chat_session = ChatSession.objects.create(
            user=request.user,
            document=document,
            title=title
        )
        
        messages.success(request, f"Chat session '{title}' created successfully.")
        return redirect('document_chat:chat', session_id=chat_session.id)
    
    return render(request, 'document_chat/create_chat_session.html', {'document': document})


@login_required
def chat(request, session_id):
    """Chat interface for a specific session."""
    chat_session = get_object_or_404(ChatSession, id=session_id, user=request.user)
    
    # Get all messages for this chat session
    messages_list = Message.objects.filter(chat_session=chat_session).order_by('timestamp')
    
    context = {
        'chat_session': chat_session,
        'document': chat_session.document,
        'messages': messages_list,
    }
    
    return render(request, 'document_chat/chat.html', context)


@login_required
def send_message(request, session_id):
    """API endpoint to send a message and get a response."""
    if request.method != 'POST':
        return HttpResponseBadRequest("Invalid request method")
    
    try:
        chat_session = get_object_or_404(ChatSession, id=session_id, user=request.user)
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return JsonResponse({'error': 'Message cannot be empty'}, status=400)
        
        # Save user message
        Message.objects.create(
            chat_session=chat_session,
            role='user',
            content=user_message
        )
        
        # Get recent message history (last 5 message pairs)
        recent_messages = []
        message_pairs = list(zip(
            Message.objects.filter(chat_session=chat_session, role='user').order_by('-timestamp')[:5],
            Message.objects.filter(chat_session=chat_session, role='assistant').order_by('-timestamp')[:5]
        ))
        
        for user_msg, assistant_msg in message_pairs:
            if user_msg and assistant_msg:
                recent_messages.append({
                    'user': user_msg.content,
                    'assistant': assistant_msg.content
                })
        
        # Search document for relevant context
        document = chat_session.document
        relevant_chunks = search_document(document, user_message, top_k=3)
        context = "\n\n".join(relevant_chunks)
        
        # Generate response
        response = generate_response(user_message, context, recent_messages)
        
        # Save assistant message
        assistant_message = Message.objects.create(
            chat_session=chat_session,
            role='assistant',
            content=response
        )
        
        # Update chat session last activity
        chat_session.save()  # This updates the last_activity field
        
        return JsonResponse({
            'message': response,
            'sources': relevant_chunks,
            'message_id': assistant_message.id
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def delete_chat_session(request, session_id):
    """Delete a chat session."""
    chat_session = get_object_or_404(ChatSession, id=session_id, user=request.user)
    document = chat_session.document
    
    if request.method == 'POST':
        chat_session.delete()
        messages.success(request, f"Chat session '{chat_session.title}' deleted successfully.")
        return redirect('document_chat:view_document', document_id=document.id)
    
    return render(request, 'document_chat/delete_chat_session.html', {'chat_session': chat_session})