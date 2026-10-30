from app import repository, security
from tests.base import PASSWORD, AppTestCase


class RegistrationTests(AppTestCase):
    def test_register_page_loads(self):
        response = self.client.get("/register")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Create an account", self.text(response))

    def test_registering_signs_you_in(self):
        response = self.register()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/journal")
        self.assertEqual(self.client.get("/journal").status_code, 200)

    def test_password_is_stored_hashed_never_as_typed(self):
        self.register(password="my secret passphrase")
        with self.app.app_context():
            user = repository.get_user_by_username("alice")
        self.assertNotIn("my secret passphrase", user["password_hash"])
        self.assertTrue(user["password_hash"].startswith(("scrypt:", "pbkdf2:")))

    def test_same_password_gets_a_different_hash_each_time(self):
        self.register("alice")
        self.register("bobby", client=self.app.test_client())
        with self.app.app_context():
            first = repository.get_user_by_username("alice")["password_hash"]
            second = repository.get_user_by_username("bobby")["password_hash"]
        self.assertNotEqual(first, second)

    def test_usernames_are_not_case_sensitive(self):
        self.register("alice")
        response = self.register("Alice ", client=self.app.test_client())
        self.assertEqual(response.status_code, 200)
        self.assertIn("already taken", self.text(response))

    def test_bad_usernames_are_rejected(self):
        for name in ["ab", "has space", "bad!name", "x" * 33, "émile", ""]:
            with self.subTest(name=name):
                response = self.register(name, client=self.app.test_client())
                self.assertEqual(response.status_code, 200)
                self.assertIn("3 to 32 letters", self.text(response))

    def test_weak_or_mismatched_passwords_are_rejected(self):
        cases = {
            "short": ("alice", "short", "short", "at least 10"),
            "mismatch": ("alice", "a long safe password", "a different one!", "don't match"),
            "same as username": ("alicealice1", "alicealice1", "alicealice1", "same as your username"),
        }
        for label, (username, password, confirm, expected) in cases.items():
            with self.subTest(label=label):
                response = self.post(
                    "/register",
                    {"username": username, "password": password, "confirm": confirm},
                    client=self.app.test_client(),
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn(expected, self.plain(response))

    def test_a_rejected_form_keeps_the_username_but_never_the_password(self):
        response = self.post(
            "/register", {"username": "carol", "password": "tiny", "confirm": "tiny"}, client=self.app.test_client()
        )
        html = self.text(response)
        self.assertIn('value="carol"', html)
        self.assertNotIn("tiny", html)

    def test_registration_can_be_closed(self):
        self.app = self.make_app(ALLOW_REGISTRATION=False)
        client = self.app.test_client()
        self.assertEqual(client.get("/register").status_code, 403)
        response = self.post("/register", {"username": "alice", "password": PASSWORD, "confirm": PASSWORD}, client=client)
        self.assertEqual(response.status_code, 403)
        with self.app.app_context():
            self.assertIsNone(repository.get_user_by_username("alice"))


class LoginTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.register(client=self.app.test_client())  # creates "alice", then that browser is thrown away

    def test_login_works(self):
        response = self.login()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get("/journal").status_code, 200)

    def test_login_records_the_time(self):
        self.login()
        with self.app.app_context():
            self.assertIsNotNone(repository.get_user_by_username("alice")["last_login_at"])

    def test_wrong_password_and_unknown_user_look_identical(self):
        wrong_password = self.login(password="not the password at all")
        unknown_user = self.login(username="nobody")
        for response in (wrong_password, unknown_user):
            self.assertEqual(response.status_code, 200)
            self.assertIn("don't match", self.plain(response))
        self.assertEqual(self.plain(wrong_password).count("don't match"), self.plain(unknown_user).count("don't match"))
        self.assertEqual(self.client.get("/journal").status_code, 302)  # still signed out

    def test_logout_ends_the_session(self):
        self.login()
        response = self.post("/logout")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get("/journal").status_code, 302)

    def test_signed_in_visitors_skip_the_login_page(self):
        self.login()
        self.assertEqual(self.client.get("/login").status_code, 302)
        self.assertEqual(self.client.get("/register").status_code, 302)

    def test_redirect_after_login_only_goes_to_this_site(self):
        cases = {
            "/journal/new": "/journal/new",
            "https://evil.example/x": "/journal",
            "//evil.example": "/journal",
            "/\\evil.example": "/journal",
            "javascript:alert(1)": "/journal",
        }
        for target, expected in cases.items():
            with self.subTest(target=target):
                response = self.login(client=self.app.test_client(), next=target)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.headers["Location"], expected)

    def test_protected_pages_send_you_to_login_and_back(self):
        response = self.client.get("/journal/new")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login?next=/journal/new", response.headers["Location"])


class SessionTests(AppTestCase):
    def test_a_deleted_account_cannot_keep_using_an_old_session(self):
        client = self.signed_in_client()
        with self.app.app_context():
            user = repository.get_user_by_username("alice")
            repository.delete_user(user["id"])
        self.assertEqual(client.get("/journal").status_code, 302)

    def test_password_helpers(self):
        with self.app.app_context():
            hashed = security.hash_password("correct horse battery")
            self.assertTrue(security.verify_password("correct horse battery", hashed))
            self.assertFalse(security.verify_password("wrong horse battery", hashed))
