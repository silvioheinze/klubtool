from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.db.models import Q
from django.shortcuts import render, redirect
from django.utils import timezone

from .models import Local, Term, Council, TermSeatDistribution, Party, Session, Committee, CommitteeMember, SessionAttachment
from .forms import LocalForm, LocalFilterForm, CouncilForm, CouncilFilterForm, TermForm, TermFilterForm, CouncilNameForm, TermSeatDistributionForm, PartyForm, PartyFilterForm, SessionForm, SessionFilterForm, CommitteeForm, CommitteeFilterForm, CommitteeMemberForm, CommitteeMemberFilterForm, SessionAttachmentForm


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
        """Check if user has permission to view Local objects"""
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        """Add terms, parties, and sessions data to context"""
        context = super().get_context_data(**kwargs)
        
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


class CouncilDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View for displaying a single Council object"""
    model = Council
    context_object_name = 'council'
    template_name = 'local/council_detail.html'

    def test_func(self):
        """Check if user has permission to view Council objects"""
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        """Add sessions and committees data to context"""
        context = super().get_context_data(**kwargs)
        # Get sessions for this council
        context['sessions'] = self.object.sessions.filter(is_active=True).order_by('-scheduled_date')[:10]
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
class SessionListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """View for listing Session objects"""
    model = Session
    context_object_name = 'sessions'
    template_name = 'local/session_list.html'
    paginate_by = 20

    def test_func(self):
        """Check if user has permission to view Session objects"""
        return self.request.user.is_superuser

    def get_queryset(self):
        """Filter sessions based on search and filter parameters"""
        queryset = Session.objects.select_related('council', 'council__local', 'term').all()
        
        # Search by title
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(council__name__icontains=search_query) |
                Q(council__local__name__icontains=search_query)
            )
        
        # Filter by council
        council_filter = self.request.GET.get('council', '')
        if council_filter:
            queryset = queryset.filter(council_id=council_filter)
        
        # Filter by status
        status_filter = self.request.GET.get('status', '')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by session type
        session_type_filter = self.request.GET.get('session_type', '')
        if session_type_filter:
            queryset = queryset.filter(session_type=session_type_filter)
        
        return queryset

    def get_context_data(self, **kwargs):
        """Add filter form to context"""
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['council_filter'] = self.request.GET.get('council', '')
        context['status_filter'] = self.request.GET.get('status', '')
        context['session_type_filter'] = self.request.GET.get('session_type', '')
        context['councils'] = Council.objects.filter(is_active=True)
        return context


class SessionDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View for displaying a single Session object"""
    model = Session
    context_object_name = 'session'
    template_name = 'local/session_detail.html'

    def test_func(self):
        """Check if user has permission to view Session objects"""
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        """Add motions data to context"""
        context = super().get_context_data(**kwargs)
        # Get motions for this session
        context['motions'] = self.object.motions.filter(is_active=True).order_by('-submitted_date')[:10]
        context['total_motions'] = self.object.motions.count()
        return context


class SessionCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View for creating a new Session object"""
    model = Session
    form_class = SessionForm
    template_name = 'local/session_form.html'
    success_url = reverse_lazy('local:session-list')

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

    def form_valid(self, form):
        """Display success message on form validation"""
        messages.success(self.request, f"Session '{form.instance.title}' created successfully.")
        return super().form_valid(form)


class SessionUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View for updating an existing Session object"""
    model = Session
    form_class = SessionForm
    template_name = 'local/session_form.html'
    success_url = reverse_lazy('local:session-list')

    def test_func(self):
        """Check if user has permission to edit Session objects"""
        return self.request.user.is_superuser

    def form_valid(self, form):
        """Display success message on form validation"""
        messages.success(self.request, f"Session '{form.instance.title}' updated successfully.")
        return super().form_valid(form)


class SessionDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """View for deleting a Session object"""
    model = Session
    template_name = 'local/session_confirm_delete.html'
    success_url = reverse_lazy('local:session-list')

    def test_func(self):
        """Check if user has permission to delete Session objects"""
        return self.request.user.is_superuser

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
        """Check if user has permission to export Session objects"""
        return self.request.user.is_superuser or self.request.user.has_role_permission('session.view')

    def get_context_data(self, **kwargs):
        """Add motions data to context"""
        context = super().get_context_data(**kwargs)
        # Get all motions for this session
        context['motions'] = self.object.motions.filter(is_active=True).order_by('-submitted_date')
        context['total_motions'] = self.object.motions.count()
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
            body { font-family: Arial, sans-serif; margin: 20px; }
            .header { text-align: center; margin-bottom: 30px; }
            .session-info { margin-bottom: 30px; }
            .motions-table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            .motions-table th, .motions-table td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            .motions-table th { background-color: #f2f2f2; }
            .status-badge { padding: 4px 8px; border-radius: 4px; font-size: 12px; }
            .status-draft { background-color: #6c757d; color: white; }
            .status-submitted { background-color: #007bff; color: white; }
            .status-approved { background-color: #28a745; color: white; }
            .status-rejected { background-color: #dc3545; color: white; }
            .status-withdrawn { background-color: #ffc107; color: black; }
        ''')
        
        # Generate PDF
        pdf = html.write_pdf(stylesheets=[css])
        
        # Create response
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="session_{self.object.pk}_{self.object.title.replace(" ", "_")}.pdf"'
        
        return response


# Committee Views
class CommitteeListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """View for listing all Committee objects"""
    model = Committee
    context_object_name = 'committees'
    template_name = 'local/committee_list.html'
    paginate_by = 20

    def test_func(self):
        """Check if user has permission to view Committee objects"""
        return self.request.user.is_superuser

    def get_queryset(self):
        """Filter queryset based on search parameters"""
        queryset = Committee.objects.all().select_related('council', 'council__local').order_by('name')
        
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
        """Check if user has permission to view Committee objects"""
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        """Add committee members and motions data to context"""
        from django.db.models import Case, When, CharField, Value
        
        context = super().get_context_data(**kwargs)
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


class CommitteeMemberDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View for displaying a single CommitteeMember object"""
    model = CommitteeMember
    context_object_name = 'member'
    template_name = 'local/committee_member_detail.html'

    def test_func(self):
        """Check if user has permission to view CommitteeMember objects"""
        return self.request.user.is_superuser


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
