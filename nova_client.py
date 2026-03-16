"""
Amazon Bedrock / Nova integration for EDIErrorDoctor.
Handles Converse API calls, prompt construction, and response parsing.
"""

import json
import re
import boto3
from botocore.exceptions import ClientError
from typing import Optional

# Model IDs
NOVA_PRO = "us.amazon.nova-pro-v1:0"
NOVA_LITE = "us.amazon.nova-lite-v1:0"

SYSTEM_PROMPT = """You are EDIErrorDoctor, an expert AI assistant specializing in X12 EDI healthcare transactions (837 claims, 835 remittances, 278 prior authorizations, 270/271 eligibility, 276/277 claim status).

You have deep knowledge of:
- X12 5010 TR3 implementation guides (005010X222A1 for 837P, 005010X221A1 for 835, 005010X217 for 278)
- SNIP validation levels 1-7
- Common payer-specific edits and companion guide rules
- Loop/segment structure, element requirements, and qualifier codes
- Revenue cycle management and claim denial root causes
- CMS-1500 and UB-04 form mappings to EDI equivalents

When analyzing EDI:
1. Identify ALL errors by SNIP level, segment ID, loop context, and element position
2. Explain each error in plain English suitable for billing staff (non-technical)
3. Provide the corrected segment with exact EDI syntax
4. Suggest the business/clinical reason for the fix
5. Flag any patterns that may cause payer-specific rejections

Format your response as structured JSON with this schema:
{
  "summary": "brief overall assessment",
  "error_count": <number>,
  "errors": [
    {
      "snip_level": <1-7>,
      "severity": "FATAL|ERROR|WARNING|INFO",
      "segment_id": "<e.g. NM1>",
      "loop": "<e.g. 2010BA>",
      "element_position": "<e.g. NM1-04>",
      "plain_english": "<what's wrong, why it matters>",
      "technical_detail": "<X12 rule or TR3 reference>",
      "original_segment": "<the bad segment>",
      "corrected_segment": "<the fixed segment>",
      "fix_explanation": "<what was changed and why>"
    }
  ],
  "corrected_edi_snippet": "<the full corrected EDI block if feasible>",
  "revenue_cycle_impact": "<what denials/delays this would cause>",
  "priority_fixes": ["<top 3 things to fix first>"]
}"""


def get_bedrock_client(region: str = "us-east-1"):
    """Initialize Bedrock runtime client."""
    return boto3.client("bedrock-runtime", region_name=region)


def clean_json_response(raw_text: str) -> dict:
    """
    Robustly parse JSON from Nova response.
    Handles markdown fences, truncation, and special characters.
    """
    clean = raw_text.strip()

    # Strip markdown code fences
    if clean.startswith("```"):
        clean = re.sub(r"^```[a-z]*\n?", "", clean)
        clean = re.sub(r"```$", "", clean).strip()

    # Attempt 1 — direct parse
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass

    # Attempt 2 — find outermost JSON object
    try:
        match = re.search(r'\{.*\}', clean, re.DOTALL)
        if match:
            return json.loads(match.group())
    except json.JSONDecodeError:
        pass

    # Attempt 3 — truncated response, close open braces
    try:
        # Count open/close braces to fix truncation
        open_braces  = clean.count('{')
        close_braces = clean.count('}')
        if open_braces > close_braces:
            clean = clean + ('}' * (open_braces - close_braces))
        return json.loads(clean)
    except json.JSONDecodeError:
        pass

    # Attempt 4 — find last valid closing brace
    try:
        last_brace = clean.rfind('}')
        if last_brace > 0:
            return json.loads(clean[:last_brace + 1])
    except json.JSONDecodeError:
        pass

    # All attempts failed
    raise ValueError(f"Could not parse JSON from Nova response. Raw: {raw_text[:200]}...")


def analyze_edi_with_nova(
    edi_text: str,
    pre_validation_issues: list,
    transaction_type: str,
    model_id: str = NOVA_PRO,
    region: str = "us-east-1"
) -> dict:
    """
    Send EDI content to Amazon Nova via Bedrock Converse API for analysis.
    Returns parsed JSON with errors and fixes.
    """
    client = get_bedrock_client(region)

    pre_val_text = ""
    if pre_validation_issues:
        issues_str = "\n".join(
            f"- [SNIP {i['snip']}] {i['severity']} in {i['segment']}: {i['message']}"
            for i in pre_validation_issues
        )
        pre_val_text = f"\n\nPre-validation flags detected by local parser:\n{issues_str}\n"

    user_message = f"""Please analyze this {transaction_type} EDI transaction for ALL errors, warnings, and improvement opportunities.
{pre_val_text}
EDI Content:
```
{edi_text}
```

Provide your complete analysis in the JSON format specified. Be thorough — check every segment, element qualifier, loop structure, and business rule. This is synthetic/demo data with intentional errors for educational purposes."""

    try:
        response = client.converse(
            modelId=model_id,
            system=[{"text": SYSTEM_PROMPT}],
            messages=[{"role": "user", "content": [{"text": user_message}]}],
            inferenceConfig={
                "maxTokens": 4096,
                "temperature": 0.1,
            }
        )

        raw_text = response["output"]["message"]["content"][0]["text"]
        return clean_json_response(raw_text)

    except ClientError as e:
        return {
            "error": True,
            "message": f"Bedrock API error: {e.response['Error']['Message']}",
            "summary": "Analysis failed — check AWS credentials and Bedrock model access.",
            "errors": []
        }
    except ValueError as e:
        return {
            "error": True,
            "message": str(e),
            "summary": "Nova response could not be parsed.",
            "errors": []
        }
    except Exception as e:
        return {
            "error": True,
            "message": f"Unexpected error: {str(e)}",
            "summary": "Analysis failed.",
            "errors": []
        }


def analyze_eob_image_with_nova(
    image_bytes: bytes,
    media_type: str = "image/jpeg",
    model_id: str = NOVA_PRO,
    region: str = "us-east-1"
) -> dict:
    """
    Multimodal: Send scanned EOB/remittance image to Nova for data extraction
    and EDI mapping suggestions.
    """
    import base64
    from PIL import Image
    import io

    client = get_bedrock_client(region)

    # Resize image if too large to avoid token overflow
    try:
        pil_img = Image.open(io.BytesIO(image_bytes))
        if pil_img.width > 1500 or pil_img.height > 2000:
            pil_img.thumbnail((1500, 2000))
            buf = io.BytesIO()
            pil_img.save(buf, format="PNG")
            image_bytes = buf.getvalue()
            media_type = "image/png"
    except Exception:
        pass  # If resize fails, use original

    user_message = """This is a scanned Explanation of Benefits (EOB) or paper remittance advice document.

Please:
1. Extract all key data fields (patient name, claim numbers, service dates, billed/allowed/paid amounts, adjustment reason codes, remark codes)
2. Map each field to its X12 835 EDI equivalent segment/element
3. Identify any data that appears incorrect, missing, or would cause EDI validation issues
4. Suggest the corresponding 835 ERA segments that should reflect this data

Respond in JSON format with fields: extracted_data, edi_mappings, potential_issues, suggested_835_segments"""

    try:
        response = client.converse(
            modelId=model_id,
            system=[{"text": SYSTEM_PROMPT}],
            messages=[{
                "role": "user",
                "content": [
                    {
                        "image": {
                            "format": media_type.split("/")[1],
                            "source": {"bytes": image_bytes}
                        }
                    },
                    {"text": user_message}
                ]
            }],
            inferenceConfig={
                "maxTokens": 4096,
                "temperature": 0.1
            }
        )

        raw_text = response["output"]["message"]["content"][0]["text"]
        return clean_json_response(raw_text)

    except ClientError as e:
        return {
            "error": True,
            "message": f"Bedrock API error: {e.response['Error']['Message']}"
        }
    except ValueError as e:
        return {
            "error": True,
            "message": str(e)
        }
    except Exception as e:
        return {
            "error": True,
            "message": f"Unexpected error: {str(e)}"
        }