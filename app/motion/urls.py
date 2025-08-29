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
    
    # Dashboard
    path('dashboard/', views.motion_dashboard_view, name='motion-dashboard'),
]
