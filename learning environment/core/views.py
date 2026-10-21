import os
import json
import time
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from google import genai
from google.genai import types
from .models import Course, Lesson, Progress

# Initialize the Gemini client
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

def dashboard(request):
    courses = Course.objects.prefetch_related('lessons').all()
    
    # Get a flat list of lesson IDs the user has completed
    completed_lessons = []
    if request.user.is_authenticated:
        completed_lessons = Progress.objects.filter(
            user=request.user, is_completed=True
        ).values_list('lesson_id', flat=True)
        
    return render(request, 'core/dashboard.html', {
        'courses': courses, 
        'completed_lessons': completed_lessons
    })

def mark_completed(request):
    if request.method == 'POST' and request.user.is_authenticated:
        data = json.loads(request.body)
        lesson_id = data.get('lesson_id')
        
        # Check if the user already has a progress record for this lesson
        progress, created = Progress.objects.get_or_create(
            user=request.user, 
            lesson_id=lesson_id,
            defaults={'is_completed': True}
        )
        
        # Only award points if this is their first time completing it
        if created or not progress.is_completed:
            progress.is_completed = True
            progress.save()
            
            request.user.total_points += 10
            request.user.save()
            return JsonResponse({"status": "success", "points_awarded": True})
            
        return JsonResponse({"status": "already_completed", "points_awarded": False})
    
    return JsonResponse({"error": "Invalid request"}, status=400)


def lesson_player(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)
    return render(request, 'core/lesson_player.html', {'lesson': lesson})

# core/views.py
def generate_all_quizzes(request):
    video_id = request.GET.get('video_id')
    duration_seconds = float(request.GET.get('duration', 0))
    user_interest = request.user.interest if request.user.is_authenticated else "general knowledge"
    
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    # Calculate exact minute marks (e.g., [60, 120, 180, 240, 300, 360, 420])
    
    minute_marks = [i * 60 for i in range(1, int(duration_seconds // 60) + 1)]
    final_time = int(duration_seconds)
    
    prompt_text = f"""
    You are an expert tutor. Watch this entire video.
    
    You MUST generate a structured curriculum consisting of exactly {len(minute_marks) + 3} multiple-choice questions themed around {user_interest}.
    
    CRITICAL TIMESTAMPS:
    1. Generate exactly ONE question for EACH of these specific timestamps in seconds: {minute_marks}. Set the 'trigger_second' to match the timestamp.
    2. Generate exactly 3 comprehensive mastery questions for the end of the video. Set their 'trigger_second' to {final_time}.
    """
    
    # Force Gemini to return a specific Array structure
    quiz_schema = {
        "type": "ARRAY",
        "items": {
            "type": "OBJECT",
            "properties": {
                "trigger_second": {"type": "INTEGER"},
                "question": {"type": "STRING"},
                "option_a": {"type": "STRING"},
                "option_b": {"type": "STRING"},
                "option_c": {"type": "STRING"},
                "option_d": {"type": "STRING"},
                "correct_option": {"type": "STRING"},
            },
            "required": ["trigger_second", "question", "option_a", "option_b", "option_c", "option_d", "correct_option"]
        }
    }
    
    # Retry loop with exponential backoff for 503 spikes
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=types.Content(
                    parts=[
                        types.Part(file_data=types.FileData(file_uri=video_url)),
                        types.Part.from_text(text=prompt_text)
                    ]
                ),
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=quiz_schema,
                    temperature=0.0,
                ),
            )
            
            # Strip potential markdown formatting from Gemini's response
            raw_text = response.text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:-3].strip()
            elif raw_text.startswith("```"):
                raw_text = raw_text[3:-3].strip()
                
            quiz_data = json.loads(raw_text)
            
            # ADD THIS LINE TO SEE EXACTLY WHAT THE AI GENERATED:
            print("🤖 RAW AI OUTPUT:", json.dumps(quiz_data, indent=2))
            
            return JsonResponse({"quizzes": quiz_data})
            
        except Exception as e:
            error_msg = str(e)
            if "503" in error_msg and attempt < 2:
                # Wait 2 seconds, then 4 seconds before trying again
                time.sleep(2 * (attempt + 1))
                continue
                
            print(f"Gemini API Error: {error_msg}")
            return JsonResponse({"error": "AI servers are currently busy. Please refresh."}, status=500)

def generate_hint(request):
    question = request.GET.get('question')
    user_answer = request.GET.get('user_answer')
    
    prompt_text = f"""
    The student was asked this question: "{question}"
    They incorrectly answered: "{user_answer}"
    Provide a concise, 1 to 2 sentence Socratic hint pointing out the misconception without giving away the correct answer.
    """
    
    # Retry loop with exponential backoff for 503 spikes
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt_text  # Text-only query: fast, cheap, and avoids video quota
            )
            return JsonResponse({"hint": response.text.strip()})
        except Exception as e:
            if "503" in str(e) and attempt < 2:
                time.sleep(1.5 * (attempt + 1))
                continue
            print(f"Hint API Error: {str(e)}")
            return JsonResponse({"error": "Hint generation temporarily unavailable."}, status=500)