"""
Chat History Router - Persistent Chat with Vector Search
Provides endpoints for saving, retrieving, and searching chat history per datasource.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
from ..services import chat_history

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat-history", tags=["chat-history"])


class SaveMessageRequest(BaseModel):
    ds_id: str
    session_id: str
    role: str  # "user" or "assistant"
    content: str
    sql_context: Optional[str] = None
    message_id: Optional[str] = None


class SaveMessageResponse(BaseModel):
    message_id: str
    success: bool


class GetHistoryResponse(BaseModel):
    messages: List[Dict[str, Any]]
    total: int
    ds_id: str


class SearchMessagesRequest(BaseModel):
    ds_id: str
    query: str
    limit: int = 10
    session_id: Optional[str] = None


class SearchMessagesResponse(BaseModel):
    results: List[Dict[str, Any]]
    query: str
    total: int


class StatsResponse(BaseModel):
    ds_id: str
    total_messages: int
    total_sessions: int
    user_messages: int
    assistant_messages: int
    collection_name: str


@router.post("/save", response_model=SaveMessageResponse)
async def save_message(body: SaveMessageRequest):
    """
    Save a chat message to vector database.

    Automatically embeds the message and stores it in a datasource-specific collection.
    Each datasource has isolated chat history.
    """
    try:
        logger.info(f"Saving message for ds_id: {body.ds_id}, session: {body.session_id}, role: {body.role}")

        message_id = chat_history.save_message(
            ds_id=body.ds_id,
            session_id=body.session_id,
            role=body.role,
            content=body.content,
            sql_context=body.sql_context,
            message_id=body.message_id
        )

        return SaveMessageResponse(
            message_id=message_id,
            success=True
        )

    except Exception as e:
        logger.error(f"Failed to save message: {e}")
        raise HTTPException(500, f"Failed to save message: {str(e)}")


@router.get("/{ds_id}", response_model=GetHistoryResponse)
async def get_history(
    ds_id: str,
    session_id: Optional[str] = None,
    limit: int = 50
):
    """
    Get recent chat history for a datasource.

    Args:
        ds_id: Datasource ID (only returns messages for this datasource)
        session_id: Optional session ID to filter by specific conversation
        limit: Maximum number of messages (default 50)

    Returns:
        List of messages sorted by timestamp (newest first)
    """
    try:
        logger.info(f"Retrieving history for ds_id: {ds_id}, session: {session_id}, limit: {limit}")

        messages = chat_history.get_recent_messages(
            ds_id=ds_id,
            session_id=session_id,
            limit=limit
        )

        return GetHistoryResponse(
            messages=messages,
            total=len(messages),
            ds_id=ds_id
        )

    except Exception as e:
        logger.error(f"Failed to get history: {e}")
        raise HTTPException(500, f"Failed to get history: {str(e)}")


@router.get("/{ds_id}/session/{session_id}")
async def get_session(ds_id: str, session_id: str):
    """
    Get all messages for a specific conversation session.

    Returns messages in chronological order (oldest to newest).
    """
    try:
        logger.info(f"Retrieving session: {session_id} for ds_id: {ds_id}")

        messages = chat_history.get_session_messages(
            ds_id=ds_id,
            session_id=session_id
        )

        return {
            "ds_id": ds_id,
            "session_id": session_id,
            "messages": messages,
            "total": len(messages)
        }

    except Exception as e:
        logger.error(f"Failed to get session: {e}")
        raise HTTPException(500, f"Failed to get session: {str(e)}")


@router.post("/search", response_model=SearchMessagesResponse)
async def search_messages(body: SearchMessagesRequest):
    """
    Semantic search for messages within a datasource.

    Uses vector embeddings to find similar messages based on meaning, not just keywords.
    Search is isolated to the specified datasource only.

    Example:
        Query: "how to create index"
        Returns: Messages about index creation, optimization, etc.
    """
    try:
        logger.info(f"Semantic search in ds_id: {body.ds_id}, query: '{body.query}'")

        results = chat_history.search_messages(
            ds_id=body.ds_id,
            query=body.query,
            limit=body.limit,
            session_id=body.session_id
        )

        return SearchMessagesResponse(
            results=results,
            query=body.query,
            total=len(results)
        )

    except Exception as e:
        logger.error(f"Failed to search messages: {e}")
        raise HTTPException(500, f"Failed to search messages: {str(e)}")


@router.delete("/{ds_id}")
async def delete_history(ds_id: str):
    """
    Delete all chat history for a datasource.

    Warning: This is permanent and cannot be undone.
    """
    try:
        logger.warning(f"Deleting all chat history for ds_id: {ds_id}")

        success = chat_history.delete_datasource_history(ds_id)

        if success:
            return {
                "success": True,
                "message": f"Chat history deleted for datasource: {ds_id}"
            }
        else:
            raise HTTPException(500, "Failed to delete chat history")

    except Exception as e:
        logger.error(f"Failed to delete history: {e}")
        raise HTTPException(500, f"Failed to delete history: {str(e)}")


@router.delete("/{ds_id}/session/{session_id}")
async def delete_session(ds_id: str, session_id: str):
    """
    Delete all messages for a specific session.

    Warning: This is permanent and cannot be undone.
    """
    try:
        logger.warning(f"Deleting session: {session_id} for ds_id: {ds_id}")

        deleted_count = chat_history.delete_session(ds_id, session_id)

        return {
            "success": True,
            "deleted_count": deleted_count,
            "message": f"Deleted {deleted_count} messages from session: {session_id}"
        }

    except Exception as e:
        logger.error(f"Failed to delete session: {e}")
        raise HTTPException(500, f"Failed to delete session: {str(e)}")


@router.get("/{ds_id}/stats", response_model=StatsResponse)
async def get_stats(ds_id: str):
    """
    Get statistics for a datasource's chat history.

    Returns:
        - Total messages
        - Total sessions/conversations
        - User vs assistant message counts
        - Collection name
    """
    try:
        logger.info(f"Getting stats for ds_id: {ds_id}")

        stats = chat_history.get_datasource_stats(ds_id)

        return StatsResponse(**stats)

    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(500, f"Failed to get stats: {str(e)}")


@router.post("/batch-save")
async def batch_save_messages(messages: List[SaveMessageRequest]):
    """
    Save multiple messages in batch (for efficiency).

    Useful for saving entire conversation sessions at once.
    """
    try:
        logger.info(f"Batch saving {len(messages)} messages")

        saved_ids = []
        errors = []

        for msg in messages:
            try:
                message_id = chat_history.save_message(
                    ds_id=msg.ds_id,
                    session_id=msg.session_id,
                    role=msg.role,
                    content=msg.content,
                    sql_context=msg.sql_context,
                    message_id=msg.message_id
                )
                saved_ids.append(message_id)
            except Exception as e:
                errors.append({
                    "message": msg.content[:50] + "...",
                    "error": str(e)
                })

        return {
            "success": len(errors) == 0,
            "saved_count": len(saved_ids),
            "error_count": len(errors),
            "saved_ids": saved_ids,
            "errors": errors
        }

    except Exception as e:
        logger.error(f"Failed to batch save: {e}")
        raise HTTPException(500, f"Failed to batch save: {str(e)}")
