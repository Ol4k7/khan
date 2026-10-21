from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('lesson/<int:lesson_id>/', views.lesson_player, name='lesson_player'),
    path('api/generate-all-quizzes/', views.generate_all_quizzes, name='generate_all_quizzes'),
    path('api/generate-hint/', views.generate_hint, name='generate_hint'),
    path('api/mark-completed/', views.mark_completed, name='mark_completed'),
]