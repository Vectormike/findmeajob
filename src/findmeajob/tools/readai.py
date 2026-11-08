from typing import Any

TRANSCRIPT_LIMIT = 30000


def _texts(items: Any) -> list[str]:
    return [item.get("text", "") if isinstance(item, dict) else str(item) for item in items or []]


def read_meeting_notes(payload: dict[str, Any]) -> dict[str, Any]:
    """Turn a Read AI meeting webhook payload into the notes Critic reads."""
    transcript = payload.get("transcript") or {}
    blocks = transcript.get("speaker_blocks", []) if isinstance(transcript, dict) else []
    lines = [f"{(block.get('speaker') or {}).get('name', 'Speaker')}: {block.get('words', '')}" for block in blocks]
    return {
        "session_id": payload.get("session_id", ""),
        "title": payload.get("title", ""),
        "start_time": payload.get("start_time", ""),
        "participants": [
            {"name": person.get("name", ""), "email": (person.get("email") or "").lower()}
            for person in payload.get("participants", [])
        ],
        "summary": payload.get("summary", ""),
        "action_items": _texts(payload.get("action_items")),
        "key_questions": _texts(payload.get("key_questions")),
        "report_url": payload.get("report_url", ""),
        "transcript": "\n".join(lines)[:TRANSCRIPT_LIMIT],
    }
