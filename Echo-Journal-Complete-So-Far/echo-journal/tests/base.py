"""Shared helpers for the tests. Every test gets a brand-new app with an empty database."""
import html
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from app import create_app

PASSWORD = "a long safe password"


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self._folder = tempfile.mkdtemp(prefix="echo-journal-test-")
        self.app = self.make_app()
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self._folder, ignore_errors=True)

    def make_app(self, **settings):
        database = Path(self._folder, "test.db").as_posix()
        config = {
            "TESTING": True,
            "SECRET_KEY": "test-secret-key-" + "x" * 32,
            "DATABASE_URL": f"sqlite:///{database}",
            "PASSWORD_HASH_METHOD": "pbkdf2:sha256:1000",  # fast; for tests only
            "ALLOW_REGISTRATION": True,
            "AUTO_MIGRATE": True,
            "SESSION_COOKIE_NAME": "echo_session",
            "SESSION_COOKIE_SECURE": False,
            "HSTS_ENABLED": False,
            "TRUST_PROXY_HEADERS": False,
        }
        config.update(settings)
        return create_app(config)

    # --- helpers -----------------------------------------------------------

    def token(self, client=None):
        """Put a CSRF token in the client's session and return it (what a real page form does)."""
        client = client or self.client
        with client.session_transaction() as session:
            session.setdefault("_csrf", "test-token-" + "0" * 30)
            return session["_csrf"]

    def post(self, url, data=None, client=None, **kwargs):
        client = client or self.client
        form = dict(data or {})
        form.setdefault("csrf_token", self.token(client))
        return client.post(url, data=form, **kwargs)

    def register(self, username="alice", password=PASSWORD, client=None):
        return self.post(
            "/register", {"username": username, "password": password, "confirm": password}, client=client
        )

    def login(self, username="alice", password=PASSWORD, client=None, **extra):
        return self.post("/login", {"username": username, "password": password, **extra}, client=client)

    def signed_in_client(self, username="alice", password=PASSWORD):
        """A new browser that has just created an account and is signed in."""
        client = self.app.test_client()
        response = self.register(username, password, client=client)
        self.assertEqual(response.status_code, 302, response.get_data(as_text=True))
        return client

    def add_entry(self, client, title="", body="Some thoughts."):
        response = self.post("/journal/new", {"title": title, "body": body}, client=client)
        self.assertEqual(response.status_code, 302, response.get_data(as_text=True))
        return int(re.search(r"/journal/(\d+)$", response.headers["Location"]).group(1))

    def text(self, response):
        """The raw HTML. Use this when checking that something was escaped."""
        return response.get_data(as_text=True)

    def plain(self, response):
        """The HTML with entities decoded (&#39; becomes '). Use this to check readable messages."""
        return html.unescape(response.get_data(as_text=True))
