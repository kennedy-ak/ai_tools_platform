from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib import messages
from django.conf import settings
from django.utils import timezone
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

import os
import json
import tempfile
import uuid
import random
from PyPDF2 import PdfReader
from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from langchain.schema import StrOutputParser
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from typing import List, Optional, Union

from .models import Quiz, Question, Option, QuizAttempt, Answer
from accounts.models import UsageLog


class QuizQuestion(BaseModel):
    question: str = Field(description="The text of the question")
    type: str = Field(description="Type of question: 'multiple_choice', 'true_false', or 'fill_in_blank'")
    options: Optional[List[str]] = Field(description="Answer options for multiple choice questions", default=None)
    correct_answer: Union[str, bool] = Field(description="The correct answer to the question")
    explanation: str = Field(description="Explanation of why the answer is correct")


class QuizQuestions(BaseModel):
    questions: List[QuizQuestion] = Field(description="List of quiz questions")


def extract_text_from_pdf(file_path):
    """Extract text from a PDF file."""
    text = ""
    with open(file_path, "rb") as file:
        pdf_reader = PdfReader(file)
        for page in pdf_reader.pages:
            text += page.extract_text()
    return text


def generate_questions(pdf_text, num_questions, question_types, difficulty, api_key):
    """Generate quiz questions using the Groq API."""
    model_name = "llama-3.3-70b-versatile"
    
    llm = ChatGroq(
        groq_api_key=api_key,
        model_name=model_name,
    )
    
    # Create a specific prompt for generating questions
    template = """
    You are an expert educational content creator. Your task is to create {num_questions} quiz questions based on the following text. 
    
    TEXT:
    {text}
    
    Create {num_questions} questions of the following type(s): {question_types}.
    The difficulty level should be: {difficulty}.
    
    For multiple-choice questions:
    - Include 4 options (labeled as "Option A", "Option B", "Option C", "Option D")
    - Make sure there is exactly one correct answer
    - VERY IMPORTANT: Make sure the correct_answer field exactly matches one of the options in the options array
    - VERY IMPORTANT: Vary which option (A, B, C, or D) is correct across different questions
    - Ensure wrong answers are plausible but clearly incorrect
    
    For true/false questions:
    - Create a balanced mix of true and false statements (roughly 50% true and 50% false)
    - Make false statements challenging but clearly incorrect
    
    For fill-in-the-blank questions:
    - Ensure there is a clear, specific answer
    - The blank should replace a key concept or term
    
    For each question, include a brief explanation of why the correct answer is right.
    
    Format your response as a JSON object that strictly follows this structure:
    ```json
    {{
        "questions": [
            {{
                "question": "Question text here",
                "type": "multiple_choice",
                "options": ["Option A", "Option B", "Option C", "Option D"],
                "correct_answer": "Option B",
                "explanation": "Explanation of why Option B is correct"
            }},
            {{
                "question": "True or false: Statement here",
                "type": "true_false",
                "options": null,
                "correct_answer": false,
                "explanation": "Explanation of why this is false"
            }},
            {{
                "question": "Statement with a _____ to fill in.",
                "type": "fill_in_blank",
                "options": null,
                "correct_answer": "word",
                "explanation": "Explanation of why 'word' is correct"
            }}
        ]
    }}
    ```
    
    IMPORTANT: Double-check that for each multiple-choice question, the correct_answer EXACTLY matches one of the strings in the options array. Do not add extra text or formatting to the correct_answer that isn't in the options.
    
    Ensure that the JSON is valid and follows the structure exactly.
    """
    
    prompt = PromptTemplate(
        template=template,
        input_variables=["text", "num_questions", "question_types", "difficulty"]
    )
    
    # Create the parser
    parser = JsonOutputParser(pydantic_object=QuizQuestions)
    
    # Create the chain
    chain = prompt | llm | parser
    
    # Truncate PDF text if it's too long
    max_tokens = 20000
    if len(pdf_text) > max_tokens:
        pdf_text = pdf_text[:max_tokens]
    
    try:
        result = chain.invoke({
            "text": pdf_text,
            "num_questions": num_questions,
            "question_types": question_types,
            "difficulty": difficulty
        })
        return result
    except Exception as e:
        print(f"Error generating questions: {str(e)}")
        return None


def find_closest_match(target, options):
    """Find the closest match for a target string in a list of options."""
    if not options:
        return None
    
    # First check for exact match
    if target in options:
        return target
    
    # Try case-insensitive match
    target_lower = target.lower().strip()
    for option in options:
        if option.lower().strip() == target_lower:
            return option
    
    # Check if the target is a substring of any option
    for option in options:
        if target_lower in option.lower().strip():
            return option
        
    # Default to first option if no match found
    return options[0]


@login_required
def index(request):
    """Main page for the quiz generator app."""
    # Get the user's quizzes
    user_quizzes = Quiz.objects.filter(user=request.user).order_by('-created_at')
    
    context = {
        'quizzes': user_quizzes,
    }
    
    return render(request, 'quiz_generator/index.html', context)


@login_required
def create_quiz(request):
    """View for creating a new quiz."""
    if request.method == 'POST':
        # Check if user has enough credits
        if request.user.profile.usage_credits < 1:
            messages.error(request, "You don't have enough credits to create a quiz. Please contact support to get more credits.")
            return redirect('quiz_generator:index')
            
        # Get form data
        uploaded_file = request.FILES.get('pdf_file')
        num_questions = int(request.POST.get('num_questions', 5))
        difficulty = request.POST.get('difficulty', 'medium')
        
        question_types = []
        if request.POST.get('mc_box'):
            question_types.append('multiple_choice')
        if request.POST.get('tf_box'):
            question_types.append('true_false')
        if request.POST.get('fib_box'):
            question_types.append('fill_in_blank')
        
        if not uploaded_file:
            messages.error(request, "Please upload a PDF file.")
            return redirect('quiz_generator:create_quiz')
            
        if not question_types:
            messages.error(request, "Please select at least one question type.")
            return redirect('quiz_generator:create_quiz')
        
        # Get the API key
        api_key = settings.GROQ_API_KEY
        if not api_key:
            messages.error(request, "GROQ API key not found. Please contact support.")
            return redirect('quiz_generator:index')
        
        # Save the file temporarily
        unique_filename = f"{uuid.uuid4().hex}.pdf"
        file_path = default_storage.save(f"tmp/{unique_filename}", ContentFile(uploaded_file.read()))
        
        try:
            # Extract text from PDF
            pdf_text = extract_text_from_pdf(default_storage.path(file_path))
            
            # Generate questions
            questions_data = generate_questions(
                pdf_text,
                num_questions,
                ", ".join(question_types),
                difficulty,
                api_key
            )
            
            if questions_data and "questions" in questions_data:
                # Create a new quiz
                quiz = Quiz.objects.create(
                    user=request.user,
                    title=f"Quiz from {uploaded_file.name}",
                    description=f"Generated from {uploaded_file.name} with {num_questions} {difficulty} difficulty questions",
                    difficulty=difficulty,
                    original_file_name=uploaded_file.name
                )
                
                # Process and save the questions
                for question_data in questions_data["questions"]:
                    # Create question
                    question_type = question_data["type"]
                    question = Question.objects.create(
                        quiz=quiz,
                        question_text=question_data["question"],
                        question_type=question_type,
                        explanation=question_data["explanation"]
                    )
                    
                    # Create options based on question type
                    if question_type == "multiple_choice":
                        correct_answer = question_data["correct_answer"]
                        
                        # Verify the correct answer is in the options
                        if correct_answer not in question_data["options"]:
                            closest_match = find_closest_match(correct_answer, question_data["options"])
                            correct_answer = closest_match
                        
                        # Create options
                        for option_text in question_data["options"]:
                            Option.objects.create(
                                question=question,
                                option_text=option_text,
                                is_correct=(option_text == correct_answer)
                            )
                    
                    elif question_type == "true_false":
                        # Create True option
                        Option.objects.create(
                            question=question,
                            option_text="True",
                            is_correct=question_data["correct_answer"] is True
                        )
                        
                        # Create False option
                        Option.objects.create(
                            question=question,
                            option_text="False",
                            is_correct=question_data["correct_answer"] is False
                        )
                    
                    elif question_type == "fill_in_blank":
                        # Create a single option with the correct answer
                        Option.objects.create(
                            question=question,
                            option_text=question_data["correct_answer"],
                            is_correct=True
                        )
                
                # Log the usage
                UsageLog.objects.create(
                    user=request.user,
                    service='quiz_generator',
                    credits_used=1
                )
                
                # Deduct credits
                request.user.profile.usage_credits -= 1
                request.user.profile.save()
                
                # Delete temporary file
                default_storage.delete(file_path)
                
                messages.success(request, "Quiz generated successfully!")
                return redirect('quiz_generator:view_quiz', quiz_id=quiz.id)
            else:
                messages.error(request, "Failed to generate questions. Please try again.")
        
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            
        # Delete temporary file
        if file_path:
            default_storage.delete(file_path)
    
    return render(request, 'quiz_generator/create_quiz.html')


@login_required
def view_quiz(request, quiz_id):
    """View for displaying a quiz."""
    quiz = get_object_or_404(Quiz, id=quiz_id, user=request.user)
    questions = quiz.questions.all()
    
    context = {
        'quiz': quiz,
        'questions': questions,
    }
    
    return render(request, 'quiz_generator/view_quiz.html', context)


@login_required
def take_quiz(request, quiz_id):
    """View for taking a quiz."""
    quiz = get_object_or_404(Quiz, id=quiz_id, user=request.user)
    
    # Create a new quiz attempt
    attempt = QuizAttempt.objects.create(
        user=request.user,
        quiz=quiz,
        start_time=timezone.now()
    )
    
    # Get all questions for this quiz
    questions = list(quiz.questions.all())
    
    context = {
        'quiz': quiz,
        'attempt': attempt,
        'questions': questions,
    }
    
    return render(request, 'quiz_generator/take_quiz.html', context)


@login_required
def submit_answer(request, attempt_id):
    """API for submitting an answer."""
    if request.method != 'POST':
        return HttpResponseBadRequest("Invalid request method")
    
    try:
        data = json.loads(request.body)
        question_id = data.get('question_id')
        option_id = data.get('option_id')
        text_answer = data.get('text_answer')
        
        attempt = get_object_or_404(QuizAttempt, id=attempt_id, user=request.user)
        question = get_object_or_404(Question, id=question_id, quiz=attempt.quiz)
        
        # Check if an answer already exists
        existing_answer = Answer.objects.filter(attempt=attempt, question=question).first()
        if existing_answer:
            answer = existing_answer
        else:
            answer = Answer(attempt=attempt, question=question)
        
        if question.question_type in ['multiple_choice', 'true_false']:
            if option_id:
                option = get_object_or_404(Option, id=option_id, question=question)
                answer.selected_option = option
            else:
                answer.selected_option = None
        else:  # fill_in_blank
            answer.text_answer = text_answer
        
        answer.check_correctness()
        
        return JsonResponse({
            'success': True,
            'is_correct': answer.is_correct,
            'explanation': question.explanation
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def finish_quiz(request, attempt_id):
    """View for finishing a quiz attempt."""
    attempt = get_object_or_404(QuizAttempt, id=attempt_id, user=request.user)
    
    # Set end time
    attempt.end_time = timezone.now()
    attempt.save()
    
    # Calculate score
    score = attempt.calculate_score()
    
    return redirect('quiz_generator:quiz_results', attempt_id=attempt.id)


@login_required
def quiz_results(request, attempt_id):
    """View for displaying quiz results."""
    attempt = get_object_or_404(QuizAttempt, id=attempt_id, user=request.user)
    
    # Ensure the score is calculated
    if attempt.score is None:
        attempt.calculate_score()
    
    # Get all answers for this attempt
    answers = attempt.answers.all().select_related('question', 'selected_option')
    
    context = {
        'attempt': attempt,
        'answers': answers,
        'quiz': attempt.quiz,
        'score': attempt.score,
    }
    
    return render(request, 'quiz_generator/quiz_results.html', context)


@login_required
def delete_quiz(request, quiz_id):
    """View for deleting a quiz."""
    quiz = get_object_or_404(Quiz, id=quiz_id, user=request.user)
    
    if request.method == 'POST':
        quiz.delete()
        messages.success(request, "Quiz deleted successfully.")
        return redirect('quiz_generator:index')
    
    return render(request, 'quiz_generator/delete_quiz.html', {'quiz': quiz})