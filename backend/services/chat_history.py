"""
Chat History Service with Vector Database (ChromaDB)
Provides persistent chat storage with semantic search, isolated per datasource.
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

# ChromaDB configuration
CHROMA_DB_DIR = Path(__file__).parent.parent / "chroma_db"

# ChromaDB client and the embedding model are heavy (ChromaDB, torch, a ~120MB
# model download). They are initialised lazily on first use so that importing this
# module — and the app — does not require them (keeps imports/CI fast and offline-safe).
_chroma_client = None
_embedding_model = None


def _get_chroma_client():
    """Lazily create the persistent ChromaDB client."""
    global _chroma_client
    if _chroma_client is None:
        import chromadb
        CHROMA_DB_DIR.mkdir(exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
        logger.info(f"ChromaDB initialized at: {CHROMA_DB_DIR}")
    return _chroma_client


def _get_embedding_model():
    """Lazily load the sentence-transformers embedding model."""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        # all-MiniLM-L6-v2: 384 dimensions, ~120MB, good performance
        _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info("Embedding model loaded: all-MiniLM-L6-v2")
    return _embedding_model


class ChatMessage:
    """Chat message with metadata"""
    def __init__(
        self,
        message_id: str,
        ds_id: str,
        session_id: str,
        role: str,
        content: str,
        sql_context: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ):
        self.message_id = message_id
        self.ds_id = ds_id
        self.session_id = session_id
        self.role = role
        self.content = content
        self.sql_context = sql_context
        # Store UTC timestamp for consistency across timezones
        self.timestamp = timestamp or datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "ds_id": self.ds_id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "sql_context": self.sql_context,
            "timestamp": self.timestamp.isoformat()
        }


def _get_collection_name(ds_id: str) -> str:
    """Get collection name for a datasource (isolated per DS)"""
    # Sanitize ds_id for collection name (alphanumeric + underscore only)
    sanitized = ''.join(c if c.isalnum() or c == '_' else '_' for c in ds_id)
    return f"chat_history_{sanitized}"


def _get_or_create_collection(ds_id: str):
    """Get or create ChromaDB collection for a datasource"""
    collection_name = _get_collection_name(ds_id)

    try:
        # Try to get existing collection
        collection = _get_chroma_client().get_collection(name=collection_name)
        logger.debug(f"Retrieved existing collection: {collection_name}")
    except Exception:
        # Create new collection if doesn't exist
        collection = _get_chroma_client().create_collection(
            name=collection_name,
            metadata={"datasource_id": ds_id}
        )
        logger.info(f"Created new collection: {collection_name} for ds_id: {ds_id}")

    return collection


def save_message(
    ds_id: str,
    session_id: str,
    role: str,
    content: str,
    sql_context: Optional[str] = None,
    message_id: Optional[str] = None
) -> str:
    """
    Save a chat message to vector database.

    Args:
        ds_id: Datasource ID (for isolation)
        session_id: Session/conversation ID
        role: 'user' or 'assistant'
        content: Message content
        sql_context: Optional SQL context
        message_id: Optional message ID (generated if not provided)

    Returns:
        Message ID
    """
    try:
        # Generate message ID if not provided
        if not message_id:
            message_id = str(uuid.uuid4())

        # Create message object
        message = ChatMessage(
            message_id=message_id,
            ds_id=ds_id,
            session_id=session_id,
            role=role,
            content=content,
            sql_context=sql_context
        )

        # Get collection for this datasource
        collection = _get_or_create_collection(ds_id)

        # Generate embedding
        embedding = _get_embedding_model().encode(content).tolist()

        # Store in ChromaDB
        collection.add(
            embeddings=[embedding],
            documents=[content],
            metadatas=[{
                "message_id": message_id,
                "ds_id": ds_id,
                "session_id": session_id,
                "role": role,
                "sql_context": sql_context or "",
                "timestamp": message.timestamp.isoformat()
            }],
            ids=[message_id]
        )

        logger.info(f"Saved message {message_id} to collection {_get_collection_name(ds_id)}")

        return message_id

    except Exception as e:
        logger.error(f"Failed to save message: {e}")
        raise


def get_recent_messages(
    ds_id: str,
    session_id: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Get recent chat messages for a datasource.

    Args:
        ds_id: Datasource ID
        session_id: Optional session ID to filter by
        limit: Maximum number of messages

    Returns:
        List of messages (sorted by timestamp, newest first)
    """
    try:
        collection = _get_or_create_collection(ds_id)

        # Build filter
        where_filter = {"ds_id": ds_id}
        if session_id:
            where_filter["session_id"] = session_id

        # Query all messages for this datasource
        results = collection.get(
            where=where_filter,
            limit=limit,
            include=["metadatas", "documents"]
        )

        # Build message list
        messages = []
        if results and results['ids']:
            for i, msg_id in enumerate(results['ids']):
                metadata = results['metadatas'][i]
                messages.append({
                    "message_id": msg_id,
                    "ds_id": metadata.get("ds_id"),
                    "session_id": metadata.get("session_id"),
                    "role": metadata.get("role"),
                    "content": results['documents'][i],
                    "sql_context": metadata.get("sql_context"),
                    "timestamp": metadata.get("timestamp")
                })

        # Sort by timestamp (newest first)
        messages.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        logger.info(f"Retrieved {len(messages)} messages for ds_id: {ds_id}")

        return messages

    except Exception as e:
        logger.error(f"Failed to get recent messages: {e}")
        return []


def search_messages(
    ds_id: str,
    query: str,
    limit: int = 10,
    session_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Semantic search for messages within a datasource.

    Args:
        ds_id: Datasource ID (search only within this datasource)
        query: Search query
        limit: Maximum results
        session_id: Optional session filter

    Returns:
        List of matching messages with similarity scores
    """
    try:
        collection = _get_or_create_collection(ds_id)

        # Generate query embedding
        query_embedding = _get_embedding_model().encode(query).tolist()

        # Build filter
        where_filter = {"ds_id": ds_id}
        if session_id:
            where_filter["session_id"] = session_id

        # Semantic search
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            where=where_filter,
            include=["metadatas", "documents", "distances"]
        )

        # Build result list
        matches = []
        if results and results['ids'] and results['ids'][0]:
            for i, msg_id in enumerate(results['ids'][0]):
                metadata = results['metadatas'][0][i]
                distance = results['distances'][0][i]

                # Convert distance to similarity score (0-1, higher is better)
                # ChromaDB uses L2 distance, convert to similarity
                similarity = 1 / (1 + distance)

                matches.append({
                    "message_id": msg_id,
                    "ds_id": metadata.get("ds_id"),
                    "session_id": metadata.get("session_id"),
                    "role": metadata.get("role"),
                    "content": results['documents'][0][i],
                    "sql_context": metadata.get("sql_context"),
                    "timestamp": metadata.get("timestamp"),
                    "similarity_score": round(similarity, 4)
                })

        logger.info(f"Semantic search in {ds_id}: '{query}' -> {len(matches)} results")

        return matches

    except Exception as e:
        logger.error(f"Failed to search messages: {e}")
        return []


def get_session_messages(
    ds_id: str,
    session_id: str
) -> List[Dict[str, Any]]:
    """
    Get all messages for a specific conversation session.

    Args:
        ds_id: Datasource ID
        session_id: Session ID

    Returns:
        List of messages in chronological order
    """
    try:
        messages = get_recent_messages(
            ds_id=ds_id,
            session_id=session_id,
            limit=1000  # High limit for full session
        )

        # Sort chronologically (oldest first for conversation flow)
        messages.sort(key=lambda x: x.get("timestamp", ""))

        return messages

    except Exception as e:
        logger.error(f"Failed to get session messages: {e}")
        return []


def delete_datasource_history(ds_id: str) -> bool:
    """
    Delete all chat history for a datasource.

    Args:
        ds_id: Datasource ID

    Returns:
        True if successful
    """
    try:
        collection_name = _get_collection_name(ds_id)

        # Delete collection
        _get_chroma_client().delete_collection(name=collection_name)

        logger.info(f"Deleted chat history for datasource: {ds_id}")

        return True

    except Exception as e:
        logger.error(f"Failed to delete datasource history: {e}")
        return False


def delete_session(ds_id: str, session_id: str) -> int:
    """
    Delete all messages for a specific session.

    Args:
        ds_id: Datasource ID
        session_id: Session ID

    Returns:
        Number of messages deleted
    """
    try:
        collection = _get_or_create_collection(ds_id)

        # Get all message IDs for this session
        results = collection.get(
            where={
                "ds_id": ds_id,
                "session_id": session_id
            },
            limit=10000
        )

        if results and results['ids']:
            message_ids = results['ids']

            # Delete messages
            collection.delete(ids=message_ids)

            logger.info(f"Deleted {len(message_ids)} messages for session: {session_id}")

            return len(message_ids)

        return 0

    except Exception as e:
        logger.error(f"Failed to delete session: {e}")
        return 0


def get_datasource_stats(ds_id: str) -> Dict[str, Any]:
    """
    Get statistics for a datasource's chat history.

    Args:
        ds_id: Datasource ID

    Returns:
        Statistics dictionary
    """
    try:
        collection = _get_or_create_collection(ds_id)

        # Get all messages
        results = collection.get(
            where={"ds_id": ds_id},
            limit=100000
        )

        total_messages = len(results['ids']) if results and results['ids'] else 0

        # Count unique sessions
        sessions = set()
        user_messages = 0
        assistant_messages = 0

        if results and results['metadatas']:
            for metadata in results['metadatas']:
                sessions.add(metadata.get("session_id"))
                if metadata.get("role") == "user":
                    user_messages += 1
                elif metadata.get("role") == "assistant":
                    assistant_messages += 1

        return {
            "ds_id": ds_id,
            "total_messages": total_messages,
            "total_sessions": len(sessions),
            "user_messages": user_messages,
            "assistant_messages": assistant_messages,
            "collection_name": _get_collection_name(ds_id)
        }

    except Exception as e:
        logger.error(f"Failed to get datasource stats: {e}")
        return {
            "ds_id": ds_id,
            "total_messages": 0,
            "total_sessions": 0,
            "user_messages": 0,
            "assistant_messages": 0,
            "error": str(e)
        }
