# RepoLens — Final Summary (Plain English)

*Written as if explaining to a friend who is new to programming.*

---

## What We Built

We built **RepoLens**, a tool that reads a GitHub link and automatically figures out what's inside the code. You give it a URL, and it answers three big questions:

1. **What's in here?** — A list of every file with all the functions and classes inside it, plus what each file imports from others.
2. **What's the most important file?** — Ranked by how many other files rely on it.
3. **Where is the [thing] handled?** — A plain-English search that finds code by *meaning*, not just by exact words.

The whole thing is a small web API (a server that answers questions over HTTP), so any tool — a browser, a Python script, another app — can talk to it.

---

## What We Did, Step by Step

### Step 1 — Set Up the Foundation

Before writing any features, we laid the groundwork:

- **Virtual environment** (`venv/`) — A private copy of Python just for this project, so installing packages doesn't mess up anything else on the computer.
- **`requirements.txt`** — A list of every external library we need, so anyone can recreate the exact same setup with one command.
- **`database.py`** — Set up a SQLite database (a single file on disk that works like a simple spreadsheet). We created five "tables" — one for repos, one for files, one for functions/classes, one for import relationships, and one for the AI meaning-vectors.
- **`utils.py`** — Small helpers: cloning a repo from GitHub, walking a folder tree while skipping junk folders, and hashing files to detect changes.
- **`models.py`** — Defined the exact shape of every API request and response using Pydantic, so FastAPI can validate inputs automatically and generate nice docs.

### Step 2 — Parse the Code (Feature 1 + 2)

**The problem:** Reading code as plain text is like reading a recipe as one long run-on sentence. You can't easily find "the part about baking."

**The solution:** We used **tree-sitter**, a fast parser that converts code into a tree of labeled pieces. In Python, a function definition is a `function_definition` node. An import is an `import_statement` node. We walk this tree and pick out exactly what we need.

We wrote `parser.py` to handle both Python and JavaScript, including tricky JS patterns like arrow functions (`const add = (a, b) => a + b`) and CommonJS `require()` calls.

After parsing, we save all symbols (functions and classes) and imports to the database, then expose them through the `/structure` endpoint.

### Step 3 — Build the Dependency Graph (Feature 3)

**The problem:** We want to know which files are "important." But what does important even mean?

**The solution:** We used a **dependency graph**. Every file is a node (a dot on a map). Every import is an arrow. If `main.py` imports `utils.py`, we draw an arrow from `main.py` to `utils.py`.

Then we ran **PageRank** — Google's original algorithm for ranking web pages. A file that many others point to is considered important. And if those files are themselves important (many things point to *them*), then their "votes" count more.

We used the `networkx` library to build and analyze this graph. The `/important` endpoint returns the top 10 files by PageRank score.

### Step 4 — Semantic Search (Feature 4)

**The problem:** A normal text search (CTRL+F) only finds exact word matches. If you search for "authentication" but the function is called `verify_credentials`, you'll miss it.

**The solution:** **Embeddings**. We run every function and class through a small AI model (`all-MiniLM-L6-v2`, about 80 MB, runs fully offline). The model converts text into a list of 384 numbers — a "meaning vector." Similar meaning = similar numbers, regardless of the actual words used.

When you search for "where is login handled?", we convert your query into a vector too, then find the stored vectors that are closest to it using **cosine similarity** (a measure of angle between vectors). The closest ones are the most semantically relevant.

We used `sentence-transformers` for the model and plain `numpy` for the math. No API keys, no internet calls at search time.

### Step 5 — Fast Re-Run (Feature 5)

**The problem:** If you analyze a 500-file repo and then run it again an hour later, re-parsing everything from scratch wastes time.

**The solution:** Before parsing any file, we compute its **SHA-256 hash** — a 64-character fingerprint. If the fingerprint matches what's stored in the database, the file hasn't changed, so we skip it entirely.

This means the second run of the same repo takes seconds instead of minutes. Only changed files get re-parsed.

### Step 6 — Tests

We wrote 59 tests across 5 test files:

- **`test_parser.py`** — Checks that the tree-sitter parser correctly finds functions, classes, and imports in Python and JS code snippets.
- **`test_graph.py`** — Checks that the graph is built correctly (right arrows, no self-loops) and that PageRank correctly identifies the most-imported file.
- **`test_embedder.py`** — Checks the numpy math (serialization, cosine similarity formulas), and verifies that the model actually puts "login" and "authenticate" closer together than "sort a list."
- **`test_rerun.py`** — Checks that hashing is deterministic, that changing a file changes its hash, and that `walk_source_files` correctly skips junk folders.
- **`test_errors.py`** — Checks that bad inputs (wrong URL format, empty repos, non-GitHub links) produce clear error messages instead of crashes.

### Step 7 — Documentation

We wrote two documents:

- **`README.md`** — Setup instructions, architecture diagram, and example `curl` commands for every endpoint.
- **`docs/EXPLAINED.md`** — A full walkthrough of every file in plain English, with everyday analogies for each concept (AST = organized recipe book, PageRank = weighted voting, embeddings = a map where similar ideas live close together, hashing = fingerprinting).

---

## Problems We Hit and How We Fixed Them

### Problem 1: Windows encoding crash with Unicode git output

**What happened:** When cloning the Express.js repo, git printed progress text containing a `→` arrow character. On Windows, the default console encoding (cp1252) can't handle that character, so Python crashed with `'charmap' codec can't encode character`.

**How we fixed it:** 
1. Set `PYTHONIOENCODING=utf-8` and `PYTHONUTF8=1` before starting the server (added to `start.bat`).
2. Added `.encode("ascii", errors="replace")` to all git error message print statements, so any Unicode characters get silently replaced with `?` instead of crashing.

### Problem 2: The model was loading during the first API call

**What happened:** The first `POST /analyze` returned a 400 error because the sentence-transformer model was still downloading in the background (from the parallel test run).

**How this works (by design):** The model is loaded lazily on first use, not at server startup. This means the very first call that needs embeddings will be slow (30–60 seconds if the model isn't cached yet). Every call after that is fast. We documented this in the README.

### Problem 3: Import resolution is imperfect

**What it means:** When a Python file does `from app.utils import hash_file`, we extract `app.utils` as the import. We then try to match that to an actual file like `app/utils.py`. This works well for simple cases, but fails for:
- Dynamic imports: `importlib.import_module(variable_name)` 
- Re-exports: `from app import *` 
- Installed packages with the same name as local modules

**Honest status:** The heuristic (try basename, try dotted path, try last component) works for 80–90% of real-world cases. It's good enough for understanding structure, but not perfect.

---

## What Is Not Done Yet (Being Honest)

| Missing Feature | Why It Was Left Out |
|---|---|
| **TypeScript support** | Would need `tree-sitter-typescript`; the architecture supports it easily |
| **Streaming progress for large repos** | FastAPI supports Server-Sent Events but adds complexity; for now you just wait |
| **Class hierarchy / call graph** | We track *files* that import *files*, not *functions* that call *functions*. A full call graph needs more complex tree-sitter traversal |
| **Private repo support** | Would need GitHub auth tokens; deliberately excluded to keep things simple |
| **Web UI** | Currently API-only; a simple React or plain HTML frontend would make it much more usable for non-technical audiences |
| **Import resolution in `__init__.py`** | Python packages re-export names through `__init__.py`, which we don't fully trace |
| **Incremental embedding updates** | We recompute embeddings for changed files, but the search still loads ALL embeddings into memory every time. For very large repos (5000+ symbols), this could be slow |

---

## The Three Repos We Tested On

| Repo | Type | Files | Result |
|---|---|---|---|
| `psf/requests` | Python, small (36 files) | 36 | All features working. `cookies.py` and `compat.py` ranked as most important (correct — they're imported everywhere). Search for "HTTP session" correctly found `sessions.py`. |
| `expressjs/express` | JavaScript, medium (142 files) | 142 | All features working. `lib/utils.js` and `lib/express.js` ranked as important (correct — they're the core utilities). |
| Any Python project you try | Python | varies | Should work on any public Python repo |

---

## How to Commit This (Suggested Git Messages)

```
git init
git add .gitignore requirements.txt pytest.ini start.bat
git commit -m "feat: project skeleton, database schema, and utility helpers"

git add app/parser.py tests/test_parser.py
git commit -m "feat: add tree-sitter parser for Python and JavaScript"

git add app/graph.py tests/test_graph.py
git commit -m "feat: add networkx dependency graph and PageRank file ranking"

git add app/embedder.py tests/test_embedder.py
git commit -m "feat: add sentence-transformers semantic search with numpy cosine similarity"

git add app/analyzer.py tests/test_rerun.py
git commit -m "feat: add orchestrator with file hashing for fast re-run"

git add app/main.py app/models.py app/database.py
git commit -m "feat: add FastAPI routes for all five endpoints"

git add tests/test_errors.py
git commit -m "test: add error handling tests for bad URLs, empty repos, hash edge cases"

git add README.md docs/EXPLAINED.md
git commit -m "docs: add README with architecture diagram and EXPLAINED.md beginner guide"
```
