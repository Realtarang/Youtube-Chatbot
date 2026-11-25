# VideoMind

**AI-powered YouTube video chat, built on Retrieval-Augmented Generation.**

Paste a YouTube link, let VideoMind extract and embed the transcript, then ask questions and get
answers grounded in what the video actually says — with clickable timestamps that seek the player.

No fabricated transcript content: if the video does not cover a question, VideoMind says so.

---

## What it does

| Capability | How it works |
| --- | --- |
| Video ingestion | URL validation → metadata (yt-dlp, oEmbed fallback) → caption extraction (`youtube-transcript-api`) |
| Transcript preprocessing | HTML entity/whitespace cleanup, duplicate caption removal, sentence boundaries kept |
| Chunking | LangChain `RecursiveCharacterTextSplitter`, ~800 tokens with ~150 token overlap, every chunk mapped back to real caption start/end times |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (384 dims), L2-normalized, windowed mean pooling for long chunks |
| Vector storage | Supabase Postgres + `pgvector`, HNSW cosine index, per-video filtering in SQL |
| Retrieval | Top-5 cosine matches above a configurable threshold, deduplicated, timestamps preserved |
| Answers | Groq (Llama 3.3 70B by default) with a strict transcript-only system prompt, citations, conversation history |
| Study tools | Short/detailed summary, important topics, quiz (MCQs + explanations), structured notes, suggested questions |
| Transcript viewer | Full transcript with search, highlighting, clickable timestamps |
| History | Per-device history with reopen/remove, videos cached server-side so nothing is reprocessed |

### Answer grounding

* Retrieved chunks are the **only** context sent to the model, and their time ranges are real caption timestamps.
* Model-produced timestamps in summaries, quizzes and notes are snapped to actual chunk starts; timestamps that cannot be
  grounded (more than 120s from a real cue) are dropped rather than displayed.
* When retrieval returns nothing above the similarity threshold, the API returns a fixed "the video doesn't cover that"
  message instead of calling the LLM.

---

## Architecture

```
Browser (React + Vite + Tailwind)
        │  axios  (VITE_API_URL)
        ▼
FastAPI  ── /api/video/process ──►  transcript_service ─► clean ─► chunk (LangChain)
   │                                            │
   │                                            ▼
   │                                    embedding_service (Sentence Transformers)
   │                                            │
   │                                            ▼
   │                          Supabase Postgres + pgvector (transcript_chunks)
   │
   ├── /api/chat ─► retrieval_service (cosine top-k) ─► groq_service ─► answer + sources
   ├── /api/video/{id}/summary|quiz|notes ─► generation_service ─► groq_service (JSON mode)
   └── /api/video/{id} | /transcript | /history | DELETE
```

Video processing is split: metadata and the transcript are stored synchronously (so the UI can render
immediately), while chunking and embedding run in a background task. The frontend polls the video status
until the index is ready. Re-posting an already indexed video returns the cached record with no re-embedding.

---

## Tech stack

**Frontend** React 18, Vite, JavaScript, Tailwind CSS v4, React Router, Axios, Lucide React
**Backend** Python 3.11, FastAPI, Uvicorn, Pydantic v2, python-dotenv / pydantic-settings, httpx
**GenAI** Groq (`llama-3.3-70b-versatile` by default), Sentence Transformers, LangChain text splitters
**Database** Supabase PostgreSQL + pgvector
**YouTube** `youtube-transcript-api`, `yt-dlp` (metadata; optional Whisper fallback via Groq)

---

## Project structure

```
videomind/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app, CORS, error handlers, health
│   │   ├── config.py               # settings from environment
│   │   ├── database.py             # async Supabase (PostgREST) client
│   │   ├── models/entities.py      # domain models
│   │   ├── schemas/                # request/response models
│   │   ├── routes/                 # video.py, chat.py, generation.py
│   │   ├── services/
│   │   │   ├── youtube_service.py      # URL parsing, metadata
│   │   │   ├── transcript_service.py   # caption extraction
│   │   │   ├── whisper_service.py      # optional STT fallback
│   │   │   ├── embedding_service.py    # Sentence Transformers
│   │   │   ├── vector_service.py       # pgvector CRUD + RPC search
│   │   │   ├── retrieval_service.py    # semantic retrieval
│   │   │   ├── groq_service.py         # Groq client + retries
│   │   │   ├── generation_service.py   # prompts, summaries, quiz, notes
│   │   │   └── processing_service.py   # ingestion orchestration
│   │   └── utils/                  # text processing, timestamps, errors
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/             # Navbar, VideoInput, VideoPlayer, ChatWindow, ...
│   │   ├── pages/                  # Home, Chat, History
│   │   ├── services/api.js
│   │   ├── hooks/                  # useVideo, useChat
│   │   ├── context/                # HistoryContext
│   │   └── utils/format.js
│   ├── vercel.json
│   └── .env.example
├── database/schema.sql
└── README.md
```

---

## Setup

### Prerequisites
* Python 3.11+
* Node.js 20+
* A [Supabase](https://supabase.com) project
* A [Groq API key](https://console.groq.com/keys)

### 1. Database (Supabase)

1. Create a Supabase project.
2. Open **SQL Editor** and run the contents of [`database/schema.sql`](database/schema.sql). This enables the
   `vector` extension, creates the tables, the HNSW index, the `match_transcript_chunks` function and the
   `updated_at` triggers.
3. Copy **Project URL** and the **service_role** key from *Project Settings → API*.

> The service_role key is used by the backend only. It bypasses RLS, so it must never appear in frontend code or a
> `VITE_*` variable.

### 2. Backend

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env      # then fill in the values
uvicorn app.main:app --reload --port 8000
```

Backend runs at `http://localhost:8000`; Swagger UI is at `http://localhost:8000/docs`.

The first request that needs embeddings downloads `all-MiniLM-L6-v2` (~90 MB). On a machine without a GPU,
install the CPU build of PyTorch first if the default wheel is too large:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env      # VITE_API_URL=http://localhost:8000
npm run dev
```

Open `http://localhost:5173`.

### 4. Production build (local check)

```bash
cd frontend && npm run build && npm run preview
```

---

## Environment variables

`backend/.env`

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `GROQ_API_KEY` | yes | – | Groq inference key (backend only) |
| `GROQ_MODEL` | no | `llama-3.3-70b-versatile` | Chat model name |
| `SUPABASE_URL` | yes | – | `https://your-project.supabase.co` |
| `SUPABASE_KEY` | yes | – | Supabase service_role key |
| `DATABASE_URL` | no | – | Postgres connection string, only for running the schema with psql |
| `FRONTEND_URL` | no | `http://localhost:5173` | Allowed CORS origin(s), comma-separated |
| `EMBEDDING_MODEL` | no | `sentence-transformers/all-MiniLM-L6-v2` | Must produce 384-dim vectors to match the schema |
| `CHUNK_SIZE_TOKENS` | no | `800` | Chunk size (converted at ~4 chars/token) |
| `CHUNK_OVERLAP_TOKENS` | no | `150` | Chunk overlap |
| `RETRIEVAL_TOP_K` | no | `5` | Chunks retrieved per question |
| `SIMILARITY_THRESHOLD` | no | `0.2` | Minimum cosine similarity |
| `GROQ_TEMPERATURE` / `GROQ_MAX_TOKENS` | no | `0.2` / `1400` | Answer generation settings |
| `ENABLE_WHISPER_FALLBACK` | no | `false` | Use Groq Whisper when captions are missing |
| `LOG_LEVEL` | no | `INFO` | Logging level |

`frontend/.env`

| Variable | Required | Purpose |
| --- | --- | --- |
| `VITE_API_URL` | yes | Base URL of the FastAPI backend |

Never put secrets in `frontend` or in any `VITE_*` variable — Vite inlines them into the browser bundle.

---

## API

All errors share one shape: `{"error": {"code": "...", "message": "..."}}`.

| Method | Path | Description |
| --- | --- | --- |
| POST | `/api/video/process` | Validate URL, extract metadata + transcript, start indexing. `202` while indexing, `200` if already cached |
| GET | `/api/video/{video_id}` | Metadata + processing status + suggested questions |
| GET | `/api/video/{video_id}/transcript` | Full transcript with `start`/`end` per cue |
| GET | `/api/video/{video_id}/history?session_id=` | Stored conversation for a session |
| POST | `/api/chat` | Ask a question; returns answer + timestamped sources |
| DELETE | `/api/chat/{session_id}` | Clear a conversation |
| POST | `/api/video/{video_id}/summary` | Short + detailed summary, topics, takeaways |
| POST | `/api/video/{video_id}/quiz?count=5` | MCQs with options, answer, explanation, timestamp |
| POST | `/api/video/{video_id}/notes` | Structured notes with sections, definitions, takeaways |
| DELETE | `/api/video/{video_id}` | Delete the video and all chunks/sessions/messages (cascade) |
| GET | `/api/health` | Configured services and model names |

Example:

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"video_id":"aircAruvnKk","question":"What is a neuron?"}'
```

```json
{
  "video_id": "aircAruvnKk",
  "session_id": "0d2f...",
  "answer": "A neuron is a container for a number between 0 and 1...",
  "sources": [
    {
      "chunk_index": 2,
      "start_time": 12.5,
      "end_time": 40.0,
      "timestamp": "00:12",
      "snippet": "Each neuron holds a number...",
      "similarity": 0.77
    }
  ],
  "model": "llama-3.3-70b-versatile"
}
```

---

## Database schema

`database/schema.sql` creates:

* **videos** — metadata, transcript JSONB, segment/chunk counts, status (`processing` / `ready` / `failed`), error fields,
  suggested questions, timestamps.
* **transcript_chunks** — `video_id`, `chunk_index`, text, `start_time`, `end_time`, `embedding vector(384)`, unique on
  `(video_id, chunk_index)`, HNSW cosine index, GIN full-text index ready for a future hybrid retriever.
* **chat_sessions** / **chat_messages** — conversation storage with the sources that backed each assistant message.
* **match_transcript_chunks(query_embedding, match_threshold, match_count, filter_video_id)** — cosine similarity search
  scoped to one video, ordered by distance, filtered by threshold.
* Cascading deletes from `videos` keep chunk, session and message data consistent.

---

## Deployment

### Database — Supabase
Run `database/schema.sql` once in the SQL editor. Nothing else to deploy.

### Backend — Render
* New **Web Service** from the repository, root directory `backend`.
* Build: `pip install -r requirements.txt`
* Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
* Environment: `GROQ_API_KEY`, `GROQ_MODEL`, `SUPABASE_URL`, `SUPABASE_KEY`, `FRONTEND_URL` (your Vercel URL),
  `EMBEDDING_MODEL`.
* The embedding model is downloaded at runtime; use a plan with enough memory (~1 GB+ is comfortable for MiniLM).

### Frontend — Vercel
* Root directory `frontend`, framework preset **Vite** (`npm run build`, output `dist`).
* Environment: `VITE_API_URL=https://<your-render-service>.onrender.com`.
* `frontend/vercel.json` rewrites all routes to `index.html` for client-side routing.

Add the deployed frontend origin to `FRONTEND_URL` on the backend (comma-separated for multiple origins).

---

## Error handling

The UI always shows a readable message, never a raw traceback.

| Situation | Behaviour |
| --- | --- |
| Invalid / unsupported URL | `400 invalid_youtube_url` |
| Private, deleted, age-restricted video | `422 video_unavailable` with an explanation |
| Captions disabled / no transcript | `422 transcript_unavailable` (Whisper fallback if enabled) |
| Empty transcript | `422 transcript_unavailable` |
| Chat before indexing finishes | `409 video_not_ready` |
| Supabase not configured / unreachable | `503 database_not_configured` or `502 database_error` |
| Groq not configured | `503 ai_not_configured` |
| Groq rate limit | retried twice, then `429 rate_limited` |
| Groq timeout / outage | `504` / `502` with a retry message |
| Duplicate processing | Cached record returned, embeddings are not regenerated |
| Indexing failure | Status `failed` with `error_message`; the UI offers **Reprocess video** |

---

## Limitations and notes

* **No user authentication.** Video transcripts are cached server-side and treated as a shared cache (keyed by video ID);
  history is stored per device in `localStorage`. Multi-user history requires adding authentication and row ownership.
* **No token streaming.** Answers are returned complete with their sources; streaming would need an SSE endpoint.
* **YouTube access is best-effort.** Transcript requests can be rate limited or blocked by YouTube from datacenter IPs;
  the API surfaces that as a clear error. Videos without captions cannot be processed unless the Whisper fallback is
  enabled (which downloads audio — only do this for content you may process).
* **Long transcripts.** Answers use the top-5 retrieved chunks. Summaries/notes/quizzes send the whole transcript when it
  fits in the context budget (~60k characters) and otherwise sample evenly across the video.
* **Embedding dimension is fixed at 384** in the schema. Changing `EMBEDDING_MODEL` requires updating `vector(384)` and
  re-indexing.
* **Processing is in-process.** Background indexing runs as an asyncio task in the API process; a restart mid-index leaves
  the video in `processing` until the stale timeout (15 min) allows a retry.
* **One embedding pass per video.** Chunk text and metadata are cached in Postgres; reprocessing is only triggered from the
  failed state (or by deleting the video first).

---

## What was verified locally

* Frontend production build (`npm run build`) completes with no errors.
* Backend starts under Uvicorn; `/api/health`, `/docs` and all routes load.
* URL parsing accepts `watch`, `youtu.be`, `shorts`, `embed`, `m.` and rejects non-YouTube links.
* Live extraction against a real YouTube video: metadata (title/channel/duration), 286 caption cues, chunking into
  overlapping chunks whose start/end times map exactly to caption cues, 384-dim embeddings, and cosine retrieval of the
  correct chunk for a sample question (similarity 0.67).
* Prompt assembly includes system rules, timestamped context and conversation history; an empty retrieval returns the
  fixed "not covered" answer without calling the LLM.
* Un-grounded timestamps produced by the model are discarded; valid ones are snapped to real cue times.
* Chat route returns session IDs, grounded sources and correct validation errors.

The Supabase and Groq calls require real credentials to exercise end-to-end; with keys configured, the workflow is
`URL → transcript → chunks → embeddings → pgvector → retrieval → Groq → answer with timestamps`.
