from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

import os
import re
import uuid
import PyPDF2
import docx
from groq import Groq

from .models import CVReview, CVDocument
from accounts.models import UsageLog


def extract_text_from_pdf(file_path):
    """Extract text from a PDF file."""
    try:
        pdf_reader = PyPDF2.PdfReader(file_path)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        print(f"Error extracting text from PDF: {str(e)}")
        return ""


def extract_text_from_docx(file_path):
    """Extract text from a DOCX file."""
    try:
        doc = docx.Document(file_path)
        text = ""
        for para in doc.paragraphs:
            text += para.text + "\n"
        return text
    except Exception as e:
        print(f"Error extracting text from DOCX: {str(e)}")
        return ""


def format_review_for_email(review_text):
    """Process the review text to convert markdown to HTML with inline CSS."""
    # Convert markdown headers to HTML headers with inline styles
    review_text = re.sub(
        r'## ([^\n]+)',
        r'<h2 style="color: #3498db; margin-top: 25px; border-left: 4px solid #3498db; padding-left: 10px;">\1</h2>',
        review_text
    )
    
    # Convert markdown bold (**text**) to HTML bold with inline styles
    review_text = re.sub(
        r'\*\*([^*]+)\*\*',
        r'<strong style="font-weight: bold;">\1</strong>',
        review_text
    )
    
    # Convert bullet points (* item) to HTML list items
    if "* " in review_text:
        # First, identify bullet point lists and wrap them in <ul> tags
        bullet_list_pattern = r'(\n\* [^\n]+(?:\n\* [^\n]+)*)'
        
        def replace_bullet_list(match):
            bullet_list = match.group(1)
            items = bullet_list.strip().split('\n* ')
            items = [item for item in items if item]
            
            html_list = '<ul style="padding-left: 20px;">\n'
            for item in items:
                html_list += f'<li style="margin-bottom: 8px;">{item}</li>\n'
            html_list += '</ul>'
            
            return html_list
        
        review_text = re.sub(bullet_list_pattern, replace_bullet_list, '\n' + review_text)
    
    # Add paragraph tags to text blocks
    paragraphs = review_text.split('\n\n')
    formatted_paragraphs = []
    
    for p in paragraphs:
        if not p.strip():
            continue
        if not (p.startswith('<h2') or p.startswith('<ul') or p.startswith('<li')):
            p = f'<p style="margin-bottom: 15px; line-height: 1.6;">{p}</p>'
        formatted_paragraphs.append(p)
    
    review_text = '\n'.join(formatted_paragraphs)
    
    # Style percentage mentions
    percentage_pattern = r'(\d{1,3}%)'
    review_text = re.sub(
        percentage_pattern, 
        r'<span style="font-weight: bold; color: #3498db;">\1</span>', 
        review_text
    )
    
    return review_text


def send_email_review(recipient_email, review_content, review_id):
    """Send an email with the CV review results."""
    try:
        subject = "Your CV Review Results from NeuroTools"
        
        # Prepare HTML content with inline styles for email
        html_content = render_to_string('cv_reviewer/email_template.html', {
            'review_content': review_content,
            'review_id': review_id
        })
        
        # Plain text alternative for email clients that don't support HTML
        text_content = strip_tags(html_content)
        
        # Create email message
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient_email]
        )
        
        # Attach HTML version
        email.attach_alternative(html_content, "text/html")
        
        # Send email
        email.send()
        return True
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False


def review_cv(cv_text, job_role=None):
    """Review the CV using Groq LLM API."""
    try:
        api_key = settings.GROQ_API_KEY
        if not api_key:
            return "Failed to initialize the Groq client. Please check your API key and try again."
        
        client = Groq(api_key=api_key)
        
        # Create system and user message based on inputs
        if job_role:
            system_message = (
                "You are a professional CV reviewer and career coach. "
                f"Provide a detailed analysis of the CV for a {job_role} position with percentage scores. Focus on: "
                "1. Overall structure and formatting (score this out of 100%), "
                "2. Content relevance for the position (score this out of 100%), "
                "3. Skills assessment compared to job requirements (score this out of 100%), "
                "4. Experience highlights and gaps (score this out of 100%), "
                "5. Specific improvement suggestions, "
                
                "Also provide an overall CV score as a percentage based on the average of all sections. "
                
                "Format your response in clear sections with markdown formatting using ## for section headers, "
                "* for bullet points, and **bold text** for important points. Include percentages for each major section. "
                "For each section, explain the reasoning behind the score and what could be improved. "
                "Use a professional and constructive tone."
            )
            user_message = f"Here is the CV content for a {job_role} position:\n\n{cv_text}"
        else:
            system_message = (
                "You are a professional CV reviewer and career coach. "
                "Provide a detailed analysis of the CV with percentage scores. Focus on: "
                "1. Overall structure and formatting (score this out of 100%), "
                "2. Content quality and clarity (score this out of 100%), "
                "3. Skills presentation (score this out of 100%), "
                "4. Experience highlights (score this out of 100%), "
                "5. Specific improvement suggestions, "
                
                "Also provide an overall CV score as a percentage based on the average of all sections. "
                
                "Format your response in clear sections with markdown formatting using ## for section headers, "
                "* for bullet points, and **bold text** for important points. Include percentages for each major section. "
                "For each section, explain the reasoning behind the score and what could be improved. "
                "Use a professional and constructive tone."
            )
            user_message = f"Here is the CV content:\n\n{cv_text}"
        
        # Choose model
        model = "llama-3.3-70b-versatile"
        
        # Generate review
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            model=model,
            temperature=0.7,
            max_tokens=1500,
            top_p=0.9
        )
        
        # Get review text
        review = chat_completion.choices[0].message.content
        
        return review
    
    except Exception as e:
        print(f"Error during CV review: {str(e)}")
        return f"An error occurred during the review process: {str(e)}"


def extract_scores(review_text):
    """Extract scores from the review text."""
    structure_score = 0
    content_score = 0
    skills_score = 0
    experience_score = 0
    overall_score = 0
    
    # Regular expressions to match scores
    structure_pattern = r'(?:structure|formatting).*?(\d{1,3})%'
    content_pattern = r'(?:content|quality|clarity).*?(\d{1,3})%'
    skills_pattern = r'(?:skills|presentation).*?(\d{1,3})%'
    experience_pattern = r'(?:experience|highlights).*?(\d{1,3})%'
    overall_pattern = r'(?:overall|final).*?score.*?(\d{1,3})%'
    
    # Extract scores using regex
    structure_match = re.search(structure_pattern, review_text, re.IGNORECASE)
    if structure_match:
        structure_score = int(structure_match.group(1))
    
    content_match = re.search(content_pattern, review_text, re.IGNORECASE)
    if content_match:
        content_score = int(content_match.group(1))
    
    skills_match = re.search(skills_pattern, review_text, re.IGNORECASE)
    if skills_match:
        skills_score = int(skills_match.group(1))
    
    experience_match = re.search(experience_pattern, review_text, re.IGNORECASE)
    if experience_match:
        experience_score = int(experience_match.group(1))
    
    overall_match = re.search(overall_pattern, review_text, re.IGNORECASE)
    if overall_match:
        overall_score = int(overall_match.group(1))
    elif structure_score and content_score and skills_score and experience_score:
        # Calculate overall score as average of other scores if not explicitly mentioned
        overall_score = (structure_score + content_score + skills_score + experience_score) // 4
    
    return {
        'structure_score': structure_score,
        'content_score': content_score,
        'skills_score': skills_score,
        'experience_score': experience_score,
        'overall_score': overall_score
    }


def extract_feedback_sections(review_text):
    """Extract feedback sections from the review text."""
    structure_feedback = ""
    content_feedback = ""
    skills_feedback = ""
    experience_feedback = ""
    improvement_suggestions = ""
    
    # Split by headers (## )
    sections = re.split(r'##\s+', review_text)
    
    for section in sections:
        if not section.strip():
            continue
            
        section_title = section.split('\n')[0].strip().lower()
        section_content = '\n'.join(section.split('\n')[1:]).strip()
        
        if 'structure' in section_title or 'format' in section_title:
            structure_feedback = section_content
        elif 'content' in section_title or 'qualit' in section_title or 'clarity' in section_title:
            content_feedback = section_content
        elif 'skill' in section_title:
            skills_feedback = section_content
        elif 'experience' in section_title:
            experience_feedback = section_content
        elif 'improve' in section_title or 'suggest' in section_title or 'recommendation' in section_title:
            improvement_suggestions = section_content
    
    return {
        'structure_feedback': structure_feedback,
        'content_feedback': content_feedback,
        'skills_feedback': skills_feedback,
        'experience_feedback': experience_feedback,
        'improvement_suggestions': improvement_suggestions
    }


@login_required
def index(request):
    """Main page for the CV Reviewer app."""
    # Get the user's CV reviews
    user_reviews = CVReview.objects.filter(user=request.user).order_by('-created_at')
    
    context = {
        'reviews': user_reviews,
    }
    
    return render(request, 'cv_reviewer/index.html', context)


@login_required
def create_review(request):
    """View for creating a new CV review."""
    if request.method == 'POST':
        # Check if user has enough credits
        if request.user.profile.usage_credits < 1:
            messages.error(request, "You don't have enough credits to review a CV. Please contact support to get more credits.")
            return redirect('cv_reviewer:index')
            
        # Get form data
        uploaded_file = request.FILES.get('cv_file')
        email = request.POST.get('email')
        job_role = request.POST.get('job_role') if request.POST.get('job_role_checkbox') else None
        
        if not uploaded_file:
            messages.error(request, "Please upload a CV file.")
            return redirect('cv_reviewer:create_review')
            
        if not email or '@' not in email:
            messages.error(request, "Please enter a valid email address.")
            return redirect('cv_reviewer:create_review')
        
        # Check file extension
        file_extension = uploaded_file.name.split('.')[-1].lower()
        if file_extension not in ['pdf', 'docx']:
            messages.error(request, "Unsupported file format. Please upload a PDF or DOCX file.")
            return redirect('cv_reviewer:create_review')
        
        # Get the API key
        api_key = settings.GROQ_API_KEY
        if not api_key:
            messages.error(request, "GROQ API key not found. Please contact support.")
            return redirect('cv_reviewer:index')
        
        # Save the file temporarily
        unique_filename = f"{uuid.uuid4().hex}.{file_extension}"
        file_path = default_storage.save(f"tmp/{unique_filename}", ContentFile(uploaded_file.read()))
        
        try:
            # Extract text from file
            if file_extension == 'pdf':
                cv_text = extract_text_from_pdf(default_storage.path(file_path))
            else:
                cv_text = extract_text_from_docx(default_storage.path(file_path))
            
            if not cv_text:
                messages.error(request, "Could not extract text from the uploaded file. Please try again with a different file.")
                default_storage.delete(file_path)
                return redirect('cv_reviewer:create_review')
            
            # Create a new review
            cv_review = CVReview.objects.create(
                user=request.user,
                original_filename=uploaded_file.name,
                job_role=job_role,
                email_address=email
            )
            
            # Generate review
            review_result = review_cv(cv_text, job_role)
            
            # Extract scores
            scores = extract_scores(review_result)
            cv_review.structure_score = scores['structure_score']
            cv_review.content_score = scores['content_score']
            cv_review.skills_score = scores['skills_score']
            cv_review.experience_score = scores['experience_score']
            cv_review.overall_score = scores['overall_score']
            
            # Extract feedback sections
            feedback = extract_feedback_sections(review_result)
            cv_review.structure_feedback = feedback['structure_feedback']
            cv_review.content_feedback = feedback['content_feedback']
            cv_review.skills_feedback = feedback['skills_feedback']
            cv_review.experience_feedback = feedback['experience_feedback']
            cv_review.improvement_suggestions = feedback['improvement_suggestions']
            
            # Save the review
            cv_review.save()
            
            # Create CV document
            cv_document = CVDocument.objects.create(
                review=cv_review,
                file=file_path,
                content_text=cv_text,
                file_type=file_extension
            )
            
            # Format review for email and send it
            formatted_review = format_review_for_email(review_result)
            
            email_sent = send_email_review(email, formatted_review, cv_review.id)
            if email_sent:
                cv_review.email_sent = True
                cv_review.save()
            
            # Log the usage
            UsageLog.objects.create(
                user=request.user,
                service='cv_reviewer',
                credits_used=1
            )
            
            # Deduct credits
            request.user.profile.usage_credits -= 1
            request.user.profile.save()
            
            messages.success(request, "CV review completed successfully! Check your email for the detailed results.")
            return redirect('cv_reviewer:view_review', review_id=cv_review.id)
        
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            
        # Delete temporary file
        default_storage.delete(file_path)
    
    return render(request, 'cv_reviewer/create_review.html')


@login_required
def view_review(request, review_id):
    """View for displaying a CV review."""
    review = get_object_or_404(CVReview, id=review_id, user=request.user)
    
    context = {
        'review': review,
    }
    
    return render(request, 'cv_reviewer/view_review.html', context)


@login_required
def delete_review(request, review_id):
    """View for deleting a CV review."""
    review = get_object_or_404(CVReview, id=review_id, user=request.user)
    
    if request.method == 'POST':
        # Delete the document file
        if hasattr(review, 'document') and review.document.file:
            review.document.file.delete(False)
        
        # Delete the review
        review.delete()
        
        messages.success(request, "CV review deleted successfully.")
        return redirect('cv_reviewer:index')
    
    return render(request, 'cv_reviewer/delete_review.html', {'review': review})