import json
import logging
import uuid
from backend.services.cache_service import get_redis

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# Conversation settings
# ─────────────────────────────────────────
MAX_HISTORY = 10          # max messages to keep
TTL_SECONDS = 24 * 60 * 60  # 24 hours — conversation expires if inactive


def generate_session_id() -> str:
    """Generates a unique session ID for a new conversation."""
    return str(uuid.uuid4())


def get_conversation_key(session_id: str) -> str:
    """Returns Redis key for a session."""
    return f"conversation:{session_id}"


def get_history(session_id: str) -> list[dict]:
    """
    Fetches conversation history from Redis.
    Returns list of {role, content} dicts.
    Returns empty list if session doesn't exist.
    """
    try:
        client = get_redis()
        key = get_conversation_key(session_id)
        raw = client.get(key)

        if not raw:
            return []

        history = json.loads(raw)  # type: ignore
        logger.info(
            f"Loaded {len(history)} messages "
            f"for session: {session_id[:8]}..."
        )
        return history

    except Exception as e:
        logger.error(f"Error loading conversation history: {e}")
        return []


def save_message(
    session_id: str,
    role: str,
    content: str
) -> None:
    """
    Appends a message to conversation history.
    Keeps only last MAX_HISTORY messages.
    Resets TTL on every message — conversation
    stays alive as long as user is active.
    """
    try:
        client = get_redis()
        key = get_conversation_key(session_id)

        # Load existing history
        history = get_history(session_id)

        # Append new message
        history.append({
            "role": role,
            "content": content
        })

        # Keep only last MAX_HISTORY messages
        # Trim from the front — oldest messages removed first
        if len(history) > MAX_HISTORY:
            history = history[-MAX_HISTORY:]

        # Save back to Redis with refreshed TTL
        client.setex(
            name=key,
            time=TTL_SECONDS,
            value=json.dumps(history)
        )

        logger.info(
            f"Saved {role} message for "
            f"session: {session_id[:8]}... "
            f"(history: {len(history)} messages)"
        )

    except Exception as e:
        logger.error(f"Error saving conversation message: {e}")


def clear_conversation(session_id: str) -> bool:
    """
    Clears conversation history for a session.
    Returns True if session existed and was cleared.
    """
    try:
        client = get_redis()
        key = get_conversation_key(session_id)
        deleted = client.delete(key)
        logger.info(f"Cleared conversation: {session_id[:8]}...")
        return deleted > 0  # type: ignore
    except Exception as e:
        logger.error(f"Error clearing conversation: {e}")
        return False


def get_conversation_stats(session_id: str) -> dict:
    """Returns stats about a conversation session."""
    try:
        client = get_redis()
        key = get_conversation_key(session_id)
        history = get_history(session_id)
        ttl = client.ttl(key)
        return {
            "session_id": session_id,
            "message_count": len(history),
            "max_history": MAX_HISTORY,
            "ttl_seconds": ttl,
            "ttl_hours": round(ttl / 3600, 1) if ttl > 0 else 0  # type: ignore
        }
    except Exception as e:
        logger.error(f"Error getting conversation stats: {e}")
        return {"error": str(e)}