-- ============================================================================
-- VideoMind database schema
-- Supabase Postgres + pgvector
--
-- Run in the Supabase SQL editor (or: psql "$DATABASE_URL" -f database/schema.sql)
-- Embedding dimension is 384 to match sentence-transformers/all-MiniLM-L6-v2.
-- If you change EMBEDDING_MODEL, change vector(384) below to the new dimension.
-- ============================================================================

create extension if not exists vector;
create extension if not exists pgcrypto;

-- ----------------------------------------------------------------------------
-- Videos: metadata, transcript and processing status
-- ----------------------------------------------------------------------------
create table if not exists public.videos (
    video_id             text primary key,
    url                  text not null,
    title                text not null default 'Untitled video',
    channel              text,
    channel_url          text,
    thumbnail_url        text,
    duration_seconds     double precision,
    description          text,
    transcript_language  text,
    transcript_source    text check (transcript_source in ('captions', 'whisper')),
    transcript           jsonb not null default '[]'::jsonb,
    segment_count        integer not null default 0,
    chunk_count          integer not null default 0,
    status               text not null default 'processing'
                         check (status in ('processing', 'ready', 'failed')),
    error_code           text,
    error_message        text,
    suggested_questions  jsonb not null default '[]'::jsonb,
    created_at           timestamptz not null default now(),
    updated_at           timestamptz not null default now(),
    processed_at         timestamptz
);

create index if not exists videos_status_idx on public.videos (status);
create index if not exists videos_created_at_idx on public.videos (created_at desc);

-- ----------------------------------------------------------------------------
-- Transcript chunks with embeddings
-- ----------------------------------------------------------------------------
create table if not exists public.transcript_chunks (
    id             uuid primary key default gen_random_uuid(),
    video_id       text not null references public.videos(video_id) on delete cascade,
    chunk_index    integer not null,
    content        text not null,
    start_time     double precision not null,
    end_time       double precision not null,
    token_estimate integer,
    embedding      vector(384),
    created_at     timestamptz not null default now(),
    unique (video_id, chunk_index)
);

create index if not exists transcript_chunks_video_idx
    on public.transcript_chunks (video_id, chunk_index);

-- HNSW gives good recall without training and works for small and large sets.
create index if not exists transcript_chunks_embedding_idx
    on public.transcript_chunks using hnsw (embedding vector_cosine_ops)
    with (m = 16, ef_construction = 64);

-- Full-text index kept ready for a future hybrid (dense + keyword) retriever.
create index if not exists transcript_chunks_content_fts_idx
    on public.transcript_chunks using gin (to_tsvector('english', content));

-- ----------------------------------------------------------------------------
-- Chat sessions and messages
-- ----------------------------------------------------------------------------
create table if not exists public.chat_sessions (
    id         uuid primary key default gen_random_uuid(),
    video_id   text not null references public.videos(video_id) on delete cascade,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists chat_sessions_video_idx on public.chat_sessions (video_id);

create table if not exists public.chat_messages (
    id         uuid primary key default gen_random_uuid(),
    session_id uuid not null references public.chat_sessions(id) on delete cascade,
    role       text not null check (role in ('user', 'assistant')),
    content    text not null,
    sources    jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists chat_messages_session_idx
    on public.chat_messages (session_id, created_at);

-- ----------------------------------------------------------------------------
-- Vector similarity search, scoped to a single video
-- ----------------------------------------------------------------------------
create or replace function public.match_transcript_chunks(
    query_embedding  vector(384),
    match_threshold  float,
    match_count      int,
    filter_video_id  text
)
returns table (
    id          uuid,
    video_id    text,
    chunk_index integer,
    content     text,
    start_time  double precision,
    end_time    double precision,
    similarity  float
)
language sql
stable
as $$
    select
        c.id,
        c.video_id,
        c.chunk_index,
        c.content,
        c.start_time,
        c.end_time,
        1 - (c.embedding <=> query_embedding) as similarity
    from public.transcript_chunks c
    where c.video_id = filter_video_id
      and c.embedding is not null
      and 1 - (c.embedding <=> query_embedding) >= match_threshold
    order by c.embedding <=> query_embedding
    limit match_count;
$$;

-- ----------------------------------------------------------------------------
-- updated_at maintenance
-- ----------------------------------------------------------------------------
create or replace function public.touch_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists videos_touch_updated_at on public.videos;
create trigger videos_touch_updated_at
    before update on public.videos
    for each row execute function public.touch_updated_at();

drop trigger if exists chat_sessions_touch_updated_at on public.chat_sessions;
create trigger chat_sessions_touch_updated_at
    before update on public.chat_sessions
    for each row execute function public.touch_updated_at();

-- ----------------------------------------------------------------------------
-- Access control
--
-- The backend uses the Supabase service-role key, which bypasses RLS. No
-- per-user identification is configured, so RLS stays disabled; the API is the
-- only writer and the browser never receives the service-role key.
-- If you add authentication later, enable RLS and scope rows by user id:
--   alter table public.videos enable row level security;
--   alter table public.chat_messages enable row level security;
--   ...
-- ----------------------------------------------------------------------------
