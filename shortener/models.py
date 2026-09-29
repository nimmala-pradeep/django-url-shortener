from django.db import models
from django.utils import timezone


class Link(models.Model):
    original_url = models.URLField(max_length=2048)
    code = models.CharField(max_length=32, unique=True)  # unique => indexed
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    click_count = models.PositiveIntegerField(default=0)
    last_accessed = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} -> {self.original_url}"

    @property
    def is_expired(self):
        return self.expires_at is not None and self.expires_at <= timezone.now()


class Click(models.Model):
    """One row per visit, used for the per-day analytics."""

    link = models.ForeignKey(Link, on_delete=models.CASCADE, related_name="clicks")
    clicked_at = models.DateTimeField(auto_now_add=True, db_index=True)
    referrer = models.CharField(max_length=500, blank=True)

    def __str__(self):
        return f"{self.link.code} @ {self.clicked_at:%Y-%m-%d %H:%M}"
