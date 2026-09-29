from django.contrib import admin

from .models import Click, Link


@admin.register(Link)
class LinkAdmin(admin.ModelAdmin):
    list_display = ("code", "original_url", "click_count", "created_at", "expires_at")
    search_fields = ("code", "original_url")


@admin.register(Click)
class ClickAdmin(admin.ModelAdmin):
    list_display = ("link", "clicked_at", "referrer")
