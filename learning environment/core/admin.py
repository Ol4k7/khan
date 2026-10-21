# core/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Course, Lesson, Progress

# Register custom user with UserAdmin for proper password hashing
admin.site.register(User, UserAdmin)

# Register the standard models
admin.site.register(Course)
admin.site.register(Lesson)
admin.site.register(Progress)