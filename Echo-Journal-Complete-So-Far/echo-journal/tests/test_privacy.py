import logging

from app import repository
from tests.base import AppTestCase

SECRET_WORDS = "a-very-private-sentence-xyzzy"


class OtherPeopleCannotSeeMyEntries(AppTestCase):
    def setUp(self):
        super().setUp()
        self.alice = self.signed_in_client("alice")
        self.bob = self.signed_in_client("bobby")
        self.entry_id = self.add_entry(self.alice, "Alice's page", SECRET_WORDS)

    def test_other_users_get_404_for_view_edit_and_delete(self):
        for url in (
            f"/journal/{self.entry_id}",
            f"/journal/{self.entry_id}/edit",
            f"/journal/{self.entry_id}/delete",
        ):
            with self.subTest(url=url):
                response = self.bob.get(url)
                self.assertEqual(response.status_code, 404)
                self.assertNotIn(SECRET_WORDS, self.text(response))

    def test_other_users_cannot_change_or_delete_it(self):
        edit = self.post(f"/journal/{self.entry_id}/edit", {"title": "hacked", "body": "hacked"}, client=self.bob)
        delete = self.post(f"/journal/{self.entry_id}/delete", client=self.bob)
        self.assertEqual(edit.status_code, 404)
        self.assertEqual(delete.status_code, 404)
        with self.app.app_context():
            entry = repository.get_entry(1, self.entry_id)
        self.assertEqual(entry["body"], SECRET_WORDS)

    def test_lists_and_search_only_cover_my_own_entries(self):
        self.assertNotIn(SECRET_WORDS, self.text(self.bob.get("/journal")))
        self.assertNotIn("Alice's page", self.text(self.bob.get("/journal?q=xyzzy")))
        self.assertIn("No entries match", self.text(self.bob.get("/journal?q=xyzzy")))

    def test_the_repository_has_no_way_to_read_an_entry_without_its_owner(self):
        with self.app.app_context():
            self.assertIsNone(repository.get_entry(2, self.entry_id))  # bobby is user 2
            self.assertEqual(repository.count_entries(2), 0)
            self.assertEqual(repository.all_entries(2), [])

    def test_logged_out_visitors_see_nothing(self):
        stranger = self.app.test_client()
        for url in (
            "/journal",
            "/journal/new",
            f"/journal/{self.entry_id}",
            f"/journal/{self.entry_id}/edit",
            f"/journal/{self.entry_id}/delete",
            "/journal/export.json",
            "/journal/export.md",
            "/account",
        ):
            with self.subTest(url=url):
                response = stranger.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login", response.headers["Location"])

    def test_logged_out_posts_do_nothing(self):
        stranger = self.app.test_client()
        response = self.post("/journal/new", {"title": "x", "body": "sneaky"}, client=stranger)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])
        with self.app.app_context():
            self.assertEqual(repository.count_entries(1), 1)


class AccountDeletionTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.alice = self.signed_in_client("alice")
        self.bob = self.signed_in_client("bobby")
        self.add_entry(self.alice, "A1", "alice one")
        self.add_entry(self.alice, "A2", "alice two")
        self.add_entry(self.bob, "B1", "bobby one")

    def delete(self, client, password="a long safe password", confirm="DELETE"):
        return self.post("/account/delete", {"password": password, "confirm": confirm}, client=client)

    def test_wrong_password_or_missing_confirmation_deletes_nothing(self):
        for kwargs in ({"password": "nope nope nope"}, {"confirm": "yes"}, {"confirm": ""}):
            with self.subTest(**kwargs):
                response = self.delete(self.alice, **kwargs)
                self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertIsNotNone(repository.get_user_by_username("alice"))
            self.assertEqual(repository.count_entries(1), 2)

    def test_deleting_the_account_removes_the_person_and_all_their_entries_only(self):
        response = self.delete(self.alice)
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            self.assertIsNone(repository.get_user_by_username("alice"))
            self.assertEqual(repository.count_entries(1), 0)
            self.assertEqual(repository.count_entries(2), 1)  # bobby is untouched
        self.assertEqual(self.alice.get("/journal").status_code, 302)  # signed out

    def test_a_new_account_with_the_same_name_starts_empty(self):
        self.delete(self.alice)
        again = self.signed_in_client("alice")
        self.assertIn("Write your first entry", self.text(again.get("/journal")))

    def test_account_page_shows_exports_and_counts(self):
        html = self.text(self.alice.get("/account"))
        self.assertIn("alice", html)
        self.assertIn("/journal/export.json", html)
        self.assertIn("Delete your account", html)


class LoggingTests(AppTestCase):
    def test_journal_text_is_never_written_to_the_logs(self):
        lines = []

        class Capture(logging.Handler):
            def emit(self, record):
                lines.append(record.getMessage())

        handler = Capture(level=logging.DEBUG)
        root = logging.getLogger()
        previous_level = root.level
        root.addHandler(handler)
        root.setLevel(logging.DEBUG)
        try:
            alice = self.signed_in_client("alice")
            entry_id = self.add_entry(alice, "Title-for-log-test", SECRET_WORDS)
            alice.get(f"/journal/{entry_id}")
            alice.get(f"/journal?q={SECRET_WORDS}")
            alice.get("/journal/export.json")
        finally:
            root.removeHandler(handler)
            root.setLevel(previous_level)
        joined = "\n".join(lines)
        self.assertNotIn(SECRET_WORDS, joined)
        self.assertNotIn("Title-for-log-test", joined)
