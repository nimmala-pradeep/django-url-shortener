import json
from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import Click, Link


class ShortenerTests(TestCase):
    def setUp(self):
        cache.clear()

    def post(self, **body):
        return self.client.post("/api/shorten", data=json.dumps(body), content_type="application/json")

    def test_creates_link_with_generated_code(self):
        res = self.post(url="https://example.com/some/long/path")
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(len(data["code"]), 6)
        self.assertTrue(data["short_url"].endswith("/" + data["code"]))

    def test_rejects_invalid_urls(self):
        for bad in ["", "not a url", "ftp://example.com/file", "javascript:alert(1)"]:
            with self.subTest(url=bad):
                self.assertEqual(self.post(url=bad).status_code, 400)

    def test_rejects_links_to_itself(self):
        self.assertEqual(self.post(url="http://testserver/abc").status_code, 400)

    def test_custom_alias_and_duplicate(self):
        self.assertEqual(self.post(url="https://example.com", alias="my-link").status_code, 201)
        self.assertEqual(self.post(url="https://example.org", alias="my-link").status_code, 409)

    def test_invalid_and_reserved_alias(self):
        self.assertEqual(self.post(url="https://example.com", alias="a").status_code, 400)
        self.assertEqual(self.post(url="https://example.com", alias="has space").status_code, 400)
        self.assertEqual(self.post(url="https://example.com", alias="admin").status_code, 400)

    def test_expiry_validation(self):
        self.assertEqual(self.post(url="https://example.com", expires_in_days=0).status_code, 400)
        self.assertEqual(self.post(url="https://example.com", expires_in_days=999).status_code, 400)
        self.assertEqual(self.post(url="https://example.com", expires_in_days="x").status_code, 400)
        res = self.post(url="https://example.com", expires_in_days=7)
        self.assertEqual(res.status_code, 201)
        self.assertIsNotNone(res.json()["expires_at"])

    def test_bad_json(self):
        res = self.client.post("/api/shorten", data="{nope", content_type="application/json")
        self.assertEqual(res.status_code, 400)

    def test_redirect_counts_clicks(self):
        Link.objects.create(original_url="https://example.com/target", code="abc123")
        res = self.client.get("/abc123", HTTP_REFERER="https://news.example")
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res["Location"], "https://example.com/target")
        link = Link.objects.get(code="abc123")
        self.assertEqual(link.click_count, 1)
        self.assertIsNotNone(link.last_accessed)
        self.assertEqual(Click.objects.filter(link=link).count(), 1)

    def test_unknown_code_is_404(self):
        self.assertEqual(self.client.get("/nope123").status_code, 404)

    def test_expired_link_is_410_and_not_counted(self):
        Link.objects.create(
            original_url="https://example.com", code="old", expires_at=timezone.now() - timedelta(minutes=1)
        )
        self.assertEqual(self.client.get("/old").status_code, 410)
        self.assertEqual(Link.objects.get(code="old").click_count, 0)

    def test_stats_endpoint(self):
        Link.objects.create(original_url="https://example.com", code="stat1")
        self.client.get("/stat1")
        self.client.get("/stat1")
        data = self.client.get("/api/stats/stat1").json()
        self.assertEqual(data["click_count"], 2)
        self.assertEqual(len(data["last_7_days"]), 7)
        self.assertEqual(data["last_7_days"][-1]["clicks"], 2)
        self.assertEqual(self.client.get("/api/stats/missing").status_code, 404)

    @override_settings(RATE_LIMIT_MAX=3)
    def test_rate_limit(self):
        codes = [self.post(url="https://example.com").status_code for _ in range(5)]
        self.assertEqual(codes, [201, 201, 201, 429, 429])

    def test_home_page_renders(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Shorten link")
