"""
EDIErrorDoctor — AI-powered X12 EDI Debugging Tool
Powered by Amazon Nova via Amazon Bedrock
"""

import streamlit as st
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from edi_parser import (
    parse_segments, detect_transaction_type, extract_snip_errors,
    segments_to_text, summarize_edi
)
from hl7_parser import (
    parse_hl7_segments, detect_hl7_message_type, extract_hl7_errors,
    summarize_hl7, is_hl7_message
)
from nova_client import analyze_edi_with_nova, analyze_eob_image_with_nova, NOVA_PRO, NOVA_LITE

# ── Page Config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="EDIErrorDoctor",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

    /* ── Global Reset ── */
    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
        background-color: #F7F9FC;
        color: #1A2B3C;
    }
    code, pre, .stCode { font-family: 'DM Mono', monospace !important; }

    /* ── Streamlit overrides ── */
    .stApp { background-color: #F7F9FC; }
    .stSidebar { background-color: #FFFFFF !important; border-right: 1px solid #E2E8F0; }
    .stSidebar .stMarkdown { color: #4A5568; }
    section[data-testid="stSidebar"] { background-color: #FFFFFF !important; }
    .stButton > button {
        background: #FFFFFF; color: #1A56DB; border: 1.5px solid #1A56DB;
        border-radius: 8px; font-weight: 500; transition: all 0.2s;
        font-family: 'DM Sans', sans-serif;
    }
    .stButton > button:hover {
        background: #1A56DB; color: #FFFFFF; border-color: #1A56DB;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #1A56DB 0%, #0E3FA8 100%);
        color: white; border: none; padding: 0.75rem 1.5rem;
        font-size: 1rem; font-weight: 600; border-radius: 10px;
        box-shadow: 0 4px 14px rgba(26,86,219,0.35);
    }
    .stButton > button[kind="primary"]:hover {
        box-shadow: 0 6px 20px rgba(26,86,219,0.5); transform: translateY(-1px);
    }
    .stTabs [data-baseweb="tab-list"] {
        background: #FFFFFF; border-radius: 10px; padding: 4px;
        border: 1px solid #E2E8F0; gap: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px; padding: 8px 20px;
        color: #64748B; font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        background: #1A56DB !important; color: white !important;
    }
    .stSelectbox > div, .stRadio > div { color: #1A2B3C; }
    .stExpander { background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; }
    .stExpander header { font-weight: 500; color: #1A2B3C; }
    div[data-testid="stFileUploader"] {
        background: #FFFFFF; border: 2px dashed #CBD5E1;
        border-radius: 12px; padding: 1rem;
    }
    textarea { background: #FFFFFF !important; border: 1px solid #E2E8F0 !important;
               border-radius: 8px !important; color: #1A2B3C !important;
               font-family: 'DM Mono', monospace !important; font-size: 0.82rem !important; }

    /* ── Header ── */
    .main-header {
        background: linear-gradient(135deg, #1A56DB 0%, #0E3FA8 60%, #0A2D7A 100%);
        padding: 2rem 2.5rem; border-radius: 16px; margin-bottom: 1.5rem;
        box-shadow: 0 8px 32px rgba(26,86,219,0.25);
        display: flex; align-items: center; gap: 1.5rem;
    }
    .main-header-icon {
        font-size: 3rem; background: rgba(255,255,255,0.15);
        border-radius: 12px; padding: 0.5rem 0.75rem; line-height: 1;
    }
    .main-header h1 { color: #FFFFFF; margin: 0; font-size: 1.9rem; font-weight: 600; letter-spacing: -0.5px; }
    .main-header p { color: rgba(255,255,255,0.75); margin: 0.3rem 0 0; font-size: 0.95rem; }
    .main-header-badge {
        margin-left: auto; background: rgba(255,255,255,0.15);
        border: 1px solid rgba(255,255,255,0.3); border-radius: 20px;
        padding: 0.3rem 0.9rem; color: white; font-size: 0.8rem; white-space: nowrap;
    }

    /* ── Metric Cards ── */
    .metric-box {
        background: #FFFFFF; border: 1px solid #E2E8F0;
        border-radius: 12px; padding: 1.25rem 1rem;
        text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .metric-box:hover { transform: translateY(-2px); box-shadow: 0 6px 16px rgba(0,0,0,0.1); }
    .metric-box .num { font-size: 2.2rem; font-weight: 700; font-family: 'DM Mono'; line-height: 1; }
    .metric-box .label { color: #64748B; font-size: 0.8rem; margin-top: 0.3rem; text-transform: uppercase; letter-spacing: 0.5px; }
    .metric-box.total .num { color: #1A56DB; }
    .metric-box.fatal .num { color: #DC2626; }
    .metric-box.error .num { color: #EA580C; }
    .metric-box.warning .num { color: #D97706; }

    /* ── Error Cards ── */
    .error-card {
        border-left: 4px solid #DC2626; background: #FFF5F5;
        padding: 1rem 1.25rem; border-radius: 0 10px 10px 0;
        margin: 0.5rem 0; box-shadow: 0 2px 6px rgba(220,38,38,0.08);
    }
    .warning-card {
        border-left: 4px solid #D97706; background: #FFFBEB;
        padding: 1rem 1.25rem; border-radius: 0 10px 10px 0;
        margin: 0.5rem 0; box-shadow: 0 2px 6px rgba(217,119,6,0.08);
    }
    .success-card {
        border-left: 4px solid #059669; background: #F0FDF4;
        padding: 1rem 1.25rem; border-radius: 0 10px 10px 0;
        margin: 0.5rem 0; box-shadow: 0 2px 6px rgba(5,150,105,0.08);
    }

    /* ── Severity badges ── */
    .severity-fatal { color: #DC2626; font-weight: 700; }
    .severity-error { color: #EA580C; font-weight: 600; }
    .severity-warning { color: #D97706; font-weight: 500; }
    .severity-info { color: #0284C7; }

    /* ── SNIP badge ── */
    .snip-badge {
        display: inline-block; background: #EFF6FF; color: #1A56DB;
        border: 1px solid #BFDBFE; padding: 2px 8px; border-radius: 20px;
        font-family: 'DM Mono'; font-size: 0.72rem; margin-right: 0.4rem;
        font-weight: 500;
    }

    /* ── EDI code box ── */
    .edi-box {
        background: #F8FAFC; border: 1px solid #E2E8F0;
        padding: 1rem; border-radius: 8px; font-family: 'DM Mono';
        font-size: 0.8rem; white-space: pre-wrap; color: #1E3A5F;
        max-height: 300px; overflow-y: auto;
    }

    /* ── Section headers ── */
    .section-header {
        font-size: 1.1rem; font-weight: 600; color: #1A2B3C;
        border-bottom: 2px solid #E2E8F0; padding-bottom: 0.5rem;
        margin: 1.5rem 0 1rem;
    }

    /* ── Sidebar section labels ── */
    .sidebar-section {
        font-size: 0.7rem; font-weight: 600; text-transform: uppercase;
        letter-spacing: 1px; color: #94A3B8; margin: 1rem 0 0.4rem;
    }

    /* ── Summary box ── */
    .summary-box {
        background: #EFF6FF; border: 1px solid #BFDBFE;
        border-radius: 10px; padding: 1rem 1.25rem; margin: 1rem 0;
        color: #1E40AF; font-size: 0.92rem;
    }

    /* ── Footer ── */
    .footer-note {
        text-align: center; color: #94A3B8; font-size: 0.78rem;
        padding: 1rem 0; border-top: 1px solid #E2E8F0; margin-top: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# ── Header ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <div class="main-header-icon">🏥</div>
    <div>
        <h1>EDIErrorDoctor</h1>
        <p>AI-powered X12 EDI &amp; HL7 v2 analysis · Powered by Amazon Nova Pro on Bedrock</p>
    </div>
    <div class="main-header-badge">🔒 100% Synthetic Data</div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-section">⚙️ Configuration</div>', unsafe_allow_html=True)

    aws_region = st.selectbox("AWS Region", ["us-east-1", "us-west-2", "eu-west-1"], index=0)
    model_choice = st.radio(
        "Nova Model",
        ["Nova Pro (Highest accuracy)", "Nova Lite (Faster)"],
        index=0
    )
    model_id = NOVA_PRO if "Pro" in model_choice else NOVA_LITE

    st.markdown("---")
    st.markdown('<div class="sidebar-section">📋 About</div>', unsafe_allow_html=True)
    st.markdown("""
        Analyzes **X12 EDI** transactions:
        - **837P/I** — Professional & Institutional Claims
        - **835** — Electronic Remittance Advice
        - **278** — Prior Authorization
        - **270/271** — Eligibility
        - **276/277** — Claim Status

        Analyzes **HL7 v2** messages:
        - **ADT** — Admit/Discharge/Transfer
        - **ORU** — Lab & Observation Results
        - **ORM** — Orders

        Checks **SNIP Levels 1–7** including syntax, business rules, and payer edits.

        🖼️ *Multimodal EOB image analysis supported.*

        ⚠️ *Demo uses 100% synthetic data. No PHI is processed.*
        """)

    roadmap_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "data", "synthetic_edi", "EDIErrorDoctor_TechStack_Roadmap.png")
    if os.path.exists(roadmap_path):
        st.image(roadmap_path, use_container_width=True)

    st.markdown("---")
    st.markdown('<div class="sidebar-section">🧪 Load Sample Files</div>', unsafe_allow_html=True)
    sample_dir = os.path.join(os.path.dirname(__file__), "data", "synthetic_edi")
    sample_files = {
        "── X12 EDI ──": None,
        "837P — Professional Claim (errors)": "837P_with_errors.edi",
        "837P — Duplicate Claim (errors)": "837P_duplicate_claim_errors.edi",
        "837I — Institutional Claim (errors)": "837I_institutional_errors.edi",
        "835 — ERA Remittance (errors)": "835_ERA_with_errors.edi",
        "835 — ERA Denial (errors)": "835_ERA_denial_errors.edi",
        "278 — Prior Auth (errors)": "278_PriorAuth_with_errors.edi",
        "270 — Eligibility Inquiry (errors)": "270_Eligibility_errors.edi",
        "276 — Claim Status Request (errors)": "276_ClaimStatus_errors.edi",
        "── HL7 v2 ──": None,
        "HL7 ADT^A01 — Admission (errors)": "HL7_ADT_A01_with_errors.hl7",
        "HL7 ADT^A08 — Patient Update (errors)": "HL7_ADT_A08_patient_update.hl7",
        "HL7 ORU^R01 — Lab Results (errors)": "HL7_ORU_R01_with_errors.hl7",
        "HL7 ORM^O01 — Lab Order (errors)": "HL7_ORM_O01_with_errors.hl7",
    }
    for label, fname in sample_files.items():
        if fname is None:
            st.markdown(f"**{label}**")
            continue
        fpath = os.path.join(sample_dir, fname)
        if os.path.exists(fpath):
            if st.button(f"📂 {label}", use_container_width=True):
                with open(fpath) as f:
                    st.session_state["loaded_edi"] = f.read()
                    st.session_state["loaded_label"] = label
                    st.session_state.pop("last_results", None)
                    st.session_state.pop("last_edi", None)

# ── Main Tabs ────────────────────────────────────────────────────────────────
tab_edi, tab_image = st.tabs(["📄 EDI Text Analysis", "🖼️ EOB Image Analysis (Multimodal)"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: EDI TEXT ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
with tab_edi:
    col_upload, col_paste = st.columns([1, 2])

    with col_upload:
        st.markdown("#### Upload EDI File")
        uploaded = st.file_uploader("Upload .edi, .txt, .x12 or .hl7 file", type=["edi", "txt", "x12", "hl7"])
        if uploaded:
            st.session_state["loaded_edi"] = uploaded.read().decode("utf-8", errors="replace")
            st.session_state["loaded_label"] = uploaded.name
            st.session_state.pop("last_results", None)
            st.session_state.pop("last_edi", None)

    with col_paste:
        st.markdown("#### Or Paste EDI Content")
        default_text = st.session_state.get("loaded_edi", "")
        edi_input = st.text_area(
            "Paste raw X12 EDI here",
            value=default_text,
            height=200,
            placeholder="ISA*00*          *00*          *ZZ*...",
            label_visibility="collapsed"
        )

    if edi_input.strip():
        # Auto-detect format
        is_hl7 = is_hl7_message(edi_input)

        if is_hl7:
            segments = parse_hl7_segments(edi_input)
            tx_type = detect_hl7_message_type(segments)
            pre_issues = extract_hl7_errors(segments, tx_type)
            summary_text = summarize_hl7(segments, tx_type)
            format_badge = "🏥 HL7 v2"
        else:
            segments = parse_segments(edi_input)
            tx_type = detect_transaction_type(segments)
            pre_issues = extract_snip_errors(segments, tx_type)
            summary_text = summarize_edi(segments, tx_type)
            format_badge = "📋 X12 EDI"

        st.markdown("---")
        st.markdown(f"**Format:** `{format_badge}` &nbsp;|&nbsp; **Detected:** `{tx_type}` &nbsp;|&nbsp; **Pre-validation issues:** `{len(pre_issues)}`")
        st.markdown(summary_text)

        analyze_btn = st.button("🔍 Analyze with Amazon Nova", type="primary", use_container_width=True)

        if analyze_btn:
            with st.spinner(f"Sending to {model_id.split('.')[-1].split(':')[0]}... analyzing EDI..."):
                results = analyze_edi_with_nova(
                    edi_text=edi_input,
                    pre_validation_issues=pre_issues,
                    transaction_type=tx_type,
                    model_id=model_id,
                    region=aws_region
                )

            st.session_state["last_results"] = results
            st.session_state["last_edi"] = edi_input

        # Display results
        if "last_results" in st.session_state:
            results = st.session_state["last_results"]

            if results.get("error"):
                st.error(f"❌ {results['message']}")
            else:
                st.markdown("## 📊 Analysis Results")

                # Metrics row
                errors = results.get("errors", [])
                fatal = sum(1 for e in errors if e.get("severity") == "FATAL")
                errs = sum(1 for e in errors if e.get("severity") == "ERROR")
                warns = sum(1 for e in errors if e.get("severity") == "WARNING")

                m1, m2, m3, m4 = st.columns(4)
                m1.markdown(f'<div class="metric-box total"><div class="num">{len(errors)}</div><div class="label">Total Issues</div></div>', unsafe_allow_html=True)
                m2.markdown(f'<div class="metric-box fatal"><div class="num">{fatal}</div><div class="label">Fatal</div></div>', unsafe_allow_html=True)
                m3.markdown(f'<div class="metric-box error"><div class="num">{errs}</div><div class="label">Errors</div></div>', unsafe_allow_html=True)
                m4.markdown(f'<div class="metric-box warning"><div class="num">{warns}</div><div class="label">Warnings</div></div>', unsafe_allow_html=True)

                st.markdown(f'<div class="summary-box">📝 <strong>Summary:</strong> {results.get("summary", "")}</div>', unsafe_allow_html=True)

                rc_impact = results.get("revenue_cycle_impact", "")
                if rc_impact:
                    st.warning(f"💰 **Revenue Cycle Impact:** {rc_impact}")

                priority = results.get("priority_fixes", [])
                if priority:
                    st.info("🎯 **Priority Fixes:**\n" + "\n".join(f"{i+1}. {p}" for i, p in enumerate(priority)))

                # Error detail cards
                st.markdown("### 🔎 Detailed Error Analysis")
                for i, err in enumerate(errors):
                    sev = err.get("severity", "INFO")
                    card_class = {
                        "FATAL": "error-card", "ERROR": "error-card",
                        "WARNING": "warning-card"
                    }.get(sev, "success-card")
                    sev_class = f"severity-{sev.lower()}"

                    with st.expander(
                        f"[SNIP {err.get('snip_level','?')}] {err.get('segment_id','?')} "
                        f"— {err.get('plain_english','')[:80]}",
                        expanded=(i < 3)
                    ):
                        cols = st.columns([1, 2])
                        with cols[0]:
                            st.markdown(f"**Severity:** `{sev}`")
                            st.markdown(f"**SNIP Level:** `{err.get('snip_level')}`")
                            st.markdown(f"**Segment:** `{err.get('segment_id')}`")
                            st.markdown(f"**Loop:** `{err.get('loop', 'N/A')}`")
                            st.markdown(f"**Element:** `{err.get('element_position', 'N/A')}`")
                        with cols[1]:
                            st.markdown(f"**Plain English:**\n{err.get('plain_english', '')}")
                            st.markdown(f"**Technical Detail:**\n{err.get('technical_detail', '')}")
                            st.markdown(f"**Fix:** {err.get('fix_explanation', '')}")

                        if err.get("original_segment"):
                            st.markdown("**❌ Original:**")
                            st.code(err["original_segment"], language="text")
                        if err.get("corrected_segment"):
                            st.markdown("**✅ Corrected:**")
                            st.code(err["corrected_segment"], language="text")

                # Corrected EDI output
                if results.get("corrected_edi_snippet"):
                    st.markdown("### ✅ Corrected EDI Output")
                    st.code(results["corrected_edi_snippet"], language="text")
                    from datetime import datetime
                    ts = datetime.now().strftime("%Y%m%d%H%M")
                    tx_short = tx_type.split()[0].replace("/", "") if tx_type else "EDI"
                    download_filename = f"{tx_short}_corrected_{ts}.edi"
                    st.download_button(
                        "⬇️ Download Corrected EDI",
                        data=results["corrected_edi_snippet"],
                        file_name=download_filename,
                        mime="text/plain"
                    )
                    st.caption("⚠️ The corrected EDI addresses the identified errors. A full re-validation against your payer's companion guide is recommended before submission.")

                # Raw JSON
                with st.expander("🔧 Raw JSON Response"):
                    st.json(results)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: EOB IMAGE ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
with tab_image:
    st.markdown("### 🖼️ EOB / Remittance Image Analysis")
    st.info("Upload a scanned EOB or paper remittance document. Nova will extract key data fields and map them to X12 835 EDI equivalents.")

    img_file = st.file_uploader(
        "Upload scanned EOB image",
        type=["jpg", "jpeg", "png", "pdf"],
        key="eob_upload"
    )

    if img_file:
        media_type = "image/jpeg" if img_file.type in ("image/jpeg",) else "image/png"
        st.image(img_file, caption="Uploaded EOB", use_container_width=True)

        if st.button("🔍 Extract & Map with Nova", type="primary"):
            with st.spinner("Nova is reading your EOB image..."):
                img_bytes = img_file.read()
                img_result = analyze_eob_image_with_nova(img_bytes, media_type, model_id, aws_region)

            if img_result.get("error"):
                st.error(img_result["message"])
            else:
                st.markdown("### 📋 Extracted Data")
                st.json(img_result.get("extracted_data", {}))

                st.markdown("### 🔗 EDI Field Mappings")
                mappings = img_result.get("edi_mappings", {})
                if mappings:
                    for field, mapping in mappings.items():
                        st.markdown(f"- **{field}** → `{mapping}`")

                if img_result.get("suggested_835_segments"):
                    st.markdown("### 📝 Suggested 835 Segments")
                    st.code(img_result["suggested_835_segments"], language="text")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("""
<div class="footer-note">
    🔒 All demo data is 100% synthetic. No real PHI is processed. &nbsp;|&nbsp;
    Built for Amazon Nova AI Hackathon 2026 &nbsp;|&nbsp;
    Powered by Amazon Bedrock · Nova Pro
</div>
""", unsafe_allow_html=True)