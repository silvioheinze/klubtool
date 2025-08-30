from django.contrib import admin
from .models import Group, GroupMember

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'short_name', 'party', 'local', 'member_count', 'is_active', 'created_at']
    list_filter = ['is_active', 'party', 'party__local', 'created_at', 'founded_date']
    search_fields = ['name', 'short_name', 'description', 'party__name']
    readonly_fields = ['created_at', 'updated_at', 'member_count']
    ordering = ['name']
    fieldsets = (
        ('Basic Information', {'fields': ('name', 'short_name', 'party', 'description', 'is_active')}),
        ('Dates', {'fields': ('founded_date', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def local(self, obj):
        return obj.party.local.name if obj.party and obj.party.local else '-'
    local.short_description = 'Local District'

    def member_count(self, obj):
        return obj.member_count
    member_count.short_description = 'Members'

@admin.register(GroupMember)
class GroupMemberAdmin(admin.ModelAdmin):
    list_display = ['user', 'group', 'get_roles_display', 'joined_date', 'is_active', 'created_at']
    list_filter = ['is_active', 'roles', 'group', 'group__party', 'joined_date', 'created_at']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name', 'group__name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-joined_date']
    fieldsets = (
        ('Membership', {'fields': ('user', 'group', 'roles', 'is_active')}),
        ('Dates', {'fields': ('joined_date', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
        ('Notes', {'fields': ('notes',), 'classes': ('collapse',)}),
    )

    def get_roles_display(self, obj):
        return obj.get_roles_display()
    get_roles_display.short_description = 'Roles'



