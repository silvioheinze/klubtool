from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse, HttpResponseRedirect
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.utils import timezone

from .models import Motion, MotionVote, MotionComment, MotionAttachment
from .forms import MotionForm, MotionFilterForm, MotionVoteForm, MotionCommentForm, MotionAttachmentForm
from user.models import CustomUser
from local.models import Session, Party
from group.models import Group


def is_superuser_or_has_permission(permission):
    """Decorator to check if user is superuser or has specific permission"""
    def check_permission(user):
        return user.is_superuser or user.has_role_permission(permission)
    return check_permission


class MotionListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """View for listing all Motion objects"""
    model = Motion
    context_object_name = 'motions'
    template_name = 'motion/motion_list.html'
    paginate_by = 20

    def test_func(self):
        """Check if user has permission to view Motion objects"""
        return self.request.user.is_superuser or self.request.user.has_role_permission('motion.view')

    def get_queryset(self):
        """Filter queryset based on search parameters"""
        queryset = Motion.objects.all().select_related(
            'session', 'group', 'submitted_by'
        ).prefetch_related('parties').order_by('-submitted_date')
        
        # Get filter form
        filter_form = MotionFilterForm(self.request.GET)
        
        if filter_form.is_valid():
            # Filter by search query
            search_query = filter_form.cleaned_data.get('search')
            if search_query:
                queryset = queryset.filter(
                    Q(title__icontains=search_query) |
                    Q(text__icontains=search_query) |
                    Q(rationale__icontains=search_query) |
                    Q(group__name__icontains=search_query)
                )
            
            # Filter by motion type
            motion_type = filter_form.cleaned_data.get('motion_type')
            if motion_type:
                queryset = queryset.filter(motion_type=motion_type)
            
            # Filter by status
            status = filter_form.cleaned_data.get('status')
            if status:
                queryset = queryset.filter(status=status)
            

            
            # Filter by session
            session = filter_form.cleaned_data.get('session')
            if session:
                queryset = queryset.filter(session=session)
            
            # Filter by group
            group = filter_form.cleaned_data.get('group')
            if group:
                queryset = queryset.filter(group=group)
            
            # Filter by party
            party = filter_form.cleaned_data.get('party')
            if party:
                queryset = queryset.filter(parties=party)
        
        return queryset

    def get_context_data(self, **kwargs):
        """Add filter form to context"""
        context = super().get_context_data(**kwargs)
        context['filter_form'] = MotionFilterForm(self.request.GET)
        return context


class MotionDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View for displaying a single Motion object"""
    model = Motion
    context_object_name = 'motion'
    template_name = 'motion/motion_detail.html'

    def test_func(self):
        """Check if user has permission to view Motion objects"""
        return self.request.user.is_superuser or self.request.user.has_role_permission('motion.view')

    def get_context_data(self, **kwargs):
        """Add additional context data"""
        context = super().get_context_data(**kwargs)
        motion = self.object
        
        # Add vote form
        context['vote_form'] = MotionVoteForm(motion=motion, voter=self.request.user)
        
        # Add comment form
        context['comment_form'] = MotionCommentForm(motion=motion, author=self.request.user)
        
        # Add attachment form
        context['attachment_form'] = MotionAttachmentForm(motion=motion, uploaded_by=self.request.user)
        
        # Get user's existing vote
        context['user_vote'] = motion.votes.filter(voter=self.request.user).first()
        
        # Get vote statistics
        votes = motion.votes.all()
        context['vote_stats'] = {
            'yes': votes.filter(vote='yes').count(),
            'no': votes.filter(vote='no').count(),
            'abstain': votes.filter(vote='abstain').count(),
            'absent': votes.filter(vote='absent').count(),
            'total': votes.count(),
        }
        
        # Get comments (public only for non-authors)
        if self.request.user.is_superuser or motion.submitted_by == self.request.user:
            context['comments'] = motion.comments.all()
        else:
            context['comments'] = motion.comments.filter(is_public=True)
        
        # Get attachments
        context['attachments'] = motion.attachments.all()
        
        return context


class MotionCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View for creating a new Motion object"""
    model = Motion
    form_class = MotionForm
    template_name = 'motion/motion_form.html'
    success_url = reverse_lazy('motion:motion-list')

    def test_func(self):
        """Check if user has permission to create Motion objects"""
        return self.request.user.is_superuser or self.request.user.has_role_permission('motion.create')

    def get_form_kwargs(self):
        """Pass user to form for automatic group assignment"""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_initial(self):
        """Set initial values based on URL parameters"""
        initial = super().get_initial()
        session_id = self.request.GET.get('session')
        if session_id:
            try:
                session = Session.objects.get(pk=session_id)
                initial['session'] = session.pk
            except Session.DoesNotExist:
                pass
        return initial

    def form_valid(self, form):
        """Set submitted_by and display success message"""
        form.instance.submitted_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, f"Motion '{form.instance.title}' created successfully.")
        return response


class MotionUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View for updating an existing Motion object"""
    model = Motion
    form_class = MotionForm
    template_name = 'motion/motion_form.html'
    success_url = reverse_lazy('motion:motion-list')

    def test_func(self):
        """Check if user has permission to edit Motion objects"""
        return self.request.user.is_superuser or self.request.user.has_role_permission('motion.edit')

    def get_form_kwargs(self):
        """Pass user to form for automatic group assignment"""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        """Display success message on form validation"""
        response = super().form_valid(form)
        messages.success(self.request, f"Motion '{form.instance.title}' updated successfully.")
        return response


class MotionDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """View for deleting a Motion object"""
    model = Motion
    template_name = 'motion/motion_confirm_delete.html'
    success_url = reverse_lazy('motion:motion-list')

    def test_func(self):
        """Check if user has permission to delete Motion objects"""
        return self.request.user.is_superuser or self.request.user.has_role_permission('motion.delete')

    def delete(self, request, *args, **kwargs):
        """Display success message on deletion"""
        motion_obj = self.get_object()
        messages.success(request, f"Motion '{motion_obj.title}' deleted successfully.")
        return super().delete(request, *args, **kwargs)


@login_required
@user_passes_test(is_superuser_or_has_permission('motion.vote'))
def motion_vote_view(request, pk):
    """View for voting on a motion"""
    motion = get_object_or_404(Motion, pk=pk)
    
    if request.method == 'POST':
        form = MotionVoteForm(request.POST, motion=motion, voter=request.user)
        if form.is_valid():
            # Check if user already voted
            existing_vote = MotionVote.objects.filter(motion=motion, voter=request.user).first()
            if existing_vote:
                # Update existing vote
                existing_vote.vote = form.cleaned_data['vote']
                existing_vote.reason = form.cleaned_data['reason']
                existing_vote.save()
                messages.success(request, "Your vote has been updated.")
            else:
                # Create new vote
                form.save()
                messages.success(request, "Your vote has been recorded.")
            
            return redirect('motion:motion-detail', pk=pk)
    else:
        form = MotionVoteForm(motion=motion, voter=request.user)
    
    return render(request, 'motion/motion_vote.html', {
        'motion': motion,
        'form': form
    })


@login_required
@user_passes_test(is_superuser_or_has_permission('motion.comment'))
def motion_comment_view(request, pk):
    """View for adding comments to a motion"""
    motion = get_object_or_404(Motion, pk=pk)
    
    if request.method == 'POST':
        form = MotionCommentForm(request.POST, motion=motion, author=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your comment has been added.")
            return redirect('motion:motion-detail', pk=pk)
    else:
        form = MotionCommentForm(motion=motion, author=request.user)
    
    return render(request, 'motion/motion_comment.html', {
        'motion': motion,
        'form': form
    })


@login_required
@user_passes_test(is_superuser_or_has_permission('motion.attach'))
def motion_attachment_view(request, pk):
    """View for uploading attachments to a motion"""
    motion = get_object_or_404(Motion, pk=pk)
    
    if request.method == 'POST':
        form = MotionAttachmentForm(request.POST, request.FILES, motion=motion, uploaded_by=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Attachment uploaded successfully.")
            return redirect('motion:motion-detail', pk=pk)
    else:
        form = MotionAttachmentForm(motion=motion, uploaded_by=request.user)
    
    return render(request, 'motion/motion_attachment.html', {
        'motion': motion,
        'form': form
    })


@login_required
@user_passes_test(is_superuser_or_has_permission('motion.view'))
def motion_dashboard_view(request):
    """Dashboard view for motion management"""
    # Get motion statistics
    total_motions = Motion.objects.count()
    draft_motions = Motion.objects.filter(status='draft').count()
    submitted_motions = Motion.objects.filter(status='submitted').count()
    approved_motions = Motion.objects.filter(status='approved').count()
    rejected_motions = Motion.objects.filter(status='rejected').count()
    
    # Get recent motions
    recent_motions = Motion.objects.select_related('session', 'group', 'submitted_by').order_by('-submitted_date')[:5]
    
    # Get motions by type
    motions_by_type = Motion.objects.values('motion_type').annotate(count=Count('id')).order_by('-count')
    
    # Get motions by status
    motions_by_status = Motion.objects.values('status').annotate(count=Count('id')).order_by('-count')
    
    # Get urgent motions
    urgent_motions = Motion.objects.filter(priority='urgent').select_related('session', 'group')[:5]
    
    context = {
        'total_motions': total_motions,
        'draft_motions': draft_motions,
        'submitted_motions': submitted_motions,
        'approved_motions': approved_motions,
        'rejected_motions': rejected_motions,
        'recent_motions': recent_motions,
        'motions_by_type': motions_by_type,
        'motions_by_status': motions_by_status,
        'urgent_motions': urgent_motions,
    }
    
    return render(request, 'motion/motion_dashboard.html', context)
