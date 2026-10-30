"""Local, on-demand NLP analysis for Echo Journal entries.

The Hugging Face models run on this computer after their weights have been
 downloaded. Journal text is never sent to a hosted inference API by this module.
"""
import json
from functools import lru_cache

EMOTION_MODEL = "j-hartmann/emotion-english-distilroberta-base"
SENTIMENT_MODEL = "cardiffnlp/twitter-roberta-base-sentiment-latest"
MAX_ANALYSIS_CHARS = 4000


class AIUnavailable(RuntimeError):
    """Raised when optional AI dependencies or model loading are unavailable."""


@lru_cache(maxsize=1)
def _pipelines():
    """Load models only when the user explicitly requests analysis."""
    try:
        from transformers import pipeline
    except ImportError as exc:
        raise AIUnavailable(
            "AI packages are not installed. Install the optional requirements-ai.txt dependencies first."
        ) from exc
    try:
        emotion = pipeline("text-classification", model=EMOTION_MODEL, top_k=None)
        sentiment = pipeline("text-classification", model=SENTIMENT_MODEL, top_k=None)
    except Exception as exc:
        # Don't include model input or journal text in the error; keep private content out of logs.
        raise AIUnavailable(
            "The local AI models could not be loaded. Check your internet connection for the first download, "
            "then try again."
        ) from exc
    return emotion, sentiment


def _scores(output):
    """Normalize Transformers pipeline output into a list of label/score dictionaries."""
    if isinstance(output, list) and output and isinstance(output[0], list):
        output = output[0]
    if isinstance(output, dict):
        output = [output]
    return sorted(
        ({"label": str(item["label"]).lower(), "score": round(float(item["score"]), 4)} for item in output),
        key=lambda item: item["score"],
        reverse=True,
    )


def analyze_text(text):
    """Analyze a bounded portion of a journal entry locally and return safe metadata."""
    cleaned = (text or "").strip()
    if not cleaned:
        raise ValueError("Write some text before running AI analysis.")
    sample = cleaned[:MAX_ANALYSIS_CHARS]
    emotion_pipe, sentiment_pipe = _pipelines()
    try:
        emotion_scores = _scores(emotion_pipe(sample, truncation=True))
        sentiment_scores = _scores(sentiment_pipe(sample, truncation=True))
    except Exception as exc:
        raise AIUnavailable("The local AI model could not analyze this entry. Try a shorter entry.") from exc
    return {
        "emotion": emotion_scores[0]["label"],
        "emotion_score": emotion_scores[0]["score"],
        "emotion_scores": emotion_scores[:3],
        "sentiment": sentiment_scores[0]["label"],
        "sentiment_score": sentiment_scores[0]["score"],
        "sentiment_scores": sentiment_scores,
        "model": f"{EMOTION_MODEL} + {SENTIMENT_MODEL}",
        "note": "AI predictions can be wrong. Use these labels for reflection, not as a diagnosis.",
    }


def serialize_analysis(result):
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"))


def deserialize_analysis(raw):
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None
