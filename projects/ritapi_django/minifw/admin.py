from django.contrib import admin
from .models import MiniFWEvent, MiniFWBlockedIP


@admin.register(MiniFWEvent)
class MiniFWEventAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'client_ip', 'domain', 'action', 'score', 'segment')
    list_filter = ('action', 'segment', 'timestamp')
    search_fields = ('client_ip', 'domain')
    readonly_fields = ('timestamp', 'segment', 'client_ip', 'domain', 'action', 'score', 'reasons')
    ordering = ('-timestamp',)


@admin.register(MiniFWBlockedIP)
class MiniFWBlockedIPAdmin(admin.ModelAdmin):
    list_display = ('ip_address', 'segment', 'blocked_at', 'expires_at', 'score', 'auto_blocked')
    list_filter = ('segment', 'auto_blocked', 'blocked_at')
    search_fields = ('ip_address',)
    readonly_fields = ('blocked_at',)
    ordering = ('-blocked_at',)
