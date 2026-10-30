import os
import unittest
from contextlib import redirect_stderr
from io import StringIO
from unittest import mock

from app import db, repository, security
from app.config import ConfigError, load_config
from tests.base import AppTestCase


class CsrfTests(AppTestCase):
    def test_posts_without_a_token_are_refused(self):
        alice = self.signed_in_client()
        for url in ("/journal/new", "/logout", "/account/delete"):
            with self.subTest(url=url):
                response = alice.post(url, data={"title": "x", "body": "y", "password": "z", "confirm": "DELETE"})
                self.assertEqual(response.status_code, 400)
                self.assertIn("expired", self.text(response))
        for url in ("/login", "/register"):
            with self.subTest(url=url):
                response = self.app.test_client().post(url, data={"username": "alice", "password": "whatever one"})
                self.assertEqual(response.status_code, 400)

    def test_posts_with_a_wrong_token_are_refused_and_change_nothing(self):
        alice = self.signed_in_client()
        self.token(alice)
        response = alice.post("/journal/new", data={"title": "x", "body": "forged", "csrf_token": "wrong"})
        self.assertEqual(response.status_code, 400)
        with self.app.app_context():
            self.assertEqual(repository.count_entries(1), 0)

    def test_the_real_token_from_the_page_works(self):
        client = self.signed_in_client()
        page = self.text(client.get("/journal/new"))
        marker = 'name="csrf_token" value="'
        token = page.split(marker)[1].split('"')[0]
        self.assertGreater(len(token), 30)
        response = client.post("/journal/new", data={"title": "ok", "body": "fine", "csrf_token": token})
        self.assertEqual(response.status_code, 302)

    def test_the_token_is_accepted_in_a_header_too(self):
        client = self.signed_in_client()
        token = self.token(client)
        response = client.post("/journal/new", data={"body": "via header"}, headers={"X-CSRF-Token": token})
        self.assertEqual(response.status_code, 302)


class HeaderAndCookieTests(AppTestCase):
    def test_security_headers_are_on_every_page(self):
        for url in ("/", "/login", "/about", "/healthz", "/does-not-exist"):
            with self.subTest(url=url):
                headers = self.client.get(url).headers
                self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
                self.assertIn("script-src 'self'", headers["Content-Security-Policy"])
                self.assertNotIn("unsafe-inline", headers["Content-Security-Policy"])
                self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
                self.assertEqual(headers["X-Frame-Options"], "DENY")
                self.assertEqual(headers["Referrer-Policy"], "no-referrer")
                self.assertIn("microphone=()", headers["Permissions-Policy"])

    def test_pages_are_not_cached_but_static_files_may_be(self):
        self.assertEqual(self.client.get("/login").headers["Cache-Control"], "no-store")
        alice = self.signed_in_client()
        self.assertEqual(alice.get("/journal").headers["Cache-Control"], "no-store")
        css = self.client.get("/static/css/app.css")
        self.assertEqual(css.status_code, 200)
        self.assertNotEqual(css.headers.get("Cache-Control"), "no-store")
        css.close()

    def test_pages_load_nothing_from_other_websites(self):
        alice = self.signed_in_client()
        self.add_entry(alice, "x", "y")
        for url in ("/", "/login", "/register", "/about", "/journal", "/journal/new", "/account"):
            with self.subTest(url=url):
                html = self.text(alice.get(url))
                self.assertNotIn("http://", html)
                self.assertNotIn("https://", html)
                self.assertNotIn("style=", html)  # inline styles would be blocked by the policy
                self.assertNotIn("onclick", html)

    def test_session_cookie_is_httponly_and_samesite(self):
        cookie = self.client.get("/register").headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)

    def test_production_cookie_and_hsts_settings(self):
        app = self.make_app(
            SESSION_COOKIE_SECURE=True, SESSION_COOKIE_NAME="__Host-echo_session", HSTS_ENABLED=True
        )
        response = app.test_client().get("/register", base_url="https://example.test")
        cookie = response.headers["Set-Cookie"]
        self.assertTrue(cookie.startswith("__Host-echo_session="))
        self.assertIn("Secure", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("max-age=31536000", response.headers["Strict-Transport-Security"])
        self.assertNotIn("Strict-Transport-Security", self.client.get("/register").headers)


class LimitsAndErrorsTests(AppTestCase):
    def test_oversized_requests_get_a_friendly_413(self):
        self.app = self.make_app(MAX_CONTENT_LENGTH=2000)
        client = self.app.test_client()
        self.register(client=client)
        response = self.post("/journal/new", {"title": "big", "body": "x" * 5000}, client=client)
        self.assertEqual(response.status_code, 413)
        self.assertIn("Too much text", self.text(response))

    def test_wrong_method_is_a_friendly_405(self):
        response = self.client.get("/logout")
        self.assertEqual(response.status_code, 405)
        self.assertIn("isn't available", self.plain(response))

    def test_health_check_needs_no_login_and_shows_nothing_private(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})

    def test_disclaimer_is_on_every_page(self):
        for url in ("/", "/login", "/about"):
            with self.subTest(url=url):
                html = self.text(self.client.get(url))
                self.assertIn("tool for self-reflection", html)
                self.assertIn("crisis", html)


class SafeRedirectUnitTests(unittest.TestCase):
    def test_safe_next_url(self):
        good = ["/journal", "/journal/new", "/journal/3/edit"]
        bad = ["", None, "journal", "//evil.example", "https://evil.example", "/\\evil.example", "/ok\nSet-Cookie: x=1", "http:evil"]
        for target in good:
            self.assertEqual(security.safe_next_url(target, "FALLBACK"), target)
        for target in bad:
            self.assertEqual(security.safe_next_url(target, "FALLBACK"), "FALLBACK", target)


class ConfigTests(unittest.TestCase):
    def test_production_refuses_a_missing_or_placeholder_secret_key(self):
        for secret in ("", "change-me"):
            with self.subTest(secret=secret):
                with mock.patch.dict(os.environ, {"APP_ENV": "production", "SECRET_KEY": secret}):
                    with self.assertRaises(ConfigError):
                        load_config()

    def test_production_refuses_a_short_secret_key(self):
        with mock.patch.dict(os.environ, {"APP_ENV": "production", "SECRET_KEY": "short"}):
            with self.assertRaises(ConfigError):
                load_config()

    def test_production_defaults_are_strict(self):
        env = {"APP_ENV": "production", "SECRET_KEY": "k" * 48, "COOKIE_SECURE": ""}
        with mock.patch.dict(os.environ, env):
            config = load_config()
        self.assertTrue(config["SESSION_COOKIE_SECURE"])
        self.assertTrue(config["HSTS_ENABLED"])
        self.assertEqual(config["SESSION_COOKIE_NAME"], "__Host-echo_session")

    def test_development_without_a_secret_key_still_starts(self):
        with mock.patch.dict(os.environ, {"APP_ENV": "development", "SECRET_KEY": "", "COOKIE_SECURE": ""}):
            with redirect_stderr(StringIO()) as note:
                config = load_config()
        self.assertGreaterEqual(len(config["SECRET_KEY"]), 32)
        self.assertIn("SECRET_KEY", note.getvalue())
        self.assertFalse(config["SESSION_COOKIE_SECURE"])

    def test_database_url_is_checked(self):
        self.assertTrue(str(db.database_path("sqlite:///x.db", "/inst")).replace("\\", "/").endswith("/inst/x.db"))
        for bad in ("postgresql://u:p@host/db", "postgres://u:p@host/db", "mysql://x", "sqlite:///:memory:"):
            with self.subTest(url=bad):
                with self.assertRaises(db.DatabaseConfigError):
                    db.database_path(bad, "/inst")


if __name__ == "__main__":
    unittest.main()
