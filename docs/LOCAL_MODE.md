# Running fully local (offline) — EntityGraph Auditor

The application is **local-first**: the default configuration needs no paid API,
no account, and — in deterministic mode — no network at all. Nothing is sent
anywhere unless you explicitly point the app at a URL or configure a cloud
provider.

## 1. Deterministic-only mode (default)

Default provider is `null`. Every deterministic stage runs (parse, structure,
EAV presence, triples that are explicit in the text, deterministic findings,
gate, FCS/PRS/HRS-style checks, exports) and semantic stages that require a model
are marked **`skipped`** with a visible reason — never faked.

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"   # or: uv venv + uv pip install -e .
alembic upgrade head
uvicorn ega_api.main:app --host 127.0.0.1 --port 8000
```

Nothing above touches the network beyond installing dependencies. Check your
mode at any time:

```bash
curl -s localhost:8000/api/v1/readiness | python -m json.tool
```

`checks.model_provider.detail` will say *"deterministic-only mode"* when no model
is configured.

## 2. Fully local LLM (Ollama) — still zero API cost

Install [Ollama](https://ollama.com), pull a model, then point the app at it:

```bash
ollama pull llama3.2:latest
export EGA_DEFAULT_PROVIDER=ollama
export EGA_OLLAMA_BASE_URL=http://localhost:11434
export EGA_OLLAMA_DEFAULT_MODEL=llama3.2:latest
```

Content is sent **only to `localhost`**. The provider layer records
`sends_data_off_device = false` for a loopback Ollama endpoint and the UI shows
this in the provider picker.

### With Docker Compose

```bash
docker compose --profile ollama up --build
# set EGA_DEFAULT_PROVIDER=ollama and EGA_OLLAMA_BASE_URL=http://ollama:11434 for the api service
docker compose exec ollama ollama pull llama3.2:latest
```

## 3. What "offline" means per input

| Input path | Network use |
|---|---|
| Paste text / upload file | none |
| Context/skill pack import | none (archives parsed locally) |
| URL fetch | one outbound request **only when you click fetch**, SSRF-guarded |
| Deterministic mode audit | none |
| Ollama audit | loopback only |
| Cloud provider audit | provider API (BYOK) — UI warns and shows "sends text off this machine" |

URL fetching is **off by default in the sense that nothing is fetched unless you
ask**. Disable it entirely for an air-gapped deployment by simply never using the
fetch action; `EGA_ALLOW_PRIVATE_URLS=false` keeps the SSRF guard on.

## 4. Air-gapped / hardened deployment

- Bind to loopback only (`EGA_HOST=127.0.0.1`) unless you set `EGA_AUTH_TOKEN`.
- Set `EGA_AUTH_TOKEN` before exposing the API/UI anywhere beyond your machine.
- Keep `EGA_ALLOW_PRIVATE_URLS=false`.
- Leave `EGA_DEFAULT_PROVIDER=null` for a strictly no-network deployment.
- Secrets at rest require `APP_ENCRYPTION_KEY` (Fernet); without it the app
  refuses to store provider/MCP credentials rather than storing them in the clear.

## 5. Integrity guarantees in local mode

- Every score is a deterministic function of stored content + profile + packs +
  prompt versions, so a local rerun reproduces the same numbers.
- Findings carry evidence offsets/excerpts; nothing is asserted without a span
  or an explicit `not_assessed`/`unknown` label.
- The report lists every `skipped_stage` and its reason, so a partial (no-model)
  audit can never be mistaken for a full one.
