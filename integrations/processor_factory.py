"""
Processor factory — returns StatementProcessor or N8NClient based on env var.

Set PYTHON_STATEMENT_PROCESSOR=true to use the pure Python processor (no n8n needed).
"""

import os
from typing import Union

from integrations.n8n_client import N8NClient
from integrations.statement_processor import StatementProcessor


def get_processor() -> Union[N8NClient, StatementProcessor]:
    """
    Return the active statement processor.

    When PYTHON_STATEMENT_PROCESSOR=true|1|yes, returns StatementProcessor (uses OPENAI_API_KEY).
    Otherwise returns N8NClient (requires N8N_WEBHOOK_URL).
    """
    use_python = os.getenv("PYTHON_STATEMENT_PROCESSOR", "").lower() in ("true", "1", "yes")
    if use_python:
        return StatementProcessor()
    return N8NClient()
