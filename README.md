# 🩺 EDIErrorDoctor
### Amazon Nova Hackathon 2025 — AI-Powered X12 EDI Diagnostics

> Turn hours of EDI error debugging into seconds with Amazon Nova Pro reasoning.

---

## Quick Start (Local Dev)

### 1. Prerequisites
- Python 3.10+
- AWS account with Amazon Bedrock access
- Nova Pro model enabled in Bedrock (see AWS Setup below)

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure AWS credentials
```bash
aws configure
# Enter your AWS Access Key ID, Secret, and region (us-east-1 recommended)
```

Or set environment variables:
```bash
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=us-east-1
```

### 4. Enable Nova models in Bedrock
1. Go to AWS Console → Amazon Bedrock → Model access
2. Request access to: **Amazon Nova Pro**, **Amazon Nova Lite**
3. Wait for approval (usually instant for Nova models)

### 5. Run the app
```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser.

---

## AWS Setup (Step by Step)

### Create an AWS Account
1. Visit https://aws.amazon.com and click "Create an AWS Account"
2. Follow sign-up steps (credit card required; free tier covers most hackathon usage)

### Enable Bedrock Model Access
```
AWS Console → Amazon Bedrock → Left sidebar: "Model access"
→ "Manage model access" → Check "Amazon Nova Pro" and "Amazon Nova Lite"
→ "Save changes"
```

### IAM Permissions Needed
Your AWS user/role needs:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:Converse",
        "bedrock:ApplyGuardrail"
      ],
      "Resource": "*"
    }
  ]
}
```

### Cost Estimate (Hackathon)
| Model | Input | Output | Est. per analysis |
|-------|-------|--------|-------------------|
| Nova Pro | $0.0008/1K tokens | $0.0032/1K tokens | ~$0.02 |
| Nova Lite | $0.00006/1K tokens | $0.00024/1K tokens | ~$0.002 |

A full hackathon demo: **< $5 total**.

---

## Project Structure

```
edi_error_doctor/
├── app.py                          # Main Streamlit application
├── requirements.txt
├── README.md
├── utils/
│   ├── edi_parser.py               # X12 segment/loop parser
│   ├── nova_client.py              # Bedrock Converse API wrapper
│   ├── guardrails.py               # PHI detection layer
│   └── report_export.py            # Markdown report generator
└── synthetic_edi/
    ├── 837P_missing_nm109.edi      # 837 Professional with subscriber ID error
    ├── 835_ERA_denial_sample.edi   # 835 ERA with denial codes
    └── 837I_inpatient_multiservice.edi  # 837 Institutional multi-service
```

---

## Features

### 📄 EDI Text Analysis
- Upload `.edi`, `.txt`, `.x12` files or paste raw EDI
- Auto-detection of transaction type (837P, 837I, 835, 278, 270/271)
- SNIP Level 1–4 validation
- Nova Pro generates:
  - Plain-English error explanations for billing staff
  - Precise fix suggestions with corrected segments
  - Complete corrected EDI for resubmission
  - Downloadable Markdown report

### 🖼️ Multimodal EOB Analysis
- Upload scanned paper EOB images (PNG, JPG, PDF)
- Nova extracts payer, claim, and payment data
- Maps extracted data to 835 ERA segments
- Identifies discrepancies and likely rejection causes

### 🔒 Privacy & Safety
- 100% synthetic data in demo
- Bedrock Guardrails PHI pattern detection
- No data leaves your AWS account
- HIPAA-eligible AWS services

---

## Demo Script (for judges)

1. **Start the app**: `streamlit run app.py`
2. **Load a sample**: Sidebar → "837P_missing_nm109.edi"
3. **Select model**: Nova Pro (best reasoning)
4. **Click Analyze**: Watch Nova identify the missing NM109 subscriber ID
5. **Review tabs**:
   - Errors tab: Plain-English explanation + SNIP level
   - Fix tab: Side-by-side original vs corrected segment
   - Corrected EDI tab: Ready-to-resubmit clean file
   - Download report: Full Markdown analysis

---

## Architecture

```
┌─────────────────────────────────────────────┐
│                Streamlit UI                  │
│  File Upload │ EDI Paste │ EOB Image Upload  │
└──────────────────┬──────────────────────────┘
                   │
        ┌──────────▼──────────┐
        │   PHI Guardrail     │  ← Bedrock Guardrails
        │   (regex + API)     │
        └──────────┬──────────┘
                   │
        ┌──────────▼──────────┐
        │    EDI Parser       │  ← Custom Python
        │  (segments/loops)   │
        └──────────┬──────────┘
                   │
        ┌──────────▼──────────┐
        │  Amazon Nova Pro    │  ← Bedrock Converse API
        │  (error reasoning)  │
        └──────────┬──────────┘
                   │
        ┌──────────▼──────────┐
        │  Structured Output  │
        │  Errors/Fixes/EDI   │
        └─────────────────────┘
```

---

## Supported X12 Transactions

| TX Set | Description | Common Errors Detected |
|--------|-------------|----------------------|
| 837P | Professional Claims | Missing NM109, invalid qualifier, CLM05 errors |
| 837I | Institutional Claims | HL loop issues, UB04 mapping, DRG errors |
| 835 | Electronic Remittance Advice | CAS balancing, CLP amounts, SVC mismatch |
| 278 | Prior Authorization | HCR codes, UM segment errors |
| 270/271 | Eligibility | AAA error codes, NM1 qualifier issues |

---

## Future Roadmap
- Voice input via Amazon Nova Sonic ("What does error CO-45 mean?")
- Real payer sandbox integration (Change Healthcare, Availity)
- Full SNIP Level 5–7 external code set validation
- Agentic prior-auth submission workflow
- FHIR R4 ↔ EDI translation assistant

---

*Built for Amazon Nova Hackathon 2025 | All demo data is 100% synthetic*
