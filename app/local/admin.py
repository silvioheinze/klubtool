from django.contrib import admin
from .models import Local, Council, Session, Term, Party, TermSeatDistribution


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
    search_fields = ['name', 'description', 'local__name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'local', 'description', 'is_active')
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
    readonly_fields = ['created_at', 'updated_at', 'allocated_seats', 'unallocated_seats']
    ordering = ['-start_date']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'start_date', 'end_date', 'description', 'is_active')
        }),
        ('Seat Management', {
            'fields': ('total_seats', 'allocated_seats', 'unallocated_seats')
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
    list_display = ['term', 'party', 'seats', 'percentage', 'created_at']
    list_filter = ['term', 'party', 'created_at']
    search_fields = ['term__name', 'party__name', 'notes']
    readonly_fields = ['created_at', 'updated_at', 'percentage']
    ordering = ['-term__start_date', '-seats']
    
    fieldsets = (
        ('Distribution Information', {
            'fields': ('term', 'party', 'seats', 'percentage')
        }),
        ('Additional Information', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def percentage(self, obj):
        if obj.percentage:
            return f"{obj.percentage:.1f}%"
        return "-"
    percentage.short_description = 'Percentage'


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
            'fields': ('scheduled_date', 'start_time', 'end_time', 'location')
        }),
        ('Content', {
            'fields': ('agenda', 'minutes', 'notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
