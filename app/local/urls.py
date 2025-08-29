from django.urls import path
from .views import (
    LocalListView, LocalDetailView, LocalCreateView, 
    LocalUpdateView, LocalDeleteView
)

app_name = 'local'

urlpatterns = [
    path('', LocalListView.as_view(), name='local-list'),
    path('create/', LocalCreateView.as_view(), name='local-create'),
    path('<int:pk>/', LocalDetailView.as_view(), name='local-detail'),
    path('<int:pk>/edit/', LocalUpdateView.as_view(), name='local-edit'),
    path('<int:pk>/delete/', LocalDeleteView.as_view(), name='local-delete'),
]
