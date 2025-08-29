from django.urls import path
from .views import (
    LocalListView, LocalDetailView, LocalCreateView, 
    LocalUpdateView, LocalDeleteView,
    CouncilListView, CouncilDetailView, CouncilCreateView,
    CouncilUpdateView, CouncilDeleteView, CouncilNameUpdateView,
    TermListView, TermDetailView, TermCreateView,
    TermUpdateView, TermDeleteView,
    TermSeatDistributionListView, TermSeatDistributionDetailView, TermSeatDistributionCreateView,
    TermSeatDistributionUpdateView, TermSeatDistributionDeleteView, TermSeatDistributionView,
    PartyListView, PartyDetailView, PartyCreateView, PartyUpdateView, PartyDeleteView,
    SessionListView, SessionDetailView, SessionCreateView, SessionUpdateView, SessionDeleteView
)

app_name = 'local'

urlpatterns = [
    # Local URLs
    path('', LocalListView.as_view(), name='local-list'),
    path('create/', LocalCreateView.as_view(), name='local-create'),
    path('<int:pk>/', LocalDetailView.as_view(), name='local-detail'),
    path('<int:pk>/edit/', LocalUpdateView.as_view(), name='local-edit'),
    path('<int:pk>/delete/', LocalDeleteView.as_view(), name='local-delete'),
    
    # Council URLs
    path('councils/', CouncilListView.as_view(), name='council-list'),
    path('councils/create/', CouncilCreateView.as_view(), name='council-create'),
    path('councils/<int:pk>/', CouncilDetailView.as_view(), name='council-detail'),
    path('councils/<int:pk>/edit/', CouncilUpdateView.as_view(), name='council-edit'),
    path('councils/<int:pk>/delete/', CouncilDeleteView.as_view(), name='council-delete'),
    path('councils/<int:pk>/edit-name/', CouncilNameUpdateView.as_view(), name='council-edit-name'),
    
    # Term URLs
    path('terms/', TermListView.as_view(), name='term-list'),
    path('terms/create/', TermCreateView.as_view(), name='term-create'),
    path('terms/<int:pk>/', TermDetailView.as_view(), name='term-detail'),
    path('terms/<int:pk>/edit/', TermUpdateView.as_view(), name='term-edit'),
    path('terms/<int:pk>/delete/', TermDeleteView.as_view(), name='term-delete'),
    
    # Term Seat Distribution URLs
    path('term-seat-distributions/', TermSeatDistributionListView.as_view(), name='term-seat-distribution-list'),
    path('term-seat-distributions/create/', TermSeatDistributionCreateView.as_view(), name='term-seat-distribution-create'),
    path('term-seat-distributions/<int:pk>/', TermSeatDistributionDetailView.as_view(), name='term-seat-distribution-detail'),
    path('term-seat-distributions/<int:pk>/edit/', TermSeatDistributionUpdateView.as_view(), name='term-seat-distribution-edit'),
    path('term-seat-distributions/<int:pk>/delete/', TermSeatDistributionDeleteView.as_view(), name='term-seat-distribution-delete'),
    path('terms/<int:pk>/seat-distribution/', TermSeatDistributionView.as_view(), name='term-seat-distribution'),
    
    # Party URLs
    path('parties/', PartyListView.as_view(), name='party-list'),
    path('parties/create/', PartyCreateView.as_view(), name='party-create'),
    path('parties/<int:pk>/', PartyDetailView.as_view(), name='party-detail'),
    path('parties/<int:pk>/edit/', PartyUpdateView.as_view(), name='party-edit'),
    path('parties/<int:pk>/delete/', PartyDeleteView.as_view(), name='party-delete'),
    
    # Session URLs
    path('sessions/', SessionListView.as_view(), name='session-list'),
    path('sessions/create/', SessionCreateView.as_view(), name='session-create'),
    path('sessions/<int:pk>/', SessionDetailView.as_view(), name='session-detail'),
    path('sessions/<int:pk>/edit/', SessionUpdateView.as_view(), name='session-edit'),
    path('sessions/<int:pk>/delete/', SessionDeleteView.as_view(), name='session-delete'),
]
