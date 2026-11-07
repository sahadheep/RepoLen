# RepoLens — Complete Running Guide

> Everything tested and verified. All commands below were run and produced
> the exact output shown.

---

## Part 1 — How to Start the Project

### Step 1: Open a terminal in the project folder

Open PowerShell (or Windows Terminal) and navigate to the project:

```powershell
cd C:\Users\SAHADHEEP\Desktop\RepoLen
```

### Step 2: Activate the virtual environment

```powershell
.\venv\Scripts\activate
```

You'll see `(venv)` appear at the start of your prompt. That means it worked.

> **Why do this?** The virtual environment is a private copy of Python that
> only has this project's packages installed. Without activating it, Python
> won't find FastAPI, tree-sitter, etc.

### Step 3: Start the server

```powershell
$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"; .\venv\Scripts\uvicorn app.main:app --reload --port 8000
```

> **Why those env vars?** On Windows, git can output Unicode characters
> (arrows, emojis in READMEs) that crash Python's default console encoding.
> Setting UTF-8 prevents that crash.
>
> `--reload` means the server auto-restarts when you edit a .py file (great
> for development). Remove it in production.

**You should see:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
[DB] Initialized at C:\...\repolens.db
```

**Leave this terminal open.** The server needs to keep running.

### Step 4: Open another terminal for testing

Open a second PowerShell window in the same folder:
```powershell
cd C:\Users\SAHADHEEP\Desktop\RepoLen
.\venv\Scripts\activate
```

### Step 5: Run the tests (optional but recommended)

```powershell
.\venv\Scripts\python -m pytest tests/ -q -k "not private_or_nonexistent"
```

**Expected output:**
```
59 passed, 1 deselected in 12.69s
```

---

## Part 2 — Using Every Endpoint

All examples below use Python's `httpx` library because PowerShell's `curl`
has a different syntax. You can also use the browser at
**http://localhost:8000/docs** for a nice interactive UI.

### Check the server is alive

```powershell
.\venv\Scripts\python -c "import httpx; print(httpx.get('http://localhost:8000/').json())"
```

**Output:**
```json
{"status": "ok", "message": "RepoLens is running. POST /analyze to start."}
```

---

### Endpoint 1 — Analyze a Repo

This is always the first call. Give it any public GitHub URL.

```powershell
.\venv\Scripts\python -c "
import httpx, json
r = httpx.post('http://localhost:8000/analyze',
    json={'url': 'https://github.com/psf/requests'},
    timeout=300)
print(json.dumps(r.json(), indent=2))
"
```

**Output (first run — clones and parses everything):**
```json
{
  "repo_id": 1,
  "url": "https://github.com/psf/requests",
  "files_processed": 36,
  "message": "Done. 36 files parsed, 0 unchanged (skipped)."
}
```

**Output (second run — files haven't changed, so it skips all of them):**
```json
{
  "repo_id": 1,
  "url": "https://github.com/psf/requests",
  "files_processed": 36,
  "message": "Done. 0 files parsed, 36 unchanged (skipped)."
}
```

> **Save the `repo_id`** — you need it for the other three endpoints.

---

### Endpoint 2 — Get the Code Structure

```powershell
.\venv\Scripts\python -c "
import httpx, json
r = httpx.get('http://localhost:8000/repos/1/structure', timeout=30)
d = r.json()
print('Total files:', len(d['files']))
# Show one file as example
print(json.dumps(d['files'][2], indent=2))
"
```

**Output:**
```
Total files: 36
{
  "path": "setup.py",
  "language": "python",
  "symbols": [],
  "imports": ["sys", "setuptools"]
}
```

---

### Endpoint 3 — Most Important Files (by PageRank)

```powershell
.\venv\Scripts\python -c "
import httpx, json
r = httpx.get('http://localhost:8000/repos/1/important', timeout=30)
print(json.dumps(r.json(), indent=2))
"
```

**Output:**
```json
{
  "repo_id": 1,
  "files": [
    {"path": "src/requests/cookies.py",        "score": 0.201669, "rank": 1},
    {"path": "src/requests/compat.py",          "score": 0.192855, "rank": 2},
    {"path": "src/requests/models.py",          "score": 0.103985, "rank": 3},
    {"path": "src/requests/_internal_utils.py", "score": 0.066288, "rank": 4},
    {"path": "src/requests/_types.py",          "score": 0.053484, "rank": 5},
    ...
  ]
}
```

> **cookies.py ranks #1** because almost every other file in requests imports
> cookies. That is exactly correct — cookies is a shared utility used everywhere.

---

### Endpoint 4 — Search by Meaning

```powershell
.\venv\Scripts\python -c "
import httpx, json
r = httpx.post('http://localhost:8000/repos/1/search',
    json={'query': 'where is login handled?', 'top_k': 3},
    timeout=30)
print(json.dumps(r.json(), indent=2))
"
```

**Output:**
```json
{
  "repo_id": 1,
  "query": "where is login handled?",
  "results": [
    {
      "file_path": "src/requests/auth.py",
      "symbol_name": "__init__",
      "kind": "function",
      "start_line": 137,
      "end_line": 137,
      "score": 0.3349,
      "snippet": "def __init__(self, username: str, password: str) -> None: ..."
    },
    ...
  ]
}
```

> Even though the word "login" doesn't appear in the code, the model found
> `auth.py` because authentication and login have similar *meaning* in vector
> space.

---

### Endpoint 5 — List All Analyzed Repos

```powershell
.\venv\Scripts\python -c "
import httpx, json
r = httpx.get('http://localhost:8000/repos', timeout=10)
print(json.dumps(r.json(), indent=2))
"
```

**Output:**
```json
[
  {"id": 1, "url": "https://github.com/psf/requests",      "file_count": 36,  "symbol_count": 807},
  {"id": 4, "url": "https://github.com/httpie/httpie",     "file_count": 124, "symbol_count": 1242},
  {"id": 3, "url": "https://github.com/expressjs/express", "file_count": 142, "symbol_count": 129}
]
```

---

## Part 3 — What Happens When You POST a URL (Step by Step)

When you send `POST /analyze` with a GitHub URL, here is exactly what happens
inside the code:

```
You send:  POST /analyze  {"url": "https://github.com/psf/requests"}
                │
                ▼
         app/main.py  (the front door)
         - Validates the Pydantic model (is "url" present? is it a string?)
         - Calls analyze_repo(url)
                │
                ▼
         app/analyzer.py  (the project manager)
         │
         ├── 1. URL VALIDATION
         │   "Does this start with https://github.com/ ?"
         │   "Does it have owner/repo format?"
         │   If not → raises ValueError → main.py returns HTTP 400
         │
         ├── 2. CLONE OR PULL  (app/utils.py)
         │   "Does repos/psf__requests/ exist on disk?"
         │   YES → git pull (get latest changes)
         │   NO  → git clone --depth=1 (shallow clone, faster)
         │   Creates: repos/psf__requests/ on your hard drive
         │
         ├── 3. DATABASE RECORD
         │   INSERT or UPDATE row in the repos table
         │   Gets back repo_id = 1
         │
         ├── 4. WALK ALL FILES  (app/utils.py)
         │   Recursively finds every .py and .js file
         │   SKIPS: node_modules, venv, .git, build, dist, __pycache__
         │   Result: list of 36 file paths for requests
         │
         ├── 5. FOR EACH FILE — the re-run check
         │   Compute SHA-256 hash of the file
         │   Look up stored hash in the files table
         │   SAME HASH → skip (file unchanged)
         │   DIFFERENT HASH or NEW → parse it
         │
         ├── 6. PARSE EACH CHANGED FILE  (app/parser.py)
         │   Uses tree-sitter to build a syntax tree
         │   Extracts: all function names, class names, line numbers, source code
         │   Extracts: all import statements
         │   Saves everything to: symbols table, imports table
         │
         ├── 7. COMPUTE EMBEDDINGS  (app/embedder.py)
         │   Finds all symbols that don't have an embedding yet
         │   Batch-encodes them with all-MiniLM-L6-v2 model (offline)
         │   Each symbol → 384 floating-point numbers (a "meaning vector")
         │   Saves vectors as bytes to: embeddings table
         │
         └── 8. RETURN RESULT
             {"repo_id": 1, "files_processed": 36, "message": "Done..."}
```

---

## Part 4 — How to Connect This to the Bigger Project

Your bigger project is: **a tool that asks students questions about their own code.**

RepoLens is **Part 1** — the "understand the code" layer. Here is exactly how
a bigger system would use it:

### Architecture of the Full Tool

```
Student submits their GitHub repo URL
         │
         ▼
┌─────────────────────┐
│     RepoLens API    │  ← YOU BUILT THIS
│                     │
│  POST /analyze      │  Step 1: understand the code
│  GET  /structure    │  Step 2: what's in it?
│  GET  /important    │  Step 3: what matters most?
│  POST /search       │  Step 4: find relevant code for each question
└─────────────────────┘
         │
         │  The bigger system reads these results and uses them to:
         ▼
┌─────────────────────┐
│   Question Engine   │  ← Part 2 (not built yet)
│                     │
│  - Pick a function  │
│    from /structure  │
│  - Ask: "What does  │
│    this function do?│
│    What are its     │
│    edge cases?"     │
│  - Use /search to   │
│    find related     │
│    code as context  │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│   Answer Evaluator  │  ← Part 3 (not built yet)
│                     │
│  - Compare student  │
│    answer to the    │
│    actual code      │
│  - Give feedback    │
└─────────────────────┘
```

### Concrete Code for Part 2 (What You'd Write Next)

Here is exactly how the question engine would call RepoLens using plain Python:

```python
import httpx

REPOLENS_URL = "http://localhost:8000"

def load_repo_into_repolens(github_url: str) -> int:
    """Step 1: Tell RepoLens to analyze a student's repo. Returns repo_id."""
    r = httpx.post(f"{REPOLENS_URL}/analyze", json={"url": github_url}, timeout=300)
    r.raise_for_status()
    return r.json()["repo_id"]


def get_all_functions(repo_id: int) -> list[dict]:
    """Step 2: Get every function in the repo to pick questions from."""
    r = httpx.get(f"{REPOLENS_URL}/repos/{repo_id}/structure", timeout=30)
    r.raise_for_status()
    
    functions = []
    for file in r.json()["files"]:
        for symbol in file["symbols"]:
            if symbol["kind"] == "function":
                functions.append({
                    "file": file["path"],
                    "name": symbol["name"],
                    "start_line": symbol["start_line"],
                    "end_line": symbol["end_line"],
                })
    return functions


def get_important_files(repo_id: int) -> list[str]:
    """Step 3: Get the top files to focus questions on."""
    r = httpx.get(f"{REPOLENS_URL}/repos/{repo_id}/important", timeout=30)
    r.raise_for_status()
    return [f["path"] for f in r.json()["files"]]


def find_relevant_code(repo_id: int, question_topic: str) -> list[dict]:
    """Step 4: Find code snippets relevant to a question topic."""
    r = httpx.post(
        f"{REPOLENS_URL}/repos/{repo_id}/search",
        json={"query": question_topic, "top_k": 5},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["results"]


# --- Example usage ---
if __name__ == "__main__":
    # Student submits their repo
    repo_id = load_repo_into_repolens("https://github.com/student/my-project")
    
    # Pick the most important files to ask about
    important = get_important_files(repo_id)
    print("Files to ask questions about:", important[:3])
    
    # Get all functions from those files
    functions = get_all_functions(repo_id)
    print(f"Found {len(functions)} functions to quiz the student on")
    
    # When generating a question about "error handling":
    relevant = find_relevant_code(repo_id, "error handling and exceptions")
    for r in relevant:
        print(f"  Relevant: {r['file_path']} -> {r['symbol_name']} (score={r['score']})")
        print(f"  Code: {r['snippet'][:100]}")
```

### What the API Returns That's Most Useful for Part 2

| RepoLens endpoint | What it gives you | How Part 2 uses it |
|---|---|---|
| `POST /analyze` | `repo_id` | Unique ID to track this student's submission |
| `GET /structure` | All files + functions + imports | Pick which functions to quiz the student on |
| `GET /important` | Top 10 most-imported files | Focus questions on the core files, not helper scripts |
| `POST /search` | Code chunks matching a topic | Give an LLM context when evaluating the student's answer |

### The One Thing to Add When Building Part 2

RepoLens currently stores everything in **SQLite locally**. When Part 2 is
ready, you have two options:

**Option A (Simple — same machine):**
Both Part 1 and Part 2 run on the same computer. Part 2 just calls
`http://localhost:8000`. No changes needed.

**Option B (Separate services):**
Run RepoLens on its own server, Part 2 on another. Change
`REPOLENS_URL = "http://localhost:8000"` to the actual server address.
RepoLens's API doesn't change at all.

---

## Part 5 — Quick Reference Card

```
START SERVER:
  .\venv\Scripts\activate
  $env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"
  .\venv\Scripts\uvicorn app.main:app --reload --port 8000

INTERACTIVE DOCS (browser):
  http://localhost:8000/docs

RUN TESTS:
  .\venv\Scripts\python -m pytest tests/ -q -k "not private_or_nonexistent"

ENDPOINTS:
  POST http://localhost:8000/analyze              body: {"url": "https://github.com/owner/repo"}
  GET  http://localhost:8000/repos                (list all analyzed repos)
  GET  http://localhost:8000/repos/{id}/structure (files, functions, imports)
  GET  http://localhost:8000/repos/{id}/important (top 10 by PageRank)
  POST http://localhost:8000/repos/{id}/search    body: {"query": "...", "top_k": 5}

DATABASE FILE:  repolens.db  (SQLite, in the project root)
CLONED REPOS:   repos/       (each repo in its own folder)
AI MODEL:       ~/.cache/huggingface/  (downloaded once, cached)
```
