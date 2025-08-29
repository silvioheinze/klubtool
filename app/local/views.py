from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.db.models import Q
from django.shortcuts import render, redirect
from django.utils import timezone

from .models import Local, Term, Council, TermSeatDistribution, Party
from .forms import LocalForm, LocalFilterForm, CouncilForm, CouncilFilterForm, TermForm, TermFilterForm, CouncilNameForm, TermSeatDistributionForm, TermSeatDistributionFilterForm


class LocalListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """View for listing all Local objects"""
    model = Local
    context_object_name = 'locals'
    template_name = 'local/local_list.html'
    paginate_by = 20

    def test_func(self):
        """Check if user has permission to view Local objects"""
        return self.request.user.is_superuser or self.request.user.has_role_permission('local.view')

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
        return self.request.user.is_superuser or self.request.user.has_role_permission('local.view')

    def get_context_data(self, **kwargs):
        """Add terms data to context"""
        context = super().get_context_data(**kwargs)
        context['terms'] = Term.objects.filter(is_active=True).order_by('-start_date')
        return context


class LocalCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View for creating a new Local object"""
    model = Local
    form_class = LocalForm
    template_name = 'local/local_form.html'
    success_url = reverse_lazy('local:local-list')

    def test_func(self):
        """Check if user has permission to create Local objects"""
        return self.request.user.is_superuser or self.request.user.has_role_permission('local.create')

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
        return self.request.user.is_superuser or self.request.user.has_role_permission('local.edit')

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
        return self.request.user.is_superuser or self.request.user.has_role_permission('local.delete')

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
        return self.request.user.is_superuser or self.request.user.has_role_permission('council.edit')

    def form_valid(self, form):
        """Display success message and redirect back to local detail"""
        messages.success(self.request, f"Council name updated to '{form.instance.name}'.")
        return redirect('local:local-detail', pk=form.instance.local.pk)

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
        return self.request.user.is_superuser or self.request.user.has_role_permission('council.view')

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
        return self.request.user.is_superuser or self.request.user.has_role_permission('council.view')


class CouncilCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View for creating a new Council object"""
    model = Council
    form_class = CouncilForm
    template_name = 'local/council_form.html'
    success_url = reverse_lazy('local:council-list')

    def test_func(self):
        """Check if user has permission to create Council objects"""
        return self.request.user.is_superuser or self.request.user.has_role_permission('council.create')

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
        return self.request.user.is_superuser or self.request.user.has_role_permission('council.edit')

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
        return self.request.user.is_superuser or self.request.user.has_role_permission('council.delete')

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
        return self.request.user.is_superuser or self.request.user.has_role_permission('term.view')

    def get_queryset(self):
        """Filter queryset based on search parameters"""
        queryset = Term.objects.all().order_by('-start_date')
        
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
        return context


class TermDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View for displaying a single Term object"""
    model = Term
    context_object_name = 'term'
    template_name = 'local/term_detail.html'

    def test_func(self):
        """Check if user has permission to view Term objects"""
        return self.request.user.is_superuser or self.request.user.has_role_permission('term.view')


class TermCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View for creating a new Term object"""
    model = Term
    form_class = TermForm
    template_name = 'local/term_form.html'
    success_url = reverse_lazy('local:term-list')

    def test_func(self):
        """Check if user has permission to create Term objects"""
        return self.request.user.is_superuser or self.request.user.has_role_permission('term.create')

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
        return self.request.user.is_superuser or self.request.user.has_role_permission('term.edit')

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
        return self.request.user.is_superuser or self.request.user.has_role_permission('term.delete')

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
        return self.request.user.is_superuser or self.request.user.has_role_permission('termseatdistribution.view')

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
        return self.request.user.is_superuser or self.request.user.has_role_permission('termseatdistribution.view')


class TermSeatDistributionCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View for creating a new TermSeatDistribution object"""
    model = TermSeatDistribution
    form_class = TermSeatDistributionForm
    template_name = 'local/term_seat_distribution_form.html'
    success_url = reverse_lazy('local:term-seat-distribution-list')

    def test_func(self):
        """Check if user has permission to create TermSeatDistribution objects"""
        return self.request.user.is_superuser or self.request.user.has_role_permission('termseatdistribution.create')

    def get_initial(self):
        """Set initial term if provided in URL"""
        initial = super().get_initial()
        term_id = self.request.GET.get('term')
        if term_id:
            try:
                term = Term.objects.get(pk=term_id)
                initial['term'] = term
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
        return self.request.user.is_superuser or self.request.user.has_role_permission('termseatdistribution.edit')

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
        return self.request.user.is_superuser or self.request.user.has_role_permission('termseatdistribution.delete')

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
        return self.request.user.is_superuser or self.request.user.has_role_permission('term.view')

    def get_context_data(self, **kwargs):
        """Add seat distributions to context"""
        context = super().get_context_data(**kwargs)
        context['seat_distributions'] = self.object.seat_distributions.select_related('party').all().order_by('-seats')
        context['parties'] = Party.objects.filter(is_active=True)
        return context
