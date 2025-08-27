# 🏠 Real Estate Listing Generator Pro  

Generate polished property listings in seconds with AI.  
Built by Yaseen Valji (Relura CEO)

---

## 📖 Overview  

Estate agents waste hours writing listings that often end up generic.  
This tool solves that problem by turning basic property details into professional, ready-to-publish descriptions instantly.  

Key features:  
- 🔒 **License-gated** via Gumroad (secure access)  
- 👨‍💻 **Admin override** for development and testing  
- 📊 **Daily usage caps + cooldowns** (auto-reset at midnight)  
- ✨ **Multiple listing variants** (headlines, bullets, full descriptions)  
- 🗂 **Session history & TXT export**  

---

## 🛠 Tech Stack  

- **Frontend:** Streamlit  
- **AI Engine:** OpenAI GPT-4o family  
- **Licensing:** Gumroad API integration  
- **Hosting:** Streamlit Cloud  
- **Config & Secrets:** Streamlit Secrets + `.env`  

---

## ⚙️ Setup  

Clone the repo:  
```bash
git clone https://github.com/relura/real-estate-listing-generator.git
cd real-estate-listing-generator
```
Install dependencies:
```bash
pip install -r requirements.txt
```
Run locally:
```bash
streamlit run app.py
```
## 🔑 Configuration

Create a .streamlit/secrets.toml file with:

OPENAI_API_KEY = "sk-your-master-key"
OPENAI_DEFAULT_MODEL = "gpt-4o-mini"
GUMROAD_PRODUCT_PERMALINK = "real-estate-listing-gen-pro"
ADMIN_BYPASS = "your-private-override"
USAGE_DAILY_LIMIT = "50"
USAGE_COOLDOWN_SECONDS = "5"

## 👤 About Relura

I’m building Relura to create practical AI tools that solve real problems for professionals.
This project started with one question: why are agents still wasting hours writing generic listings by hand?

The Real Estate Listing Generator Pro is our answer — fast, reliable, and professional.
This is just the first step.



