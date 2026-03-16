"""
EDIErrorDoctor - Amazon Nova Hackathon 2025
AI-powered X12 EDI debugging tool for healthcare revenue cycle teams.
"""

import streamlit as st
import json
from pathlib import Path
from utils.edi_parser import parse_edi_file, EDIParseResult
from utils.nova_client import analyze_edi_with_nova, analyze_image_with_nova
from utils.guardrails import check_for_phi
from utils.report_export import generate_report

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="EDIErrorDoctor",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600;700&display=swap');

:root {
    --bg:       #0d1117;
    --surface:  #161b22;
    --border:   #30363d;
    --accent:   #58a6ff;
    --green:    #3fb950;
    --red:      #f85149;
    --yellow:   #d29922;
    --text:     #e6edf3;
    --muted:    #8b949e;
    --mono:     'IBM Plex Mono', monospace;
    --sans:     'IBM Plex Sans', sans-serif;
}

html, body, [class*="css"] {
    font-family: var(--sans);
    background-color: var(--bg);
    color: var(--text);
}

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: var(--surface);
    border-right: 1px solid var(--border);
}

/* Header */
.edi-header {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 1.5rem 0 1rem;
    border-bottom: 1px solid var(--border);
    margin-bottom: 1.5rem;
}
.edi-header .logo {
    font-size: 2.2rem;
    line-height: 1;
}
.edi-header h1 {
    font-size: 1.7rem;
    font-weight: 700;
    color: var(--text);
    margin: 0;
    letter-spacing: -0.02em;
}
.edi-header .sub {
    font-size: 0.78rem;
    color: var(--muted);
    font-family: var(--mono);
    letter-spacing: 0.06em;
    text-transform: uppercase;
}

/* Metric cards */
.metric-row { display: flex; gap: 12px; margin-bottom: 1.5rem; flex-wrap: wrap; }
.metric-card {
    flex: 1; min-width: 130px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1rem 1.2rem;
}
.metric-card .val { font-size: 1.8rem; font-weight: 700; font-family: var(--mono); }
.metric-card .lbl { font-size: 0.72rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; margin-top: 2px; }
.metric-card.red   .val { color: var(--red); }
.metric-card.yellow .val { color: var(--yellow); }
.metric-card.green  .val { color: var(--green); }
.metric-card.blue   .val { color: var(--accent); }

/* Error item */
.error-item {
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 3px solid var(--red);
    border-radius: 6px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.8rem;
}
.error-item.warning { border-left-color: var(--yellow); }
.error-item .seg {
    font-family: var(--mono);
    font-size: 0.82rem;
    color: var(--accent);
    margin-bottom: 6px;
}
.error-item .msg { font-size: 0.93rem; color: var(--text); }
.error-item .fix {
    margin-top: 8px;
    font-size: 0.85rem;
    color: var(--muted);
    font-family: var(--mono);
    background: rgba(88,166,255,0.07);
    border-radius: 4px;
    padding: 6px 10px;
}

/* Code block override */
.stCode, pre {
    font-family: var(--mono) !important;
    background: #0d1117 !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
}

/* Buttons */
.stButton > button {
    background: var(--accent) !important;
    color: #0d1117 !important;
    font-weight: 600 !important;
    border: none !important;
    border-radius: 6px !important;
    font-family: var(--sans) !important;
}
.stButton > button:hover { opacity: 0.85 !important; }

/* Tabs */
[data-baseweb="tab-list"] { border-bottom: 1px solid var(--border) !important; }
[data-baseweb="tab"] { font-family: var(--sans) !important; color: var(--muted) !important; }
[aria-selected="true"] { color: var(--accent) !important; }

/* Success/error banners */
.stAlert { border-radius: 6px !important; }

/* Section labels */
.section-label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--muted);
    font-family: var(--mono);
    margin-bottom: 8px;
    margin-top: 1.5rem;
}

.snip-badge {
    display: inline-block;
    font-family: var(--mono);
    font-size: 0.72rem;
    padding: 2px 8px;
    border-radius: 4px;
    background: rgba(88,166,255,0.12);
    color: var(--accent);
    border: 1px solid rgba(88,166,255,0.3);
    margin-right: 6px;
}
</style>
""", unsafe_allow_html=True)


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="edi-header">
  <div class="logo">🩺</div>
  <div>
    <h1>EDIErrorDoctor</h1>
    <div class="sub">Amazon Nova · X12 EDI Diagnostics · Healthcare Revenue Cycle</div>
  </div>
</div>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Configuration")

    aws_region = st.selectbox(
        "AWS Region",
        ["us-east-1", "us-west-2", "eu-west-1"],
        index=0,
    )
    nova_model = st.selectbox(
        "Nova Model",
        ["amazon.nova-pro-v1:0", "amazon.nova-lite-v1:0", "amazon.nova-micro-v1:0"],
        index=0,
        help="Nova Pro recommended for complex 837/835 analysis"
    )
    guardrails_on = st.toggle("Bedrock Guardrails (PHI detection)", value=True)

    st.divider()
    st.markdown("### 📂 Load Sample Files")
    sample_dir = Path(__file__).parent / "synthetic_edi"
    samples = list(sample_dir.glob("*.edi")) if sample_dir.exists() else []
    if samples:
        chosen = st.selectbox("Synthetic test file", ["— choose —"] + [f.name for f in samples])
        if chosen != "— choose —":
            st.session_state["sample_loaded"] = (sample_dir / chosen).read_text()
            st.success(f"Loaded: {chosen}")
    else:
        st.info("No sample files found. Run `python synthetic_edi/generate_samples.py` first.")

    st.divider()
    st.markdown(
        "<div style='font-size:0.72rem; color:#8b949e;'>"
        "⚠️ Demo uses 100% synthetic data.<br>No real PHI is ever processed."
        "</div>", unsafe_allow_html=True
    )


# ── Main tabs ─────────────────────────────────────────────────────────────────
tab_text, tab_image, tab_about = st.tabs(["📄 EDI Text Analysis", "🖼️ EOB Image (Multimodal)", "ℹ️ About"])


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — EDI Text Analysis
# ═══════════════════════════════════════════════════════════════════════════════
with tab_text:
    col_upload, col_or, col_paste = st.columns([3, 0.3, 3])

    with col_upload:
        st.markdown('<div class="section-label">Upload EDI File</div>', unsafe_allow_html=True)
        uploaded = st.file_uploader(
            "Drop .edi / .txt / .x12 file here",
            type=["edi", "txt", "x12"],
            label_visibility="collapsed",
        )

    with col_or:
        st.markdown("<br><br><center style='color:#8b949e;font-size:0.8rem;'>— or —</center>", unsafe_allow_html=True)

    with col_paste:
        st.markdown('<div class="section-label">Paste EDI Directly</div>', unsafe_allow_html=True)
        default_text = st.session_state.get("sample_loaded", "")
        edi_text_input = st.text_area(
            "Paste raw X12 EDI here",
            value=default_text,
            height=150,
            placeholder="ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *230101*1200*^*00501*000000001*0*T*:~\n...",
            label_visibility="collapsed",
        )

    # Resolve final EDI text
    edi_raw = None
    if uploaded:
        edi_raw = uploaded.read().decode("utf-8", errors="replace")
        st.success(f"✅ File loaded: `{uploaded.name}` ({len(edi_raw):,} chars)")
    elif edi_text_input.strip():
        edi_raw = edi_text_input.strip()

    st.markdown('<div class="section-label">Transaction Type</div>', unsafe_allow_html=True)
    tx_type = st.radio(
        "Transaction type",
        ["Auto-detect", "837P (Professional)", "837I (Institutional)", "835 ERA", "278 Prior Auth", "270/271 Eligibility"],
        horizontal=True,
        label_visibility="collapsed",
    )

    run_btn = st.button("🔍 Analyze with Amazon Nova", disabled=(edi_raw is None), use_container_width=True)

    if run_btn and edi_raw:
        # PHI guardrail check
        if guardrails_on:
            phi_result = check_for_phi(edi_raw)
            if phi_result["detected"]:
                st.error(
                    f"🛑 **Guardrail triggered**: Possible PHI pattern detected "
                    f"(`{phi_result['pattern']}`). Please use synthetic data only."
                )
                st.stop()

        with st.spinner("Parsing EDI structure…"):
            parse_result: EDIParseResult = parse_edi_file(edi_raw, tx_type)

        with st.spinner("Consulting Amazon Nova…"):
            nova_result = analyze_edi_with_nova(
                edi_raw, parse_result, nova_model, aws_region
            )

        # ── Summary metrics ──
        errors   = nova_result.get("errors", [])
        warnings = nova_result.get("warnings", [])
        n_segs   = parse_result.segment_count
        snip_lvl = parse_result.highest_snip_level

        st.markdown(f"""
        <div class="metric-row">
          <div class="metric-card red">
            <div class="val">{len(errors)}</div>
            <div class="lbl">Errors</div>
          </div>
          <div class="metric-card yellow">
            <div class="val">{len(warnings)}</div>
            <div class="lbl">Warnings</div>
          </div>
          <div class="metric-card blue">
            <div class="val">{n_segs}</div>
            <div class="lbl">Segments</div>
          </div>
          <div class="metric-card {'green' if snip_lvl >= 5 else 'yellow'}">
            <div class="val">L{snip_lvl}</div>
            <div class="lbl">SNIP Level</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Tabs: Errors / Fix / Clean EDI / Raw JSON ──
        r1, r2, r3, r4 = st.tabs(["🚨 Errors & Explanations", "🔧 Fix Suggestions", "✅ Corrected EDI", "📋 Raw Analysis"])

        with r1:
            if not errors and not warnings:
                st.success("No errors found — EDI appears valid!")
            for e in errors:
                snip = f'<span class="snip-badge">SNIP {e.get("snip_level","?")}</span>' if e.get("snip_level") else ""
                st.markdown(f"""
                <div class="error-item">
                  <div class="seg">{snip}{e.get('segment','')}</div>
                  <div class="msg">💬 {e.get('explanation', e.get('message',''))}</div>
                  {'<div class="fix">→ ' + e.get('fix_hint','') + '</div>' if e.get('fix_hint') else ''}
                </div>
                """, unsafe_allow_html=True)
            for w in warnings:
                st.markdown(f"""
                <div class="error-item warning">
                  <div class="seg">{w.get('segment','')}</div>
                  <div class="msg">⚠️ {w.get('explanation', w.get('message',''))}</div>
                </div>
                """, unsafe_allow_html=True)

        with r2:
            summary = nova_result.get("fix_summary", "")
            if summary:
                st.markdown(f"**Nova's Fix Plan:**\n\n{summary}")
            st.divider()
            for i, e in enumerate(errors, 1):
                if e.get("corrected_segment"):
                    st.markdown(f"**Fix {i} — `{e.get('segment','')}`**")
                    cols = st.columns(2)
                    with cols[0]:
                        st.caption("Original")
                        st.code(e.get("original_segment", "—"), language="text")
                    with cols[1]:
                        st.caption("Corrected")
                        st.code(e.get("corrected_segment"), language="text")

        with r3:
            clean_edi = nova_result.get("corrected_edi", "")
            if clean_edi:
                st.code(clean_edi, language="text")
                st.download_button(
                    "⬇️ Download Corrected EDI",
                    data=clean_edi,
                    file_name="corrected_claim.edi",
                    mime="text/plain",
                )
            else:
                st.info("No corrected EDI generated (file may be valid or errors too severe).")

        with r4:
            st.json(nova_result)
            report_md = generate_report(parse_result, nova_result)
            st.download_button(
                "⬇️ Export Markdown Report",
                data=report_md,
                file_name="edi_analysis_report.md",
                mime="text/markdown",
            )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Multimodal EOB Image
# ═══════════════════════════════════════════════════════════════════════════════
with tab_image:
    st.markdown("### Upload Scanned EOB / Remittance Image")
    st.caption("Nova will extract key data and map it to EDI 835 equivalents, identifying discrepancies.")

    img_file = st.file_uploader(
        "Upload EOB image (PNG, JPG, PDF)",
        type=["png", "jpg", "jpeg", "pdf"],
        label_visibility="collapsed",
    )
    if img_file:
        st.image(img_file, caption="Uploaded EOB", use_column_width=True)
        if st.button("🔍 Analyze EOB with Nova Vision"):
            with st.spinner("Nova is reading the EOB…"):
                result = analyze_image_with_nova(img_file.read(), img_file.type, nova_model, aws_region)
            st.subheader("Extracted Data")
            st.json(result.get("extracted_data", {}))
            st.subheader("835 Mapping & Issues")
            for issue in result.get("issues", []):
                st.warning(f"**{issue['field']}**: {issue['description']}")
    else:
        st.info("Upload a scanned EOB, paper remittance, or explanation of benefits to begin.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — About
# ═══════════════════════════════════════════════════════════════════════════════
with tab_about:
    st.markdown("""
## About EDIErrorDoctor

**EDIErrorDoctor** uses **Amazon Nova Pro** via Amazon Bedrock to provide AI-powered 
diagnostics for X12 EDI healthcare transactions.

### Supported Transaction Types
| TX Set | Description |
|--------|-------------|
| **837P** | Professional claims |
| **837I** | Institutional claims |
| **835** | Electronic Remittance Advice |
| **278** | Prior Authorization |
| **270/271** | Eligibility Inquiry/Response |

### SNIP Validation Levels
| Level | Description |
|-------|-------------|
| 1 | Basic ISA/GS envelope integrity |
| 2 | Syntactical requirements |
| 3 | Balancing requirement |
| 4 | Inter-segment syntax rules |
| 5 | External code sets |
| 6 | Internal code sets |
| 7 | Product/provider approval |

### Privacy & Compliance
- ✅ 100% synthetic data in demo
- ✅ Amazon Bedrock Guardrails for PHI detection
- ✅ No data stored outside your AWS account
- ✅ HIPAA-eligible AWS services used throughout

### Architecture
```
User Upload → Streamlit UI
    → PHI Guardrail Check (Bedrock)
    → EDI Parser (Python)
    → Amazon Nova Pro (Bedrock Converse API)
    → Structured Error + Fix Response
    → Corrected EDI Export
```
    """)
