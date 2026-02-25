---
title: NutriScan
emoji: 🥗
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
license: mit
---

<div align="center">

# 🥗 NutriScan

### AI-Powered Visual Food Diary

**Snap a photo of your meal → AI identifies the food → macros logged instantly.**

[![Live Demo](https://img.shields.io/badge/Live%20Demo-HuggingFace%20Spaces-yellow?style=for-the-badge&logo=huggingface)](https://dronesmasher-nutriscan.hf.space)
[![Python](https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python)](https://python.org)
[![Django](https://img.shields.io/badge/Django-5.1-green?style=for-the-badge&logo=django)](https://djangoproject.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

</div>

---

## What is NutriScan?

NutriScan is a full-stack web application that turns meal photos into detailed nutritional data. Upload a photo of anything you eat — the app uses a **Vision Transformer (Swin Transformer)** to identify the food, then automatically fetches **calories, protein, carbs, and fat** from the USDA FoodData Central database. Every meal is logged to your personal dashboard with charts showing your intake trends over time.

Built as a portfolio project to demonstrate ML integration, async programming, and modern full-stack development — running entirely on **free infrastructure**.

---

## ✨ Features

- 📸 **Photo upload** — drag-and-drop or click-to-select meal photos
- 🧠 **AI food recognition** — Swin Transformer model trained on Food-101 (92.1% accuracy, 101 food classes)
- 🥦 **Automatic macro lookup** — calories, protein, carbs, fat & fiber pulled from the USDA database
- 📊 **Personal dashboard** — 7-day calorie trend chart + today's macro breakdown (doughnut chart)
- 📋 **Meal history** — scrollable log of all past meals with thumbnails and macro summaries
- ⚡ **Real-time updates** — HTMX polling shows analysis results without page reloads
- 🔐 **User authentication** — secure registration, login, and session management
- 📱 **Responsive UI** — works on desktop and mobile

---

## 🛠️ Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Backend** | Django 5.1 + Gunicorn | Robust, batteries-included Python web framework |
| **ML Model** | [`skylord/swin-finetuned-food101`](https://huggingface.co/skylord/swin-finetuned-food101) | Swin Transformer, 92.1% accuracy on Food-101 |
| **Nutrition API** | [USDA FoodData Central](https://fdc.nal.usda.gov/) | Free, CC0-licensed, 600k+ foods, 1k req/hr |
| **Frontend** | HTMX + Alpine.js + Tailwind CSS | No build step — works natively with Django templates |
| **Charts** | Chart.js 4.x | Lightweight canvas charts via CDN |
| **Async Tasks** | Python `threading` | Zero-dependency background ML inference |
| **Database** | Neon (PostgreSQL) | Free tier that never expires |
| **File Storage** | Supabase Storage | 1 GB free, private buckets, no credit card |
| **Hosting** | HuggingFace Spaces (Docker) | 16 GB RAM free — enough to run the ViT model in-process |
| **Total Cost** | **$0 / month** | Entirely free stack |

---

## 🏗️ Architecture

```
User uploads photo
       │
       ▼
Django view (upload_meal)
  ├─ Saves image to Supabase Storage
  ├─ Creates MealLog(status=PROCESSING) in Neon PostgreSQL
  └─ Spawns daemon thread
            │
            ▼
    Background Thread (tasks.py)
      ├─ Swin Transformer classifies image → "pizza" (94% confidence)
      ├─ USDA API lookup → calories, protein, carbs, fat
      └─ Updates MealLog(status=DONE) with nutrition data
            │
            ▼
HTMX polls /api/meal/<id>/status/ every 2s
  └─ Swaps in result card when DONE (no page reload)
```

---

## 📁 Project Structure

```
Nutri-Scan/
├── config/
│   ├── settings.py        # All configuration (env-var driven)
│   ├── urls.py            # Root URL routing
│   └── wsgi.py
├── core/
│   ├── models.py          # MealLog model
│   ├── views.py           # Upload, poll, dashboard, auth views
│   ├── urls.py            # App URL patterns
│   ├── forms.py           # Upload + registration forms
│   ├── ml.py              # Swin Transformer wrapper (loaded once at startup)
│   ├── usda.py            # USDA FoodData Central API client
│   ├── storage.py         # Supabase Storage upload helper
│   ├── tasks.py           # Background thread logic
│   └── admin.py           # Django admin registration
├── templates/
│   ├── base.html          # Base layout (Tailwind, HTMX, Alpine CDN)
│   ├── auth/              # Login & register pages
│   └── core/
│       ├── dashboard.html # Main dashboard with Chart.js
│       ├── index.html     # Landing page
│       └── partials/      # HTMX swap targets (processing, result, error)
├── static/css/app.css     # HTMX indicator + transition styles
├── Dockerfile             # Bakes ML model into image; exposes port 7860
├── requirements.txt
└── .env.example           # Environment variable template
```

---

## 🚀 Local Development

### Prerequisites

- Python 3.11+
- A [Neon](https://neon.tech) free account (PostgreSQL)
- A [Supabase](https://supabase.com) free account (Storage)
- A [USDA API key](https://api.data.gov/signup) (free, email only)

### Setup

```bash
# 1. Clone the repo
git clone https://github.com/prakhyat-w/Nutri-Scan.git
cd Nutri-Scan

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env with your actual keys (see table below)

# 5. Run migrations
python manage.py migrate

# 6. Start the dev server
python manage.py runserver 7860
```

Visit [http://localhost:7860](http://localhost:7860) and register an account.

### Environment Variables

| Variable | Where to get it |
|---|---|
| `SECRET_KEY` | Run: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DEBUG` | `True` for local dev, `False` in production |
| `DATABASE_URL` | Neon dashboard → Connection Details → Connection string |
| `SUPABASE_URL` | Supabase project → Settings → API → Project URL |
| `SUPABASE_ANON_KEY` | Supabase project → Settings → API → `anon public` key |
| `SUPABASE_BUCKET` | Name of your Supabase Storage bucket (e.g. `meal-photos`) |
| `FDC_API_KEY` | [api.data.gov/signup](https://api.data.gov/signup) — free, email only |
| `ALLOWED_HOSTS` | Your domain or `*` for local dev |

---

## ☁️ Deployment (HuggingFace Spaces)

NutriScan is deployed as a Docker Space on HuggingFace — free CPU hardware with 16 GB RAM, enough to run the Swin model in-process.

```bash
# Add the HF remote (replace YOUR_USERNAME)
git remote add hf https://huggingface.co/spaces/YOUR_USERNAME/nutriscan

# Push to deploy (rebuilds automatically)
git push hf main
```

**Space setup checklist:**
- [ ] Create Space → Docker SDK → CPU Basic (free)
- [ ] Add all environment variables as **Repository Secrets** in Space Settings
- [ ] Set `ALLOWED_HOSTS` secret to `YOUR_USERNAME-nutriscan.hf.space`
- [ ] Run `python manage.py migrate` once after first successful build
- [ ] Set up a keep-warm ping at [cron-job.org](https://cron-job.org) (every 10 min, GET your Space URL)

---

## 🗺️ Roadmap

- [ ] Barcode scanning via Open Food Facts API
- [ ] Custom serving size input (currently shows per-100g values)
- [ ] Weekly/monthly nutrition reports with PDF export
- [ ] Food correction — let users override the AI's detected label
- [ ] Progressive Web App (PWA) for mobile camera access
- [ ] Multi-item meal detection (identify multiple foods in one photo)

---

## 📄 License

MIT — see [LICENSE](LICENSE) for details.

---

<div align="center">
  Built with Django · HuggingFace Transformers · USDA FoodData Central
</div>