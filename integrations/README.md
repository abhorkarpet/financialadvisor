# Integration Modules

This directory contains integration modules for connecting the Financial Advisor application with external services.

## Modules

### `n8n_client.py`

Client library for interacting with n8n workflow automation platform.

**Purpose:** Upload financial statement PDFs to n8n workflow and receive extracted structured data.

**Usage:**

```python
from integrations.n8n_client import N8NClient

# Initialize client
client = N8NClient(
    webhook_url='https://your-n8n.com/webhook/financial-statement-upload',
    auth_token='optional_token',  # Optional
    timeout=120  # seconds
)

# Upload files
with open('statement.pdf', 'rb') as f:
    result = client.upload_statements([f])

if result['success']:
    csv_data = result['data']
    print(f"Extracted {result['rows_extracted']} accounts")
else:
    print(f"Error: {result['error']}")
```

**Environment Variables:**
- `N8N_WEBHOOK_URL` - Webhook URL (required)
- `N8N_WEBHOOK_TOKEN` - Authentication token (optional)

**Features:**
- Automatic retry with exponential backoff
- Timeout handling
- Multi-file upload support
- Response validation
- Connection testing

**Error Handling:**

```python
from integrations.n8n_client import N8NError

try:
    client = N8NClient()
except N8NError as e:
    print(f"Configuration error: {e}")
```

**Response Format:**

```python
{
    'success': True,
    'data': 'document_type,period_start,...\n...',  # CSV string
    'rows_extracted': 5,
    'has_data': True,
    'execution_time': 12.34  # seconds
}
```

**Testing:**

```bash
# Set environment variable
export N8N_WEBHOOK_URL="https://your-webhook-url"

# Run test
python integrations/n8n_client.py
```

## CSV Output Format

The n8n workflow returns CSV with the following columns:

| Column | Description | Example |
|--------|-------------|---------|
| `document_type` | Type of document | "401k_statement" |
| `period_start` | Statement period start | "2024-01-01" |
| `period_end` | Statement period end | "2024-03-31" |
| `label` | Account category label | "Employee Deferral" |
| `value` | Current balance | 125000.00 |
| `currency` | Currency code | "USD" |
| `account_type` | Account type | "401k" |
| `asset_category` | Asset category | "retirement" |
| `tax_treatment` | Tax classification | "pre_tax" |
| `instrument_type` | Instrument type | "mixed" |
| `confidence` | Extraction confidence | 0.95 |
| `notes` | Additional notes | "Q1 2024 statement" |

## Tax Treatment Values

- `pre_tax` - Traditional 401k, Traditional IRA, etc.
- `post_tax` - Roth IRA, Roth 401k, Brokerage, HSA

## Development

### Adding New Integrations

To add a new integration:

1. Create a new module file (e.g., `new_service_client.py`)
2. Implement error class and client class
3. Add to `__init__.py`:
   ```python
   from .new_service_client import NewServiceClient, NewServiceError
   __all__ = ['N8NClient', 'N8NError', 'NewServiceClient', 'NewServiceError']
   ```
4. Add documentation
5. Add tests

### Testing

```bash
# Test n8n client
python -m pytest tests/test_n8n_client.py

# Manual testing
python integrations/n8n_client.py
```

## Troubleshooting

### "N8N_WEBHOOK_URL not set"
Set the environment variable or pass `webhook_url` parameter.

### "Webhook test failed"
- Check if n8n workflow is active
- Verify webhook URL is correct
- Test with curl to isolate the issue

### "Request timed out"
- Increase timeout: `N8NClient(timeout=300)`
- Check n8n workflow execution time
- Verify network connectivity

### "Invalid JSON response"
- Check n8n workflow "Combine into one CSV" node
- Ensure response format is correct
- Review n8n execution logs

## Security Best Practices

1. **Never commit .env files** - Use `.env.example` as template
2. **Use webhook authentication** - Set `N8N_WEBHOOK_TOKEN`
3. **Validate inputs** - Client validates file types
4. **Handle errors gracefully** - Don't expose sensitive error details
5. **Use HTTPS** - Always use secure connections

## Support

For issues related to:
- **n8n setup:** See `workflows/README.md`
- **Integration code:** Check this documentation
- **Streamlit app:** See main project README
