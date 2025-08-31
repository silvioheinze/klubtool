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

from .models import Motion, MotionVote, MotionComment, MotionAttachment, MotionStatus, MotionGroupDecision
from .forms import MotionForm, MotionFilterForm, MotionVoteForm, MotionCommentForm, MotionAttachmentForm, MotionStatusForm, MotionGroupDecisionForm
from user.models import CustomUser
from local.models import Session, Party
from group.models import Group


def is_superuser_or_has_permission(permission):
    """Decorator to check if user is superuser or has specific permission"""
    def check_permission(user):
        return user.is_superuser or user.has_role_permission(permission)
    return check_permission


def is_leader_or_deputy_leader(user, motion):
    """Check if user is a leader or deputy leader of the motion's group"""
    if user.is_superuser:
        return True
    
    if not motion.group:
        return False
    
    # Check if user is a member of the motion's group with leader or deputy leader role
    from group.models import GroupMember
    from user.models import Role
    
    try:
        # Get leader and deputy leader roles
        leader_role = Role.objects.get(name='Leader')
        deputy_leader_role = Role.objects.get(name='Deputy Leader')
        
        # Check if user has these roles in the motion's group
        membership = GroupMember.objects.filter(
            user=user,
            group=motion.group,
            is_active=True,
            roles__in=[leader_role, deputy_leader_role]
        ).first()
        
        return membership is not None
    except Role.DoesNotExist:
        return False


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
        
        # Add status change form
        context['status_form'] = MotionStatusForm(motion=motion, changed_by=self.request.user)
        
        # Add group decision form
        context['group_decision_form'] = MotionGroupDecisionForm(motion=motion, created_by=self.request.user)
        
        # Add permission checks for group decisions
        context['can_add_group_decision'] = self.request.user.is_superuser or is_leader_or_deputy_leader(self.request.user, motion)
        context['can_delete_group_decision'] = self.request.user.is_superuser or is_leader_or_deputy_leader(self.request.user, motion)
        
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
        
        # Get status history
        context['status_history'] = motion.status_history.all()
        
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
@user_passes_test(is_superuser_or_has_permission('motion.edit'))
def motion_status_change_view(request, pk):
    """View for changing motion status"""
    motion = get_object_or_404(Motion, pk=pk)
    
    if request.method == 'POST':
        form = MotionStatusForm(request.POST, motion=motion, changed_by=request.user)
        if form.is_valid():
            # Get the new status
            new_status = form.cleaned_data['status']
            reason = form.cleaned_data['reason']
            committee = form.cleaned_data.get('committee')
            
            # Set attributes for the save method to use
            motion._status_changed_by = request.user
            motion._status_change_reason = reason
            motion._status_committee = committee
            
            # Update the motion status
            motion.status = new_status
            
            # If status is 'refer_to_committee', also update the motion's committee
            if new_status == 'refer_to_committee' and committee:
                motion.committee = committee
            
            # Save the motion (this will trigger the save method which creates the status history entry)
            motion.save()
            
            messages.success(request, f"Motion status changed to '{motion.get_status_display()}' successfully.")
            return redirect('motion:motion-detail', pk=pk)
    else:
        form = MotionStatusForm(motion=motion, changed_by=request.user)
    
    return render(request, 'motion/motion_status_change.html', {
        'motion': motion,
        'form': form
    })


@login_required
@user_passes_test(lambda u: u.is_superuser)
def motion_status_delete_view(request, motion_pk, status_pk):
    """View for deleting a motion status entry (superuser only)"""
    motion = get_object_or_404(Motion, pk=motion_pk)
    status_entry = get_object_or_404(MotionStatus, pk=status_pk, motion=motion)
    
    if request.method == 'POST':
        status_entry.delete()
        messages.success(request, f"Status entry '{status_entry.get_status_display()}' deleted successfully.")
        return redirect('motion:motion-detail', pk=motion_pk)
    
    return render(request, 'motion/motion_status_confirm_delete.html', {
        'motion': motion,
        'status_entry': status_entry
    })


@login_required
def motion_group_decision_view(request, pk):
    """View for creating group decisions on motions"""
    motion = get_object_or_404(Motion, pk=pk)
    
    # Check if user has permission (superuser, leader, or deputy leader)
    if not (request.user.is_superuser or is_leader_or_deputy_leader(request.user, motion)):
        messages.error(request, "You don't have permission to add group decisions.")
        return redirect('motion:motion-detail', pk=pk)
    
    if request.method == 'POST':
        form = MotionGroupDecisionForm(request.POST, motion=motion, created_by=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f"Group decision '{form.instance.get_decision_display()}' added successfully.")
            return redirect('motion:motion-detail', pk=pk)
    else:
        form = MotionGroupDecisionForm(motion=motion, created_by=request.user)
    
    return render(request, 'motion/motion_group_decision.html', {
        'motion': motion,
        'form': form
    })


@login_required
def motion_group_decision_delete_view(request, motion_pk, decision_pk):
    """View for deleting a motion group decision entry (superuser, leader, or deputy leader only)"""
    motion = get_object_or_404(Motion, pk=motion_pk)
    decision_entry = get_object_or_404(MotionGroupDecision, pk=decision_pk, motion=motion)
    
    # Check if user has permission (superuser, leader, or deputy leader)
    if not (request.user.is_superuser or is_leader_or_deputy_leader(request.user, motion)):
        messages.error(request, "You don't have permission to delete group decisions.")
        return redirect('motion:motion-detail', pk=motion_pk)
    
    if request.method == 'POST':
        decision_entry.delete()
        messages.success(request, f"Group decision '{decision_entry.get_decision_display()}' deleted successfully.")
        return redirect('motion:motion-detail', pk=motion_pk)
    
    return render(request, 'motion/motion_group_decision_confirm_delete.html', {
        'motion': motion,
        'decision_entry': decision_entry
    })


class MotionExportPDFView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View for exporting motion information as PDF"""
    model = Motion
    context_object_name = 'motion'
    template_name = 'motion/motion_export_pdf.html'

    def test_func(self):
        """Check if user has permission to export Motion objects"""
        return self.request.user.is_superuser or self.request.user.has_role_permission('motion.view')

    def get_context_data(self, **kwargs):
        """Add additional context data"""
        context = super().get_context_data(**kwargs)
        # Get votes for this motion
        context['votes'] = self.object.votes.all().select_related('voter').order_by('voter__first_name')
        context['vote_stats'] = {
            'yes': self.object.votes.filter(vote='yes').count(),
            'no': self.object.votes.filter(vote='no').count(),
            'abstain': self.object.votes.filter(vote='abstain').count(),
            'absent': self.object.votes.filter(vote='absent').count(),
            'total': self.object.votes.count(),
        }
        # Get comments for this motion
        context['comments'] = self.object.comments.filter(is_public=True).select_related('author').order_by('created_at')
        # Get attachments for this motion
        context['attachments'] = self.object.attachments.all().order_by('uploaded_at')
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
            .motion-info { margin-bottom: 30px; }
            .motion-text { margin-bottom: 20px; padding: 15px; border: 1px solid #ddd; background-color: #f9f9f9; }
            .votes-table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            .votes-table th, .votes-table td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            .votes-table th { background-color: #f2f2f2; }
            .vote-badge { padding: 4px 8px; border-radius: 4px; font-size: 12px; }
            .vote-yes { background-color: #28a745; color: white; }
            .vote-no { background-color: #dc3545; color: white; }
            .vote-abstain { background-color: #ffc107; color: black; }
            .vote-absent { background-color: #6c757d; color: white; }
            .comments-section { margin-top: 20px; }
            .comment { margin-bottom: 15px; padding: 10px; border: 1px solid #ddd; background-color: #f9f9f9; }
            .attachments-section { margin-top: 20px; }
            .attachment { margin-bottom: 10px; padding: 8px; border: 1px solid #ddd; }
        ''')
        
        # Generate PDF
        pdf = html.write_pdf(stylesheets=[css])
        
        # Create response
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="motion_{self.object.pk}_{self.object.title.replace(" ", "_")}.pdf"'
        
        return response
