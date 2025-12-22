from django.urls import path
from . import views

app_name = 'question'

urlpatterns = [
    # Question CRUD URLs
    path('', views.QuestionListView.as_view(), name='question-list'),
    path('create/', views.QuestionCreateView.as_view(), name='question-create'),
    path('<int:pk>/', views.QuestionDetailView.as_view(), name='question-detail'),
    path('<int:pk>/edit/', views.QuestionUpdateView.as_view(), name='question-edit'),
    path('<int:pk>/delete/', views.QuestionDeleteView.as_view(), name='question-delete'),
    path('<int:pk>/attach/', views.question_attachment_view, name='question-attach'),
    path('<int:pk>/status-change/', views.question_status_change_view, name='question-status-change'),
    path('<int:question_pk>/status/<int:status_pk>/delete/', views.question_status_delete_view, name='question-status-delete'),
]

