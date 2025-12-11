from django.contrib import admin
from .models import Local, Council, Committee, CommitteeMember, Session, Term, Party, TermSeatDistribution, SessionPresence


@admin.register(Local)
class LocalAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active', 'created_at', 'updated_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'code', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'description', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Council)
class CouncilAdmin(admin.ModelAdmin):
    list_display = ['name', 'local', 'is_active', 'created_at']
    list_filter = ['is_active', 'local', 'created_at']
    search_fields = ['name', 'local__name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'local', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_date', 'end_date', 'total_seats', 'allocated_seats', 'is_active', 'is_current']
    list_filter = ['is_active', 'start_date', 'end_date']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at', 'allocated_seats']
    ordering = ['-start_date']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'start_date', 'end_date', 'description', 'is_active')
        }),
        ('Seat Management', {
            'fields': ('total_seats', 'allocated_seats')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def is_current(self, obj):
        return obj.is_current
    is_current.boolean = True
    is_current.short_description = 'Current'

    def allocated_seats(self, obj):
        return obj.allocated_seats
    allocated_seats.short_description = 'Allocated Seats'


@admin.register(Party)
class PartyAdmin(admin.ModelAdmin):
    list_display = ['name', 'short_name', 'color', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'short_name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'short_name', 'description', 'is_active')
        }),
        ('Branding', {
            'fields': ('color', 'logo')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(TermSeatDistribution)
class TermSeatDistributionAdmin(admin.ModelAdmin):
    list_display = ['term', 'party', 'seats', 'created_at']
    list_filter = ['term', 'party', 'created_at']
    search_fields = ['term__name', 'party__name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-term__start_date', '-seats']
    
    fieldsets = (
        ('Distribution Information', {
            'fields': ('term', 'party', 'seats')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Committee)
class CommitteeAdmin(admin.ModelAdmin):
    list_display = ['name', 'abbreviation', 'council', 'committee_type', 'chairperson', 'member_count', 'is_active']
    list_filter = ['committee_type', 'is_active', 'council', 'created_at']
    search_fields = ['name', 'abbreviation', 'description', 'chairperson', 'council__name']
    readonly_fields = ['created_at', 'updated_at', 'member_count']
    ordering = ['name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'abbreviation', 'council', 'committee_type', 'description', 'is_active')
        }),
        ('Leadership', {
            'fields': ('chairperson',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def member_count(self, obj):
        return obj.member_count
    member_count.short_description = 'Members'


@admin.register(CommitteeMember)
class CommitteeMemberAdmin(admin.ModelAdmin):
    list_display = ['user', 'committee', 'role', 'joined_date', 'is_active']
    list_filter = ['role', 'is_active', 'committee', 'joined_date']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'committee__name']
    readonly_fields = ['joined_date', 'created_at', 'updated_at']
    ordering = ['-joined_date']
    
    fieldsets = (
        ('Membership Information', {
            'fields': ('committee', 'user', 'role', 'is_active')
        }),
        ('Additional Information', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('joined_date', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ['title', 'council', 'term', 'session_type', 'status', 'scheduled_date', 'is_active']
    list_filter = ['session_type', 'status', 'is_active', 'council', 'term', 'scheduled_date']
    search_fields = ['title', 'agenda', 'minutes', 'council__name', 'term__name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-scheduled_date']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'council', 'term', 'session_type', 'status', 'is_active')
        }),
        ('Schedule', {
            'fields': ('scheduled_date', 'location')
        }),
        ('Content', {
            'fields': ('agenda', 'minutes', 'notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SessionPresence)
class SessionPresenceAdmin(admin.ModelAdmin):
    list_display = ['session', 'party', 'present_count', 'updated_at']
    list_filter = ['session', 'party', 'updated_at']
    search_fields = ['session__title', 'party__name', 'party__short_name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-updated_at', 'party__name']
    
    fieldsets = (
        ('Presence Information', {
            'fields': ('session', 'party', 'present_count')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
