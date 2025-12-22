# Financial Statement Uploader - Setup Guide

This guide will help you set up the Financial Statement Uploader feature, which uses n8n and AI to automatically extract account data from PDF financial statements.

## Overview

**What it does:**
- Upload multiple PDF financial statements (401k, IRA, brokerage, etc.)
- AI extracts account balances and categorizes by tax treatment
- Returns structured CSV data with account information
- Automatically removes personal information (PII)

**Technology Stack:**
- **n8n:** Workflow automation platform
- **OpenAI GPT-4.1:** AI for text extraction and classification
- **Streamlit:** Web interface
- **Python:** Integration code

## Prerequisites

Before you begin, ensure you have:
- [ ] Python 3.8 or higher
- [ ] n8n instance (cloud or self-hosted)
- [ ] OpenAI API key
- [ ] Git (to clone the repository)

## Step-by-Step Setup

### Step 1: Install Dependencies

```bash
# Navigate to project directory
cd financialadvisor

# Install Python dependencies
pip install -r requirements.txt
```

**New dependencies added:**
- `requests` - HTTP client for webhook calls
- `python-dotenv` - Environment variable management

### Step 2: Set Up n8n Workflow

#### Option A: n8n Cloud (Recommended for beginners)

1. **Sign up for n8n Cloud**
   - Go to https://n8n.io/cloud
   - Create a free account
   - Note your instance URL (e.g., `https://yourname.app.n8n.cloud`)

2. **Import the workflow**
   - In n8n, click **Workflows** → **Add Workflow** → **Import from File**
   - **Recommended:** Select `workflows/n8n-statement-categorizer-webhook.json` (webhook-ready version)
   - **Alternative:** Select `workflows/n8n-statement-categorizer.json` (requires manual webhook setup)
   - Click **Import**

#### Option B: Self-Hosted n8n

```bash
# Using Docker
docker run -it --rm \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  docker.n8n.io/n8nio/n8n

# Access at http://localhost:5678
```

Then import the workflow as described in Option A.

### Step 3: Configure OpenAI in n8n

1. **Get OpenAI API Key**
   - Go to https://platform.openai.com/api-keys
   - Create a new API key
   - Copy the key (you won't see it again!)

2. **Add to n8n**
   - Open the imported workflow
   - Click on **"OpenAI Chat Model"** node
   - Click **"Create New Credential"**
   - Paste your API key
   - Click **Save**
   - Repeat for **"OpenAI Chat Model1"** node (or select the same credential)

### Step 4: Activate Workflow and Get Webhook URL

#### If you imported the webhook-ready version (`n8n-statement-categorizer-webhook.json`)

**Great!** Your workflow already has a webhook configured. Skip to substep 7 below.

#### If you imported the original version (`n8n-statement-categorizer.json`)

You need to convert the Form Trigger to a Webhook:

1. **Delete Form Trigger**
   - Click on the **"On form submission"** node
   - Press `Delete` key

2. **Add Webhook Node**
   - Click the **+** button
   - Search for "Webhook"
   - Select **"Webhook"** from Triggers

3. **Configure Webhook**
   ```
   HTTP Method: POST
   Path: financial-statement-upload
   Authentication: None (or configure as needed)
   Response Mode: Last Node
   Response Data: All Entries

   Options → Binary Data: ✓ Enabled
   ```

4. **Connect Nodes**
   - Draw connection: **Webhook** → **Split the files**

5. **Update "Split the files" Code**

   Replace the JavaScript in **"Split the files"** node with:

   ```javascript
   // Handle webhook file upload format
   const items = $input.all();
   let output = [];

   items.forEach(item => {
     const binaryData = item.binary;

     if (binaryData) {
       Object.keys(binaryData).forEach(key => {
         output.push({
           json: item.json,
           binary: { data: binaryData[key] }
         });
       });
     }
   });

   return output;
   ```

6. **Save and Activate** (If you made changes)
   - Click **Save** (top right)
   - Toggle **Active** to ON
   - The workflow is now live!

---

#### For Both Versions:

7. **Copy Webhook URL**
   - Click on the **Webhook** node in your workflow
   - Copy the **Production URL** that appears
   - Example: `https://yourname.app.n8n.cloud/webhook/financial-statement-upload`
   - **Save this URL** - you'll need it in the next step!

### Step 5: Configure Environment Variables

1. **Create .env file**
   ```bash
   # In the financialadvisor directory
   cp .env.example .env
   ```

2. **Edit .env file**
   ```bash
   nano .env  # or use your preferred editor
   ```

   Add your webhook URL:
   ```
   N8N_WEBHOOK_URL=https://yourname.app.n8n.cloud/webhook/financial-statement-upload
   ```

   Optional - add authentication token if configured:
   ```
   N8N_WEBHOOK_TOKEN=your_secret_token
   ```

3. **Save the file** (Ctrl+O, Enter, Ctrl+X for nano)

### Step 6: Test the Setup

1. **Test webhook connectivity**
   ```bash
   python integrations/n8n_client.py
   ```

   Expected output:
   ```
   ✓ Webhook URL configured
   ✓ Webhook is reachable
   ```

2. **Test with curl** (optional)
   ```bash
   curl -X POST https://your-webhook-url \
     -F "file=@path/to/sample-statement.pdf"
   ```

### Step 7: Launch the Uploader App

```bash
streamlit run statement_uploader.py
```

The app will open in your browser at `http://localhost:8501`

## Using the Statement Uploader

1. **Upload PDFs**
   - Click "Browse files" or drag & drop
   - Select one or more financial statement PDFs
   - Supported: 401k, IRA, Roth IRA, Brokerage, HSA statements

2. **Extract Data**
   - Click **"Extract & Categorize"**
   - Wait for processing (usually 10-30 seconds per file)

3. **Review Results**
   - View extracted accounts in table format
   - See tax treatment breakdown
   - Download CSV or JSON

4. **Download or Use Data**
   - Download for manual entry
   - Future: Auto-import to main app

## Troubleshooting

### Configuration Issues

**"N8N_WEBHOOK_URL not set"**
- Ensure `.env` file exists in project root
- Check the variable name is exactly `N8N_WEBHOOK_URL`
- Restart the Streamlit app

**"Webhook is not reachable"**
- Verify n8n workflow is **Active** (toggle in n8n)
- Check webhook URL is correct (no typos)
- Test with curl to isolate issue

### Processing Issues

**"No data extracted"**
- Ensure PDFs contain actual financial statements
- Check the Text Classifier node in n8n (should classify as "FINANCIAL")
- Review confidence scores in results

**"Processing failed"**
- Check n8n workflow execution logs
- Verify OpenAI API key is valid and has credits
- Check AI Agent node for errors

**"Timeout"**
- Large PDFs may take longer
- Increase timeout in code: `N8NClient(timeout=300)`
- Check n8n workflow execution time

### n8n Workflow Issues

**Workflow fails at "Extract from File"**
- PDF may be scanned image (OCR quality issue)
- Try with a digital PDF (not scanned)

**Workflow fails at "AI Agent"**
- Check OpenAI API credits
- Review AI Agent prompt in n8n
- Check execution logs for API errors

**No CSV returned**
- Check "Combine into one CSV" node
- Ensure all nodes are connected
- Review n8n execution flow

## Advanced Configuration

### Webhook Authentication

To secure your webhook:

1. **In n8n Webhook node:**
   ```
   Authentication: Header Auth
   Header Name: Authorization
   Header Value: Bearer YOUR_SECRET_TOKEN
   ```

2. **In .env file:**
   ```
   N8N_WEBHOOK_TOKEN=YOUR_SECRET_TOKEN
   ```

### Custom Timeout

For processing many large files:

```python
from integrations.n8n_client import N8NClient

client = N8NClient(timeout=300)  # 5 minutes
```

### Rate Limiting

If processing many files, consider:
- Processing in batches
- Adding delays between uploads
- Configuring n8n rate limits

## Security Best Practices

1. **Never commit .env file** - Already in `.gitignore`
2. **Rotate API keys regularly** - Both OpenAI and webhook tokens
3. **Use HTTPS only** - Especially for production
4. **Review extracted data** - Verify PII is removed
5. **Limit file sizes** - Prevent abuse

## File Structure

After setup, your directory should look like:

```
financialadvisor/
├── .env                          # Your config (git-ignored)
├── .env.example                  # Template
├── statement_uploader.py         # Streamlit app
├── integrations/
│   ├── __init__.py
│   ├── n8n_client.py            # Webhook client
│   └── README.md
├── workflows/
│   ├── n8n-statement-categorizer.json
│   └── README.md
└── requirements.txt              # Updated with new deps
```

## Cost Estimates

### n8n Cloud
- **Free tier:** 5,000 workflow executions/month
- **Starter:** $20/month for 15,000 executions

### OpenAI API
- **GPT-4.1-mini:** ~$0.15 per 1M input tokens
- **Typical cost per statement:** $0.01 - $0.05
- **100 statements/month:** ~$1-5

**Total estimated cost for moderate use:** $0-25/month

## Next Steps

### Integration with Main App

Future enhancement: Auto-populate assets in main Financial Advisor app

```python
# Planned feature
if result['success']:
    accounts = parse_csv_to_accounts(result['data'])
    for account in accounts:
        add_to_portfolio(account)
```

### Additional Features

- [ ] Support for CSV and Excel uploads
- [ ] Batch processing with queue
- [ ] Historical tracking of uploads
- [ ] Auto-categorization improvements
- [ ] Multi-currency support

## Getting Help

### Documentation
- **n8n setup:** `workflows/README.md`
- **Integration API:** `integrations/README.md`
- **Main app:** Root `README.md`

### Resources
- n8n Documentation: https://docs.n8n.io/
- OpenAI API: https://platform.openai.com/docs
- Streamlit: https://docs.streamlit.io/

### Support
- Check logs in n8n workflow executions
- Review Streamlit app error messages
- Test individual components (webhook, client, etc.)

## Success Checklist

Before considering setup complete:

- [ ] n8n workflow imported and active
- [ ] OpenAI credentials configured in n8n
- [ ] Webhook trigger configured (not form trigger)
- [ ] Webhook URL copied
- [ ] .env file created with webhook URL
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Connection test passes
- [ ] Sample PDF successfully processed
- [ ] CSV data displays correctly
- [ ] Can download results

**Congratulations!** You're ready to use the Financial Statement Uploader.
