import re
import secrets
import string

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator

ALPHABET = string.ascii_letters + string.digits
ALIAS_RE = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
# Paths the app already uses, so an alias can't shadow them.
RESERVED = {"admin", "api", "static", "stats"}

_url_validator = URLValidator(schemes=["http", "https"])


def generate_code(length=6):
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def validate_target_url(url, own_host):
    """Return an error message, or None if the URL is acceptable."""
    if not url:
        return "Enter a URL to shorten."
    if len(url) > 2048:
        return "That URL is too long (2048 characters max)."
    try:
        _url_validator(url)
    except ValidationError:
        return "Enter a valid URL that starts with http:// or https://."
    host = url.split("://", 1)[1].split("/", 1)[0].split("@")[-1].split(":")[0].lower()
    if host == own_host.split(":")[0].lower():
        return "That link already points to this site."
    return None


def validate_alias(alias):
    if not ALIAS_RE.match(alias):
        return "Aliases use 3 to 32 letters, numbers, hyphens or underscores."
    if alias.lower() in RESERVED:
        return "That alias is reserved. Pick another."
    return None


def client_ip(request):
    # Behind a proxy (Render, Railway...) use the proxy's forwarded header instead.
    return request.META.get("REMOTE_ADDR", "unknown")


def is_rate_limited(ip):
    key = f"rl:{ip}"
    cache.add(key, 0, settings.RATE_LIMIT_WINDOW_SECONDS)
    try:
        count = cache.incr(key)
    except ValueError:  # key expired between add and incr
        cache.set(key, 1, settings.RATE_LIMIT_WINDOW_SECONDS)
        count = 1
    return count > settings.RATE_LIMIT_MAX
