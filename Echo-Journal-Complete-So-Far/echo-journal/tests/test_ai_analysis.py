"""Milestone 2 route/privacy tests. Model inference is mocked to keep tests fast/offline."""
import json
from unittest.mock import patch

from .base import AppTestCase


class AIAnalysisTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.alice = self.signed_in_client("alice")
        self.entry_id = self.add_entry(self.alice, "Reflection", "I feel happy about finishing my assignment.")
        self.result = {
            "emotion": "joy",
            "emotion_score": 0.91,
            "emotion_scores": [{"label": "joy", "score": 0.91}],
            "sentiment": "positive",
            "sentiment_score": 0.96,
            "sentiment_scores": [{"label": "positive", "score": 0.96}],
            "model": "test-emotion + test-sentiment",
            "note": "AI predictions can be wrong. Use these labels for reflection, not as a diagnosis.",
        }

    @patch("app.ai_analysis.analyze_text")
    def test_owner_can_analyze_and_see_saved_results(self, analyze_text):
        analyze_text.return_value = self.result
        response = self.post(f"/journal/{self.entry_id}/analyze", client=self.alice)
        self.assertEqual(response.status_code, 302)
        page = self.alice.get(f"/journal/{self.entry_id}")
        self.assertEqual(page.status_code, 200)
        body = self.text(page)
        self.assertIn("Positive", body)
        self.assertIn("Joy", body)
        self.assertIn("not a diagnosis", body)

    @patch("app.ai_analysis.analyze_text")
    def test_model_unavailable_does_not_break_entry_view(self, analyze_text):
        from app.ai_analysis import AIUnavailable
        analyze_text.side_effect = AIUnavailable("Optional AI dependencies are missing.")
        response = self.post(f"/journal/{self.entry_id}/analyze", client=self.alice)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.alice.get(f"/journal/{self.entry_id}").status_code, 200)

    @patch("app.ai_analysis.analyze_text")
    def test_other_user_cannot_analyze_entry(self, analyze_text):
        bob = self.signed_in_client("bob")
        response = self.post(f"/journal/{self.entry_id}/analyze", client=bob)
        self.assertEqual(response.status_code, 404)
        analyze_text.assert_not_called()

    def test_analysis_endpoint_requires_login(self):
        response = self.client.post(f"/journal/{self.entry_id}/analyze")
        self.assertIn(response.status_code, (302, 400))

    def test_analysis_json_is_not_in_journal_exports(self):
        response = self.alice.get("/journal/export.json")
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.get_data(as_text=True))
        self.assertNotIn("analysis_json", payload["entries"][0])
