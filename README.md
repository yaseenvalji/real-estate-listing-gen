🏠 Relura — Real Estate Listing Generator Pro

Generate professional property listings in seconds.

Why it exists

Estate agents lose hours writing listings that often sound the same. This tool solves that — you enter the details, it creates polished copy instantly.

Features

Instant property descriptions, headlines & bullet points

Multiple tones (luxury, family, investor, professional)

Fair-use limits to keep performance reliable

Secure Gumroad license system + admin override

Tech stack

Frontend: Streamlit

AI: OpenAI GPT-4o family

Licensing: Gumroad API integration

Hosting: Streamlit Cloud

Secrets: Streamlit → Settings → Secrets

Example secrets:

OPENAI_API_KEY = "sk-your-master-key"
OPENAI_DEFAULT_MODEL = "gpt-4o-mini"
GUMROAD_PRODUCT_PERMALINK = "real-estate-listing-gen-pro"
ADMIN_BYPASS = "override-code"
USAGE_DAILY_LIMIT = "50"
USAGE_COOLDOWN_SECONDS = "5"

Run locally
git clone https://github.com/relura/real-estate-listing-generator.git
cd real-estate-listing-generator
pip install -r requirements.txt
streamlit run app.py

Roadmap

Bulk CSV upload

Export to Word/PDF

Portal-specific templates (Rightmove, Zoopla)

About Relura

We build practical AI tools that save time and help professionals win more business.

👉 Product page: [link]
📩 support@yourdomain.com
