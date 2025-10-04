from django.contrib import admin
from .models import Motion, MotionVote, MotionComment, MotionAttachment, MotionStatus


@admin.register(Motion)
class MotionAdmin(admin.ModelAdmin):
    """Admin configuration for Motion model"""
    list_display = [
        'title', 'motion_type', 'status', 'group', 'session', 
        'submitted_by', 'submitted_date', 'supporting_parties_count'
    ]
    list_filter = [
        'motion_type', 'status', 'group__party__local', 
        'session__council', 'submitted_date', 'is_active'
    ]
    search_fields = ['title', 'description', 'group__name', 'submitted_by__username']
    readonly_fields = ['submitted_date', 'last_modified', 'created_at', 'updated_at']
    filter_horizontal = ['parties']
    date_hierarchy = 'submitted_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'motion_type', 'status')
        }),
        ('Relationships', {
            'fields': ('session', 'group', 'parties')
        }),

        ('Metadata', {
            'fields': ('submitted_by', 'submitted_date', 'last_modified', 'is_active'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def supporting_parties_count(self, obj):
        """Display count of supporting parties"""
        return obj.supporting_parties_count
    supporting_parties_count.short_description = 'Supporting Parties'


@admin.register(MotionVote)
class MotionVoteAdmin(admin.ModelAdmin):
    """Admin configuration for MotionVote model"""
    list_display = ['motion', 'party', 'status', 'get_vote_summary', 'total_votes_cast', 'participation_rate', 'voted_at']
    list_filter = ['voted_at', 'motion__status', 'party__local', 'status__status']
    search_fields = ['motion__title', 'party__name', 'notes']
    readonly_fields = ['voted_at', 'total_votes_cast', 'participation_rate']
    date_hierarchy = 'voted_at'
    
    fieldsets = (
        ('Vote Information', {
            'fields': ('motion', 'party', 'status', 'approve_votes', 'reject_votes')
        }),
        ('Vote Summary', {
            'fields': ('total_votes_cast', 'participation_rate', 'notes'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('voted_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_vote_summary(self, obj):
        """Display vote summary"""
        return obj.get_vote_summary()
    get_vote_summary.short_description = 'Vote Summary'
    
    def total_votes_cast(self, obj):
        """Display total votes cast"""
        return obj.total_votes_cast
    total_votes_cast.short_description = 'Total Votes Cast'
    
    def participation_rate(self, obj):
        """Display participation rate"""
        return f"{obj.participation_rate:.1f}%"
    participation_rate.short_description = 'Participation Rate'


@admin.register(MotionComment)
class MotionCommentAdmin(admin.ModelAdmin):
    """Admin configuration for MotionComment model"""
    list_display = ['motion', 'author', 'is_public', 'created_at']
    list_filter = ['is_public', 'created_at', 'motion__status']
    search_fields = ['motion__title', 'author__username', 'content']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Comment Information', {
            'fields': ('motion', 'author', 'content', 'is_public')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(MotionAttachment)
class MotionAttachmentAdmin(admin.ModelAdmin):
    """Admin configuration for MotionAttachment model"""
    list_display = ['filename', 'motion', 'file_type', 'uploaded_by', 'uploaded_at']
    list_filter = ['file_type', 'uploaded_at', 'motion__status']
    search_fields = ['filename', 'motion__title', 'uploaded_by__username', 'description']
    readonly_fields = ['uploaded_at']
    date_hierarchy = 'uploaded_at'
    
    fieldsets = (
        ('Attachment Information', {
            'fields': ('motion', 'file', 'filename', 'file_type', 'description')
        }),
        ('Upload Information', {
            'fields': ('uploaded_by', 'uploaded_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(MotionStatus)
class MotionStatusAdmin(admin.ModelAdmin):
    """Admin configuration for MotionStatus model"""
    list_display = ['motion', 'status', 'changed_by', 'changed_at']
    list_filter = ['status', 'changed_at', 'motion__status']
    search_fields = ['motion__title', 'changed_by__username', 'reason']
    readonly_fields = ['changed_at']
    date_hierarchy = 'changed_at'
    
    fieldsets = (
        ('Status Change Information', {
            'fields': ('motion', 'status', 'changed_by', 'reason')
        }),
        ('Timestamps', {
            'fields': ('changed_at',),
            'classes': ('collapse',)
        }),
    )
