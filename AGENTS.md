<<<<<<< HEAD
<!-- appforge-ports 68380e412097 -->
=======
<!-- appforge-ports 6684c07e40a1 -->
>>>>>>> 5b44fdad84324f26274739f10a5d0036568cb9ad
# Project

This project has a reserved port block (stable across restarts — the preview
pane and any preview URL the user shares point here):

<<<<<<< HEAD
- **Frontend / preview: `16900`** — run the frontend dev server on this
  port; it is what the Preview pane opens first.
- **Main backend / API: `16901`** (for full-stack projects)
- **Spare ports: `16902`, `16903`, `16904`** — additional services (workers, websocket
=======
- **Frontend / preview: `19465`** — run the frontend dev server on this
  port; it is what the Preview pane opens first.
- **Main backend / API: `19466`** (for full-stack projects)
- **Spare ports: `19467`, `19468`, `19469`** — additional services (workers, websocket
>>>>>>> 5b44fdad84324f26274739f10a5d0036568cb9ad
  servers, second API, etc.) in this order.

Rules:

- ALWAYS bind every server to 0.0.0.0 (not localhost) so the public preview
  can reach it.
- **Start the frontend dev server as soon as the app is scaffolded, and keep it
  running** — the Preview pane has nothing to show until it is up. Verify it
<<<<<<< HEAD
  responds (`curl -sf http://localhost:16900`) before ending a task.
- **Run long-lived servers DETACHED so they survive AI-runtime restarts**
  (AppForge restarts the runtime on config/model changes — a server that is a
  child of the runtime process dies with it):
  `mkdir -p /tmp/opencode && setsid nohup npm run dev -- --host 0.0.0.0 --port 16900 >/tmp/opencode/frontend.log 2>&1 &`
  then check the log / `curl -sf http://localhost:16900`. NEVER run a dev
  server in the foreground of a tool call — it blocks the tool and gets killed
  on every abort or restart.
- Frontend: `npm run dev -- --host 0.0.0.0 --port 16900`
  (Next.js: `npm run dev -- -p 16900`).
- Backend/API on `16901`: e.g. `uvicorn main:app --host 0.0.0.0 --port 16901`,
  `PORT=16901 node server.js`, `flask run --host 0.0.0.0 --port 16901`.
=======
  responds (`curl -sf http://localhost:19465`) before ending a task.
- **Run long-lived servers DETACHED so they survive AI-runtime restarts**
  (AppForge restarts the runtime on config/model changes — a server that is a
  child of the runtime process dies with it):
  `mkdir -p /tmp/opencode && setsid nohup npm run dev -- --host 0.0.0.0 --port 19465 >/tmp/opencode/frontend.log 2>&1 &`
  then check the log / `curl -sf http://localhost:19465`. NEVER run a dev
  server in the foreground of a tool call — it blocks the tool and gets killed
  on every abort or restart.
- Frontend: `npm run dev -- --host 0.0.0.0 --port 19465`
  (Next.js: `npm run dev -- -p 19465`).
- Backend/API on `19466`: e.g. `uvicorn main:app --host 0.0.0.0 --port 19466`,
  `PORT=19466 node server.js`, `flask run --host 0.0.0.0 --port 19466`.
>>>>>>> 5b44fdad84324f26274739f10a5d0036568cb9ad
- **Installing dependencies: prefer `bun install`** — Bun is preinstalled and
  several times faster than npm; run it detached or with a generous timeout
  and NEVER poll in a tight loop. Fall back to `npm install` only if bun
  fails. Long installs: start them detached
  (`setsid nohup ... >/tmp/opencode/install.log 2>&1 &`) and poll the log.
- **Frontend → backend calls MUST go through the frontend dev server's
  proxy**, so the browser only ever talks to the frontend origin (no CORS,
  works through the shared preview URL):
  - Vite — in `vite.config.ts`:
<<<<<<< HEAD
    `server: { proxy: { "/api": "http://localhost:16901" } }`, then call
    `fetch("/api/...")` from the frontend (never `localhost:16901` directly).
  - Next.js — `rewrites()` in `next.config.js`:
    `{ source: "/api/:path*", destination: "http://localhost:16901/:path*" }`.
=======
    `server: { proxy: { "/api": "http://localhost:19466" } }`, then call
    `fetch("/api/...")` from the frontend (never `localhost:19466` directly).
  - Next.js — `rewrites()` in `next.config.js`:
    `{ source: "/api/:path*", destination: "http://localhost:19466/:path*" }`.
>>>>>>> 5b44fdad84324f26274739f10a5d0036568cb9ad
  - If the backend does not live under an `/api` prefix, pick one and proxy it.
- If an assigned port is already taken, do NOT kill the process holding it —
  that belongs to another project, and its owner may have shared that URL
  with someone. Move that server to the next free port instead (`ss -ltn`
  shows what's taken); use the spare ports first.
- NEVER kill, restart, or rebind processes belonging to another project
  folder under /home/user/workspaces.

  **IMPORANT**: In vite as well as fastapi CORS config, remeber that this is a dev app,
  so, you should apply * as CORS to it, so that it never breaks.


## Interactive planning (octto) — embedded brainstorm panel

When the user asks for a NEW app, site, tool, or a major new feature from
scratch, delegate to the "octto" agent to run the structured brainstorm. The
octto agent will call create_brainstorm, which opens an interactive question
panel EMBEDDED IN THE USER'S CHAT (the panel renders automatically — do not
describe it, do not apologize for it, and do NOT try to open a browser). Ask
your branch questions through that panel; the user answers by clicking.

When create_brainstorm returns a session_id, the user is answering in the
panel — wait for their input with await_brainstorm_complete. Call
await_brainstorm_complete AT MOST 3 TIMES. If it is still waiting after the
third call, STOP: end your turn with one short line (e.g. "The brainstorm
stays open — answer the questions above and ask me to continue when ready").
Do NOT keep retrying, do NOT build anything, and do NOT invent answers. When
an await completes with an approved plan, build it. Do NOT use octto for
small fixes, edits, or iteration on existing code.

ALWAYS include one rank question near the end of every brainstorm asking the
user to PRIORITIZE the proposed features/scope in order (most important
first) — build strictly in that priority order, and if you run out of time
or budget, the lowest-ranked items are dropped first.

NEVER call any of these octto tools directly — they break the embedded
panel and can flood the model context with raw file data: start_session,
end_session, get_answer, get_next_answer, list_questions, cancel_question,
push_question, and the per-type ask/show tools. create_brainstorm and
await_brainstorm_complete handle everything automatically. If the user asks
for a demonstration or a description of the question types, describe them
in text — do NOT open a session to demonstrate.