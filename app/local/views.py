from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, FormView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.db.models import Q, Prefetch, Case, When, Value, IntegerField
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils.translation import gettext_lazy as _
import json

from .models import Local, Term, Council, TermSeatDistribution, Party, Session, Committee, CommitteeMeeting, CommitteeMeetingAttachment, CommitteeMember, CommitteeParticipationSubstitute, SessionAttachment, SessionPresence, SessionExcuse
from .forms import LocalForm, LocalFilterForm, CouncilForm, CouncilFilterForm, TermForm, TermFilterForm, CouncilNameForm, TermSeatDistributionForm, PartyForm, PartyFilterForm, SessionForm, SessionFilterForm, CommitteeForm, CommitteeFilterForm, CommitteeMeetingForm, CommitteeMemberForm, CommitteeMemberFilterForm, SessionAttachmentForm, CommitteeMeetingAttachmentForm, SessionInvitationForm, SessionMinutesForm, CommitteeParticipationSubstituteForm


class LocalListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """View for listing all Local objects"""
    model = Local
    context_object_name = 'locals'
    template_name = 'local/local_list.html'
    paginate_by = 20

    def test_func(self):
        """Check if user has permission to view Local objects"""
        return self.request.user.is_superuser

    def get_queryset(self):
        """Filter queryset based on search parameters"""
        queryset = Local.objects.all().order_by('name')
        
        # Filter by search query
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(code__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        
        # Filter by status
        status_filter = self.request.GET.get('status', '')
        if status_filter == 'active':
            queryset = queryset.filter(is_active=True)
        elif status_filter == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        return queryset

    def get_context_data(self, **kwargs):
        """Add filter form to context"""
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['status_filter'] = self.request.GET.get('status', '')
        return context


class LocalDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View for displaying a single Local object"""
    model = Local
    context_object_name = 'local'
    template_name = 'local/local_detail.html'

    def test_func(self):
        """Allow superusers or group members whose group's party belongs to this local."""
        if self.request.user.is_superuser:
            return True
        local_pk = self.kwargs.get('pk')
        if local_pk is None:
            return False
        try:
            local_pk = int(local_pk)
        except (TypeError, ValueError):
            return False
        # User can access local if the local's council is in their accessible councils
        council_id = Council.objects.filter(local_id=local_pk).values_list('pk', flat=True).first()
        if council_id is None:
            return False
        return council_id in _get_user_accessible_council_ids(self.request.user)

    def get_context_data(self, **kwargs):
        """Add terms, parties, and sessions data to context"""
        context = super().get_context_data(**kwargs)
        # Show edit/add/delete buttons only to users who have access (same checks as Update/Create/Delete views)
        context['can_edit_local'] = self.request.user.is_superuser
        context['can_add_party'] = self.request.user.is_superuser
        context['can_add_term'] = self.request.user.is_superuser
        context['can_view_party'] = self.request.user.is_superuser
        context['can_edit_party'] = self.request.user.is_superuser
        context['can_delete_party'] = self.request.user.is_superuser
        context['can_manage_terms'] = self.request.user.is_superuser  # View, Edit, Seats (TermDetailView, TermUpdateView, TermSeatDistributionView)

        # Get all active terms (not just those connected through seat distributions)
        # This allows users to see and configure terms even before creating parties
        context['terms'] = Term.objects.filter(is_active=True).order_by('-start_date')

        context['parties'] = self.object.parties.filter(is_active=True).order_by('name')
        
        # Get the current term and its seat distribution
        from django.utils import timezone
        today = timezone.now().date()
        current_term = Term.objects.filter(
            start_date__lte=today,
            end_date__gte=today,
            is_active=True
        ).first()
        
        if current_term:
            context['current_term'] = current_term
            # Get seat distributions for parties in this local
            context['current_term_seat_distributions'] = current_term.seat_distributions.filter(
                party__local=self.object
            ).select_related('party').order_by('-seats')
        
        # Get the last 3 sessions for the council
        if self.object.council:
            context['recent_sessions'] = self.object.council.sessions.filter(is_active=True).order_by('-scheduled_date')[:3]
        else:
            context['recent_sessions'] = []
        return context


class LocalCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View for creating a new Local object"""
    model = Local
    form_class = LocalForm
    template_name = 'local/local_form.html'
    success_url = reverse_lazy('local:local-list')

    def test_func(self):
        """Check if user has permission to create Local objects"""
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        """Add context information for URL parameters"""
        context = super().get_context_data(**kwargs)
        
        # Check for local parameter in URL
        local_id = self.request.GET.get('local')
        if local_id:
            try:
                local = Local.objects.get(pk=local_id)
                context['parent_local'] = local
            except Local.DoesNotExist:
                pass
        
        return context

    def form_valid(self, form):
        """Display success message on form validation"""
        messages.success(self.request, f"Local '{form.instance.name}' created successfully with a default council.")
        return super().form_valid(form)


class LocalUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View for updating an existing Local object"""
    model = Local
    form_class = LocalForm
    template_name = 'local/local_form.html'
    success_url = reverse_lazy('local:local-list')

    def test_func(self):
        """Check if user has permission to edit Local objects"""
        return self.request.user.is_superuser

    def form_valid(self, form):
        """Display success message on form validation"""
        messages.success(self.request, f"Local '{form.instance.name}' updated successfully.")
        return super().form_valid(form)


class LocalDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """View for deleting a Local object"""
    model = Local
    template_name = 'local/local_confirm_delete.html'
    success_url = reverse_lazy('local:local-list')

    def test_func(self):
        """Check if user has permission to delete Local objects"""
        return self.request.user.is_superuser

    def delete(self, request, *args, **kwargs):
        """Display success message on deletion"""
        local_obj = self.get_object()
        messages.success(request, f"Local '{local_obj.name}' deleted successfully.")
        return super().delete(request, *args, **kwargs)


class CouncilNameUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View for updating only the council name"""
    model = Council
    form_class = CouncilNameForm
    template_name = 'local/council_name_form.html'

    def test_func(self):
        """Check if user has permission to edit Council objects"""
        return self.request.user.is_superuser

    def form_valid(self, form):
        """Display success message and save the form"""
        response = super().form_valid(form)
        messages.success(self.request, f"Council name updated to '{form.instance.name}'.")
        return response

    def get_success_url(self):
        """Redirect back to the local detail page"""
        return reverse_lazy('local:local-detail', kwargs={'pk': self.object.local.pk})


# Council Views
class CouncilListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """View for listing all Council objects"""
    model = Council
    context_object_name = 'councils'
    template_name = 'local/council_list.html'
    paginate_by = 20

    def test_func(self):
        """Check if user has permission to view Council objects"""
        return self.request.user.is_superuser

    def get_queryset(self):
        """Filter queryset based on search parameters"""
        queryset = Council.objects.select_related('local').all().order_by('name')
        
        # Filter by search query
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(local__name__icontains=search_query)
            )
        
        # Filter by local
        local_filter = self.request.GET.get('local', '')
        if local_filter:
            queryset = queryset.filter(local_id=local_filter)
        
        # Filter by status
        status_filter = self.request.GET.get('status', '')
        if status_filter == 'active':
            queryset = queryset.filter(is_active=True)
        elif status_filter == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        return queryset

    def get_context_data(self, **kwargs):
        """Add filter form to context"""
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['local_filter'] = self.request.GET.get('local', '')
        context['status_filter'] = self.request.GET.get('status', '')
        context['locals'] = Local.objects.filter(is_active=True)
        return context


def _get_user_accessible_council_ids(user):
    """Return set of council PKs the user can access (via group membership: group's party belongs to local with that council)."""
    if user.is_superuser:
        return set(Council.objects.filter(is_active=True).values_list('pk', flat=True))
    from group.models import GroupMember
    return set(
        GroupMember.objects.filter(
            user=user,
            is_active=True,
            group__party__isnull=False,
            group__party__local__isnull=False,
        ).exclude(
            group__party__local__council__isnull=True,
        ).values_list('group__party__local__council__pk', flat=True).distinct()
    )


class CouncilDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View for displaying a single Council object"""
    model = Council
    context_object_name = 'council'
    template_name = 'local/council_detail.html'

    def test_func(self):
        """Allow superusers or users who are group members in a group whose party's local has this council."""
        if self.request.user.is_superuser:
            return True
        council_pk = self.kwargs.get('pk')
        if council_pk is None:
            return False
        try:
            council_pk = int(council_pk)
        except (TypeError, ValueError):
            return False
        return council_pk in _get_user_accessible_council_ids(self.request.user)

    def get_context_data(self, **kwargs):
        """Add sessions and committees data to context"""
        context = super().get_context_data(**kwargs)
        # Show edit/add/export buttons only to users who have access (same checks as Update/Create/Export views)
        context['can_edit_council'] = self.request.user.is_superuser
        context['can_add_session'] = self.request.user.is_superuser
        context['can_add_committee'] = self.request.user.is_superuser
        context['can_export_committees_pdf'] = (
            self.request.user.is_superuser
            or self.request.user.has_role_permission('session.view')
            or self.object.pk in _get_user_accessible_council_ids(self.request.user)
        )

        # Get sessions for this council, youngest (most recent) date first
        context['sessions'] = self.object.sessions.filter(is_active=True).order_by('-scheduled_date')
        context['total_sessions'] = self.object.sessions.count()
        # Get committees for this council
        context['committees'] = self.object.committees.filter(is_active=True).order_by('name')
        context['total_committees'] = self.object.committees.count()
        
        # Get the current term and its seat distribution
        from django.utils import timezone
        today = timezone.now().date()
        current_term = Term.objects.filter(
            start_date__lte=today,
            end_date__gte=today,
            is_active=True
        ).first()
        
        if current_term:
            context['current_term'] = current_term
            # Get seat distributions for parties in this council's local
            if self.object.local:
                context['current_term_seat_distributions'] = current_term.seat_distributions.filter(
                    party__local=self.object.local
                ).select_related('party').order_by('-seats')
            else:
                context['current_term_seat_distributions'] = []
        else:
            context['current_term'] = None
            context['current_term_seat_distributions'] = []
        
        return context


class CouncilCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View for creating a new Council object"""
    model = Council
    form_class = CouncilForm
    template_name = 'local/council_form.html'
    success_url = reverse_lazy('local:council-list')

    def test_func(self):
        """Check if user has permission to create Council objects"""
        return self.request.user.is_superuser

    def get_initial(self):
        """Set initial local if provided in URL"""
        initial = super().get_initial()
        local_id = self.request.GET.get('local')
        if local_id:
            try:
                local = Local.objects.get(pk=local_id)
                initial['local'] = local
            except Local.DoesNotExist:
                pass
        return initial

    def form_valid(self, form):
        """Display success message on form validation"""
        messages.success(self.request, f"Council '{form.instance.name}' created successfully.")
        return super().form_valid(form)


class CouncilUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View for updating an existing Council object"""
    model = Council
    form_class = CouncilForm
    template_name = 'local/council_form.html'
    success_url = reverse_lazy('local:council-list')

    def test_func(self):
        """Check if user has permission to edit Council objects"""
        return self.request.user.is_superuser

    def form_valid(self, form):
        """Display success message on form validation"""
        messages.success(self.request, f"Council '{form.instance.name}' updated successfully.")
        return super().form_valid(form)


class CouncilDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """View for deleting a Council object"""
    model = Council
    template_name = 'local/council_confirm_delete.html'
    success_url = reverse_lazy('local:council-list')

    def test_func(self):
        """Check if user has permission to delete Council objects"""
        return self.request.user.is_superuser

    def delete(self, request, *args, **kwargs):
        """Display success message on deletion"""
        council_obj = self.get_object()
        messages.success(request, f"Council '{council_obj.name}' deleted successfully.")
        return super().delete(request, *args, **kwargs)


# Term Views
class TermListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """View for listing all Term objects"""
    model = Term
    context_object_name = 'terms'
    template_name = 'local/term_list.html'
    paginate_by = 20

    def test_func(self):
        """Check if user has permission to view Term objects"""
        return self.request.user.is_superuser

    def get_queryset(self):
        """Filter queryset based on search parameters"""
        queryset = Term.objects.all().order_by('-start_date')
        
        # Filter by local
        local_filter = self.request.GET.get('local', '')
        if local_filter:
            # Filter terms that have seat distributions with parties belonging to this local
            queryset = queryset.filter(
                seat_distributions__party__local_id=local_filter
            ).distinct()
        
        # Filter by search query
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        
        # Filter by status
        status_filter = self.request.GET.get('status', '')
        if status_filter == 'active':
            queryset = queryset.filter(is_active=True)
        elif status_filter == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        # Filter by current status
        current_filter = self.request.GET.get('is_current', '')
        if current_filter == 'True':
            queryset = queryset.filter(start_date__lte=timezone.now().date(), end_date__gte=timezone.now().date())
        elif current_filter == 'False':
            queryset = queryset.exclude(start_date__lte=timezone.now().date(), end_date__gte=timezone.now().date())
        
        return queryset

    def get_context_data(self, **kwargs):
        """Add filter form to context"""
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['status_filter'] = self.request.GET.get('status', '')
        context['current_filter'] = self.request.GET.get('is_current', '')
        context['local_filter'] = self.request.GET.get('local', '')
        
        # Add local object to context if filtering by local
        local_filter = self.request.GET.get('local', '')
        if local_filter:
            try:
                from .models import Local
                context['filtered_local'] = Local.objects.get(pk=local_filter)
            except Local.DoesNotExist:
                context['filtered_local'] = None
        
        return context


class TermDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View for displaying a single Term object"""
    model = Term
    context_object_name = 'term'
    template_name = 'local/term_detail.html'

    def test_func(self):
        """Check if user has permission to view Term objects"""
        return self.request.user.is_superuser


class TermCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View for creating a new Term object"""
    model = Term
    form_class = TermForm
    template_name = 'local/term_form.html'
    success_url = reverse_lazy('local:term-list')

    def test_func(self):
        """Check if user has permission to create Term objects"""
        return self.request.user.is_superuser

    def form_valid(self, form):
        """Display success message on form validation"""
        messages.success(self.request, f"Term '{form.instance.name}' created successfully.")
        return super().form_valid(form)


class TermUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View for updating an existing Term object"""
    model = Term
    form_class = TermForm
    template_name = 'local/term_form.html'
    success_url = reverse_lazy('local:term-list')

    def test_func(self):
        """Check if user has permission to edit Term objects"""
        return self.request.user.is_superuser

    def form_valid(self, form):
        """Display success message on form validation"""
        messages.success(self.request, f"Term '{form.instance.name}' updated successfully.")
        return super().form_valid(form)


class TermDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """View for deleting a Term object"""
    model = Term
    template_name = 'local/term_confirm_delete.html'
    success_url = reverse_lazy('local:term-list')

    def test_func(self):
        """Check if user has permission to delete Term objects"""
        return self.request.user.is_superuser

    def delete(self, request, *args, **kwargs):
        """Display success message on deletion"""
        term_obj = self.get_object()
        messages.success(request, f"Term '{term_obj.name}' deleted successfully.")
        return super().delete(request, *args, **kwargs)


# TermSeatDistribution Views
class TermSeatDistributionListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """View for listing all TermSeatDistribution objects"""
    model = TermSeatDistribution
    context_object_name = 'seat_distributions'
    template_name = 'local/term_seat_distribution_list.html'
    paginate_by = 20

    def test_func(self):
        """Check if user has permission to view TermSeatDistribution objects"""
        return self.request.user.is_superuser

    def get_queryset(self):
        """Filter queryset based on search parameters"""
        queryset = TermSeatDistribution.objects.select_related('term', 'party').all().order_by('-term__start_date', '-seats')
        
        # Filter by term
        term_filter = self.request.GET.get('term', '')
        if term_filter:
            queryset = queryset.filter(term_id=term_filter)
        
        # Filter by party
        party_filter = self.request.GET.get('party', '')
        if party_filter:
            queryset = queryset.filter(party_id=party_filter)
        
        # Filter by seats range
        min_seats = self.request.GET.get('min_seats', '')
        if min_seats:
            queryset = queryset.filter(seats__gte=min_seats)
        
        max_seats = self.request.GET.get('max_seats', '')
        if max_seats:
            queryset = queryset.filter(seats__lte=max_seats)
        
        return queryset

    def get_context_data(self, **kwargs):
        """Add filter form to context"""
        context = super().get_context_data(**kwargs)
        context['term_filter'] = self.request.GET.get('term', '')
        context['party_filter'] = self.request.GET.get('party', '')
        context['min_seats'] = self.request.GET.get('min_seats', '')
        context['max_seats'] = self.request.GET.get('max_seats', '')
        context['terms'] = Term.objects.filter(is_active=True)
        context['parties'] = Party.objects.filter(is_active=True)
        return context


class TermSeatDistributionDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View for displaying a single TermSeatDistribution object"""
    model = TermSeatDistribution
    context_object_name = 'seat_distribution'
    template_name = 'local/term_seat_distribution_detail.html'

    def test_func(self):
        """Check if user has permission to view TermSeatDistribution objects"""
        return self.request.user.is_superuser


class TermSeatDistributionCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View for creating a new TermSeatDistribution object"""
    model = TermSeatDistribution
    form_class = TermSeatDistributionForm
    template_name = 'local/term_seat_distribution_form.html'
    success_url = reverse_lazy('local:term-seat-distribution-list')

    def test_func(self):
        """Check if user has permission to create TermSeatDistribution objects"""
        return self.request.user.is_superuser

    def get_initial(self):
        """Set initial term if provided in URL"""
        initial = super().get_initial()
        term_id = self.request.GET.get('term')
        if term_id:
            try:
                term = Term.objects.get(pk=term_id)
                initial['term'] = term.pk
            except Term.DoesNotExist:
                pass
        return initial

    def form_valid(self, form):
        """Display success message on form validation"""
        messages.success(self.request, f"Seat distribution for {form.instance.party.name} in {form.instance.term.name} created successfully.")
        return super().form_valid(form)


class TermSeatDistributionUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View for updating an existing TermSeatDistribution object"""
    model = TermSeatDistribution
    form_class = TermSeatDistributionForm
    template_name = 'local/term_seat_distribution_form.html'
    success_url = reverse_lazy('local:term-seat-distribution-list')

    def test_func(self):
        """Check if user has permission to edit TermSeatDistribution objects"""
        return self.request.user.is_superuser

    def form_valid(self, form):
        """Display success message on form validation"""
        messages.success(self.request, f"Seat distribution for {form.instance.party.name} in {form.instance.term.name} updated successfully.")
        return super().form_valid(form)


class TermSeatDistributionDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """View for deleting a TermSeatDistribution object"""
    model = TermSeatDistribution
    template_name = 'local/term_seat_distribution_confirm_delete.html'
    success_url = reverse_lazy('local:term-seat-distribution-list')

    def test_func(self):
        """Check if user has permission to delete TermSeatDistribution objects"""
        return self.request.user.is_superuser

    def delete(self, request, *args, **kwargs):
        """Display success message on deletion"""
        seat_distribution_obj = self.get_object()
        messages.success(request, f"Seat distribution for {seat_distribution_obj.party.name} in {seat_distribution_obj.term.name} deleted successfully.")
        return super().delete(request, *args, **kwargs)


class TermSeatDistributionView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View for displaying seat distribution for a specific term"""
    model = Term
    context_object_name = 'term'
    template_name = 'local/term_seat_distribution.html'

    def test_func(self):
        """Check if user has permission to view Term objects"""
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        """Add seat distributions to context"""
        context = super().get_context_data(**kwargs)
        context['seat_distributions'] = self.object.seat_distributions.select_related('party').all().order_by('-seats')
        context['parties'] = Party.objects.filter(is_active=True)
        return context


# Party Views
class PartyListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """View for listing all Party objects"""
    model = Party
    context_object_name = 'parties'
    template_name = 'local/party_list.html'
    paginate_by = 20

    def test_func(self):
        """Check if user has permission to view Party objects"""
        return self.request.user.is_superuser

    def get_queryset(self):
        """Filter queryset based on search parameters"""
        queryset = Party.objects.select_related('local').all().order_by('name')
        
        # Filter by search query
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(short_name__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(local__name__icontains=search_query)
            )
        
        # Filter by local
        local_filter = self.request.GET.get('local', '')
        if local_filter:
            queryset = queryset.filter(local_id=local_filter)
        
        # Filter by status
        status_filter = self.request.GET.get('status', '')
        if status_filter == 'active':
            queryset = queryset.filter(is_active=True)
        elif status_filter == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        return queryset

    def get_context_data(self, **kwargs):
        """Add filter form to context"""
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['local_filter'] = self.request.GET.get('local', '')
        context['status_filter'] = self.request.GET.get('status', '')
        context['locals'] = Local.objects.filter(is_active=True)
        return context


class PartyDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View for displaying a single Party object"""
    model = Party
    context_object_name = 'party'
    template_name = 'local/party_detail.html'

    def test_func(self):
        """Check if user has permission to view Party objects"""
        return self.request.user.is_superuser


class PartyCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View for creating a new Party object"""
    model = Party
    form_class = PartyForm
    template_name = 'local/party_form.html'
    success_url = reverse_lazy('local:party-list')

    def test_func(self):
        """Check if user has permission to create Party objects"""
        return self.request.user.is_superuser

    def get_initial(self):
        """Set initial local if provided in URL"""
        initial = super().get_initial()
        local_id = self.request.GET.get('local')
        if local_id:
            try:
                local = Local.objects.get(pk=local_id)
                initial['local'] = local.pk
            except Local.DoesNotExist:
                pass
        return initial

    def get_context_data(self, **kwargs):
        """Add context information for URL parameters"""
        context = super().get_context_data(**kwargs)
        
        # Check for local parameter in URL
        local_id = self.request.GET.get('local')
        if local_id:
            try:
                local = Local.objects.get(pk=local_id)
                context['parent_local'] = local
            except Local.DoesNotExist:
                pass
        
        return context

    def get_success_url(self):
        """Redirect to local detail page if local parameter is provided"""
        local_id = self.request.GET.get('local')
        if local_id:
            try:
                local = Local.objects.get(pk=local_id)
                return reverse('local:local-detail', kwargs={'pk': local.pk})
            except Local.DoesNotExist:
                pass
        return super().get_success_url()

    def form_valid(self, form):
        """Display success message on form validation"""
        messages.success(self.request, f"Party '{form.instance.name}' created successfully.")
        return super().form_valid(form)


class PartyUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View for updating an existing Party object"""
    model = Party
    form_class = PartyForm
    template_name = 'local/party_form.html'
    success_url = reverse_lazy('local:party-list')

    def test_func(self):
        """Check if user has permission to edit Party objects"""
        return self.request.user.is_superuser

    def form_valid(self, form):
        """Display success message on form validation"""
        messages.success(self.request, f"Party '{form.instance.name}' updated successfully.")
        return super().form_valid(form)


class PartyDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """View for deleting a Party object"""
    model = Party
    template_name = 'local/party_confirm_delete.html'
    success_url = reverse_lazy('local:party-list')

    def test_func(self):
        """Check if user has permission to delete Party objects"""
        return self.request.user.is_superuser

    def delete(self, request, *args, **kwargs):
        """Display success message on deletion"""
        party_obj = self.get_object()
        messages.success(request, f"Party '{party_obj.name}' deleted successfully.")
        return super().delete(request, *args, **kwargs)


# Session Views
class SessionDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View for displaying a single Session object"""
    model = Session
    context_object_name = 'session'
    template_name = 'local/session_detail.html'

    def test_func(self):
        """Allow superusers or group members whose group's council is the session's council."""
        if self.request.user.is_superuser:
            return True
        session_pk = self.kwargs.get('pk')
        if session_pk is None:
            return False
        try:
            session_pk = int(session_pk)
        except (TypeError, ValueError):
            return False
        council_id = Session.objects.filter(pk=session_pk).values_list('council_id', flat=True).first()
        if council_id is None:
            return False
        return council_id in _get_user_accessible_council_ids(self.request.user)

    def get_context_data(self, **kwargs):
        """Add motions and questions data to context"""
        from django.db.models import Case, When, IntegerField
        from motion.models import Question

        context = super().get_context_data(**kwargs)
        # Show edit/add buttons only to users who have access (same checks as Update/Invitation/Cancel/Minutes/Attachment views and motion/question create)
        user = self.request.user
        context['can_edit_session'] = user.is_superuser
        context['can_add_invitation'] = user.is_superuser
        context['can_cancel_session'] = user.is_superuser
        context['can_add_minutes'] = user.is_superuser
        context['can_attach_session'] = user.is_superuser
        accessible_council_ids = _get_user_accessible_council_ids(user)
        context['can_add_motion'] = (
            user.is_superuser or user.has_role_permission('motion.create')
            or self.object.council_id in accessible_council_ids
        )
        context['can_add_question'] = (
            user.is_superuser or user.has_role_permission('motion.create')
            or self.object.council_id in accessible_council_ids
        )
        # Show Export and Participants sidebar to superusers, group admins (via template), or regular group members of this session's council
        context['can_see_export_and_participants'] = self.object.council_id in accessible_council_ids

        # Get all motions for this session
        # Order: regular motions by session_rank, then not_admitted motions at the end
        motions_queryset = self.object.motions.filter(is_active=True)
        context['motions'] = motions_queryset.annotate(
            status_order=Case(
                When(status='not_admitted', then=1),
                default=0,
                output_field=IntegerField()
            )
        ).order_by('status_order', 'session_rank', '-submitted_date')
        context['total_motions'] = self.object.motions.count()
        
        # Get all questions for this session
        # Order by session_rank (then by submitted_date as fallback)
        context['questions'] = Question.objects.filter(
            session=self.object,
            is_active=True
        ).select_related('group', 'submitted_by').prefetch_related('parties', 'interventions').order_by('session_rank', '-submitted_date')
        context['total_questions'] = context['questions'].count()
        
        # Get presence tracking data
        session = self.object
        if session.council and session.council.local:
            # Get current term and seat distributions
            today = timezone.now().date()
            current_term = Term.objects.filter(
                start_date__lte=today,
                end_date__gte=today,
                is_active=True
            ).first()
            
            if current_term:
                # Get seat distributions for parties in this council's local
                seat_distributions = TermSeatDistribution.objects.filter(
                    term=current_term,
                    party__local=session.council.local,
                    party__is_active=True
                ).select_related('party').order_by('-seats', 'party__name')
                
                # Get or create presence records for each party
                presence_data = []
                total_seats = 0
                total_present = 0
                gruene_present = 0
                
                for distribution in seat_distributions:
                    presence, created = SessionPresence.objects.get_or_create(
                        session=session,
                        party=distribution.party,
                        defaults={'present_count': 0}
                    )
                    presence_data.append({
                        'party': distribution.party,
                        'seats': distribution.seats,
                        'present_count': presence.present_count,
                    })
                    total_seats += distribution.seats
                    total_present += presence.present_count
                    
                    # Check if this is GRÜNE party (check both name and short_name)
                    party_name = distribution.party.name.upper()
                    party_short = distribution.party.short_name.upper() if distribution.party.short_name else ""
                    if 'GRÜNE' in party_name or 'GRÜNE' in party_short or 'GRUNE' in party_name or 'GRUNE' in party_short:
                        gruene_present = presence.present_count
                
                context['presence_data'] = presence_data
                context['total_seats'] = total_seats
                context['total_present'] = total_present
                # Majority is GRÜNE >= half of total present
                context['majority_needed'] = (total_present // 2) + 1 if total_present > 0 else 0
                context['has_majority'] = gruene_present >= context['majority_needed'] if total_present > 0 else False
                # Participants: group members from parties with seats in current term (political group members)
                party_ids = [d.party_id for d in seat_distributions]
                from group.models import GroupMember
                context['session_participants'] = (
                    GroupMember.objects.filter(
                        group__party_id__in=party_ids,
                        group__party__is_active=True,
                        group__is_active=True,
                        is_active=True,
                    )
                    .select_related('user', 'group', 'group__party')
                    .order_by('group__party__name', 'group__name', 'user__last_name', 'user__first_name')
                )
            else:
                context['presence_data'] = []
                context['total_seats'] = 0
                context['total_present'] = 0
                context['majority_needed'] = 0
                context['has_majority'] = False
                context['session_participants'] = []
        else:
            context['presence_data'] = []
            context['total_seats'] = 0
            context['total_present'] = 0
            context['majority_needed'] = 0
            context['has_majority'] = False
            context['session_participants'] = []

        # Session excuses: who has excused themselves (for Participants section)
        context['excused_user_ids'] = list(
            SessionExcuse.objects.filter(session=self.object).values_list('user_id', flat=True)
        )
        context['user_has_excused'] = self.request.user.pk in context['excused_user_ids']
        participants = context.get('session_participants')
        if hasattr(participants, 'filter'):
            context['user_is_participant'] = participants.filter(user_id=self.request.user.pk).exists()
        else:
            context['user_is_participant'] = any(gm.user_id == self.request.user.pk for gm in (participants or []))

        return context


class SessionExcuseView(LoginRequiredMixin, View):
    """View to excuse oneself from a council session or cancel the excuse (POST only)."""
    http_method_names = ['get', 'post']

    def get(self, request, pk):
        return redirect('local:session-detail', pk=pk)

    def post(self, request, pk):
        session = get_object_or_404(Session, pk=pk)
        # Check user is in participants (group member from a party with seats in current term)
        from group.models import GroupMember
        today = timezone.now().date()
        current_term = Term.objects.filter(
            start_date__lte=today, end_date__gte=today, is_active=True
        ).first()
        if not current_term or not session.council or not session.council.local:
            messages.error(request, _('You cannot excuse yourself for this session.'))
            return redirect('local:session-detail', pk=pk)
        party_ids = list(
            TermSeatDistribution.objects.filter(
                term=current_term,
                party__local=session.council.local,
                party__is_active=True,
            ).values_list('party_id', flat=True)
        )
        is_participant = GroupMember.objects.filter(
            group__party_id__in=party_ids,
            group__party__is_active=True,
            group__is_active=True,
            is_active=True,
            user_id=request.user.pk,
        ).exists()
        if not is_participant:
            messages.error(request, _('You are not a participant of this session.'))
            return redirect('local:session-detail', pk=pk)
        clear = request.POST.get('clear') == '1'
        if clear:
            SessionExcuse.objects.filter(session=session, user=request.user).delete()
            messages.success(request, _('Excuse cancelled.'))
        else:
            note = (request.POST.get('note') or '').strip()
            SessionExcuse.objects.update_or_create(
                session=session,
                user=request.user,
                defaults={'note': note},
            )
            messages.success(request, _('You have excused yourself from this session.'))
        return redirect('local:session-detail', pk=pk)


class SessionCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View for creating a new Session object"""
    model = Session
    form_class = SessionForm
    template_name = 'local/session_form.html'
    success_url = reverse_lazy('local:council-list')

    def test_func(self):
        """Check if user has permission to create Session objects"""
        return self.request.user.is_superuser

    def get_initial(self):
        """Set initial council if provided in URL"""
        initial = super().get_initial()
        council_id = self.request.GET.get('council')
        if council_id:
            try:
                council = Council.objects.get(pk=council_id)
                initial['council'] = council.pk
            except Council.DoesNotExist:
                pass
        return initial

    def get_success_url(self):
        """Redirect to the council detail page after successful creation"""
        if hasattr(self.object, 'council') and self.object.council:
            return reverse('local:council-detail', kwargs={'pk': self.object.council.pk})
        return str(self.success_url)

    def form_valid(self, form):
        """Display success message on form validation"""
        messages.success(self.request, f"Session '{form.instance.title}' created successfully.")
        return super().form_valid(form)


class SessionUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View for updating an existing Session object"""
    model = Session
    form_class = SessionForm
    template_name = 'local/session_form.html'
    success_url = reverse_lazy('local:council-list')

    def test_func(self):
        """Check if user has permission to edit Session objects"""
        return self.request.user.is_superuser

    def get_success_url(self):
        """Redirect to session detail page after successful update"""
        return reverse('local:session-detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        """Display success message on form validation"""
        messages.success(self.request, f"Session '{form.instance.title}' updated successfully.")
        return super().form_valid(form)


class SessionDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """View for deleting a Session object"""
    model = Session
    template_name = 'local/session_confirm_delete.html'
    success_url = reverse_lazy('local:council-list')

    def test_func(self):
        """Check if user has permission to delete Session objects"""
        return self.request.user.is_superuser

    def get_success_url(self):
        """Redirect to council detail page after deletion"""
        council_pk = self.object.council_id if hasattr(self.object, 'council_id') and self.object.council_id else None
        if council_pk:
            return reverse('local:council-detail', kwargs={'pk': council_pk})
        return str(self.success_url)

    def delete(self, request, *args, **kwargs):
        """Display success message on deletion"""
        session_obj = self.get_object()
        messages.success(request, f"Session '{session_obj.title}' deleted successfully.")
        return super().delete(request, *args, **kwargs)


class SessionExportPDFView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View for exporting session information and motions as PDF"""
    model = Session
    context_object_name = 'session'
    template_name = 'local/session_export_pdf.html'

    def test_func(self):
        """Allow superuser, session.view permission, or regular group members for the session's council."""
        user = self.request.user
        if user.is_superuser or user.has_role_permission('session.view'):
            return True
        session_pk = self.kwargs.get('pk')
        if session_pk is None:
            return False
        try:
            session_pk = int(session_pk)
        except (TypeError, ValueError):
            return False
        council_id = Session.objects.filter(pk=session_pk).values_list('council_id', flat=True).first()
        if council_id is None:
            return False
        return council_id in _get_user_accessible_council_ids(user)

    def get_context_data(self, **kwargs):
        """Add motions and questions data to context"""
        from motion.models import MotionGroupDecision, Question
        
        context = super().get_context_data(**kwargs)
        # Get all motions for this session with prefetched parties, group_decisions, and interventions
        # Exclude not_admitted motions from PDF export
        # Order by session_rank (then by submitted_date as fallback)
        # Order group_decisions by decision_time descending to get latest first
        context['motions'] = self.object.motions.filter(
            is_active=True
        ).exclude(
            status='not_admitted'
        ).prefetch_related(
            'parties',
            'interventions',
            Prefetch(
                'group_decisions',
                queryset=MotionGroupDecision.objects.select_related('committee').order_by('-decision_time')
            )
        ).order_by('session_rank', '-submitted_date')
        context['total_motions'] = self.object.motions.count()
        
        # Get all questions for this session
        context['questions'] = Question.objects.filter(
            session=self.object,
            is_active=True
        ).prefetch_related(
            'parties',
            'interventions'
        ).order_by('session_rank', '-submitted_date')
        context['total_questions'] = context['questions'].count()
        return context

    def render_to_response(self, context, **response_kwargs):
        """Render PDF response"""
        from django.template.loader import render_to_string
        from django.http import HttpResponse
        from weasyprint import HTML, CSS
        from django.conf import settings
        import os
        
        # Render the template to HTML
        html_string = render_to_string(self.template_name, context)
        
        # Create PDF using WeasyPrint
        html = HTML(string=html_string)
        css = CSS(string='''
            @page {
                size: A4 landscape;
                margin: 15mm;
            }
            body { 
                font-family: Arial, sans-serif; 
                margin: 0;
                font-size: 10pt;
            }
            .header { 
                text-align: center; 
                margin-bottom: 20px; 
            }
            .header h1 {
                font-size: 14pt;
                margin: 0 0 5px 0;
            }
            .header p {
                font-size: 10pt;
                margin: 2px 0;
            }
            .motions-table { 
                width: 100%; 
                border-collapse: collapse; 
                margin-top: 20px;
                page-break-inside: auto;
            }
            .motions-table thead {
                display: table-header-group;
            }
            .motions-table tbody tr {
                page-break-inside: avoid;
                page-break-after: auto;
            }
            .motions-table th, .motions-table td { 
                border: 1px solid #333; 
                padding: 8px; 
                text-align: left;
                vertical-align: top;
            }
            .motions-table th { 
                background-color: #f2f2f2; 
                font-weight: bold;
            }
            .motions-table td:first-child {
                width: 5%;
                text-align: center;
                font-weight: bold;
            }
            .motions-table th:first-child {
                text-align: center;
            }
            .motions-table td:nth-child(2) {
                width: 25%;
            }
            .motions-table td:nth-child(3) {
                width: 20%;
            }
            .motions-table td:nth-child(4) {
                width: 25%;
            }
            .motions-table td:nth-child(5) {
                width: 25%;
            }
            .no-motions {
                text-align: center;
                color: #666;
                font-style: italic;
                margin: 40px 0;
            }
            .footer {
                margin-top: 30px;
                padding-top: 15px;
                border-top: 1px solid #ddd;
                text-align: center;
                color: #666;
                font-size: 8pt;
            }
            .footer p {
                margin: 2px 0;
            }
        ''')
        
        # Generate PDF
        pdf = html.write_pdf(stylesheets=[css])
        
        # Create response
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="session_{self.object.pk}_{self.object.title.replace(" ", "_")}.pdf"'
        
        return response


@login_required
def session_export_ics(request, pk):
    """Export a single session as an ICS calendar file."""
    session = get_object_or_404(Session, pk=pk)
    # Allow: superuser, session.view permission, or session is in user's councils/committees (personal calendar)
    can_export = (
        request.user.is_superuser
        or request.user.has_role_permission('session.view')
    )
    if not can_export:
        from group.models import GroupMember
        user_council_ids = set()
        for m in GroupMember.objects.filter(user=request.user, is_active=True).select_related('group__party__local'):
            if getattr(m.group.party, 'local', None) and getattr(m.group.party.local, 'council', None):
                user_council_ids.add(m.group.party.local.council_id)
        if session.council_id in user_council_ids:
            can_export = True
        if not can_export and session.committee_id:
            from .models import CommitteeMember
            can_export = CommitteeMember.objects.filter(
                user=request.user, committee_id=session.committee_id, is_active=True
            ).exists()
    if not can_export:
        messages.error(request, "You don't have permission to export this session.")
        return redirect('local:session-detail', pk=pk)

    dtstart = session.scheduled_date
    if not timezone.is_aware(dtstart):
        dtstart = timezone.make_aware(dtstart)
    dtstart_utc = dtstart.astimezone(timezone.UTC)
    dtend_utc = dtstart_utc + timezone.timedelta(hours=1)
    dtstart_str = dtstart_utc.strftime('%Y%m%dT%H%M%SZ')
    dtend_str = dtend_utc.strftime('%Y%m%dT%H%M%SZ')
    uid = f"session-{session.pk}@{request.get_host()}"

    def escape_ics(text):
        if not text:
            return ""
        text = str(text).replace('\\', '\\\\').replace(',', '\\,').replace(';', '\\;').replace('\n', '\\n')
        return text

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Klubtool//Session//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTART:{dtstart_str}",
        f"DTEND:{dtend_str}",
        f"SUMMARY:{escape_ics(session.title)}",
    ]
    if session.location:
        lines.append(f"LOCATION:{escape_ics(session.location)}")
    if session.agenda:
        lines.append(f"DESCRIPTION:{escape_ics(session.agenda)}")
    session_url = request.build_absolute_uri(reverse('local:session-detail', args=[session.pk]))
    lines.append(f"URL:{session_url}")
    lines.append(f"DTSTAMP:{timezone.now().astimezone(timezone.UTC).strftime('%Y%m%dT%H%M%SZ')}")
    lines.extend(["STATUS:CONFIRMED", "END:VEVENT", "END:VCALENDAR"])
    ics_file = "\r\n".join(lines)
    response = HttpResponse(ics_file, content_type='text/calendar; charset=utf-8')
    filename = f"session_{session.pk}_{session.title.replace(' ', '_')}.ics"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def committee_meeting_export_ics(request, pk):
    """Export a single committee meeting as an ICS calendar file."""
    meeting = get_object_or_404(CommitteeMeeting, pk=pk)
    can_export = (
        request.user.is_superuser
        or request.user.has_role_permission('session.view')
    )
    if not can_export:
        from .models import CommitteeMember
        can_export = CommitteeMember.objects.filter(
            user=request.user, committee_id=meeting.committee_id, is_active=True
        ).exists()
    if not can_export and meeting.committee_id:
        council_id = Committee.objects.filter(pk=meeting.committee_id).values_list('council_id', flat=True).first()
        if council_id is not None and council_id in _get_user_accessible_council_ids(request.user):
            can_export = True
    if not can_export:
        messages.error(request, _("You don't have permission to export this meeting."))
        return redirect('local:committee-meeting-detail', pk=pk)

    dtstart = meeting.scheduled_date
    if not timezone.is_aware(dtstart):
        dtstart = timezone.make_aware(dtstart)
    dtstart_utc = dtstart.astimezone(timezone.UTC)
    dtend_utc = dtstart_utc + timezone.timedelta(hours=1)
    dtstart_str = dtstart_utc.strftime('%Y%m%dT%H%M%SZ')
    dtend_str = dtend_utc.strftime('%Y%m%dT%H%M%SZ')
    uid = f"committee-meeting-{meeting.pk}@{request.get_host()}"

    def escape_ics(text):
        if not text:
            return ""
        text = str(text).replace('\\', '\\\\').replace(',', '\\,').replace(';', '\\;').replace('\n', '\\n')
        return text

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Klubtool//Committee Meeting//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTART:{dtstart_str}",
        f"DTEND:{dtend_str}",
        f"SUMMARY:{escape_ics(meeting.title)}",
    ]
    if meeting.location:
        lines.append(f"LOCATION:{escape_ics(meeting.location)}")
    if meeting.description:
        lines.append(f"DESCRIPTION:{escape_ics(meeting.description)}")
    meeting_url = request.build_absolute_uri(reverse('local:committee-meeting-detail', args=[meeting.pk]))
    lines.append(f"URL:{meeting_url}")
    lines.append(f"DTSTAMP:{timezone.now().astimezone(timezone.UTC).strftime('%Y%m%dT%H%M%SZ')}")
    lines.extend(["STATUS:CONFIRMED", "END:VEVENT", "END:VCALENDAR"])
    ics_file = "\r\n".join(lines)
    response = HttpResponse(ics_file, content_type='text/calendar; charset=utf-8')
    filename = f"committee_meeting_{meeting.pk}_{meeting.title.replace(' ', '_')}.ics"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


class CouncilCommitteesExportPDFView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View for exporting all committees of a council as PDF"""
    model = Council
    context_object_name = 'council'
    template_name = 'local/council_committees_export_pdf.html'

    def test_func(self):
        """Allow superusers, users with session.view, or group members whose group's council is this council."""
        if self.request.user.is_superuser:
            return True
        if self.request.user.has_role_permission('session.view'):
            return True
        council_pk = self.kwargs.get('pk')
        if council_pk is None:
            return False
        try:
            council_pk = int(council_pk)
        except (TypeError, ValueError):
            return False
        return council_pk in _get_user_accessible_council_ids(self.request.user)

    def get_context_data(self, **kwargs):
        """Add committees with members and substitute members to context"""
        from django.db.models import Case, When, CharField, Value
        
        context = super().get_context_data(**kwargs)
        # Get all active committees for this council with their members
        committees = self.object.committees.filter(is_active=True).order_by('name')
        
        # Prefetch members with proper ordering
        from django.db.models import Prefetch
        committees_list = []
        for committee in committees:
            # Get members (excluding substitute members)
            members = committee.members.filter(
                is_active=True
            ).exclude(
                role='substitute_member'
            ).select_related('user').prefetch_related(
                'user__group_memberships__group__party'
            ).annotate(
                role_order=Case(
                    When(role='chairperson', then=Value(1)),
                    When(role='vice_chairperson', then=Value(2)),
                    When(role='member', then=Value(3)),
                    default=Value(4),
                    output_field=CharField(),
                )
            ).order_by('role_order', 'user__first_name', 'user__last_name')
            
            # Get substitute members
            substitute_members = committee.members.filter(
                is_active=True,
                role='substitute_member'
            ).select_related('user').prefetch_related(
                'user__group_memberships__group__party'
            ).order_by('user__first_name', 'user__last_name')
            
            # Combine members and substitute members into pairs for the table
            combined_members = []
            members_list = list(members)
            substitute_list = list(substitute_members)
            max_length = max(len(members_list), len(substitute_list))
            
            for i in range(max_length):
                member = members_list[i] if i < len(members_list) else None
                substitute = substitute_list[i] if i < len(substitute_list) else None
                combined_members.append({
                    'member': member,
                    'substitute': substitute,
                })
            
            committees_list.append({
                'committee': committee,
                'members': members,
                'substitute_members': substitute_members,
                'combined_members': combined_members,
            })
        
        context['committees_data'] = committees_list
        context['total_committees'] = len(committees_list)
        
        # Get the user's political group name for the title
        from group.models import GroupMember
        user_group = GroupMember.objects.filter(
            user=self.request.user,
            is_active=True
        ).select_related('group').first()
        
        if user_group:
            context['group_name'] = user_group.group.name
        else:
            # Fallback to council name if user has no group
            context['group_name'] = self.object.name
        
        return context

    def render_to_response(self, context, **response_kwargs):
        """Render PDF response"""
        from django.template.loader import render_to_string
        from django.http import HttpResponse
        from weasyprint import HTML, CSS
        
        # Render the template to HTML
        html_string = render_to_string(self.template_name, context)
        
        # Create PDF using WeasyPrint
        html = HTML(string=html_string)
        css = CSS(string='''
            @page {
                size: A4 portrait;
                margin: 15mm;
            }
            body { 
                font-family: Arial, sans-serif; 
                margin: 0;
                font-size: 10pt;
            }
            .header { 
                text-align: center; 
                margin-bottom: 20px; 
            }
            .header h1 {
                font-size: 16pt;
                margin: 0 0 5px 0;
            }
            .header p {
                font-size: 10pt;
                margin: 2px 0;
            }
            .committee-section {
                margin-bottom: 25px;
                page-break-inside: avoid;
            }
            .committee-title {
                font-size: 12pt;
                font-weight: bold;
                margin-bottom: 10px;
                padding: 8px;
                background-color: #f2f2f2;
            }
            .committee-info {
                margin-bottom: 10px;
                font-size: 9pt;
                color: #666;
            }
            .members-table { 
                width: 100%; 
                border-collapse: collapse; 
                margin-top: 10px;
                margin-bottom: 15px;
                font-size: 9pt;
            }
            .members-table th, .members-table td { 
                border: none; 
                padding: 6px; 
                text-align: left;
                vertical-align: top;
            }
            .members-table th { 
                background-color: #fff; 
                font-weight: bold;
            }
            .members-table th:first-child,
            .members-table td:first-child {
                width: 50%;
            }
            .members-table th:nth-child(2),
            .members-table td:nth-child(2) {
                width: 50%;
            }
            .substitute-section {
                margin-top: 10px;
                margin-bottom: 10px;
            }
            .substitute-title {
                font-size: 10pt;
                font-weight: bold;
                margin-bottom: 5px;
            }
            .footer {
                margin-top: 30px;
                padding-top: 15px;
                border-top: 1px solid #ddd;
                text-align: center;
                color: #666;
                font-size: 8pt;
            }
            .footer p {
                margin: 2px 0;
            }
        ''')
        
        # Generate PDF
        pdf = html.write_pdf(stylesheets=[css])
        
        # Create response
        from django.utils import timezone
        from datetime import datetime
        
        # Get group name from context (already set in get_context_data)
        group_name = context.get('group_name', self.object.name)
        
        # Format date for filename
        date_str = timezone.now().strftime('%Y-%m-%d')
        
        # Create filename: group_name_stand_date.pdf
        # Replace spaces and special characters for filename safety
        safe_group_name = group_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
        filename = f"{safe_group_name}_Stand_{date_str}.pdf"
        
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response


@login_required
@require_http_methods(["POST"])
def update_motion_order(request, session_pk):
    """AJAX view to update the order/rank of motions in a session"""
    from motion.models import Motion
    
    # Check permissions - user must be superuser or have session view permission
    if not (request.user.is_superuser or request.user.has_role_permission('session.view')):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        session = get_object_or_404(Session, pk=session_pk)
        data = json.loads(request.body)
        motion_orders = data.get('motion_orders', [])
        
        # Update each motion's session_rank
        for order_data in motion_orders:
            motion_id = order_data.get('motion_id')
            rank = order_data.get('rank')
            
            if motion_id and rank is not None:
                try:
                    motion = Motion.objects.get(pk=motion_id, session=session)
                    motion.session_rank = rank
                    motion.save(update_fields=['session_rank'])
                except Motion.DoesNotExist:
                    continue
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def update_question_order(request, session_pk):
    """AJAX view to update the order/rank of questions in a session"""
    from motion.models import Question
    
    # Check permissions - user must be superuser or have session view permission
    if not (request.user.is_superuser or request.user.has_role_permission('session.view')):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        session = get_object_or_404(Session, pk=session_pk)
        data = json.loads(request.body)
        question_orders = data.get('question_orders', [])
        
        # Update each question's session_rank
        for order_data in question_orders:
            question_id = order_data.get('question_id')
            rank = order_data.get('rank')
            
            if question_id and rank is not None:
                try:
                    question = Question.objects.get(pk=question_id, session=session)
                    question.session_rank = rank
                    question.save(update_fields=['session_rank'])
                except Question.DoesNotExist:
                    continue
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def update_session_presence(request, session_pk, party_pk):
    """AJAX view to update presence count for a party in a session"""
    # Check permissions - user must be superuser or have session view permission
    if not (request.user.is_superuser or request.user.has_role_permission('session.view')):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        session = get_object_or_404(Session, pk=session_pk)
        party = get_object_or_404(Party, pk=party_pk)
        
        # Verify party belongs to the session's council local
        if not (session.council and session.council.local and party.local == session.council.local):
            return JsonResponse({'error': 'Party does not belong to this session\'s local'}, status=400)
        
        data = json.loads(request.body)
        action = data.get('action')  # 'increment' or 'decrement'
        
        # Get or create presence record
        presence, created = SessionPresence.objects.get_or_create(
            session=session,
            party=party,
            defaults={'present_count': 0}
        )
        
        # Update count based on action
        if action == 'increment':
            # Get seat distribution to ensure we don't exceed total seats
            today = timezone.now().date()
            current_term = Term.objects.filter(
                start_date__lte=today,
                end_date__gte=today,
                is_active=True
            ).first()
            
            if current_term:
                seat_dist = TermSeatDistribution.objects.filter(
                    term=current_term,
                    party=party
                ).first()
                max_seats = seat_dist.seats if seat_dist else 999
                
                if presence.present_count < max_seats:
                    presence.present_count += 1
                    presence.save(update_fields=['present_count'])
        elif action == 'decrement':
            if presence.present_count > 0:
                presence.present_count -= 1
                presence.save(update_fields=['present_count'])
        else:
            return JsonResponse({'error': 'Invalid action'}, status=400)
        
        # Calculate totals
        total_seats = 0
        total_present = 0
        gruene_present = 0
        today = timezone.now().date()
        current_term = Term.objects.filter(
            start_date__lte=today,
            end_date__gte=today,
            is_active=True
        ).first()
        
        if current_term and session.council and session.council.local:
            seat_distributions = TermSeatDistribution.objects.filter(
                term=current_term,
                party__local=session.council.local,
                party__is_active=True
            )
            
            for dist in seat_distributions:
                total_seats += dist.seats
                presence_record = SessionPresence.objects.filter(
                    session=session,
                    party=dist.party
                ).first()
                present_count = presence_record.present_count if presence_record else 0
                total_present += present_count
                
                # Check if this is GRÜNE party (check both name and short_name)
                party_name = dist.party.name.upper()
                party_short = dist.party.short_name.upper() if dist.party.short_name else ""
                if 'GRÜNE' in party_name or 'GRÜNE' in party_short or 'GRUNE' in party_name or 'GRUNE' in party_short:
                    gruene_present = present_count
        
        # Majority is GRÜNE >= half of total present
        majority_needed = (total_present // 2) + 1 if total_present > 0 else 0
        has_majority = gruene_present >= majority_needed if total_present > 0 else False
        
        return JsonResponse({
            'success': True,
            'present_count': presence.present_count,
            'total_present': total_present,
            'total_seats': total_seats,
            'majority_needed': majority_needed,
            'has_majority': has_majority
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


# Committee Views
class CommitteeListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """View for listing all Committee objects"""
    model = Committee
    context_object_name = 'committees'
    template_name = 'local/committee_list.html'
    paginate_by = 20

    def test_func(self):
        """Allow superuser or any user who can access at least one council (via connected group)."""
        if self.request.user.is_superuser:
            return True
        return bool(_get_user_accessible_council_ids(self.request.user))

    def get_queryset(self):
        """Filter queryset: superusers see all committees; others see only committees of their connected councils."""
        user = self.request.user
        base = Committee.objects.all().select_related('council', 'council__local').order_by('name')
        if user.is_superuser:
            queryset = base
        else:
            council_ids = _get_user_accessible_council_ids(user)
            queryset = base.filter(council_id__in=council_ids) if council_ids else base.none()
        
        # Filter by search query
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(chairperson__icontains=search_query) |
                Q(council__name__icontains=search_query)
            )
        
        # Filter by committee type
        committee_type_filter = self.request.GET.get('committee_type', '')
        if committee_type_filter:
            queryset = queryset.filter(committee_type=committee_type_filter)
        
        # Filter by council
        council_filter = self.request.GET.get('council', '')
        if council_filter:
            queryset = queryset.filter(council_id=council_filter)

        return queryset

    def get_context_data(self, **kwargs):
        """Add filter form to context"""
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['committee_type_filter'] = self.request.GET.get('committee_type', '')
        context['council_filter'] = self.request.GET.get('council', '')
        context['councils'] = Council.objects.filter(is_active=True)
        return context


class CommitteeDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View for displaying a single Committee object"""
    model = Committee
    context_object_name = 'committee'
    template_name = 'local/committee_detail.html'

    def test_func(self):
        """Allow superuser or members of a group connected to the committee's council."""
        if self.request.user.is_superuser:
            return True
        committee_pk = self.kwargs.get('pk')
        if committee_pk is None:
            return False
        try:
            committee_pk = int(committee_pk)
        except (TypeError, ValueError):
            return False
        council_id = Committee.objects.filter(pk=committee_pk).values_list('council_id', flat=True).first()
        if council_id is None:
            return False
        return council_id in _get_user_accessible_council_ids(self.request.user)

    def get_context_data(self, **kwargs):
        """Add committee members and motions data to context"""
        from django.db.models import Case, When, CharField, Value
        from group.models import GroupMember

        context = super().get_context_data(**kwargs)
        user = self.request.user
        # Permission flags: show edit/add buttons only to users who can access those views
        context['can_edit_committee'] = user.is_superuser
        context['can_add_committee_member'] = (
            user.is_superuser
            or GroupMember.objects.filter(
                user=user,
                is_active=True,
                roles__name__in=['Leader', 'Deputy Leader'],
            ).exists()
        )
        context['can_edit_committee_member'] = user.is_superuser
        context['can_add_committee_meeting'] = user.is_superuser
        context['can_edit_committee_meeting'] = user.is_superuser
        # Get active members for this committee with custom role ordering
        context['members'] = self.object.members.filter(is_active=True).select_related('user').annotate(
            role_order=Case(
                When(role='chairperson', then=Value(1)),
                When(role='vice_chairperson', then=Value(2)),
                When(role='member', then=Value(3)),
                When(role='substitute_member', then=Value(4)),
                default=Value(5),
                output_field=CharField(),
            )
        ).order_by('role_order', 'user__first_name', 'user__last_name')
        context['total_members'] = self.object.members.count()
        # Get motions assigned to this committee
        context['motions'] = self.object.motions.filter(is_active=True).order_by('-submitted_date')[:5]
        context['total_motions'] = self.object.motions.count()
        # Get committee meetings (replaces committee sessions)
        context['meetings'] = self.object.meetings.filter(is_active=True).order_by('-scheduled_date')
        context['total_meetings'] = self.object.meetings.count()
        return context


class CommitteeCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View for creating a new Committee object"""
    model = Committee
    form_class = CommitteeForm
    template_name = 'local/committee_form.html'

    def test_func(self):
        """Check if user has permission to create Committee objects"""
        return self.request.user.is_superuser

    def get_initial(self):
        """Set initial council if provided in URL"""
        initial = super().get_initial()
        council_id = self.request.GET.get('council')
        if council_id:
            try:
                council = Council.objects.get(pk=council_id)
                initial['council'] = council.pk
            except Council.DoesNotExist:
                pass
        return initial
    
    def get_context_data(self, **kwargs):
        """Add local to context if council is pre-filled"""
        context = super().get_context_data(**kwargs)
        council_id = self.request.GET.get('council')
        if council_id:
            try:
                council = Council.objects.get(pk=council_id)
                context['local'] = council.local
            except Council.DoesNotExist:
                pass
        return context

    def get_success_url(self):
        """Redirect to the linked council after successful creation"""
        if hasattr(self.object, 'council') and self.object.council:
            return reverse('local:council-detail', kwargs={'pk': self.object.council.pk})
        return reverse('local:committee-list')

    def form_valid(self, form):
        """Display success message on form validation"""
        messages.success(self.request, f"Committee '{form.instance.name}' created successfully.")
        return super().form_valid(form)


class CommitteeUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View for updating an existing Committee object"""
    model = Committee
    form_class = CommitteeForm
    template_name = 'local/committee_form.html'
    success_url = reverse_lazy('local:committee-list')

    def test_func(self):
        """Check if user has permission to edit Committee objects"""
        return self.request.user.is_superuser

    def get_success_url(self):
        """Redirect to committee detail after edit"""
        return reverse('local:committee-detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        """Add local to context"""
        context = super().get_context_data(**kwargs)
        if self.object and self.object.council:
            context['local'] = self.object.council.local
        return context

    def form_valid(self, form):
        """Display success message on form validation"""
        messages.success(self.request, f"Committee '{form.instance.name}' updated successfully.")
        return super().form_valid(form)


class CommitteeDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """View for deleting a Committee object"""
    model = Committee
    template_name = 'local/committee_confirm_delete.html'
    success_url = reverse_lazy('local:committee-list')

    def test_func(self):
        """Check if user has permission to delete Committee objects"""
        return self.request.user.is_superuser

    def delete(self, request, *args, **kwargs):
        """Display success message on deletion"""
        committee_obj = self.get_object()
        messages.success(request, f"Committee '{committee_obj.name}' deleted successfully.")
        return super().delete(request, *args, **kwargs)


# Committee Meeting Views
class CommitteeMeetingCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View for creating a new CommitteeMeeting (optionally for a specific committee)."""
    model = CommitteeMeeting
    form_class = CommitteeMeetingForm
    template_name = 'local/committee_meeting_form.html'

    def test_func(self):
        return self.request.user.is_superuser

    def get_initial(self):
        initial = super().get_initial()
        committee_pk = self.kwargs.get('committee_pk') or self.request.GET.get('committee')
        if committee_pk:
            try:
                committee = Committee.objects.get(pk=committee_pk)
                initial['committee'] = committee
            except Committee.DoesNotExist:
                pass
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        committee_pk = self.kwargs.get('committee_pk') or self.request.GET.get('committee')
        if committee_pk:
            try:
                kwargs['committee'] = Committee.objects.get(pk=committee_pk)
            except Committee.DoesNotExist:
                pass
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        committee_pk = self.kwargs.get('committee_pk') or self.request.GET.get('committee')
        if committee_pk:
            try:
                context['committee'] = Committee.objects.get(pk=committee_pk)
            except Committee.DoesNotExist:
                context['committee'] = None
        else:
            context['committee'] = None
        return context

    def get_success_url(self):
        if self.object.committee_id:
            return reverse('local:committee-detail', kwargs={'pk': self.object.committee_id})
        return reverse('local:committee-list')

    def form_valid(self, form):
        messages.success(self.request, _("Committee meeting '%(title)s' created successfully.") % {'title': form.instance.title})
        return super().form_valid(form)


class CommitteeMeetingDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View for displaying a single CommitteeMeeting."""
    model = CommitteeMeeting
    context_object_name = 'meeting'
    template_name = 'local/committee_meeting_detail.html'

    def test_func(self):
        """Allow superuser or members of a group connected to the meeting's committee's council."""
        if self.request.user.is_superuser:
            return True
        meeting_pk = self.kwargs.get('pk')
        if meeting_pk is None:
            return False
        try:
            meeting_pk = int(meeting_pk)
        except (TypeError, ValueError):
            return False
        council_id = (
            CommitteeMeeting.objects.filter(pk=meeting_pk)
            .values_list('committee__council_id', flat=True)
            .first()
        )
        if council_id is None:
            return False
        return council_id in _get_user_accessible_council_ids(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['committee'] = self.object.committee
        # Show edit button only to users who can access CommitteeMeetingUpdateView
        context['can_edit_committee_meeting'] = self.request.user.is_superuser
        # Participants: committee members who take part in the meeting (excluding substitute members)
        role_order = Case(
            When(role='chairperson', then=Value(1)),
            When(role='vice_chairperson', then=Value(2)),
            When(role='member', then=Value(3)),
            default=Value(4),
            output_field=IntegerField(),
        )
        participants = list(
            self.object.committee.members
            .filter(is_active=True)
            .exclude(role='substitute_member')
            .order_by(role_order, 'user__last_name', 'user__first_name')
        )
        context['participants'] = participants
        # Map participant member pk -> substitute_member (CommitteeMember) for this meeting
        substitute_map = {
            s.member_id: s.substitute_member
            for s in CommitteeParticipationSubstitute.objects.filter(
                committee_meeting=self.object
            ).select_related('substitute_member', 'substitute_member__user')
        }
        context['participants_with_substitute'] = [(m, substitute_map.get(m.pk)) for m in participants]
        # Substitute form for current user (only if they are a participant)
        my_participant = next((p for p in participants if p.user_id == self.request.user.pk), None)
        existing_sub = None
        if my_participant:
            existing_sub = CommitteeParticipationSubstitute.objects.filter(
                committee_meeting=self.object, member=my_participant
            ).first()
        context['substitute_form'] = CommitteeParticipationSubstituteForm(
            committee=self.object.committee,
            initial={'substitute_member': existing_sub.substitute_member_id} if existing_sub else None,
        )
        context['my_participant'] = my_participant
        return context


class CommitteeMeetingSetSubstituteView(LoginRequiredMixin, View):
    """View to set or clear a substitute for the current user at a committee meeting (POST only)."""
    http_method_names = ['get', 'post']

    def get(self, request, pk):
        return redirect('local:committee-meeting-detail', pk=pk)

    def post(self, request, pk):
        meeting = get_object_or_404(CommitteeMeeting, pk=pk)
        if not request.user.is_superuser:
            messages.error(request, _('Permission denied.'))
            return redirect('local:committee-meeting-detail', pk=pk)
        member_pk = request.POST.get('member')
        if not member_pk:
            messages.error(request, _('Invalid request.'))
            return redirect('local:committee-meeting-detail', pk=pk)
        member = get_object_or_404(CommitteeMember, pk=member_pk)
        if member.committee_id != meeting.committee_id or member.user_id != request.user.pk or member.role == 'substitute_member':
            messages.error(request, _('You can only set a substitute for yourself as a regular committee member.'))
            return redirect('local:committee-meeting-detail', pk=pk)
        form = CommitteeParticipationSubstituteForm(request.POST, committee=meeting.committee)
        if not form.is_valid():
            err = next(iter(form.errors.values()), [_('Invalid selection.')])
            messages.error(request, err[0] if err else _('Invalid selection.'))
            return redirect('local:committee-meeting-detail', pk=pk)
        substitute_member = form.cleaned_data.get('substitute_member')
        if substitute_member:
            if substitute_member.committee_id != meeting.committee_id or substitute_member.role != 'substitute_member':
                messages.error(request, _('Invalid substitute member.'))
                return redirect('local:committee-meeting-detail', pk=pk)
            CommitteeParticipationSubstitute.objects.update_or_create(
                committee_meeting=meeting, member=member,
                defaults={'substitute_member': substitute_member},
            )
            messages.success(request, _('Substitute set: %(name)s will attend in your place.') % {'name': substitute_member.user.get_full_name() or substitute_member.user.username})
        else:
            deleted_count, _by_model = CommitteeParticipationSubstitute.objects.filter(committee_meeting=meeting, member=member).delete()
            if deleted_count:
                messages.success(request, _('Substitute cleared.'))
        return redirect('local:committee-meeting-detail', pk=pk)


class CommitteeMeetingUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View for updating a CommitteeMeeting."""
    model = CommitteeMeeting
    form_class = CommitteeMeetingForm
    context_object_name = 'meeting'
    template_name = 'local/committee_meeting_form.html'

    def test_func(self):
        return self.request.user.is_superuser

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.object and self.object.committee_id:
            kwargs['committee'] = self.object.committee
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['committee'] = self.object.committee if self.object else None
        return context

    def get_success_url(self):
        if self.object.committee_id:
            return reverse('local:committee-detail', kwargs={'pk': self.object.committee_id})
        return reverse('local:committee-list')

    def form_valid(self, form):
        messages.success(self.request, _("Committee meeting '%(title)s' updated successfully.") % {'title': form.instance.title})
        return super().form_valid(form)


class CommitteeMeetingDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """View for deleting a CommitteeMeeting."""
    model = CommitteeMeeting
    template_name = 'local/committee_meeting_confirm_delete.html'
    context_object_name = 'meeting'

    def test_func(self):
        return self.request.user.is_superuser

    def get_success_url(self):
        if self.object.committee_id:
            return reverse('local:committee-detail', kwargs={'pk': self.object.committee_id})
        return reverse('local:committee-list')

    def delete(self, request, *args, **kwargs):
        meeting = self.get_object()
        committee_pk = meeting.committee_id
        messages.success(request, _("Committee meeting '%(title)s' deleted successfully.") % {'title': meeting.title})
        result = super().delete(request, *args, **kwargs)
        return result


# Committee Member Views
class CommitteeMemberListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """View for listing all CommitteeMember objects"""
    model = CommitteeMember
    context_object_name = 'members'
    template_name = 'local/committee_member_list.html'
    paginate_by = 20

    def test_func(self):
        """Check if user has permission to view CommitteeMember objects"""
        return self.request.user.is_superuser

    def get_queryset(self):
        """Filter queryset based on search parameters"""
        queryset = CommitteeMember.objects.all().select_related('committee', 'user').order_by('-joined_date')
        
        # Filter by search query
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(user__username__icontains=search_query) |
                Q(user__first_name__icontains=search_query) |
                Q(user__last_name__icontains=search_query) |
                Q(committee__name__icontains=search_query)
            )
        
        # Filter by role
        role_filter = self.request.GET.get('role', '')
        if role_filter:
            queryset = queryset.filter(role=role_filter)
        
        # Filter by committee
        committee_filter = self.request.GET.get('committee', '')
        if committee_filter:
            queryset = queryset.filter(committee_id=committee_filter)
        
        return queryset

    def get_context_data(self, **kwargs):
        """Add filter form to context"""
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['role_filter'] = self.request.GET.get('role', '')
        context['committee_filter'] = self.request.GET.get('committee', '')
        context['committees'] = Committee.objects.filter(is_active=True)
        return context


class CommitteeMemberCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View for creating a new CommitteeMember object"""
    model = CommitteeMember
    form_class = CommitteeMemberForm
    template_name = 'local/committee_member_form.html'

    def test_func(self):
        """Check if user has permission to create CommitteeMember objects"""
        # Allow superusers
        if self.request.user.is_superuser:
            return True
        
        # Allow Group Leaders and Deputy Leaders
        from group.models import GroupMember
        return GroupMember.objects.filter(
            user=self.request.user,
            is_active=True,
            roles__name__in=['Leader', 'Deputy Leader']
        ).exists()

    def get_initial(self):
        """Set initial committee if provided in URL"""
        initial = super().get_initial()
        committee_id = self.request.GET.get('committee')
        if committee_id:
            try:
                committee = Committee.objects.get(pk=committee_id)
                initial['committee'] = committee.pk
            except Committee.DoesNotExist:
                pass
        return initial

    def get_success_url(self):
        """Redirect to the linked committee after successful creation"""
        if hasattr(self.object, 'committee') and self.object.committee:
            return reverse('local:committee-detail', kwargs={'pk': self.object.committee.pk})
        return reverse('local:committee-member-list')

    def form_valid(self, form):
        """Display success message on form validation"""
        messages.success(self.request, f"Member '{form.instance.user.username}' added to committee '{form.instance.committee.name}' successfully.")
        return super().form_valid(form)


class CommitteeMemberUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View for updating an existing CommitteeMember object"""
    model = CommitteeMember
    form_class = CommitteeMemberForm
    template_name = 'local/committee_member_form.html'

    def test_func(self):
        """Check if user has permission to edit CommitteeMember objects"""
        return self.request.user.is_superuser

    def get_success_url(self):
        """Redirect to the committee detail page after successful update"""
        return reverse('local:committee-detail', kwargs={'pk': self.object.committee.pk})

    def form_valid(self, form):
        """Display success message on form validation"""
        messages.success(self.request, f"Committee member '{form.instance.user.username}' updated successfully.")
        return super().form_valid(form)


class CommitteeMemberDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """View for deleting a CommitteeMember object"""
    model = CommitteeMember
    template_name = 'local/committee_member_confirm_delete.html'
    success_url = reverse_lazy('local:committee-member-list')

    def test_func(self):
        """Check if user has permission to delete CommitteeMember objects"""
        return self.request.user.is_superuser

    def delete(self, request, *args, **kwargs):
        """Display success message on deletion"""
        member_obj = self.get_object()
        messages.success(request, f"Member '{member_obj.user.username}' removed from committee '{member_obj.committee.name}' successfully.")
        return super().delete(request, *args, **kwargs)


class SessionAttachmentView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View for uploading attachments to sessions"""
    model = SessionAttachment
    form_class = SessionAttachmentForm
    template_name = 'local/session_attachment_form.html'
    
    def test_func(self):
        """Check if user has permission to upload session attachments"""
        return self.request.user.is_superuser
    
    def get_session(self):
        """Get the session from URL parameter"""
        from django.shortcuts import get_object_or_404
        return get_object_or_404(Session, pk=self.kwargs['session_pk'])
    
    def get_form_kwargs(self):
        """Pass session and user to form"""
        kwargs = super().get_form_kwargs()
        kwargs['session'] = self.get_session()
        kwargs['uploaded_by'] = self.request.user
        return kwargs
    
    def get_success_url(self):
        """Redirect to session detail page"""
        return reverse_lazy('local:session-detail', kwargs={'pk': self.get_session().pk})
    
    def get_context_data(self, **kwargs):
        """Add session to context"""
        context = super().get_context_data(**kwargs)
        context['session'] = self.get_session()
        return context
    
    def form_valid(self, form):
        """Display success message on form validation"""
        messages.success(self.request, f"Attachment '{form.instance.filename}' uploaded successfully.")
        return super().form_valid(form)


class SessionInvitationUploadView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    """View for uploading invitation PDF and setting session status to invited."""
    form_class = SessionInvitationForm
    template_name = 'local/session_invitation_form.html'

    def test_func(self):
        return self.request.user.is_superuser

    def get_session(self):
        return get_object_or_404(Session, pk=self.kwargs['session_pk'])

    def dispatch(self, request, *args, **kwargs):
        session = self.get_session()
        if session.status != 'scheduled':
            messages.error(request, _("Invitation can only be added when the session is scheduled."))
            return redirect('local:session-detail', pk=session.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('local:session-detail', kwargs={'pk': self.get_session().pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['session'] = self.get_session()
        return context

    def form_valid(self, form):
        import os
        session = self.get_session()
        file = form.cleaned_data['file']
        description = form.cleaned_data.get('description') or ''
        attachment = SessionAttachment(
            session=session,
            file=file,
            file_type='invitation',
            filename=os.path.basename(file.name),
            description=description,
            uploaded_by=self.request.user,
        )
        attachment.save()
        session.status = 'invited'
        session.save(update_fields=['status'])
        messages.success(self.request, _("Invitation uploaded and session status set to Invited."))
        return redirect(self.get_success_url())


class SessionCancelView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View to confirm and cancel a session (set status to cancelled)."""
    model = Session
    context_object_name = 'session'
    template_name = 'local/session_cancel_confirm.html'

    def test_func(self):
        return self.request.user.is_superuser

    def dispatch(self, request, *args, **kwargs):
        session = self.get_object()
        if session.status not in ('scheduled', 'invited'):
            messages.error(request, _("Only scheduled or invited sessions can be cancelled."))
            return redirect('local:session-detail', pk=session.pk)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        session = self.get_object()
        session.status = 'cancelled'
        session.save(update_fields=['status'])
        messages.success(request, _("Session has been cancelled."))
        return redirect('local:session-detail', pk=session.pk)


class SessionMinutesUpdateView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    """View for adding or editing session minutes (when status is completed)."""
    form_class = SessionMinutesForm
    template_name = 'local/session_minutes_form.html'

    def test_func(self):
        return self.request.user.is_superuser

    def get_session(self):
        return get_object_or_404(Session, pk=self.kwargs['session_pk'])

    def dispatch(self, request, *args, **kwargs):
        session = self.get_session()
        if session.status != 'completed':
            messages.error(request, _("Minutes can only be added for completed sessions."))
            return redirect('local:session-detail', pk=session.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        return {'minutes': self.get_session().minutes}

    def get_success_url(self):
        return reverse('local:session-detail', kwargs={'pk': self.get_session().pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['session'] = self.get_session()
        return context

    def form_valid(self, form):
        session = self.get_session()
        session.minutes = form.cleaned_data.get('minutes') or ''
        session.save(update_fields=['minutes'])
        messages.success(self.request, _("Minutes saved successfully."))
        return redirect(self.get_success_url())


class CommitteeMeetingAttachmentView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View for uploading attachments to committee meetings"""
    model = CommitteeMeetingAttachment
    form_class = CommitteeMeetingAttachmentForm
    template_name = 'local/committee_meeting_attachment_form.html'

    def test_func(self):
        """Check if user has permission to upload committee meeting attachments"""
        return self.request.user.is_superuser

    def get_committee_meeting(self):
        """Get the committee meeting from URL parameter"""
        from django.shortcuts import get_object_or_404
        return get_object_or_404(CommitteeMeeting, pk=self.kwargs['committee_meeting_pk'])

    def get_form_kwargs(self):
        """Pass committee_meeting and user to form"""
        kwargs = super().get_form_kwargs()
        kwargs['committee_meeting'] = self.get_committee_meeting()
        kwargs['uploaded_by'] = self.request.user
        return kwargs

    def get_success_url(self):
        """Redirect to committee meeting detail page"""
        return reverse_lazy(
            'local:committee-meeting-detail',
            kwargs={'pk': self.get_committee_meeting().pk}
        )

    def get_context_data(self, **kwargs):
        """Add meeting to context"""
        context = super().get_context_data(**kwargs)
        context['meeting'] = self.get_committee_meeting()
        return context

    def form_valid(self, form):
        """Display success message on form validation"""
        messages.success(
            self.request,
            f"Attachment '{form.instance.filename}' uploaded successfully."
        )
        return super().form_valid(form)
