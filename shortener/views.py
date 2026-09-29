import json
from datetime import timedelta

from django.db import IntegrityError
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import Click, Link
from .utils import (
    client_ip,
    generate_code,
    is_rate_limited,
    validate_alias,
    validate_target_url,
)


def _error(message, status):
    return JsonResponse({"error": message}, status=status)


def _link_payload(request, link):
    return {
        "code": link.code,
        "short_url": request.build_absolute_uri(f"/{link.code}"),
        "original_url": link.original_url,
        "created_at": link.created_at.isoformat(),
        "expires_at": link.expires_at.isoformat() if link.expires_at else None,
    }


def index(request):
    return render(request, "shortener/index.html")


@require_POST
def shorten(request):
    if is_rate_limited(client_ip(request)):
        return _error("Too many requests. Wait a minute and try again.", 429)

    try:
        data = json.loads(request.body or b"{}")
        if not isinstance(data, dict):
            raise ValueError
    except ValueError:
        return _error("Request body must be a JSON object.", 400)

    url = str(data.get("url") or "").strip()
    alias = str(data.get("alias") or "").strip()
    days = data.get("expires_in_days")

    problem = validate_target_url(url, request.get_host())
    if problem:
        return _error(problem, 400)

    expires_at = None
    if days not in (None, ""):
        try:
            days = int(days)
        except (TypeError, ValueError):
            return _error("Expiry must be a whole number of days.", 400)
        if not 1 <= days <= 365:
            return _error("Expiry must be between 1 and 365 days.", 400)
        expires_at = timezone.now() + timedelta(days=days)

    if alias:
        problem = validate_alias(alias)
        if problem:
            return _error(problem, 400)
        try:
            link = Link.objects.create(original_url=url, code=alias, expires_at=expires_at)
        except IntegrityError:
            return _error("That alias is taken. Pick another.", 409)
    else:
        link = None
        for _ in range(5):  # retry on the rare code collision
            try:
                link = Link.objects.create(
                    original_url=url, code=generate_code(), expires_at=expires_at
                )
                break
            except IntegrityError:
                continue
        if link is None:
            return _error("Could not generate a unique code. Try again.", 500)

    return JsonResponse(_link_payload(request, link), status=201)


def follow(request, code):
    try:
        link = Link.objects.get(code=code)
    except Link.DoesNotExist:
        return not_found(request)

    if link.is_expired:
        return render(
            request,
            "shortener/notice.html",
            {"title": "This link has expired", "message": "The owner set it to stop working after a certain date."},
            status=410,
        )

    Link.objects.filter(pk=link.pk).update(
        click_count=F("click_count") + 1, last_accessed=timezone.now()
    )
    Click.objects.create(link=link, referrer=request.META.get("HTTP_REFERER", "")[:500])
    return redirect(link.original_url)  # 302, so every visit is counted


@require_GET
def stats(request, code):
    try:
        link = Link.objects.get(code=code)
    except Link.DoesNotExist:
        return _error("No link with that code.", 404)

    today = timezone.now().date()
    start = today - timedelta(days=6)
    counts = {}
    for clicked_at in link.clicks.filter(clicked_at__date__gte=start).values_list("clicked_at", flat=True):
        day = clicked_at.date()
        counts[day] = counts.get(day, 0) + 1
    last_7_days = [
        {"date": (start + timedelta(days=i)).isoformat(), "clicks": counts.get(start + timedelta(days=i), 0)}
        for i in range(7)
    ]

    payload = _link_payload(request, link)
    payload.update(
        {
            "click_count": link.click_count,
            "last_accessed": link.last_accessed.isoformat() if link.last_accessed else None,
            "expired": link.is_expired,
            "last_7_days": last_7_days,
        }
    )
    return JsonResponse(payload)


def not_found(request, exception=None):
    return render(
        request,
        "shortener/notice.html",
        {"title": "Link not found", "message": "Check the address for typos, or create a new short link."},
        status=404,
    )
