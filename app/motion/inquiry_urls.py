from django.urls import path
from . import views

app_name = 'inquiry'

urlpatterns = [
    # Inquiry CRUD URLs
    path('', views.InquiryListView.as_view(), name='inquiry-list'),
    path('create/', views.InquiryCreateView.as_view(), name='inquiry-create'),
    path('<int:pk>/', views.InquiryDetailView.as_view(), name='inquiry-detail'),
    path('<int:pk>/edit/', views.InquiryUpdateView.as_view(), name='inquiry-edit'),
    path('<int:pk>/delete/', views.InquiryDeleteView.as_view(), name='inquiry-delete'),
    path('<int:pk>/attach/', views.inquiry_attachment_view, name='inquiry-attach'),
    path('<int:pk>/status-change/', views.inquiry_status_change_view, name='inquiry-status-change'),
    path('<int:inquiry_pk>/status/<int:status_pk>/delete/', views.inquiry_status_delete_view, name='inquiry-status-delete'),
]
