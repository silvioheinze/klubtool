from django.urls import path
from . import views

app_name = 'motion'

urlpatterns = [
    # Motion CRUD URLs
    path('', views.MotionListView.as_view(), name='motion-list'),
    path('create/', views.MotionCreateView.as_view(), name='motion-create'),
    path('<int:pk>/', views.MotionDetailView.as_view(), name='motion-detail'),
    path('<int:pk>/edit/', views.MotionUpdateView.as_view(), name='motion-edit'),
    path('<int:pk>/delete/', views.MotionDeleteView.as_view(), name='motion-delete'),
    
    # Motion interaction URLs
    path('<int:pk>/vote/', views.motion_vote_view, name='motion-vote'),
    path('<int:pk>/comment/', views.motion_comment_view, name='motion-comment'),
    path('<int:pk>/attach/', views.motion_attachment_view, name='motion-attach'),
    path('<int:pk>/status-change/', views.motion_status_change_view, name='motion-status-change'),
    path('<int:motion_pk>/status/<int:status_pk>/delete/', views.motion_status_delete_view, name='motion-status-delete'),
    path('<int:pk>/group-decision/', views.motion_group_decision_view, name='motion-group-decision'),
    path('<int:motion_pk>/group-decision/<int:decision_pk>/delete/', views.motion_group_decision_delete_view, name='motion-group-decision-delete'),
    path('<int:pk>/export-pdf/', views.MotionExportPDFView.as_view(), name='motion-export-pdf'),
    
    # Question CRUD URLs
    path('questions/', views.QuestionListView.as_view(), name='question-list'),
    path('questions/create/', views.QuestionCreateView.as_view(), name='question-create'),
    path('questions/<int:pk>/', views.QuestionDetailView.as_view(), name='question-detail'),
    path('questions/<int:pk>/edit/', views.QuestionUpdateView.as_view(), name='question-edit'),
    path('questions/<int:pk>/delete/', views.QuestionDeleteView.as_view(), name='question-delete'),
    path('questions/<int:pk>/attach/', views.question_attachment_view, name='question-attach'),
    path('questions/<int:pk>/status-change/', views.question_status_change_view, name='question-status-change'),
    path('questions/<int:question_pk>/status/<int:status_pk>/delete/', views.question_status_delete_view, name='question-status-delete'),
]
