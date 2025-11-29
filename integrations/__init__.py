"""
Integration modules for Financial Advisor application.

This package contains integrations with external services:
- n8n workflow automation
- Statement parsing utilities
"""

from .n8n_client import N8NClient, N8NError

__all__ = ['N8NClient', 'N8NError']
