"""
rag/preferences.py
───────────────────
Seeds your personal preferences into the RAG database.
Run once:  python -m rag.preferences

Add new preferences here anytime and re-run to update.
"""
from rag.store import store_preference

PREFERENCES = [
    # ── Task duration preferences ─────────────────────────────────────────────
    {
        "id":       "pref_hair",
        "text":     "Getting hair done takes 2 hours, not 30-60 minutes. Always schedule 2h for this task.",
        "metadata": {"category": "task_duration", "task": "hair"},
    },
    {
        "id":       "pref_coding",
        "text":     "Coding and building systems takes more than 2 hours. Deep work coding sessions should be at least 2-3 hours. Never schedule coding in short 30-60 min blocks.",
        "metadata": {"category": "task_duration", "task": "coding"},
    },

    # ── Daily routine preferences ─────────────────────────────────────────────
    {
        "id":       "pref_shower_timing",
        "text":     "Prefers taking shower in the evening or at night, not in the morning. Morning shower + bathroom routine should be rescheduled to evening if possible.",
        "metadata": {"category": "routine", "task": "shower"},
    },

    # ── Content preferences ───────────────────────────────────────────────────
    {
        "id":       "pref_islamic_videos",
        "text":     "Loves watching Islamic videos in English for personal growth and getting around sins. Preferred podcast/video content should be in English and focus on personal development, avoiding sins, and spiritual growth.",
        "metadata": {"category": "content", "type": "islamic_videos"},
    },

    # ── Work style ────────────────────────────────────────────────────────────
    {
        "id":       "pref_deep_work",
        "text":     "Deep work tasks like coding and building systems require long uninterrupted blocks of 2-3 hours minimum. Do not break coding sessions into short blocks.",
        "metadata": {"category": "work_style", "task": "deep_work"},
    },
]


def seed():
    print("Seeding personal preferences into RAG database...")
    for p in PREFERENCES:
        store_preference(p["id"], p["text"], p["metadata"])
        print(f"  ✓ Stored: {p['id']}")
    print(f"\nDone! {len(PREFERENCES)} preferences stored.")


if __name__ == "__main__":
    seed()