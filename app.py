# app.py — Real Estate Listing Generator (Pro + BYOK, polished & complete)

import os
import io
import json
import time
import textwrap
import requests
import streamlit as st
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from dotenv import load_dotenv
from openai import OpenAI

# ======================= Config & Secrets =======================
load_dotenv()

def get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    # Prefer Streamlit Cloud secrets, fallback to environment
    try:
        return st.secrets.get(name, os.getenv(name, default))
    except Exception:
        return os.getenv(name, default)

# Pro plan (your key)
MASTER_OPENAI_API_KEY = get_secret("OPENAI_API_KEY")

# Dual / Single Gumroad product(s)
GUMROAD_PRODUCT_PERMALINK_PRO = get_secret("GUMROAD_PRODUCT_PERMALINK_PRO")
GUMROAD_PRODUCT_PERMALINK_BYOK = get_secret("GUMROAD_PRODUCT_PERMALINK_BYOK")
GUMROAD_PRODUCT_PERMALINK = get_secret("GUMROAD_PRODUCT_PERMALINK")  # single-product fallback

# Model & defaults
DEFAULT_MODEL = get_secret("OPENAI_DEFAULT_MODEL", "gpt-4o-mini")

# ======================= Page Setup & Style =======================
st.set_page_config(
    page_title="Real Estate Listing Generator",
    page_icon="🏠",
    layout="centered",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.block-container { padding-top: 2rem; }
h1 span.brand { color: #E63946; }
div[data-testid="stMetric"] { background: #fafafa; border-radius: 12px; padding: 10px; border: 1px solid #eee; }
div.stButton > button { border-radius: 10px; padding: 0.6rem 1rem; }
div.stDownloadButton > button { border-radius: 10px; }
hr { border: none; border-top: 1px solid #eee; margin: 18px 0; }
.small { color:#666; font-size: 0.9rem; }
.kbd { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; background:#f1f1f1; padding:2px 6px; border-radius:6px; }
.result-card { border:1px solid #eee; border-radius:12px; padding:16px; background:#fff; margin-bottom:14px; }
</style>
""", unsafe_allow_html=True)

st.title("🏠 <span class='brand'>Real Estate Listing Generator</span>", help="Generate polished property listings in seconds.")
st.caption("Enter a few details, choose tone & format, and get copy you can use immediately.")

# ======================= Session State =======================
if "licensed" not in st.session_state:
    st.session_state.licensed = False
if "plan" not in st.session_state:
    st.session_state.plan = None       # "pro" or "byok"
if "history" not in st.session_state:
    st.session_state.history = []      # [{inputs, outputs, ts}]
if "last_variants" not in st.session_state:
    st.session_state.last_variants = []  # list[str]

# ======================= Gumroad License (Optional) =======================
def verify_gumroad_license(license_key: str, product_permalink: str) -> Dict[str, Any]:
    """
    Minimal verification call to Gumroad. Returns JSON or {}.
    """
    try:
        url = "https://api.gumroad.com/v2/licenses/verify"
        data = {
            "product_permalink": product_permalink,
            "license_key": license_key,
            "increment_uses_count": False
        }
        r = requests.post(url, data=data, timeout=10)
        return r.json() if r.ok else {}
    except Exception:
        return {}

def license_gate():
    """Show a license gate if any Gumroad permalink envs are set."""
    dual = bool(GUMROAD_PRODUCT_PERMALINK_PRO or GUMROAD_PRODUCT_PERMALINK_BYOK)
    single = bool(GUMROAD_PRODUCT_PERMALINK) and not dual

    if not (dual or single):
        # No gating configured -> allow access
        st.session_state.licensed = True
        st.session_state.plan = "pro" if MASTER_OPENAI_API_KEY else "byok"
        return

    st.info("🔒 Enter your license key to unlock.", icon="🔑")
    with st.form("license_form"):
        license_key = st.text_input("License key", placeholder="XXXX-XXXX-XXXX-XXXX")
        submit = st.form_submit_button("Unlock")

    if submit:
        # Build list of permalinks to check
        permalinks = []
        if dual:
            if GUMROAD_PRODUCT_PERMALINK_PRO:
                permalinks.append(("pro", GUMROAD_PRODUCT_PERMALINK_PRO))
            if GUMROAD_PRODUCT_PERMALINK_BYOK:
                permalinks.append(("byok", GUMROAD_PRODUCT_PERMALINK_BYOK))
        else:
            # single product
            permalinks.append(("pro" if MASTER_OPENAI_API_KEY else "byok", GUMROAD_PRODUCT_PERMALINK))

        ok_plan = None
        for plan, p in permalinks:
            j = verify_gumroad_license(license_key, p)
            if j.get("success"):
                ok_plan = plan
                break

        if ok_plan:
            st.session_state.licensed = True
            st.session_state.plan = ok_plan
            st.success(f"License verified ✅ ({ok_plan.upper()} plan)")
            st.rerun()
        else:
            st.error("Invalid license. Please check your key or contact support.")

if not st.session_state.licensed:
    license_gate()
    if not st.session_state.licensed:
        st.stop()

# ======================= API Client =======================
def get_openai_client() -> Optional[OpenAI]:
    """Return OpenAI client for PRO (master key) or BYOK (user key)."""
    if st.session_state.plan == "pro":
        if not MASTER_OPENAI_API_KEY:
            st.error("Server misconfigured: missing OPENAI_API_KEY for PRO plan.")
            return None
        return OpenAI(api_key=MASTER_OPENAI_API_KEY)

    # BYOK
    with st.sidebar:
        st.subheader("🔑 API Key (BYOK)")
        user_key = st.text_input(
            "Your OpenAI API key",
            type="password",
            placeholder="sk-...",
            help="Your requests bill to your own OpenAI account."
        )
        st.caption("We do not store your key. It remains in your session.")
    if not user_key:
        st.warning("Enter your OpenAI API key in the sidebar to continue.", icon="⚠️")
        return None
    return OpenAI(api_key=user_key)

client = get_openai_client()
if client is None:
    st.stop()

# ======================= Sidebar Controls =======================
with st.sidebar:
    st.header("⚙️ Settings")
    model = st.selectbox(
        "Model",
        options=[DEFAULT_MODEL, "gpt-4o", "gpt-4o-mini"],
        index=0,
        help="4o-mini is cost-effective and fast. 4o is higher quality at higher cost."
    )
    temperature = st.slider("Creativity (temperature)", 0.0, 1.2, 0.7, 0.1)
    variants = st.select_slider("Number of variants", options=[1, 2, 3], value=2)
    st.divider()
    st.caption("Pro tip: keep variants at 2–3 to pick the best version quickly.")

# ======================= Form =======================
with st.form("listing_form"):
    st.subheader("Property Details")

    address = st.text_input("Address / Area", placeholder="e.g., 20 Maunder Close, RM16 6BB")
    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        beds = st.number_input("Bedrooms", min_value=0, step=1, value=2)
    with col2:
        baths = st.number_input("Bathrooms", min_value=0, step=1, value=1)
    with col3:
        property_type = st.selectbox("Property Type", [
            "Flat/Apartment", "House", "Studio", "Bungalow", "Townhouse", "New Build", "Other"
        ])

    features = st.text_area(
        "Key Features (comma-separated)",
        value="south-facing garden, remodeled kitchen, off-street parking, near station",
        help="3–8 concise features work best."
    )

    st.subheader("Style & Constraints")
    tone = st.selectbox("Tone", [
        "Professional", "Warm", "Luxury", "Concise", "Investor-Focused", "Family-Friendly"
    ])
    audience = st.selectbox("Target Audience", [
        "General buyers", "First-time buyers", "Families", "Investors", "Renters"
    ])
    length = st.slider("Length (words)", 80, 240, 150, 10)
    spelling = st.selectbox("Spelling", ["UK", "US"])
    include_keywords = st.text_input("Must-include keywords (comma-separated)", placeholder="near schools, chain-free")
    avoid_phrases = st.text_input("Avoid phrases (comma-separated)", placeholder="The property, apologies")
    format_choice = st.selectbox("Format", [
        "Paragraphs",
        "Short summary + paragraph",
        "Headline + paragraph"
    ])

    st.subheader("Extras")
    add_title = st.checkbox("Generate a property headline/title", value=True)
    add_cta = st.checkbox("Generate a short call-to-action line", value=True)
    add_bullets = st.checkbox("Add 3 selling-point bullets (optional)", value=False)

    submitted = st.form_submit_button("✨ Generate Listing")

# ======================= Prompt Builder =======================
def build_prompt() -> str:
    kw_in = [k.strip() for k in include_keywords.split(",") if k.strip()]
    avoid = [k.strip() for k in avoid_phrases.split(",") if k.strip()]
    words_hint = f"Aim for ~{length} words (±15%)."

    format_rules = {
        "Paragraphs": "Produce 1–2 short paragraphs. No bullet lists.",
        "Short summary + paragraph": "Start with a one-sentence summary, then one paragraph. No bullet lists.",
        "Headline + paragraph": "Begin with a short, catchy headline on its own line, then one paragraph.",
    }

    label_beds = "studio" if beds == 0 else f"{beds}-bedroom"
    label_baths = f"{baths} bathroom" if baths == 1 else f"{baths} bathrooms"

    spelling_note = "Use UK spelling." if spelling == "UK" else "Use US spelling."

    bullets_clause = "Also include 3 concise selling-point bullets." if add_bullets else "Do not use bullet lists."

    title_clause = "If appropriate, include a property headline/title." if add_title else "Do not include a separate headline."
    cta_clause = "End with a short one-line call to action." if add_cta else "Do not include a call to action."

    must_include = ("Ensure you naturally include these keywords: " + ", ".join(kw_in) + ".") if kw_in else ""
    avoid_text = ("Avoid using these words/phrases: " + ", ".join(avoid) + ".") if avoid else ""

    return f"""
You are an expert real-estate listing copywriter.

Write a polished listing for a {property_type.lower()} at {address}.
It is a {label_beds}, {label_baths} property.
Key features: {features or "N/A"}.
Target audience: {audience}.
Desired tone: {tone.lower()}.
Formatting style: {format_choice}.
{title_clause}
{cta_clause}
{bullets_clause}
{words_hint}
{spelling_note}
{must_include}
{avoid_text}

Rules:
- Clear, engaging, and sales-focused.
- Avoid repetition and filler.
- No apologies or AI disclaimers.
- Keep it realistic; don't invent features.

Return only the listing text (no extra commentary).
""".strip()

# ======================= Generation =======================
def generate_variants(n: int) -> List[str]:
    """Generate n variants using the chat.completions API."""
    prompt = build_prompt()
    results = []
    for i in range(n):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You write excellent property listings."},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                max_tokens=700,
            )
            text = (resp.choices[0].message.content or "").strip()
            if text:
                results.append(text)
        except Exception as e:
            st.error(f"OpenAI error (variant {i+1}): {e}")
            break
    return results

def to_txt_bundle(texts: List[str]) -> bytes:
    """Create a plain-text bundle for download."""
    chunks = []
    for idx, t in enumerate(texts, start=1):
        chunks.append(f"=== VARIANT {idx} ===\n{t}\n")
    return "\n".join(chunks).encode("utf-8")

# ======================= Render & Actions =======================
if submitted:
    if not address.strip():
        st.error("Please enter an address/location.")
    else:
        with st.spinner("Generating…"):
            outs = generate_variants(int(variants))

        if not outs:
            st.warning("No text returned. Try adjusting inputs and generate again.")
        else:
            st.session_state.last_variants = outs
            # Record history (lightweight)
            st.session_state.history.append({
                "inputs": {
                    "address": address,
                    "beds": beds,
                    "baths": baths,
                    "property_type": property_type,
                    "features": features,
                    "tone": tone,
                    "audience": audience,
                    "length": length,
                    "spelling": spelling,
                    "include_keywords": include_keywords,
                    "avoid_phrases": avoid_phrases,
                    "format_choice": format_choice,
                    "title": add_title,
                    "cta": add_cta,
                    "bullets": add_bullets,
                },
                "outputs": outs,
                "ts": int(time.time())
            })

            st.subheader("Results")
            for i, text in enumerate(outs, start=1):
                with st.container():
                    st.markdown(f"**Variant {i}**")
                    st.markdown(f"<div class='result-card'>{textwrap.dedent(text)}</div>", unsafe_allow_html=True)
                    c1, c2 = st.columns([1,1])
                    with c1:
                        st.code(text, language="markdown")
                    with c2:
                        st.button(f"Copy Variant {i}", type="secondary", key=f"copy_btn_{i}",
                                  help="Select the code block on the left and press ⌘C / Ctrl+C to copy.")

            # Download all
            data = to_txt_bundle(outs)
            st.download_button(
                "⬇️ Download all variants (.txt)",
                data=data,
                file_name="listing_variants.txt",
                mime="text/plain"
            )

# ======================= History Panel =======================
with st.expander("🕘 History (this session)"):
    if not st.session_state.history:
        st.caption("No history yet.")
    else:
        for item in reversed(st.session_state.history[-5:]):
            ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(item["ts"]))
            meta = item["inputs"]
            st.markdown(f"**{meta.get('address','(no address)')}** — {ts}")
            st.caption(f"{meta.get('beds')} bd / {meta.get('baths')} ba · {meta.get('property_type')}")
            for j, out in enumerate(item["outputs"], start=1):
                st.markdown(f"*Variant {j}:* {out[:160]}{'…' if len(out)>160 else ''}")
            st.markdown("---")

# ======================= Footer Tips =======================
st.markdown("<hr/>", unsafe_allow_html=True)
st.caption("Tip: For UK agents, keep spelling on UK and emphasize proximity to stations, schools, and high streets. For investors, highlight yields, tenant appeal, and low maintenance.")
