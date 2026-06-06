"""
AI Chat Streaming Endpoint - Real-time streaming responses like ChatGPT

This endpoint provides Server-Sent Events (SSE) streaming for a more interactive chat experience.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
import json
import asyncio

from ..deps import resolve_agent
from ..services.ai_client import LLMClient
from ..services.context_builder import build_ai_context
from ..services.gated_context import build_gated_context
from ..services.tool_registry import scrub_literals, normalize_sql
from ..services.llm_settings import resolve_provider_trust

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai-chat", tags=["ai-chat-stream"])


class ChatMessage(BaseModel):
    role: str
    content: str


class StreamChatRequest(BaseModel):
    ds_id: str
    message: str
    conversation_history: List[ChatMessage] = []
    current_sql: Optional[str] = None


async def _stream_chat_response(
    ds_id: str,
    message: str,
    conversation_history: List[ChatMessage],
    current_sql: Optional[str]
):
    """
    Generator function for streaming chat responses.

    Yields Server-Sent Events (SSE) in the format:
    data: {"type": "token", "content": "text chunk"}
    data: {"type": "done"}
    """
    try:
        # Resolve agent and get context
        agent = resolve_agent(ds_id)
        db_type = agent.get_db_type().upper()
        engine = agent.get_db_type().lower()
        trust = resolve_provider_trust()

        logger.info(f"Streaming AI Chat - DB: {db_type}, trust={trust}, Message: {message[:100]}...")

        # Build context. PostgreSQL uses the provider-trust gated path (sample rows only for
        # local models, metadata tools sanitized); other engines keep the legacy builder.
        # Default the message defensively: scrubbed for hosted Postgres so a context-build
        # failure can never leave literals in the prompt; the gated path re-confirms below.
        safe_message = (
            scrub_literals(message)
            if (engine == "postgres" and trust == "hosted") else message
        )
        try:
            if engine == "postgres":
                context_str, safe_message = await build_gated_context(
                    ds_id=ds_id, engine=engine, trust=trust,
                    user_message=message, current_sql=current_sql,
                )
            else:
                context_str = build_ai_context(
                    ds_id=ds_id,
                    user_message=message,
                    current_sql=current_sql,
                    max_tables=5,
                    include_sample_data=True
                )
        except Exception as e:
            logger.warning(f"Context building failed: {e}")
            context_str = "Schema unavailable"

        # Build system prompt
        system_prompt = f"""You are an expert {db_type} database assistant with deep understanding of database schemas and data.

DATABASE CONTEXT:
{context_str}

Your capabilities:
1. Generate SQL queries from natural language descriptions
2. Optimize existing queries for better performance
3. Explain query errors and suggest fixes
4. Suggest creating missing tables with appropriate schema
5. Validate query logic and suggest improvements

CRITICAL GUIDELINES:
- ALWAYS analyze the provided schema carefully, including column names and data types
- LOOK at the sample data to understand the actual data format and values
- Use EXACT column names from the schema (case-sensitive)
- Understand relationships between tables (look for _id columns and foreign keys)
- Always provide executable SQL when generating queries
- For {db_type}, use appropriate syntax and best practices
- Keep responses conversational and actionable
- Think step-by-step and explain your reasoning

Respond in a natural, conversational tone. You can think out loud as you work through the problem.
"""

        # Build messages
        messages = [{"role": "system", "content": system_prompt}]

        for msg in conversation_history[-5:]:
            messages.append({"role": msg.role, "content": msg.content})

        user_content_parts = []
        if current_sql:
            # Literals in the editor SQL are an egress channel too: scrub them for hosted
            # Postgres models the same way the NL question is scrubbed above.
            safe_sql = (
                normalize_sql(current_sql)
                if (engine == "postgres" and trust == "hosted") else current_sql
            )
            user_content_parts.append(f"Current SQL in editor:\n```sql\n{safe_sql}\n```\n")
        # safe_message == message for local trust; literals scrubbed for hosted models.
        user_content_parts.append(f"User request: {safe_message}")

        messages.append({"role": "user", "content": "\n".join(user_content_parts)})

        # Stream response from LLM
        llm = LLMClient()

        # Send initial event
        yield f"data: {json.dumps({'type': 'start', 'message': 'Analyzing your request...'})}\n\n"

        # Get streaming generator
        stream_generator = llm.chat(messages, json_response=False, stream=True)

        # Stream tokens
        for token in stream_generator:
            event_data = {
                "type": "token",
                "content": token
            }
            yield f"data: {json.dumps(event_data)}\n\n"
            # Small delay to avoid overwhelming the client
            await asyncio.sleep(0.01)

        # Send completion event
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as e:
        logger.error(f"Streaming error: {e}", exc_info=True)
        error_event = {
            "type": "error",
            "message": str(e)
        }
        yield f"data: {json.dumps(error_event)}\n\n"


@router.post("/chat/stream")
async def stream_chat(body: StreamChatRequest):
    """
    Streaming AI chat endpoint - returns Server-Sent Events (SSE).

    **Streaming Response Format:**

    The response is a stream of Server-Sent Events (SSE). Each event is a JSON object:

    ```
    data: {"type": "start", "message": "Analyzing your request..."}

    data: {"type": "token", "content": "text chunk"}
    data: {"type": "token", "content": "next chunk"}
    ...

    data: {"type": "done"}
    ```

    **Event Types:**
    - `start`: Initial event when processing begins
    - `token`: Individual text chunk from the AI response
    - `done`: Indicates the response is complete
    - `error`: Error occurred during streaming

    **Example Usage (JavaScript):**

    ```javascript
    const eventSource = new EventSource('/ai-chat/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ds_id: 'postgres-test',
        message: 'Show me all students'
      })
    });

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'token') {
        // Append token to display
        console.log(data.content);
      } else if (data.type === 'done') {
        eventSource.close();
      }
    };
    ```

    **Example Usage (curl):**

    ```bash
    curl -N -X POST http://localhost:8000/ai-chat/chat/stream \\
      -H "Content-Type: application/json" \\
      -d '{"ds_id":"postgres-test","message":"Show me all students"}'
    ```

    **Benefits:**
    - Real-time, progressive response display
    - Better user experience (like ChatGPT)
    - Lower perceived latency
    - Can show thinking process step-by-step
    """
    try:
        return StreamingResponse(
            _stream_chat_response(
                ds_id=body.ds_id,
                message=body.message,
                conversation_history=body.conversation_history,
                current_sql=body.current_sql
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Disable nginx buffering
            }
        )

    except Exception as e:
        logger.error(f"Stream setup failed: {e}")
        raise HTTPException(500, f"Failed to initialize streaming: {str(e)}")
