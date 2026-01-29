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
from django.utils.translation import gettext_lazy as _

from .models import Motion, MotionVote, MotionComment, MotionAttachment, MotionStatus, MotionGroupDecision, Question, QuestionStatus, QuestionAttachment
from .forms import MotionForm, MotionFilterForm, MotionVoteForm, MotionVoteFormSetFactory, MotionVoteTypeForm, MotionCommentForm, MotionAttachmentForm, MotionStatusForm, MotionGroupDecisionForm, QuestionForm, QuestionFilterForm, QuestionStatusForm, QuestionAttachmentForm
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


def can_change_question_status(user, question):
    """Check if user can change question status (superuser, group admin, leader, or deputy leader)"""
    if user.is_superuser:
        return True
    
    if not question.group:
        return False
    
    # Check if user is a group admin
    if question.group.has_group_admin(user):
        return True
    
    # Check if user is a leader or deputy leader
    from group.models import GroupMember
    from user.models import Role
    
    try:
        leader_role = Role.objects.get(name='Leader')
        deputy_leader_role = Role.objects.get(name='Deputy Leader')
        
        membership = GroupMember.objects.filter(
            user=user,
            group=question.group,
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
        ).prefetch_related('parties', 'tags').order_by('-submitted_date')
        
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
            
            # Filter by tags
            tags = filter_form.cleaned_data.get('tags')
            if tags:
                queryset = queryset.filter(tags__in=tags).distinct()
        
        return queryset

    def get_context_data(self, **kwargs):
        """Add filter form to context"""
        context = super().get_context_data(**kwargs)
        context['filter_form'] = MotionFilterForm(self.request.GET)
        
        # Get tag counts for word cloud (from all motions, not just filtered)
        from .models import Tag
        from django.db.models import Count
        # Get all tags used in motions, with their counts
        tag_counts = Tag.objects.filter(
            motions__isnull=False,
            is_active=True
        ).annotate(
            count=Count('motions', distinct=True)
        ).order_by('-count', 'name')
        context['tag_counts'] = tag_counts
        
        # Get currently selected tags from GET parameters
        selected_tag_ids = []
        if 'tags' in self.request.GET:
            try:
                selected_tag_ids = [int(tid) for tid in self.request.GET.getlist('tags')]
            except (ValueError, TypeError):
                pass
        context['selected_tag_ids'] = selected_tag_ids
        
        # Add user to context for permission checks in template
        context['user'] = self.request.user
        
        return context


class MotionDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View for displaying a single Motion object"""
    model = Motion
    context_object_name = 'motion'
    template_name = 'motion/motion_detail.html'

    def test_func(self):
        """Check if user has permission to view Motion objects"""
        return self.request.user.is_superuser or self.request.user.has_role_permission('motion.view')
    
    def get_queryset(self):
        """Prefetch related objects for better performance"""
        return Motion.objects.prefetch_related('interventions', 'parties', 'group_decisions')

    def get_context_data(self, **kwargs):
        """Add additional context data"""
        context = super().get_context_data(**kwargs)
        motion = self.object
        
        # Add vote formset
        parties = Party.objects.filter(
            local=motion.session.council.local,
            is_active=True
        )
        context['vote_formset'] = MotionVoteFormSetFactory(
            motion=motion,
            initial=[{'party': party.pk} for party in parties]
        )
        
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
        
        # Add permission check for vote deletion
        context['can_delete_votes'] = self.request.user.is_superuser or self.request.user.has_role_permission('motion.vote')
        
        # Add permission check for status changes
        context['can_change_status'] = self.request.user.is_superuser or self.request.user.has_role_permission('motion.edit')
        
        # Always determine action buttons from the last non-deleted status in history
        last_non_deleted = motion.status_history.exclude(status='deleted').order_by('-changed_at').first()
        context['status_for_buttons'] = last_non_deleted.status if last_non_deleted else motion.status
        
        # Get all votes for this motion
        votes = motion.votes.all().select_related('party', 'status', 'vote_session').order_by('-voted_at', 'party__name')
        
        # Get term and seat distributions for displaying max seats
        from local.models import Term, TermSeatDistribution
        from django.utils.translation import gettext_lazy as _
        session = motion.session
        term = session.term
        if not term and session.council and session.council.local:
            today = timezone.now().date()
            term = Term.objects.filter(
                start_date__lte=today,
                end_date__gte=today,
                is_active=True
            ).first()

        party_seat_map = {}
        if term:
            seat_distributions = TermSeatDistribution.objects.filter(
                term=term,
                party__local=session.council.local,
                party__is_active=True
            ).select_related('party')
            party_seat_map = {dist.party.pk: dist.seats for dist in seat_distributions}

        context['term'] = term
        context['party_seat_map'] = party_seat_map
        
        # Group votes by vote_type and vote_name
        vote_rounds = {}
        vote_overview_list = []
        
        for vote in votes:
            # Create a key for grouping: vote_type and vote_name combination
            round_key = f"{vote.vote_type}_{vote.vote_name or 'default'}"
            
            if round_key not in vote_rounds:
                vote_rounds[round_key] = {
                    'round_key': round_key,
                    'vote_name': vote.vote_name or '',
                    'vote_type': vote.vote_type,
                    'vote_session': vote.vote_session,
                    'voted_at': vote.voted_at,
                    'votes': [],
                    'total_approve': 0,
                    'total_reject': 0,
                    'total_cast': 0,
                    'parties_count': 0,
                    'parties': set(),
                    'outcome': vote.outcome or '',
                }
            
            # Add max seats to vote data for template
            vote.max_seats = party_seat_map.get(vote.party.pk, 0)
            vote_rounds[round_key]['votes'].append(vote)
            vote_rounds[round_key]['total_approve'] += vote.approve_votes
            vote_rounds[round_key]['total_reject'] += vote.reject_votes
            vote_rounds[round_key]['total_cast'] += vote.total_votes_cast
            vote_rounds[round_key]['parties'].add(vote.party)
            vote_rounds[round_key]['parties_count'] = len(vote_rounds[round_key]['parties'])
        
        # Calculate outcome for each vote round and create overview list
        for round_key, round_data in vote_rounds.items():
            total_favor = round_data['total_approve']
            total_against = round_data['total_reject']
            
            # Use stored outcome if available, otherwise calculate
            if not round_data['outcome']:
                if round_data['vote_type'] == 'regular':
                    if total_favor > total_against:
                        round_data['outcome'] = 'adopted'
                        round_data['outcome_text'] = _('Motion adopted by majority')
                    elif total_against > total_favor:
                        round_data['outcome'] = 'rejected'
                        round_data['outcome_text'] = _('Motion rejected by majority')
                    else:
                        round_data['outcome'] = 'tie'
                        round_data['outcome_text'] = _('Tie - no majority')
                elif round_data['vote_type'] == 'refer_to_committee':
                    if total_favor > total_against:
                        round_data['outcome'] = 'referred'
                        round_data['outcome_text'] = _('Motion referred to committee by majority')
                    else:
                        round_data['outcome'] = 'not_referred'
                        round_data['outcome_text'] = _('Motion not referred to committee')
            else:
                # Map outcome to text
                outcome_map = {
                    'adopted': _('Motion adopted by majority'),
                    'rejected': _('Motion rejected by majority'),
                    'tie': _('Tie - no majority'),
                    'referred': _('Motion referred to committee by majority'),
                    'not_referred': _('Motion not referred to committee'),
                }
                round_data['outcome_text'] = outcome_map.get(round_data['outcome'], '')
            
            # Add to overview list (sorted by voted_at, most recent first)
            vote_overview_list.append(round_data)
        
        # Sort overview list by voted_at (most recent first)
        vote_overview_list.sort(key=lambda x: x['voted_at'], reverse=True)
        
        context['vote_rounds'] = vote_rounds
        context['vote_overview_list'] = vote_overview_list
        
        # Overall vote statistics (across all rounds)
        total_approve = sum(vote.approve_votes for vote in votes)
        total_reject = sum(vote.reject_votes for vote in votes)
        total_votes_cast = total_approve + total_reject
        
        context['vote_stats'] = {
            'approve': total_approve,
            'reject': total_reject,
            'total_cast': total_votes_cast,
            'parties_voted': len(set(vote.party for vote in votes)),
            'rounds_count': len(vote_rounds)
        }
        
        # Get comments (public only for non-authors)
        if self.request.user.is_superuser or motion.submitted_by == self.request.user:
            context['comments'] = motion.comments.all()
        else:
            context['comments'] = motion.comments.filter(is_public=True)
        
        # Get attachments
        context['attachments'] = motion.attachments.all()
        
        # Get status history with votes for vote-results popup
        context['status_history'] = motion.status_history.prefetch_related('votes', 'votes__party').all()
        
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

    def get_success_url(self):
        """Redirect to session detail page after successful motion creation"""
        if hasattr(self.object, 'session') and self.object.session:
            return reverse('local:session-detail', kwargs={'pk': self.object.session.pk})
        return super().get_success_url()

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

    def get_success_url(self):
        """Redirect to motion detail page after successful update"""
        return reverse('motion:motion-detail', kwargs={'pk': self.object.pk})

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
        motion = self.get_object()
        
        # Superusers can delete any motion
        if self.request.user.is_superuser:
            return True
        
        # Users can delete their own motions
        if motion.submitted_by == self.request.user:
            return True
        
        # Group admins can delete motions from their groups
        if motion.group and is_leader_or_deputy_leader(self.request.user, motion):
            return True
        
        return False

    def delete(self, request, *args, **kwargs):
        """Display success message on deletion"""
        motion_obj = self.get_object()
        messages.success(request, f"Motion '{motion_obj.title}' deleted successfully.")
        return super().delete(request, *args, **kwargs)


@login_required
@user_passes_test(is_superuser_or_has_permission('motion.vote'))
def motion_vote_view(request, pk):
    """View for recording party votes on a motion"""
    motion = get_object_or_404(Motion, pk=pk)
    
    # Get parties for this motion's session council
    parties = Party.objects.filter(
        local=motion.session.council.local,
        is_active=True
    )
    
    if request.method == 'POST':
        formset = MotionVoteFormSetFactory(
            request.POST,
            motion=motion,
            initial=[{'party': party.pk} for party in parties]
        )
        if formset.is_valid():
            # Process each form in the formset
            for form in formset:
                if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                    party = form.cleaned_data['party']
                    approve_votes = form.cleaned_data.get('approve_votes', 0)
                    reject_votes = form.cleaned_data.get('reject_votes', 0)
                    notes = form.cleaned_data.get('notes', '')
                    
                    # Create new vote (always create new vote for standalone vote recording)
                    MotionVote.objects.create(
                        motion=motion,
                        party=party,
                        approve_votes=approve_votes,
                        reject_votes=reject_votes,
                        notes=notes
                    )
            
            messages.success(request, "All party votes have been recorded successfully.")
            return redirect('motion:motion-detail', pk=pk)
    else:
        formset = MotionVoteFormSetFactory(
            motion=motion,
            initial=[{'party': party.pk} for party in parties]
        )
    
    return render(request, 'motion/motion_vote.html', {
        'motion': motion,
        'formset': formset
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
    """View for changing motion status with integrated voting"""
    motion = get_object_or_404(Motion, pk=pk)
    
    # Get parties for this motion's session council
    parties = Party.objects.filter(
        local=motion.session.council.local,
        is_active=True
    )
    
    # Get term and seat distributions for vote validation
    from local.models import Term, TermSeatDistribution
    from django.utils import timezone
    session = motion.session
    term = session.term
    if not term and session.council and session.council.local:
        today = timezone.now().date()
        term = Term.objects.filter(
            start_date__lte=today,
            end_date__gte=today,
            is_active=True,
            local=session.council.local
        ).first()
    
    party_seat_map = {}
    if term:
        seat_distributions = TermSeatDistribution.objects.filter(
            term=term,
            party__local=session.council.local,
            party__is_active=True
        ).select_related('party')
        party_seat_map = {dist.party.pk: dist.seats for dist in seat_distributions}
    
    # Get status from query parameter (required)
    initial_status = request.GET.get('status', None)
    if not initial_status:
        messages.error(request, "Status parameter is required.")
        return redirect('motion:motion-detail', pk=pk)
    
    # Check if votes are required for this status
    requires_votes = initial_status in ['approved', 'rejected', 'refer_to_committee', 'voted_in_committee']
    
    if request.method == 'POST':
        # Use the status from query parameter, not from POST data (include FILES for answer_pdf upload)
        form = MotionStatusForm(request.POST, request.FILES, motion=motion, changed_by=request.user, locked_status=initial_status)
        
        # Only create and validate vote formset if votes are required
        if requires_votes:
            vote_formset = MotionVoteFormSetFactory(
                request.POST,
                motion=motion,
                initial=[{'party': party.pk} for party in parties],
                party_seat_map=party_seat_map
            )
            vote_formset_valid = vote_formset.is_valid()
        else:
            # For statuses that don't require votes, create formset with minimal POST data
            # Only include management form fields to prevent validation errors
            from django.http import QueryDict
            minimal_post = QueryDict(mutable=True)
            # Add management form fields if they exist in POST (to prevent formset errors)
            if 'form-TOTAL_FORMS' in request.POST:
                minimal_post['form-TOTAL_FORMS'] = request.POST.get('form-TOTAL_FORMS', '0')
                minimal_post['form-INITIAL_FORMS'] = request.POST.get('form-INITIAL_FORMS', '0')
                minimal_post['form-MIN_NUM_FORMS'] = request.POST.get('form-MIN_NUM_FORMS', '0')
                minimal_post['form-MAX_NUM_FORMS'] = request.POST.get('form-MAX_NUM_FORMS', '1000')
            vote_formset = MotionVoteFormSetFactory(
                minimal_post,
                motion=motion,
                initial=[{'party': party.pk} for party in parties],
                party_seat_map=party_seat_map
            )
            # Don't validate - votes aren't required for this status
            # Just mark as valid without calling is_valid() which would trigger clean()
            vote_formset_valid = True
        
        # Validate form
        form_valid = form.is_valid()
        
        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Status change form submission - Form valid: {form_valid}, Vote formset valid: {vote_formset_valid}, Requires votes: {requires_votes}, Status: {initial_status}")
        if not form_valid:
            logger.warning(f"Form validation failed. Errors: {form.errors}")
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
        if requires_votes and not vote_formset_valid:
            logger.warning(f"Vote formset validation failed. Errors: {vote_formset.non_form_errors()}")
            for error in vote_formset.non_form_errors():
                messages.error(request, f"Votes: {error}")
        
        # Log validation results
        logger.info(f"Validation results - Form valid: {form_valid}, Vote formset valid: {vote_formset_valid}, Requires votes: {requires_votes}")
        
        if form_valid and vote_formset_valid:
            logger.info(f"Form and formset are valid. Proceeding with status change to: {initial_status}")
            
            # Get the new status (use locked_status to ensure it matches query parameter)
            new_status = initial_status
            reason = form.cleaned_data.get('reason', '')
            committee = form.cleaned_data.get('committee')
            session = form.cleaned_data.get('session')
            
            # For "refer to committee": check majority (approve > reject); if no majority, record in log but don't refer
            if initial_status == 'refer_to_committee' and requires_votes:
                total_approve = 0
                total_reject = 0
                for vote_form in vote_formset:
                    if vote_form.cleaned_data and not vote_form.cleaned_data.get('DELETE', False):
                        total_approve += (vote_form.cleaned_data.get('approve_votes') or 0)
                        total_reject += (vote_form.cleaned_data.get('reject_votes') or 0)
                if total_approve <= total_reject:
                    # No majority for referral: record in status log, don't refer
                    new_status = 'refer_no_majority'
                    reason = (reason or '').strip()
                    reason_note = _('Referral to committee rejected – no majority (in favor: %(approve)s, against: %(reject)s).') % {
                        'approve': total_approve,
                        'reject': total_reject,
                    }
                    reason = f"{reason_note}\n{reason}" if reason else reason_note
                    committee = None  # Don't set committee
                    logger.info(f"Refer to committee: no majority (approve={total_approve}, reject={total_reject}). Setting status to refer_no_majority.")
            
            # Debug logging
            logger.info(f"Saving status change: status={new_status}, reason={reason}, committee={committee}, session={session}")
            logger.info(f"Current motion status: {motion.status}")
            
            # Set attributes for the save method to use
            motion._status_changed_by = request.user
            motion._status_change_reason = reason
            motion._status_committee = committee
            motion._status_session = session
            
            # Update the motion status
            old_status = motion.status
            motion.status = new_status
            
            # If status is 'refer_to_committee' or 'voted_in_committee', also update the motion's committee (not for refer_no_majority)
            if new_status in ['refer_to_committee', 'voted_in_committee'] and committee:
                motion.committee = committee
            
            # If status is 'tabled' and session is provided, update the motion's session
            if new_status == 'tabled' and session:
                motion.session = session
            
            # Save the motion (this will trigger the save method which creates the status history entry)
            motion.save()
            
            logger.debug(f"Motion saved. Old status: {old_status}, New status: {motion.status}")
            
            # If status is 'answered', attach the uploaded PDF to the new status entry
            if new_status == 'answered':
                status_entry = motion.status_history.first()
                answer_pdf = form.cleaned_data.get('answer_pdf')
                if status_entry and answer_pdf:
                    status_entry.answer_pdf = answer_pdf
                    status_entry.save(update_fields=['answer_pdf'])
                    logger.info(f"Saved answer PDF to status entry {status_entry.pk}")
            
            # Process vote formset if status requires voting (including refer_no_majority so votes are recorded)
            if new_status in ['approved', 'rejected', 'refer_to_committee', 'refer_no_majority', 'voted_in_committee']:
                # Get the status entry that was just created
                status_entry = motion.status_history.first()
                
                if not status_entry:
                    logger.error(f"Status entry was not created for motion {motion.pk} with status {new_status}")
                    messages.error(request, "Status was updated but status history entry was not created. Please check the logs.")
                else:
                    logger.info(f"Creating votes for status entry {status_entry.pk}")
                    votes_created = 0
                for vote_form in vote_formset:
                    if vote_form.cleaned_data and not vote_form.cleaned_data.get('DELETE', False):
                        party = vote_form.cleaned_data.get('party')
                        approve_votes = vote_form.cleaned_data.get('approve_votes', 0) or 0
                        reject_votes = vote_form.cleaned_data.get('reject_votes', 0) or 0
                        notes = vote_form.cleaned_data.get('notes', '')
                        
                        # Only create vote if there are actual votes (approve or reject > 0) and party is set
                        if (approve_votes > 0 or reject_votes > 0) and party:
                            MotionVote.objects.create(
                                motion=motion,
                                party=party,
                                status=status_entry,
                                approve_votes=approve_votes,
                                reject_votes=reject_votes,
                                notes=notes
                            )
                            votes_created += 1
                            logger.info(f"Created vote for party {party.name}: approve={approve_votes}, reject={reject_votes}")
                        elif (approve_votes > 0 or reject_votes > 0) and not party:
                            logger.warning(f"Skipping vote creation: votes entered but no party set (approve={approve_votes}, reject={reject_votes})")
                    
                    logger.info(f"Created {votes_created} votes for status change")
            
            # Create success message
            if new_status == 'refer_no_majority':
                messages.warning(
                    request,
                    _("Referral to committee was rejected – no majority. Votes have been recorded and the motion remains on the agenda.")
                )
            elif requires_votes:
                messages.success(request, f"Motion status changed to '{motion.get_status_display()}' and votes recorded successfully.")
            else:
                messages.success(request, f"Motion status changed to '{motion.get_status_display()}'.")
            
            logger.debug(f"Redirecting to motion detail page for motion {pk}")
            return redirect('motion:motion-detail', pk=pk)
        else:
            # Form is invalid - re-render with errors
            # Get the status display name for the template
            status_display = dict(Motion.STATUS_CHOICES).get(initial_status, initial_status)
            
            # Log detailed error information
            logger.warning(f"Form validation failed. Form errors: {form.errors if not form_valid else 'None'}")
            logger.warning(f"Vote formset errors: {vote_formset.non_form_errors() if requires_votes and not vote_formset_valid else 'N/A'}")
            
            # Show form errors as messages
            if not form_valid:
                logger.warning(f"Form has {len(form.errors)} error fields")
                for field, errors in form.errors.items():
                    for error in errors:
                        logger.warning(f"Form error - {field}: {error}")
                        messages.error(request, f"{field}: {error}")
            # Only show vote formset errors if votes are required
            if requires_votes and not vote_formset_valid:
                for error in vote_formset.non_form_errors():
                    logger.warning(f"Vote formset error: {error}")
                    messages.error(request, f"Votes: {error}")
            
            # Also check for individual form errors in the formset
            # Only show errors for forms that have votes entered (to avoid confusing errors on empty forms)
            if requires_votes:
                for i, vote_form in enumerate(vote_formset):
                    if vote_form.errors:
                        # Check if this form has votes - if not, skip showing errors (it's just an empty form)
                        prefix = vote_form.prefix
                        has_votes = False
                        if request.POST:
                            approve_str = request.POST.get(f'{prefix}-approve_votes', '')
                            reject_str = request.POST.get(f'{prefix}-reject_votes', '')
                            try:
                                approve_votes = int(approve_str) if approve_str and approve_str.strip() else 0
                                reject_votes = int(reject_str) if reject_str and reject_str.strip() else 0
                                has_votes = approve_votes > 0 or reject_votes > 0
                            except (ValueError, TypeError):
                                pass
                        
                        # Only show errors if this form has votes (empty forms can have errors but we'll ignore them)
                        if has_votes:
                            logger.warning(f"Vote form {i} errors: {vote_form.errors}")
                            for field, errors in vote_form.errors.items():
                                for error in errors:
                                    messages.error(request, f"Vote form {i+1} - {field}: {error}")
            
            return render(request, 'motion/motion_status_change.html', {
                'motion': motion,
                'form': form,
                'vote_formset': vote_formset,
                'status_display': status_display,
            })
    else:
        # Status must be provided via query parameter
        form = MotionStatusForm(motion=motion, changed_by=request.user, locked_status=initial_status)
        # Create vote formset (will be shown/hidden based on status via JavaScript)
        vote_formset = MotionVoteFormSetFactory(
            motion=motion,
            initial=[{'party': party.pk} for party in parties],
            party_seat_map=party_seat_map
        )
    
    # Get the status display name for the template
    status_display = dict(Motion.STATUS_CHOICES).get(initial_status, initial_status)
    
    return render(request, 'motion/motion_status_change.html', {
        'motion': motion,
        'form': form,
        'status_display': status_display,
        'vote_formset': vote_formset
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


@login_required
@user_passes_test(is_superuser_or_has_permission('motion.vote'))
def motion_vote_delete_view(request, motion_pk, vote_type, vote_name_encoded):
    """View for deleting a vote round (all votes with the same vote_type and vote_name)"""
    from urllib.parse import unquote
    from django.utils.translation import gettext_lazy as _
    
    motion = get_object_or_404(Motion, pk=motion_pk)
    
    # Decode vote_name from URL (or use 'default' if empty)
    vote_name = unquote(vote_name_encoded) if vote_name_encoded != 'default' else ''
    
    if request.method == 'POST':
        # Get all votes for this round
        round_filter = {'motion': motion, 'vote_type': vote_type}
        if vote_name:
            round_filter['vote_name'] = vote_name
        else:
            round_filter['vote_name'] = ''
        
        votes_to_delete = MotionVote.objects.filter(**round_filter)
        votes_count = votes_to_delete.count()
        
        if votes_count == 0:
            messages.error(request, _("No votes found to delete."))
            return redirect('motion:motion-detail', pk=motion_pk)
        
        # Delete all votes in this round
        votes_to_delete.delete()
        
        messages.success(request, _("Vote round deleted successfully. %(count)d vote(s) removed.") % {'count': votes_count})
        return redirect('motion:motion-detail', pk=motion_pk)
    
    # GET request - show confirmation page
    round_filter = {'motion': motion, 'vote_type': vote_type}
    if vote_name:
        round_filter['vote_name'] = vote_name
    else:
        round_filter['vote_name'] = ''
    
    votes_in_round = MotionVote.objects.filter(**round_filter).select_related('party').order_by('party__name')
    
    if votes_in_round.count() == 0:
        messages.error(request, _("No votes found for this round."))
        return redirect('motion:motion-detail', pk=motion_pk)
    
    # Calculate round statistics
    total_approve = sum(vote.approve_votes for vote in votes_in_round)
    total_reject = sum(vote.reject_votes for vote in votes_in_round)
    
    return render(request, 'motion/motion_vote_confirm_delete.html', {
        'motion': motion,
        'vote_type': vote_type,
        'vote_name': vote_name,
        'votes': votes_in_round,
        'votes_count': votes_in_round.count(),
        'total_approve': total_approve,
        'total_reject': total_reject,
    })


@login_required
@user_passes_test(is_superuser_or_has_permission('motion.vote'))
def motion_vote_edit_view(request, motion_pk, vote_type, vote_name_encoded):
    """View for editing a vote round (all votes with the same vote_type and vote_name)"""
    from urllib.parse import unquote
    from django.utils.translation import gettext_lazy as _
    from django.utils import timezone
    from local.models import Term, TermSeatDistribution, Party, Session, Committee
    import logging
    logger = logging.getLogger(__name__)
    
    motion = get_object_or_404(Motion, pk=motion_pk)
    
    # Decode vote_name from URL (or use 'default' if empty)
    vote_name = unquote(vote_name_encoded) if vote_name_encoded != 'default' else ''
    
    # Get existing votes for this round
    round_filter = {'motion': motion, 'vote_type': vote_type}
    if vote_name:
        round_filter['vote_name'] = vote_name
    else:
        round_filter['vote_name'] = ''
    
    existing_votes = MotionVote.objects.filter(**round_filter).select_related('party').order_by('party__name')
    
    if existing_votes.count() == 0:
        messages.error(request, _("No votes found for this round."))
        return redirect('motion:motion-detail', pk=motion_pk)
    
    # Get term and seat distributions
    session = motion.session
    term = session.term
    
    if not term and session.council and session.council.local:
        today = timezone.now().date()
        term = Term.objects.filter(
            start_date__lte=today,
            end_date__gte=today,
            is_active=True
        ).first()
    
    if not term:
        messages.error(request, _("No active term found for this session. Please ensure the session has a term assigned."))
        return redirect('motion:motion-detail', pk=motion_pk)
    
    parties = Party.objects.filter(
        local=session.council.local,
        is_active=True
    ).order_by('name')
    
    seat_distributions = TermSeatDistribution.objects.filter(
        term=term,
        party__in=parties
    ).select_related('party')
    
    party_seat_map = {dist.party.pk: dist.seats for dist in seat_distributions}
    parties = [p for p in parties if p.pk in party_seat_map]
    
    if request.method == 'POST':
        vote_type_form = MotionVoteTypeForm(request.POST, motion=motion)
        
        # Prepare initial data for formset from existing votes
        initial_data = []
        for party in parties:
            existing_vote = existing_votes.filter(party=party).first()
            if existing_vote:
                initial_data.append({
                    'party': party.pk,
                    'approve_votes': existing_vote.approve_votes,
                    'reject_votes': existing_vote.reject_votes,
                    'notes': existing_vote.notes,
                })
            else:
                initial_data.append({'party': party.pk})
        
        formset = MotionVoteFormSetFactory(
            request.POST,
            motion=motion,
            initial=initial_data,
            vote_type=request.POST.get('vote_type', vote_type),
            party_seat_map=party_seat_map
        )
        
        if vote_type_form.is_valid() and formset.is_valid():
            new_vote_type = vote_type_form.cleaned_data['vote_type']
            new_vote_name = vote_type_form.cleaned_data.get('vote_name', '').strip()
            new_vote_session = vote_type_form.cleaned_data.get('vote_session') or motion.session
            new_committee = vote_type_form.cleaned_data.get('committee')
            
            # Update or create votes for each party
            votes_updated = 0
            for form in formset:
                if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                    party = form.cleaned_data['party']
                    approve_votes = form.cleaned_data.get('approve_votes', 0) or 0
                    reject_votes = form.cleaned_data.get('reject_votes', 0) or 0
                    notes = form.cleaned_data.get('notes', '')
                    
                    # Get or create vote for this party in this round
                    vote, created = MotionVote.objects.update_or_create(
                        motion=motion,
                        party=party,
                        vote_type=new_vote_type,
                        vote_name=new_vote_name or '',
                        defaults={
                            'vote_session': new_vote_session,
                            'approve_votes': approve_votes,
                            'reject_votes': reject_votes,
                            'notes': notes,
                        }
                    )
                    votes_updated += 1
                    logger.debug(f"Vote {'created' if created else 'updated'} for party {party.name}: approve={approve_votes}, reject={reject_votes}")
            
            # Delete votes for parties that are no longer in the formset or have been removed
            # (This handles cases where a party was removed from the council)
            current_party_ids = {form.cleaned_data['party'].pk for form in formset if form.cleaned_data and not form.cleaned_data.get('DELETE', False)}
            votes_to_delete = existing_votes.exclude(party_id__in=current_party_ids)
            deleted_count = votes_to_delete.count()
            if deleted_count > 0:
                votes_to_delete.delete()
                logger.debug(f"Deleted {deleted_count} votes for parties no longer in the formset")
            
            # Recalculate totals and outcome for the updated round
            updated_round_filter = {'motion': motion, 'vote_type': new_vote_type}
            if new_vote_name:
                updated_round_filter['vote_name'] = new_vote_name
            else:
                updated_round_filter['vote_name'] = ''
            
            round_votes = MotionVote.objects.filter(**updated_round_filter)
            
            total_favor = sum(vote.approve_votes for vote in round_votes)
            total_against = sum(vote.reject_votes for vote in round_votes)
            
            # Calculate outcome
            if new_vote_type == 'regular':
                if total_favor > total_against:
                    outcome = 'adopted'
                elif total_against > total_favor:
                    outcome = 'rejected'
                else:
                    outcome = 'tie'
            elif new_vote_type == 'refer_to_committee':
                if total_favor > total_against:
                    outcome = 'referred'
                else:
                    outcome = 'not_referred'
            else:
                outcome = ''
            
            # Update totals and outcome for all votes in this round
            round_votes.update(
                total_favor=total_favor,
                total_against=total_against,
                outcome=outcome
            )
            
            messages.success(request, _("Vote round updated successfully. %(count)d vote(s) updated.") % {'count': votes_updated})
            return redirect('motion:motion-detail', pk=motion_pk)
        else:
            # Form validation failed
            if not vote_type_form.is_valid():
                for field, errors in vote_type_form.errors.items():
                    for error in errors:
                        messages.error(request, f"Vote Type Form - {field}: {error}")
            if not formset.is_valid():
                for error in formset.non_form_errors():
                    messages.error(request, f"Formset Error: {error}")
    else:
        # GET request - prepare forms with existing data
        # Get first vote to determine initial values
        first_vote = existing_votes.first()
        
        vote_type_form = MotionVoteTypeForm(motion=motion, initial={
            'vote_type': vote_type,
            'vote_name': vote_name,
            'vote_session': first_vote.vote_session if first_vote and first_vote.vote_session else motion.session,
        })
        
        # Prepare initial data for formset from existing votes
        initial_data = []
        for party in parties:
            existing_vote = existing_votes.filter(party=party).first()
            if existing_vote:
                initial_data.append({
                    'party': party.pk,
                    'approve_votes': existing_vote.approve_votes,
                    'reject_votes': existing_vote.reject_votes,
                    'notes': existing_vote.notes,
                })
            else:
                initial_data.append({'party': party.pk})
        
        formset = MotionVoteFormSetFactory(
            motion=motion,
            initial=initial_data,
            vote_type=vote_type,
            party_seat_map=party_seat_map
        )
    
    # Prepare party data with seat information for template
    party_data = []
    for party in parties:
        max_seats = party_seat_map.get(party.pk, 0)
        existing_vote = existing_votes.filter(party=party).first()
        
        party_data.append({
            'party': party,
            'max_seats': max_seats,
            'existing_vote': existing_vote
        })
    
    # Create a combined list for the template
    forms_with_data = []
    for i, form in enumerate(formset):
        if i < len(party_data):
            forms_with_data.append({
                'form': form,
                'party_info': party_data[i]
            })
        else:
            forms_with_data.append({
                'form': form,
                'party_info': None
            })
    
    return render(request, 'motion/motion_vote.html', {
        'motion': motion,
        'vote_type_form': vote_type_form,
        'formset': formset,
        'forms_with_data': forms_with_data,
        'term': term,
        'party_seat_map': party_seat_map,
        'is_edit': True,
        'vote_type': vote_type,
        'vote_name': vote_name,
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
        # Get votes for this motion (party-based votes)
        votes = self.object.votes.all().select_related('party', 'status').order_by('party__name')
        context['votes'] = votes
        
        # Calculate vote statistics
        total_approve = sum(vote.approve_votes for vote in votes)
        total_reject = sum(vote.reject_votes for vote in votes)
        total_cast = total_approve + total_reject
        
        context['vote_stats'] = {
            'approve': total_approve,
            'reject': total_reject,
            'total_cast': total_cast,
            'parties_voted': len(set(vote.party for vote in votes)),
            'total': votes.count(),
        }
        
        # Get comments for this motion
        context['comments'] = self.object.comments.filter(is_public=True).select_related('author').order_by('created_at')
        # Get attachments for this motion
        context['attachments'] = self.object.attachments.all().order_by('uploaded_at')
        
        # Prepare parties with logo paths for PDF generation
        # Order parties by seat count in the council (if available)
        from django.utils import timezone
        from local.models import Term, TermSeatDistribution
        
        parties_with_logos = []
        party_seat_map = {}
        
        # Get the council from the motion's session
        council = None
        if self.object.session and self.object.session.council:
            council = self.object.session.council
            
            # Get current term and seat distributions
            today = timezone.now().date()
            current_term = Term.objects.filter(
                start_date__lte=today,
                end_date__gte=today,
                is_active=True
            ).first()
            
            if current_term and council.local:
                # Get seat distributions for parties in this council's local
                seat_distributions = TermSeatDistribution.objects.filter(
                    term=current_term,
                    party__local=council.local
                ).select_related('party')
                
                # Create a map of party ID to seat count
                for distribution in seat_distributions:
                    party_seat_map[distribution.party.pk] = distribution.seats
        
        # Get all parties for this motion and sort by seat count (descending)
        parties = list(self.object.parties.all())
        parties.sort(key=lambda p: (-party_seat_map.get(p.pk, 0), p.name))
        
        # Prepare parties with logo paths
        for party in parties:
            party_data = {
                'party': party,
                'logo_name': None
            }
            if party.logo:
                # Store the relative path from MEDIA_ROOT (just the filename/relative path)
                party_data['logo_name'] = party.logo.name
            parties_with_logos.append(party_data)
        
        context['parties_with_logos'] = parties_with_logos
        # Also provide ordered parties list for use in text
        context['ordered_parties'] = parties
        
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
        # Use MEDIA_ROOT as base_url so WeasyPrint can find images via file paths
        css = CSS(string='''
            body { font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }
            p { line-height: 1.6; }
            h1 { font-size: 20px; }
            h2 { font-size: 16px; text-align: center; }
            .header { text-align: center; margin-bottom: 30px; }
            .motion-info { margin-bottom: 30px; }
            .motion-text { margin-bottom: 20px; }
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
        
        if settings.MEDIA_ROOT:
            # Use file:// protocol with absolute path for WeasyPrint
            base_url = f"file://{os.path.abspath(settings.MEDIA_ROOT)}/"
        else:
            base_url = None
        
        try:
            html = HTML(string=html_string, base_url=base_url)
            # Generate PDF
            pdf = html.write_pdf(stylesheets=[css])
        except (AttributeError, TypeError) as e:
            # Handle Python 3.13 compatibility issue with WeasyPrint
            # Try without base_url as a workaround
            if 'transform' in str(e) or 'super' in str(e) or 'base_url' in str(e):
                html = HTML(string=html_string)
                pdf = html.write_pdf(stylesheets=[css])
            else:
                raise
        
        # Create response
        # Generate filename: motion_type_motion_title.pdf (with spaces replaced by underscores)
        motion_type = self.object.get_motion_type_display().replace(" ", "_")
        motion_title = self.object.title.replace(" ", "_")
        filename = f"{motion_type}_{motion_title}.pdf"
        
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response


# Question Views
class QuestionListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """View for listing Question objects"""
    model = Question
    context_object_name = 'questions'
    template_name = 'motion/question_list.html'
    paginate_by = 20

    def test_func(self):
        """Check if user has permission to view Question objects"""
        return self.request.user.is_superuser or self.request.user.has_role_permission('motion.view')

    def get_queryset(self):
        """Filter queryset based on search parameters"""
        queryset = Question.objects.filter(is_active=True).select_related(
            'session', 'group', 'submitted_by'
        ).prefetch_related('parties', 'tags').order_by('-submitted_date')
        
        # Get filter form
        filter_form = QuestionFilterForm(self.request.GET)
        
        if filter_form.is_valid():
            # Filter by search query
            search_query = filter_form.cleaned_data.get('search')
            if search_query:
                queryset = queryset.filter(
                    Q(title__icontains=search_query) |
                    Q(text__icontains=search_query) |
                    Q(group__name__icontains=search_query)
                )
            
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
            
            # Filter by tags
            tags = filter_form.cleaned_data.get('tags')
            if tags:
                queryset = queryset.filter(tags__in=tags).distinct()
        
        return queryset

    def get_context_data(self, **kwargs):
        """Add filter form to context"""
        context = super().get_context_data(**kwargs)
        context['filter_form'] = QuestionFilterForm(self.request.GET)
        
        # Get tag counts for word cloud (from all questions, not just filtered)
        from .models import Tag
        from django.db.models import Count
        # Get all tags used in questions, with their counts
        tag_counts = Tag.objects.filter(
            questions__isnull=False,
            is_active=True
        ).annotate(
            count=Count('questions', distinct=True)
        ).order_by('-count', 'name')
        context['tag_counts'] = tag_counts
        
        # Get currently selected tags from GET parameters
        selected_tag_ids = []
        if 'tags' in self.request.GET:
            try:
                selected_tag_ids = [int(tag_id) for tag_id in self.request.GET.getlist('tags')]
            except (ValueError, TypeError):
                pass
        context['selected_tag_ids'] = selected_tag_ids
        
        return context


class QuestionDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View for displaying a single Question object"""
    model = Question
    context_object_name = 'question'
    template_name = 'motion/question_detail.html'

    def test_func(self):
        """Check if user has permission to view Question objects"""
        return self.request.user.is_superuser or self.request.user.has_role_permission('motion.view')

    def get_queryset(self):
        return Question.objects.prefetch_related('interventions', 'parties', 'group', 'attachments')
    
    def get_context_data(self, **kwargs):
        """Add additional context data"""
        context = super().get_context_data(**kwargs)
        question = self.object
        
        # Add attachment form
        context['attachment_form'] = QuestionAttachmentForm(question=question, uploaded_by=self.request.user)
        
        # Add status change form
        context['status_form'] = QuestionStatusForm(question=question, changed_by=self.request.user)
        
        # Add permission check for status changes
        context['can_change_status'] = can_change_question_status(self.request.user, question)
        
        # Get attachments
        context['attachments'] = question.attachments.all().order_by('-uploaded_at')
        
        # Get status history
        context['status_history'] = question.status_history.all()
        
        return context


class QuestionCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View for creating a new Question object"""
    model = Question
    form_class = QuestionForm
    template_name = 'motion/question_form.html'
    success_url = reverse_lazy('question:question-list')

    def test_func(self):
        """Check if user has permission to create Question objects"""
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

    def get_success_url(self):
        """Redirect to session detail page after successful question creation"""
        if hasattr(self.object, 'session') and self.object.session:
            return reverse('local:session-detail', kwargs={'pk': self.object.session.pk})
        return super().get_success_url()

    def form_valid(self, form):
        """Set submitted_by and display success message"""
        form.instance.submitted_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, f"Question '{form.instance.title}' created successfully.")
        return response


class QuestionUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View for updating an existing Question object"""
    model = Question
    form_class = QuestionForm
    template_name = 'motion/question_form.html'
    success_url = reverse_lazy('question:question-list')

    def test_func(self):
        """Check if user has permission to edit Question objects"""
        return self.request.user.is_superuser or self.request.user.has_role_permission('motion.edit')

    def get_form_kwargs(self):
        """Pass user to form for automatic group assignment"""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_success_url(self):
        """Redirect to question detail page after successful update"""
        return reverse('question:question-detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        """Display success message on form validation"""
        response = super().form_valid(form)
        messages.success(self.request, f"Question '{form.instance.title}' updated successfully.")
        return response


class QuestionDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """View for deleting a Question object"""
    model = Question
    template_name = 'motion/question_confirm_delete.html'
    success_url = reverse_lazy('question:question-list')

    def test_func(self):
        """Check if user has permission to delete Question objects"""
        question = self.get_object()
        
        # Superusers can delete any question
        if self.request.user.is_superuser:
            return True
        
        # Users can delete their own questions
        if question.submitted_by == self.request.user:
            return True
        
        # Group admins can delete questions from their groups
        if question.group:
            from group.models import GroupMember
            from user.models import Role
            
            try:
                leader_role = Role.objects.get(name='Leader')
                deputy_leader_role = Role.objects.get(name='Deputy Leader')
                
                membership = GroupMember.objects.filter(
                    user=self.request.user,
                    group=question.group,
                    is_active=True,
                    roles__in=[leader_role, deputy_leader_role]
                ).first()
                
                if membership:
                    return True
            except Role.DoesNotExist:
                pass
        
        return False

    def delete(self, request, *args, **kwargs):
        """Display success message on deletion"""
        question_obj = self.get_object()
        messages.success(request, f"Question '{question_obj.title}' deleted successfully.")
        return super().delete(request, *args, **kwargs)


@login_required
@user_passes_test(is_superuser_or_has_permission('motion.attach'))
def question_attachment_view(request, pk):
    """View for uploading attachments to a question"""
    question = get_object_or_404(Question, pk=pk)
    
    if request.method == 'POST':
        form = QuestionAttachmentForm(request.POST, request.FILES, question=question, uploaded_by=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Attachment uploaded successfully.")
            return redirect('question:question-detail', pk=pk)
    else:
        form = QuestionAttachmentForm(question=question, uploaded_by=request.user)
    
    return render(request, 'motion/question_attachment.html', {
        'question': question,
        'form': form
    })


@login_required
def question_status_change_view(request, pk):
    """View for changing question status"""
    question = get_object_or_404(Question, pk=pk)
    
    # Check permissions
    if not can_change_question_status(request.user, question):
        messages.error(request, "You don't have permission to change the status of this question.")
        return redirect('question:question-detail', pk=pk)
    
    if request.method == 'POST':
        form = QuestionStatusForm(request.POST, question=question, changed_by=request.user)
        
        if form.is_valid():
            # Get the new status
            new_status = form.cleaned_data['status']
            reason = form.cleaned_data['reason']
            committee = form.cleaned_data.get('committee')
            
            # Set attributes for the save method to use
            question._status_changed_by = request.user
            question._status_change_reason = reason
            question._status_committee = committee
            
            # Update the question status
            question.status = new_status
            
            # Save the question (this will trigger the save method which creates the status history entry)
            question.save()
            
            messages.success(request, f"Question status changed to '{question.get_status_display()}'.")
            return redirect('question:question-detail', pk=pk)
    else:
        form = QuestionStatusForm(question=question, changed_by=request.user)
    
    return render(request, 'motion/question_status_change.html', {
        'question': question,
        'form': form
    })


@login_required
@user_passes_test(lambda u: u.is_superuser)
def question_status_delete_view(request, question_pk, status_pk):
    """View for deleting a question status entry (superuser only)"""
    question = get_object_or_404(Question, pk=question_pk)
    status_entry = get_object_or_404(QuestionStatus, pk=status_pk, question=question)
    
    if request.method == 'POST':
        status_entry.delete()
        messages.success(request, "Status entry deleted successfully.")
        return redirect('question:question-detail', pk=question_pk)
    
    return render(request, 'motion/question_status_confirm_delete.html', {
        'question': question,
        'status_entry': status_entry
    })
