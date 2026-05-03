"""
Processor factory — returns StatementProcessor or N8NClient based on env var.

Set PYTHON_STATEMENT_PROCESSOR=true to use the pure Python processor (no n8n needed).
"""

import os
from typing import Union

from integrations.n8n_client import N8NClient
from integrations.statement_processor import StatementProcessor


def check_processor_configured() -> tuple:
    """Check whether a statement processor is fully configured.

    Returns:
        (ok: bool, error_msg: str)  — error_msg is empty when ok is True.
    """
    use_python = os.getenv("PYTHON_STATEMENT_PROCESSOR", "").lower() in ("true", "1", "yes")
    if use_python:
        if not os.getenv("OPENAI_API_KEY"):
            return False, (
                "PYTHON_STATEMENT_PROCESSOR is enabled but OPENAI_API_KEY is not set. "
                "Add your OpenAI API key to continue."
            )
        return True, ""
    if os.getenv("N8N_WEBHOOK_URL"):
        return True, ""
    return False, (
        "No statement processor is configured. "
        "Set PYTHON_STATEMENT_PROCESSOR=true and OPENAI_API_KEY to use the built-in processor, "
        "or set N8N_WEBHOOK_URL to use the n8n webhook."
    )


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
