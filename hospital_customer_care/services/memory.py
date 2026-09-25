"""
Session memory for the AI Hospital Customer Care System.

Uses AutoGen's ListMemory for in-session context.
Relevant information is selectively retrieved rather than dumped verbatim.

IMPORTANT: For production healthcare use, memory must be:
  - Encrypted at rest and in transit
  - Access-controlled (role-based)
  - Covered by a retention and deletion policy
  - Subject to audit logging
  - Consent-managed
  - Stored in a HIPAA/GDPR-compliant backend

For this prototype, memory is kept in-process per session.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from autogen_core.memory import ListMemory, MemoryContent, MemoryMimeType

logger = logging.getLogger(__name__)


class SessionMemory:
    """
    Thin wrapper around AutoGen ListMemory for one patient session.

    Only relevant context excerpts are stored.
    PII is minimised: we store clinical context, not full patient records.
    """

    def __init__(self) -> None:
        self._memory = ListMemory(name="hospital_session_memory")

    async def add(self, content: str, mime_type: MemoryMimeType = MemoryMimeType.TEXT) -> None:
        """Add a context item to session memory."""
        try:
            await self._memory.add(MemoryContent(content=content, mime_type=mime_type))
            logger.debug("[MEMORY] Added context entry")
        except Exception as exc:
            logger.warning("[MEMORY] Failed to add entry: %s", exc)

    async def get_all(self) -> List[str]:
        """Return all stored context items as plain strings."""
        try:
            result = await self._memory.query("all context")
            return [item.content for item in result.results if item.content]
        except Exception as exc:
            logger.warning("[MEMORY] Failed to retrieve context: %s", exc)
            return []

    async def get_relevant(self, query: str) -> str:
        """Return memory relevant to a query, joined into a string."""
        try:
            result = await self._memory.query(query)
            snippets = [item.content for item in result.results if item.content]
            return "\n".join(snippets) if snippets else ""
        except Exception as exc:
            logger.warning("[MEMORY] Failed to query context: %s", exc)
            return ""

    def get_autogen_memory(self) -> ListMemory:
        """Return the underlying AutoGen ListMemory for injection into agents."""
        return self._memory

    async def clear(self) -> None:
        """Clear all session memory."""
        try:
            await self._memory.clear()
            logger.debug("[MEMORY] Session memory cleared")
        except Exception as exc:
            logger.warning("[MEMORY] Failed to clear memory: %s", exc)
