import json

from app import repository
from tests.base import AppTestCase


class EntryTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.alice = self.signed_in_client("alice")

    def test_write_read_and_list_an_entry(self):
        entry_id = self.add_entry(self.alice, "Monday", "Walked home the long way.")
        page = self.text(self.alice.get(f"/journal/{entry_id}"))
        self.assertIn("Monday", page)
        self.assertIn("Walked home the long way.", page)
        listing = self.text(self.alice.get("/journal"))
        self.assertIn("Monday", listing)
        self.assertIn("Walked home", listing)

    def test_an_entry_needs_some_text(self):
        for body in ["", "   \n  "]:
            with self.subTest(body=body):
                response = self.post("/journal/new", {"title": "x", "body": body}, client=self.alice)
                self.assertEqual(response.status_code, 200)
                self.assertIn("Write something", self.text(response))

    def test_limits_are_enforced_and_the_text_is_kept_on_screen(self):
        response = self.post("/journal/new", {"title": "T" * 121, "body": "short"}, client=self.alice)
        self.assertIn("Titles can be up to 120", self.text(response))
        response = self.post("/journal/new", {"title": "ok", "body": "z" * 20_001}, client=self.alice)
        self.assertIn("up to 20,000", self.text(response))
        self.assertIn("zzzz", self.text(response))  # nothing the person typed is thrown away
        with self.app.app_context():
            self.assertEqual(repository.count_entries(1), 0)

    def test_line_endings_and_title_whitespace_are_tidied(self):
        entry_id = self.add_entry(self.alice, "  spaced\n title  ", "one\r\ntwo\rthree")
        with self.app.app_context():
            entry = repository.get_entry(1, entry_id)
        self.assertEqual(entry["title"], "spaced title")
        self.assertEqual(entry["body"], "one\ntwo\nthree")

    def test_edit_changes_the_entry(self):
        entry_id = self.add_entry(self.alice, "Before", "old words")
        self.assertEqual(self.alice.get(f"/journal/{entry_id}/edit").status_code, 200)
        response = self.post(f"/journal/{entry_id}/edit", {"title": "After", "body": "new words"}, client=self.alice)
        self.assertEqual(response.status_code, 302)
        page = self.text(self.alice.get(f"/journal/{entry_id}"))
        self.assertIn("After", page)
        self.assertIn("new words", page)
        self.assertNotIn("old words", page)

    def test_delete_asks_first_and_get_never_deletes(self):
        entry_id = self.add_entry(self.alice, "Doomed", "bye")
        confirm = self.alice.get(f"/journal/{entry_id}/delete")
        self.assertEqual(confirm.status_code, 200)
        self.assertIn("can't be undone", self.text(confirm))
        self.assertEqual(self.alice.get(f"/journal/{entry_id}").status_code, 200)  # still there
        response = self.post(f"/journal/{entry_id}/delete", client=self.alice)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.alice.get(f"/journal/{entry_id}").status_code, 404)

    def test_entries_are_shown_as_text_never_as_html(self):
        attack = "<script>alert(1)</script><img src=x onerror=alert(2)>"
        entry_id = self.add_entry(self.alice, "<b>bold</b>", attack)
        for url in (f"/journal/{entry_id}", "/journal", f"/journal/{entry_id}/edit", f"/journal/{entry_id}/delete"):
            with self.subTest(url=url):
                html = self.text(self.alice.get(url))
                self.assertNotIn("<script>alert(1)</script>", html)
                self.assertNotIn("<img src=x", html)
                self.assertNotIn("<b>bold</b>", html)

    def test_unknown_entry_is_a_friendly_404(self):
        response = self.alice.get("/journal/99999")
        self.assertEqual(response.status_code, 404)
        self.assertIn("Page not found", self.text(response))


class SearchAndPagingTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.alice = self.signed_in_client("alice")

    def test_search_finds_titles_and_text_ignoring_case(self):
        self.add_entry(self.alice, "Garden", "Planted TOMATOES today.")
        self.add_entry(self.alice, "Tomato soup", "Tasted great.")
        self.add_entry(self.alice, "Other", "Nothing relevant.")
        html = self.text(self.alice.get("/journal?q=tomato"))
        self.assertIn("Garden", html)
        self.assertIn("Tomato soup", html)
        self.assertNotIn("Nothing relevant", html)
        self.assertIn("2 entries match", html)

    def test_percent_and_underscore_are_searched_literally(self):
        self.add_entry(self.alice, "Percent", "I was 100% sure.")
        self.add_entry(self.alice, "Plain", "I was 1000 sure.")
        self.add_entry(self.alice, "Under", "snake_case here")
        self.add_entry(self.alice, "Other", "snakeXcase here")
        percent = self.text(self.alice.get("/journal?q=100%25"))
        self.assertIn("Percent", percent)
        self.assertNotIn("Plain", percent)
        under = self.text(self.alice.get("/journal?q=snake_case"))
        self.assertIn("Under", under)
        self.assertNotIn("Other", under)

    def test_search_with_no_matches_says_so(self):
        self.add_entry(self.alice, "A", "hello")
        self.assertIn("No entries match", self.text(self.alice.get("/journal?q=zzz")))

    def test_pagination(self):
        for number in range(25):
            self.add_entry(self.alice, f"Entry {number:02d}", "text")
        first = self.text(self.alice.get("/journal"))
        self.assertEqual(first.count('class="entry-link"'), 10)
        self.assertIn("Entry 24", first)  # newest first
        self.assertIn("Page 1 of 3", first)
        last = self.text(self.alice.get("/journal?page=3"))
        self.assertEqual(last.count('class="entry-link"'), 5)
        self.assertIn("Entry 00", last)

    def test_odd_page_numbers_do_not_break_anything(self):
        self.add_entry(self.alice, "A", "hello")
        for page in ["abc", "-4", "0", "999999", "9" * 5000, ""]:
            with self.subTest(page=page):
                self.assertEqual(self.alice.get(f"/journal?page={page}").status_code, 200)

    def test_empty_journal_invites_a_first_entry(self):
        self.assertIn("Write your first entry", self.text(self.alice.get("/journal")))


class ExportTests(AppTestCase):
    def test_json_export_has_only_my_entries(self):
        alice = self.signed_in_client("alice")
        bob = self.signed_in_client("bobby")
        self.add_entry(alice, "Mine", "alice wrote this — café ☕")
        self.add_entry(bob, "Theirs", "bobby secret text")
        response = alice.get("/journal/export.json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response.headers["Content-Disposition"])
        self.assertIn(".json", response.headers["Content-Disposition"])
        data = json.loads(self.text(response))
        self.assertEqual(data["entry_count"], 1)
        self.assertEqual(data["entries"][0]["title"], "Mine")
        self.assertIn("café ☕", data["entries"][0]["body"])
        self.assertNotIn("bobby secret text", self.text(response))
        self.assertNotIn("password", self.text(response).lower())

    def test_markdown_export(self):
        alice = self.signed_in_client("alice")
        self.add_entry(alice, "First", "hello there")
        self.add_entry(alice, "", "no title here")
        response = alice.get("/journal/export.md")
        text = self.text(response)
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response.headers["Content-Disposition"])
        self.assertIn("## First", text)
        self.assertIn("## Untitled", text)
        self.assertLess(text.index("hello there"), text.index("no title here"))  # oldest first
