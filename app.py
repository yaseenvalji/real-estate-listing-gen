# app.py — Real Estate Listing Generator (PRO only, with readable output cards)

import os
import time
import textwrap
import requests
import datetime as dt
import streamlit as st
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from openai import OpenAI

# ================== Config & Secrets ==================
load_dotenv()

def get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    try:
        return st.secrets.get(name, os.getenv(name, default))
    except Exception:
        return os.getenv(name, default)

# Required (your master API key; users never see this)
OPENAI_API_KEY = get_secret("OPENAI_API_KEY")
DEFAULT_MODEL  = get_secret("OPENAI_DEFAULT_MODEL", "gpt-4o-mini")

# License gate (Gumroad permalink slug, e.g., "real-estate-listing-gen-pro")
GUMROAD_PRODUCT_PERMALINK = get_secret("GUMROAD_PRODUCT_PERMALINK", "")

# Admin override (enter this in the gate to unlock without purchase)
ADMIN_OVERRIDE_CODE = get_secret("ADMIN_BYPASS", "")  # leave blank to disable

# Usage controls
USAGE_DAILY_LIMIT      = int(get_secret("USAGE_DAILY_LIMIT", "50"))      # generations/day
USAGE_COOLDOWN_SECONDS = int(get_secret("USAGE_COOLDOWN_SECONDS", "5"))  # seconds between clicks

# Model temperature (fixed; no slider)
TEMPERATURE = 0.7

# ================== Page & Styles ==================
st.set_page_config(page_title="Real Estate Listing Generator", page_icon="🏠", layout="centered")

st.markdown("""
<style>
/* Layout */
.block-container { padding-top: 2rem; }

/* Buttons */
div.stButton > button, div.stDownloadButton > button { 
  border-radius: 10px; padding: 0.6rem 1rem; 
}

/* Result card: strong contrast for both themes */
.result-card {
  border:1px solid #e8e8e8; 
  border-radius:12px; 
  padding:18px; 
  background:#ffffff; 
  box-shadow: 0 2px 14px rgba(0,0,0,0.05);
  margin:14px 0;
}
.result-card, .result-card * { 
  color:#111 !important; 
  text-shadow:none !important; 
  opacity:1 !important; 
}
.result-card code, .result-card pre {
  background:transparent !important; 
  color:#111 !important;
}

/* Misc */
hr { border:none; border-top:1px solid #eee; margin: 18px 0; }
.small { color:#666; font-size:0.9rem; }
.variant-title { font-weight:600; margin-top:8px; }
</style>
""", unsafe_allow_html=True)

st.title("🏠 Real Estate Listing Generator")
# Show this caption ONLY before the user unlocks
if not st.session_state.get("licensed", False):
    st.caption("Unlock with your purchase key. Admins can use a private override code.")

# ================== Guards ==================
if not OPENAI_API_KEY:
    st.error("Server misconfigured: missing OPENAI_API_KEY (set it in Streamlit Secrets).")
    st.stop()

# ================== Session State ==================
if "licensed" not in st.session_state:
    st.session_state.licensed = False
if "history" not in st.session_state:
    st.session_state.history = []
if "last_variants" not in st.session_state:
    st.session_state.last_variants = []
if "usage" not in st.session_state:
    st.session_state.usage = {
        "date": dt.date.today().isoformat(),
        "count": 0,
        "last_ts": 0.0,
        "bypass": False,  # True when admin override is accepted
    }

# ================== License Helpers ==================
def verify_gumroad_license(license_key: str, product_permalink: str) -> bool:
    """Return True if the Gumroad license is valid for the product."""
    try:
        url = "https://api.gumroad.com/v2/licenses/verify"
        data = {
            "product_permalink": product_permalink,
            "license_key": license_key,
            "increment_uses_count": False,
        }
        r = requests.post(url, data=data, timeout=10)
        j = r.json() if r.ok else {}
        return bool(j.get("success"))
    except Exception:
        return False

def show_license_gate():
    """Gate: unlock with Gumroad license key or admin override."""
    st.info("🔒 Enter your Access Key to unlock.", icon="🔑")
    with st.form("license_form"):
        access_key = st.text_input("Access Key", placeholder="Your Gumroad license key", type="password")
        ok = st.form_submit_button("Unlock")

    if ok:
        # Admin override first
        if ADMIN_OVERRIDE_CODE and access_key.strip() == ADMIN_OVERRIDE_CODE.strip():
            st.session_state.usage["bypass"] = True
            st.session_state.licensed = True
            st.success("Admin override accepted ✅")
            st.rerun()

        # Otherwise validate with Gumroad
        if not GUMROAD_PRODUCT_PERMALINK:
            st.error("Server misconfigured: missing GUMROAD_PRODUCT_PERMALINK. Contact support.")
            st.stop()

        valid = verify_gumroad_license(access_key.strip(), GUMROAD_PRODUCT_PERMALINK)
        if valid:
            st.session_state.licensed = True
            st.success("License verified ✅")
            st.rerun()
        else:
            st.error("Invalid access key. Please check your key or contact support.")

# Show gate if not yet licensed
if not st.session_state.licensed:
    show_license_gate()
    if not st.session_state.licensed:
        st.stop()

# ================== OpenAI Client ==================
client = OpenAI(api_key=OPENAI_API_KEY)

# ================== Sidebar Controls ==================
with st.sidebar:
    st.header("⚙️ Settings")

    # De-duplicated model list (DEFAULT first)
    models = list(dict.fromkeys([DEFAULT_MODEL, "gpt-4o-mini", "gpt-4o"]))
    model = st.selectbox("Model", options=models, index=0)

    # No creativity slider; fixed temperature
    variants = st.select_slider("Number of variants", options=[1, 2, 3], value=2)

    # Usage counters (reset at local midnight)
    st.markdown("---")
    today = dt.date.today().isoformat()
    if st.session_state.usage["date"] != today:
        st.session_state.usage["date"] = today
        st.session_state.usage["count"] = 0
        st.session_state.usage["last_ts"] = 0.0

    remaining = max(0, USAGE_DAILY_LIMIT - st.session_state.usage["count"])
    st.metric(label="Generations left (today)", value=remaining)

    if st.session_state.usage.get("bypass"):
        st.success("Admin bypass active")

# ================== Form ==================
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
    avoid_phrases   = st.text_input("Avoid phrases (comma-separated)", placeholder="The property, apologies")
    format_choice = st.selectbox("Format", [
        "Paragraphs",
        "Short summary + paragraph",
        "Headline + paragraph"
    ])

    st.subheader("Extras")
    add_title   = st.checkbox("Generate a property headline/title", value=True)
    add_cta     = st.checkbox("Generate a short call-to-action line", value=True)
    add_bullets = st.checkbox("Add 3 selling-point bullets (optional)", value=False)

    submitted = st.form_submit_button("✨ Generate Listing")

# ================== Prompt Builder ==================
def build_prompt() -> str:
    kw = [k.strip() for k in include_keywords.split(",") if k.strip()]
    avoid = [k.strip() for k in avoid_phrases.split(",") if k.strip()]
    label_beds  = "studio" if beds == 0 else f"{beds}-bedroom"
    label_baths = f"{baths} bathroom" if baths == 1 else f"{baths} bathrooms"
    words_hint  = f"Aim for ~{length} words (±15%)."
    spelling_note = "Use UK spelling." if spelling == "UK" else "Use US spelling."

    bullets_clause = "Also include 3 concise selling-point bullets." if add_bullets else "Do not use bullet lists."
    title_clause   = "If appropriate, include a property headline/title." if add_title else "Do not include a separate headline."
    cta_clause     = "End with a short one-line call to action." if add_cta else "Do not include a call to action."
    must_include   = ("Ensure you naturally include these keywords: " + ", ".join(kw) + ".") if kw else ""
    avoid_text     = ("Avoid using these words/phrases: " + ", ".join(avoid) + ".") if avoid else ""

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
Aim for ~{length} words (±15%).
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

# ================== Generation ==================
def generate_variants(n: int) -> List[str]:
    prompt = build_prompt()
    outs = []
    for i in range(n):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You write excellent property listings."},
                    {"role": "user", "content": prompt},
                ],
                temperature=TEMPERATURE,
                max_tokens=700,
            )
            text = (resp.choices[0].message.content or "").strip()
            if text:
                outs.append(text)
        except Exception as e:
            st.error(f"OpenAI error (variant {i+1}): {e}")
            break
    return outs

def to_txt_bundle(texts: List[str]) -> bytes:
    body = []
    for idx, t in enumerate(texts, start=1):
        body.append(f"=== VARIANT {idx} ===\n{t}\n")
    return "\n".join(body).encode("utf-8")

# ================== Submit Logic (caps + cooldown) ==================
if submitted:
    if not address.strip():
        st.error("Please enter an address/location.")
    else:
        now = time.time()
        usage = st.session_state.usage
        is_admin = bool(usage.get("bypass"))

        # Enforce caps unless admin override
        if not is_admin:
            # Daily limit
            if usage["count"] >= USAGE_DAILY_LIMIT:
                reset_at = dt.datetime.combine(dt.date.today() + dt.timedelta(days=1), dt.time.min)
                mins_left = int((reset_at - dt.datetime.now()).total_seconds() // 60)
                st.error(f"Daily limit reached. Resets in ~{mins_left} minutes.")
                st.stop()

            # Cooldown between clicks
            since = now - float(usage["last_ts"])
            if since < USAGE_COOLDOWN_SECONDS:
                wait = int(USAGE_COOLDOWN_SECONDS - since + 1)
                st.warning(f"Please wait {wait}s before generating again.")
                st.stop()

        with st.spinner("Generating…"):
            outs = generate_variants(int(variants))

        if not outs:
            st.warning("No text returned. Try adjusting inputs and generate again.")
        else:
            if not is_admin:
                usage["count"] += 1
                usage["last_ts"] = now

            st.session_state.last_variants = outs
            st.session_state.history.append({
                "inputs": {
                    "address": address, "beds": beds, "baths": baths,
                    "property_type": property_type, "features": features,
                    "tone": tone, "audience": audience, "length": length,
                    "spelling": spelling, "include_keywords": include_keywords,
                    "avoid_phrases": avoid_phrases, "format_choice": format_choice,
                    "title": add_title, "cta": add_cta, "bullets": add_bullets,
                },
                "outputs": outs,
                "ts": int(time.time())
            })

            st.subheader("Results")
            for i, text in enumerate(outs, start=1):
                st.markdown(f"<div class='variant-title'>Variant {i}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='result-card'>{textwrap.dedent(text)}</div>", unsafe_allow_html=True)

                with st.expander("Show raw text (copy)"):
                    # read-only textarea for easy copy
                    st.text_area(label=f"Variant {i} (raw)", value=text, height=220, key=f"raw_{i}")

            st.download_button(
                "⬇️ Download all variants (.txt)",
                data=to_txt_bundle(outs),
                file_name="listing_variants.txt",
                mime="text/plain"
            )

# ================== History ==================
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

st.markdown("<hr/>", unsafe_allow_html=True)
st.caption("Unlocked via Gumroad access key or admin override. Contact: yaseen.valji@gmail.com")
