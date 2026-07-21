# Blink — Scalable URL Shortener (Zero-Cost Cloud Stack)

A production-style URL shortening service built entirely on free-tier cloud infrastructure — no local servers, no credit card, no self-hosted database. Designed to demonstrate real system-design thinking (caching, rate limiting, distributed ID generation, async analytics) rather than just a CRUD toy.

> Redirect fast. Scale honestly. Cost nothing.

---

## ✨ Features

- **Core shortening & redirect** — base62-encoded short codes backed by Postgres
- **Custom aliases** — pick your own short code, with charset/length validation
- **Write-through Redis cache** — redirects are served from cache before hitting the DB
- **Rate limiting** — per-IP token bucket on link creation to prevent abuse
- **Link expiry & soft delete** — TTL-based expiry with cache invalidation on disable
- **Malicious URL screening** — every submitted URL is checked against Google Safe Browsing before a short link is issued
- **Auth & per-user links** — optional sign-in via Supabase Auth, with higher rate limits for authenticated users
- **Abuse reporting** — anyone can report a link; flagged links can be disabled by an admin
- **Async click analytics** — clicks are streamed to a worker and aggregated without slowing down the redirect path
- **Snowflake-style ID generation** — timestamp + machine-id + sequence IDs, built to scale horizontally even on a single instance
- **QR code generation** — instant QR code for any short link
- **Load-tested** — published p50/p99 latency numbers under real traffic

---

## 🏗️ Architecture

```
                     ┌─────────────────────┐
                     │   Cloudflare Pages  │  ← Frontend (static, edge-delivered)
                     └──────────┬──────────┘
                                │ HTTPS
                     ┌──────────▼───────────┐
                     │   Render Web Service │  ← FastAPI / Node backend
                     └──────────┬───────────┘
                    ┌───────────┼────────────┐
                    │           │            │
           ┌────────▼────┐ ┌────▼──────┐ ┌───▼────────────────┐
           │ Neon /      │ │ Upstash   │ │ Google Safe        │
           │ Supabase    │ │ Redis     │ │ Browsing API v4    │
           │ (Postgres)  │ │ (cache +  │ │ (malicious URL     │
           │             │ │ rate limit│ │  screening)        │
           │             │ │ + streams)│ │                    │
           └─────────────┘ └───────────┘ └────────────────────┘
```

**Request flow (redirect path):**
`GET /:code` → check Redis cache → cache hit? redirect immediately → cache miss? read Postgres → populate cache → redirect → fire click event to Redis Stream (async, non-blocking)

**Request flow (create path):**
`POST /shorten` → rate limit check (Redis) → Safe Browsing check (cached verdicts) → generate Snowflake-style ID → base62 encode → write to Postgres → write-through to Redis → return short URL

---

## 🧰 Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | Cloudflare Pages / Vercel | Free forever, edge delivery, no card required |
| Backend | FastAPI on Render (free Web Service) | No card required, simple Docker/Git deploy |
| Database | Neon (serverless Postgres) or Supabase | Free indefinitely, scales to zero, fast resume |
| Cache & rate limiter | Upstash Redis | REST-based, works over serverless/Render without persistent TCP |
| Malicious URL check | Google Safe Browsing Lookup API v4 | Free for non-commercial use |
| Analytics | Postgres `click_events` table | No need for ClickHouse/Kafka at this traffic scale |
| Async queue | Upstash Redis Streams | Avoids standing up Kafka |
| Auth | Supabase Auth | Bundled free with Supabase Postgres |
| CI/CD | GitHub Actions | Free minutes for a repo this size |

> **Known trade-off:** Render's free tier spins down after ~15 minutes of inactivity, causing a 30–50s cold start on the next request. This is called out here deliberately rather than hidden — see [Limitations](#-known-limitations).

---

## 📂 Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entrypoint
│   │   ├── routes/
│   │   │   ├── shorten.py       # POST /shorten
│   │   │   └── redirect.py      # GET /:code
│   │   ├── services/
│   │   │   ├── cache.py         # Redis read/write-through logic
│   │   │   ├── ratelimit.py     # Token bucket implementation
│   │   │   ├── safebrowsing.py  # Malicious URL check + verdict cache
│   │   │   └── idgen.py         # Snowflake-style ID generator
│   │   ├── models/               # SQLAlchemy models
│   │   └── workers/
│   │       └── analytics.py      # Redis Stream consumer → click_events
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   └── package.json
├── load-tests/
│   └── k6-script.js
├── docs/
│   └── api-spec.md
├── .github/workflows/
│   └── ci.yml
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- Free accounts: [Render](https://render.com), [Neon](https://neon.tech) or [Supabase](https://supabase.com), [Upstash](https://upstash.com), [Google Cloud](https://console.cloud.google.com) (Safe Browsing API key)

### 1. Clone & configure
```bash
git clone https://github.com/<your-username>/blink.git
cd blink
cp .env.example .env
```

Fill in `.env`:
```env
DATABASE_URL=postgresql://...
UPSTASH_REDIS_REST_URL=...
UPSTASH_REDIS_REST_TOKEN=...
SAFE_BROWSING_API_KEY=...
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
JWT_SECRET=...
```

### 2. Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```

### 4. Deploy
- Push `backend/` to Render as a Web Service (Docker or native Python runtime)
- Push `frontend/` to Cloudflare Pages or Vercel
- Point frontend's API base URL to the Render service URL

---

## 📡 API Reference

### `POST /shorten`
Create a new short link.

**Request**
```json
{
  "url": "https://example.com/very/long/path",
  "custom_alias": "my-link",   // optional
  "expires_in_days": 30        // optional
}
```

**Response**
```json
{
  "short_url": "https://blink.link/aB3xQ",
  "code": "aB3xQ",
  "expires_at": "2026-08-20T00:00:00Z"
}
```

### `GET /:code`
Redirects to the original URL (302). Fires an async click event.

### `POST /report`
Report a link as malicious/abusive.

### `GET /analytics/:code`
Returns aggregated click stats for a link (auth required for private links).

Full spec: [`docs/api-spec.md`](docs/api-spec.md)

---

## 🧪 Testing & Load Testing

```bash
# Unit tests
cd backend && pytest

# Load test (k6)
k6 run load-tests/k6-script.js
```

Latest load test results (published in `docs/load-test-report.md`):

| Metric | Value |
|---|---|
| p50 latency (cache hit) | *TBD* |
| p99 latency (cache hit) | *TBD* |
| p50 latency (cache miss) | *TBD* |
| Throughput | *TBD req/s* |

---

## ⚠️ Known Limitations

- **Cold starts:** Render's free Web Service sleeps after ~15 min idle; first request after sleep takes 30–50s. Acceptable for a demo/portfolio project, called out explicitly rather than hidden.
- **Safe Browsing rate limits:** Verdicts are cached locally so repeat submissions of the same domain don't re-check every time, but heavy bulk creation could still hit Google's quota.
- **Upstash free tier:** 500K commands/month — comfortably enough for demo traffic, but load tests should be run with an eye on the usage counter.

---

## 🗺️ Roadmap

- [X] Core shorten + redirect (M1–M3)
- [ ] Redis caching, rate limiting, expiry, custom aliases (M4–M7)
- [ ] Malicious URL screening, auth, abuse reporting (M8–M10)
- [ ] Async analytics, Snowflake ID generator (M11–M12)
- [ ] Load testing report with real numbers (M13)
- [ ] QR code generation (M14)
- [ ] Multi-instance demo proving ID/cache correctness under horizontal scale (M15)

---

## 📄 License

MIT — free to use, modify, and build on.

---

## 🙋 Author

Built by Yashu — B.Tech CSE, Graphic Era Hill University.
