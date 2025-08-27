import os
import streamlit as st
from dotenv import load_dotenv

# OpenAI Python SDK v1+
from openai import OpenAI

# ---------- Setup ----------
load_dotenv()  # loads variables from .env into environment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

st.set_page_config(page_title="Listing Generator", page_icon="🏠", layout="centered")
st.title("🏠 Real Estate Listing Description Generator")
st.write("Enter the property details to generate a compelling listing description.")

# Warn early if key is missing
if not OPENAI_API_KEY:
    st.error("OPENAI_API_KEY is missing. Create a .env file and add your key.")
    st.stop()

client = OpenAI(api_key=OPENAI_API_KEY)

# ---------- UI ----------
with st.form("listing_form"):
    address = st.text_input("Property Location/Address", placeholder="e.g., London NW1")
    col1, col2 = st.columns(2)
    with col1:
        beds = st.number_input("Bedrooms", min_value=0, step=1, value=2)
    with col2:
        baths = st.number_input("Bathrooms", min_value=0, step=1, value=1)

    features = st.text_area(
        "Key Features (comma-separated)",
        value="south-facing garden, remodeled kitchen, near tube",
    )
    tone = st.selectbox("Tone", ["Professional", "Warm", "Luxury", "Concise"], index=0)
    length = st.slider("Target Length (words)", min_value=80, max_value=220, value=150, step=10)

    submitted = st.form_submit_button("Generate Description")

# ---------- Generate ----------
if submitted:
    if not address.strip():
        st.error("Please enter an address/location.")
        st.stop()

    prompt = f"""
You are a skilled UK real-estate listing copywriter.
Write a polished property listing in a {tone.lower()} tone.

Property:
- Address/Area: {address}
- Bedrooms: {beds}
- Bathrooms: {baths}
- Features: {features}

Requirements:
- Aim for ~{length} words (±15%).
- 1–2 paragraphs, no bullet lists.
- Avoid repetition and filler.
- UK spelling. Do not mention being an AI.
"""

    with st.spinner("Generating..."):
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",  # cost-effective, modern
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that writes excellent property listings."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=500,
            )
            text = (resp.choices[0].message.content or "").strip()

            if not text:
                st.warning("No text returned. Try again or adjust inputs.")
            else:
                st.subheader("Listing Description")
                st.write(text)
                st.download_button("Download as .txt", text, file_name="listing.txt")

        except Exception as e:
            st.error(f"OpenAI error: {e}")
