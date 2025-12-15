"""
n8n Webhook Client for Financial Statement Processing

This module provides a client for interacting with the n8n workflow
that extracts and categorizes financial statements from PDF files.
"""

import os
import time
import json
import logging
from typing import List, Dict, Optional, BinaryIO, Union
from io import BytesIO
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class N8NError(Exception):
    """Base exception for n8n client errors"""
    pass


class N8NClient:
    """
    Client for interacting with n8n Financial Statement Categorizer workflow.

    This client handles:
    - File upload to n8n webhook
    - Response parsing
    - Error handling and retries
    - Timeout management
    """

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        auth_token: Optional[str] = None,
        timeout: int = 120,
        max_retries: int = 3
    ):
        """
        Initialize n8n client.

        Args:
            webhook_url: n8n webhook URL. If None, reads from N8N_WEBHOOK_URL env var
            auth_token: Optional authentication token for webhook
            timeout: Request timeout in seconds (default: 120)
            max_retries: Number of retries for failed requests (default: 3)

        Raises:
            N8NError: If webhook_url is not provided and not in environment
        """
        self.webhook_url = webhook_url or os.getenv('N8N_WEBHOOK_URL')
        if not self.webhook_url:
            raise N8NError(
                "Webhook URL not provided. Set N8N_WEBHOOK_URL environment variable "
                "or pass webhook_url parameter."
            )

        self.auth_token = auth_token or os.getenv('N8N_WEBHOOK_TOKEN')
        self.timeout = timeout
        self.max_retries = max_retries

        # Configure session with retry logic
        self.session = self._create_session()

        logger.info(f"N8N client initialized with webhook: {self._mask_url(self.webhook_url)}")

    def _create_session(self) -> requests.Session:
        """Create requests session with retry configuration"""
        session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,  # Wait 1s, 2s, 4s between retries
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def _mask_url(self, url: str) -> str:
        """Mask sensitive parts of URL for logging"""
        if not url:
            return "None"
        # Show only domain
        parts = url.split('/')
        if len(parts) > 2:
            return f"{parts[0]}//{parts[2]}/***"
        return url

    def _prepare_headers(self) -> Dict[str, str]:
        """Prepare request headers"""
        headers = {}

        if self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'

        return headers

    def upload_statements(
        self,
        files: Union[List[BinaryIO], List[bytes], List[tuple]]
    ) -> Dict:
        """
        Upload financial statement PDFs to n8n workflow.

        Args:
            files: List of file objects, bytes, or tuples (filename, file_content)
                  Examples:
                  - [open('file.pdf', 'rb')]
                  - [pdf_bytes]
                  - [('statement.pdf', pdf_bytes)]

        Returns:
            Dict with keys:
                - success: bool
                - data: CSV string if successful
                - error: str if failed
                - execution_time: float (seconds)

        Raises:
            N8NError: If upload fails after retries
        """
        start_time = time.time()

        try:
            # Prepare files for upload
            files_data = self._prepare_files(files)

            logger.info(f"Uploading {len(files_data)} file(s) to n8n workflow")

            # Make request
            response = self.session.post(
                self.webhook_url,
                files=files_data,
                headers=self._prepare_headers(),
                timeout=self.timeout
            )

            execution_time = time.time() - start_time

            # Handle response
            if response.status_code == 200:
                result = self._parse_response(response)
                result['execution_time'] = execution_time

                logger.info(
                    f"Successfully processed statements in {execution_time:.2f}s"
                )

                return result
            else:
                error_msg = f"n8n webhook returned status {response.status_code}: {response.text}"
                logger.error(error_msg)

                return {
                    'success': False,
                    'error': error_msg,
                    'execution_time': execution_time
                }

        except requests.exceptions.Timeout:
            error_msg = f"Request timed out after {self.timeout}s"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'execution_time': time.time() - start_time
            }

        except requests.exceptions.RequestException as e:
            error_msg = f"Request failed: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'execution_time': time.time() - start_time
            }

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'error': error_msg,
                'execution_time': time.time() - start_time
            }

    def _prepare_files(
        self,
        files: Union[List[BinaryIO], List[bytes], List[tuple]]
    ) -> List[tuple]:
        """
        Prepare files for multipart upload.

        Returns:
            List of tuples: [('file', ('filename.pdf', file_content, 'application/pdf'))]
        """
        prepared_files = []

        for idx, file_input in enumerate(files):
            if isinstance(file_input, tuple):
                # Already in (filename, content) format
                filename, content = file_input
                prepared_files.append((
                    'file',
                    (filename, content, 'application/pdf')
                ))

            elif isinstance(file_input, bytes):
                # Raw bytes
                filename = f'statement_{idx + 1}.pdf'
                prepared_files.append((
                    'file',
                    (filename, file_input, 'application/pdf')
                ))

            elif hasattr(file_input, 'read'):
                # File-like object
                content = file_input.read()
                filename = getattr(file_input, 'name', f'statement_{idx + 1}.pdf')

                # Extract just the filename if it's a full path
                if '/' in filename or '\\' in filename:
                    filename = os.path.basename(filename)

                prepared_files.append((
                    'file',
                    (filename, content, 'application/pdf')
                ))

            else:
                raise N8NError(
                    f"Invalid file format at index {idx}. "
                    "Expected file object, bytes, or (filename, bytes) tuple."
                )

        return prepared_files

    def _parse_response(self, response: requests.Response) -> Dict:
        """
        Parse n8n webhook response.

        Expected response format (new JSON format):
        {
            "data": [
                {
                    "output": "{\"document_metadata\": {...}, \"accounts\": [...], \"warnings\": [...]}"
                },
                ...
            ]
        }

        Or direct array format:
        [
            {
                "output": "{\"document_metadata\": {...}, \"accounts\": [...], \"warnings\": [...]}"
            },
            ...
        ]

        Or legacy CSV format:
        {
            "combinedCsv": "document_type,period_start,...\\n..."
        }

        Or for errors:
        {
            "error": "error message"
        }
        """
        try:
            data = response.json()

            # Check for error in response
            if isinstance(data, dict) and 'error' in data:
                return {
                    'success': False,
                    'error': data['error']
                }

            # Check for wrapped JSON array format (new n8n response)
            if isinstance(data, dict) and 'data' in data:
                return self._parse_json_array_response(data['data'])

            # Check for direct JSON array format
            if isinstance(data, list):
                return self._parse_json_array_response(data)

            # Check for legacy CSV format
            if isinstance(data, dict) and 'combinedCsv' in data:
                return self._parse_csv_response(data)

            # Unexpected response format
            return {
                'success': False,
                'error': f'Unexpected response format: {data}'
            }

        except ValueError as e:
            # JSON parsing failed
            return {
                'success': False,
                'error': f'Invalid JSON response: {str(e)}'
            }

    def _parse_json_array_response(self, data: List[Dict]) -> Dict:
        """
        Parse new JSON array response format.

        Each item has an 'output' field containing a JSON string with:
        - document_metadata
        - accounts (array)
        - raw_tax_sources (array, optional)
        - warnings (array)
        """
        try:
            all_accounts = []
            all_warnings = []

            for item in data:
                if 'output' not in item:
                    continue

                # Parse the output JSON string
                output = json.loads(item['output'])

                # Extract accounts
                if 'accounts' in output:
                    for account in output['accounts']:
                        # Add document metadata to account
                        if 'document_metadata' in output:
                            account['_document_metadata'] = output['document_metadata']

                        # If account doesn't have tax_buckets but document has raw_tax_sources,
                        # associate the raw sources with this account for display
                        if 'raw_tax_sources' in output and output['raw_tax_sources']:
                            if 'tax_buckets' not in account or not account['tax_buckets']:
                                # Store raw_tax_sources for potential client-side processing
                                account['_raw_tax_sources'] = output['raw_tax_sources']

                        all_accounts.append(account)

                # Collect warnings
                if 'warnings' in output:
                    all_warnings.extend(output['warnings'])

            if not all_accounts:
                return {
                    'success': False,
                    'error': 'No accounts found in response'
                }

            return {
                'success': True,
                'data': all_accounts,  # List of account dictionaries
                'warnings': all_warnings,
                'rows_extracted': len(all_accounts),
                'has_data': len(all_accounts) > 0,
                'format': 'json'
            }

        except (json.JSONDecodeError, KeyError) as e:
            return {
                'success': False,
                'error': f'Error parsing JSON response: {str(e)}'
            }

    def _parse_csv_response(self, data: Dict) -> Dict:
        """Parse legacy CSV response format."""
        csv_content = data['combinedCsv']

        # Validate CSV has content beyond header
        lines = csv_content.strip().split('\n')
        has_data = len(lines) > 1

        return {
            'success': True,
            'data': csv_content,  # CSV string
            'rows_extracted': len(lines) - 1,  # Subtract header
            'has_data': has_data,
            'format': 'csv'
        }

    def test_connection(self) -> bool:
        """
        Test if webhook is accessible.

        Returns:
            bool: True if webhook is reachable
        """
        try:
            # Try to HEAD request (some webhooks may not support this)
            # so we do a quick GET instead
            response = requests.get(
                self.webhook_url,
                timeout=5
            )

            # Webhook endpoints typically return 404 for GET
            # but that means they're reachable
            logger.info(f"Webhook test: Status {response.status_code}")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Webhook test failed: {str(e)}")
            return False


# Convenience function
def upload_financial_statements(
    files: Union[List[BinaryIO], List[bytes], List[tuple]],
    webhook_url: Optional[str] = None,
    auth_token: Optional[str] = None
) -> Dict:
    """
    Convenience function to upload financial statements.

    Args:
        files: List of files to upload
        webhook_url: Optional webhook URL (uses env var if not provided)
        auth_token: Optional auth token

    Returns:
        Dict with upload results
    """
    client = N8NClient(webhook_url=webhook_url, auth_token=auth_token)
    return client.upload_statements(files)


if __name__ == "__main__":
    # Example usage
    print("n8n Client - Financial Statement Processor")
    print("=" * 50)

    # Check if webhook URL is configured
    webhook_url = os.getenv('N8N_WEBHOOK_URL')

    if not webhook_url:
        print("\n❌ N8N_WEBHOOK_URL not set in environment")
        print("\nTo use this client:")
        print("1. Set up your n8n workflow (see workflows/README.md)")
        print("2. Set N8N_WEBHOOK_URL environment variable")
        print("\nExample:")
        print("  export N8N_WEBHOOK_URL='https://your-n8n.com/webhook/financial-statement-upload'")
    else:
        print(f"\n✓ Webhook URL configured")

        # Test connection
        client = N8NClient()
        if client.test_connection():
            print("✓ Webhook is reachable")
        else:
            print("✗ Webhook test failed")
