# n8n Workflow - Financial Statement Categorizer

This directory contains the n8n workflow for extracting and categorizing financial statements from PDF documents.

## Available Workflows

### 1. Webhook-Ready Version (Recommended) ⭐
**File:** `n8n-statement-categorizer-webhook.json`

**Status:** Ready to use immediately with Streamlit app

This version has the webhook trigger pre-configured. Simply import, add your OpenAI credentials, activate, and copy the webhook URL.

**Use this if:** You want to get started quickly with minimal configuration.

### 2. Original Form Trigger Version
**File:** `n8n-statement-categorizer.json`

**Status:** Requires manual conversion to webhook

This is the original workflow with a form trigger. You'll need to manually convert it to a webhook trigger (see instructions below).

**Use this if:** You want to learn the conversion process or prefer the form interface.

---

## Workflow Overview (Both Versions)

**What it does:**
1. Accepts multi-PDF file uploads
2. Extracts text using OCR
3. Classifies documents (FINANCIAL vs NON-FINANCIAL)
4. Extracts structured data (account balances, tax categories)
5. Returns CSV with standardized financial data

**Output Format:**
```csv
document_type,period_start,period_end,label,value,currency,account_type,asset_category,tax_treatment,instrument_type,confidence,notes
```

## Setup Instructions

### Prerequisites
- n8n instance (Cloud or Self-hosted)
- OpenAI API key (for GPT-4.1-mini)

### Step 1: Import Workflow

**Option A: Webhook-Ready Version (Recommended)**

1. Log into your n8n instance
2. Click **"Workflows"** → **"Add Workflow"** → **"Import from File"**
3. Select `n8n-statement-categorizer-webhook.json`
4. Click **"Import"**
5. Skip to Step 2 (no conversion needed!)

**Option B: Original Form Trigger Version**

1. Log into your n8n instance
2. Click **"Workflows"** → **"Add Workflow"** → **"Import from File"**
3. Select `n8n-statement-categorizer.json`
4. Click **"Import"**
5. Continue to Step 3 to convert to webhook

### Step 2: Configure OpenAI Credentials

1. Click on **"OpenAI Chat Model"** node
2. Click **"Create New Credential"**
3. Enter your OpenAI API key
4. Save and apply to both OpenAI nodes in the workflow

### Step 3: Activate and Get Webhook URL

**If you imported the webhook-ready version, skip to substep 5 below.**

**If you imported the original form trigger version, follow these steps to convert:**

---

#### Converting Form Trigger to Webhook (Original Version ONLY)

#### Instructions:

1. **Delete the "On form submission" node**
   - Click on the "On form submission" node
   - Press `Delete` or right-click → Delete

2. **Add Webhook node**
   - Click the **"+"** button or search for "Webhook"
   - Select **"Webhook"** from the trigger nodes
   - Configure it with these settings:

   ```
   HTTP Method: POST
   Path: financial-statement-upload
   Authentication: None (or configure as needed)
   Response Mode: Last Node
   Response Data: All Entries

   Options:
   ✓ Binary Data: true (to accept file uploads)
   ```

3. **Connect the Webhook node**
   - Draw a connection from **Webhook** → **Split the files** node
   - This replaces the form trigger connection

4. **Modify "Split the files" node** (Important!)

   The current code expects form data. Replace the JavaScript with:

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

5. **Save and Activate**
   - Click **"Save"** (top right)
   - Toggle **"Active"** to ON

---

#### For Both Versions: Get Your Webhook URL

6. **Copy Webhook URL**
   - Click on the **"Webhook"** node in your workflow
   - Copy the **Production URL** that appears
   - The webhook URL will look like:
     - **Cloud:** `https://your-instance.app.n8n.cloud/webhook/financial-statement-upload`
     - **Self-hosted:** `https://your-domain.com/webhook/financial-statement-upload`

   - Save this URL - you'll need it for the `.env` file

### Step 4: Test the Webhook

Test using curl:

```bash
curl -X POST https://your-n8n-instance.com/webhook/financial-statement-upload \
  -F "file=@/path/to/sample-statement.pdf"
```

Expected response:
```json
{
  "combinedCsv": "document_type,period_start,period_end,label,value,currency,account_type,asset_category,tax_treatment,instrument_type,confidence,notes\n..."
}
```

## Workflow Details

### Nodes Explained

1. **Webhook** (Trigger)
   - Receives PDF files from Streamlit app
   - Accepts multiple files via multipart/form-data

2. **Split the files**
   - Separates multiple PDFs for individual processing
   - JavaScript code to handle binary data

3. **Extract from File**
   - OCR extraction from PDFs
   - Outputs raw text content

4. **Text Classifier**
   - Uses GPT-4.1-mini to classify documents
   - Categories: FINANCIAL / NON-FINANCIAL
   - Filters out irrelevant documents

5. **AI Agent**
   - Extracts structured data using sophisticated prompts
   - Maps tax categories (pre_tax, post_tax)
   - Removes PII automatically
   - Enforces strict extraction rules

6. **Combine into one CSV**
   - Merges results from all PDFs
   - Returns single CSV with all accounts

### Tax Treatment Mapping

The workflow automatically maps account types to tax treatments:

**Pre-tax:**
- 401(k) employee deferrals
- Employer match
- Traditional IRA
- Rollover IRA

**Post-tax:**
- Roth IRA
- Roth 401(k) contributions
- Brokerage accounts
- HSA
- Checking/Savings

## Troubleshooting

### Webhook not responding
- Check if workflow is **Active**
- Verify OpenAI credentials are configured
- Check n8n logs for errors

### No data extracted
- Ensure PDFs contain actual financial statements
- Check Text Classifier is marking documents as "FINANCIAL"
- Review AI Agent execution logs

### CSV format issues
- The AI Agent should return raw CSV (no markdown)
- If you see backticks or formatting, check the system prompt

### File upload errors
- Verify webhook accepts binary data
- Check file size limits in n8n settings
- Ensure Content-Type is multipart/form-data

## Security Notes

- **PII Removal:** The workflow automatically removes personal information
- **API Keys:** Store OpenAI credentials securely in n8n
- **Webhook Auth:** Consider adding authentication to the webhook
- **File Validation:** Only PDF files are processed

## Advanced Configuration

### Add Webhook Authentication

To secure your webhook:

1. In the Webhook node, set:
   ```
   Authentication: Header Auth
   ```

2. Configure credentials:
   ```
   Name: Authorization
   Value: Bearer YOUR_SECRET_TOKEN
   ```

3. Update your `.env` file with:
   ```
   N8N_WEBHOOK_TOKEN=YOUR_SECRET_TOKEN
   ```

### Rate Limiting

For production use, consider:
- Adding rate limiting in n8n
- Implementing queue management for large batches
- Setting timeout values appropriately

## Next Steps

After setup:
1. Update `/home/user/financialadvisor/.env` with your webhook URL
2. Run the Streamlit uploader: `streamlit run statement_uploader.py`
3. Test with sample financial statements
4. Integrate with main application

## Support

For n8n-specific issues:
- [n8n Documentation](https://docs.n8n.io/)
- [n8n Community](https://community.n8n.io/)

For workflow/integration issues:
- Check the main project README
- Review logs in both n8n and Streamlit
