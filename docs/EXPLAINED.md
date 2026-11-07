# RepoLens — Explained in Plain English

> This document explains every file in the project, what the key concepts mean,
> and how everything fits together. Written for someone who knows Python basics
> but is new to these ideas.

---

## Table of Contents

1. [The Big Picture](#the-big-picture)
2. [File-by-File Walkthrough](#file-by-file-walkthrough)
3. [Key Concepts Explained Simply](#key-concepts-explained-simply)
4. [How the Files Talk to Each Other](#how-the-files-talk-to-each-other)

---

## The Big Picture

Imagine you inherited a giant project from someone who left no documentation.
You have hundreds of files, and you want to answer:

- *"What files exist and what's in each one?"*
- *"Which file is the most important one I should read first?"*
- *"Where is the login code?"*

RepoLens answers all three questions automatically. You give it a GitHub link,
and it does the work.

---

## File-by-File Walkthrough

### `app/database.py` — The Storage Setup

**What it does:** Creates the SQLite database and all five tables when the
app starts. Think of it as setting up a filing cabinet with labeled folders
before you start storing anything.

**Main pieces:**
- `DB_PATH` — the path to `repolens.db` (the database file)
- `get_connection()` — opens a connection to the database so other code can
  read and write to it
- `init_db()` — creates the five tables if they don't exist yet:
  - `repos` — one row per GitHub repo you've analyzed
  - `files` — one row per source file inside a repo
  - `symbols` — one row per function or class found in a file
  - `imports` — one row per "file A imports module B" relationship
  - `embeddings` — one row per symbol's meaning vector (more on this later)

**How it connects:** Every other module calls `get_connection()` to get access
to the database.

---

### `app/utils.py` — The Helpers

**What it does:** Small, reusable tools that don't belong anywhere else.

**Main pieces:**
- `SKIP_DIRS` — a set of folder names we never look inside (like `node_modules`,
  `venv`, `.git`). Without this, we'd waste time parsing thousands of library files.
- `clone_repo(url)` — downloads a GitHub repo to your hard drive using Git.
  If you've downloaded it before, it just pulls the latest changes instead.
- `walk_source_files(root)` — walks every folder and subfolder looking for `.py`
  and `.js` files, skipping anything in `SKIP_DIRS`.
- `hash_file(path)` — reads a file and creates a 64-character "fingerprint"
  called a SHA-256 hash. If two files have the same hash, they are byte-for-byte
  identical.

**How it connects:** Used by `analyzer.py` (which calls all three functions)
and by the tests.

---

### `app/parser.py` — The Code Reader

**What it does:** Reads source code and extracts structured information from it —
specifically, the names and locations of all functions and classes, plus all
import statements.

**Main pieces:**
- `Symbol` — a simple data container holding one function or class:
  its kind ("function" or "class"), name, start line, end line, and source code.
- `FileAnalysis` — a container for everything we learned from one file:
  its path, language, list of symbols, and list of imports.
- `_parse_python(source)` — uses tree-sitter to parse a Python string into a tree,
  then walks the tree looking for `function_definition`, `class_definition`,
  `import_statement`, and `import_from_statement` nodes.
- `_parse_javascript(source)` — same idea but for JavaScript: finds
  `function_declaration`, `class_declaration`, arrow functions, ES module imports,
  and CommonJS `require()` calls.
- `parse_file(file_path, repo_root)` — the public function: reads a file from
  disk, calls the right parser, and returns a `FileAnalysis` object.

**How it connects:** Called by `analyzer.py` for every source file it finds.

---

### `app/graph.py` — The Map Builder

**What it does:** Takes the list of import relationships and builds a directed
graph (a map of arrows), then uses that map to figure out which files are most
important.

**Main pieces:**
- `build_graph(files_with_imports)` — takes a list of `(file_path, [imports])`
  pairs and creates a NetworkX directed graph. An edge from file A to file B
  means "A imports B".
- `_build_path_lookup(all_paths)` — creates a dictionary so we can match
  import strings like `"utils"` or `"app.utils"` to the actual file path
  `"app/utils.py"`.
- `_resolve_module(module, from_path, lookup)` — tries to match one import name
  to a real file. Returns `None` if it's an external library (like `numpy`).
- `rank_files(graph, top_n)` — runs PageRank on the graph and returns the
  top N files by score. Falls back to simple in-degree counting for very small
  repos.
- `get_graph_stats(graph)` — returns a quick summary (node count, edge count)
  for debugging.

**How it connects:** Called by `analyzer.py` after parsing, and called directly
by the `/important` endpoint in `main.py`.

---

### `app/embedder.py` — The Meaning Machine

**What it does:** Converts every function and class into a "meaning vector" —
a list of 384 numbers that captures what the code is about. Then, when you
search, it converts your question into a vector too and finds the closest match.

**Main pieces:**
- `MODEL_NAME` — the name of the AI model we use (`all-MiniLM-L6-v2`). It's
  about 80 MB and runs entirely on your computer.
- `get_model()` — loads the model once and keeps it in memory. Loading a model
  is slow, so we only do it once per server start.
- `_array_to_bytes(arr)` / `_bytes_to_array(data)` — convert a numpy array to
  raw bytes and back. We need this because SQLite can't store numpy arrays
  directly, but it can store raw bytes.
- `embed_text(text)` — turns a string of text into a 384-number vector.
- `embed_symbols(conn, repo_id)` — finds all symbols that don't have an embedding
  yet, embeds them all at once (batch processing is much faster), and saves the
  vectors to the database.
- `search(conn, repo_id, query, top_k)` — embeds the query, loads all stored
  vectors for the repo, computes cosine similarity between the query and every
  stored vector, and returns the top K matches.

**How it connects:** Called by `analyzer.py` at the end of analysis, and called
by the `/search` endpoint in `main.py`.

---

### `app/analyzer.py` — The Orchestrator

**What it does:** This is the "project manager" module. When you call `POST /analyze`,
this runs. It calls all the other modules in the right order.

**Main piece:**
- `analyze_repo(url)` — the single function that does everything:
  1. Validates the URL looks like a GitHub URL
  2. Clones or pulls the repo
  3. Gets or creates the repo record in the database
  4. Walks every source file
  5. For each file: checks the hash, skips if unchanged, or parses if new/changed
  6. Saves symbols and imports to the database
  7. Computes embeddings for any new symbols

**How it connects:** Called by the `POST /analyze` endpoint in `main.py`.
It orchestrates `utils.py`, `parser.py`, `graph.py`, and `embedder.py`.

---

### `app/models.py` — The Contracts

**What it does:** Defines the exact shape of every API request and response.
FastAPI uses these to validate inputs and generate the docs at `/docs`.

**Main pieces:**
- `AnalyzeRequest` — what you send to `POST /analyze`: just a `url` string
- `SearchRequest` — what you send to `POST /repos/{id}/search`: a `query`
  string and optional `top_k` number
- `AnalyzeResponse` — what you get back from analyze: repo_id, url, files_processed, message
- `StructureResponse` — list of files with their symbols and imports
- `ImportantFilesResponse` — ranked list of files with PageRank scores
- `SearchResponse` — list of matching code chunks with scores and snippets

**How it connects:** Used by `main.py` for all request/response validation.

---

### `app/main.py` — The API Layer

**What it does:** Defines all the HTTP endpoints. This is the "front door" of
the application.

**Main pieces:**
- `startup()` — called when the server starts; initializes the database
- `root()` — `GET /` — a simple health check
- `analyze(request)` — `POST /analyze` — kicks off a full repo analysis
- `structure(repo_id)` — `GET /repos/{id}/structure` — returns files and symbols
- `important_files(repo_id)` — `GET /repos/{id}/important` — returns the top
  10 most important files
- `search(repo_id, request)` — `POST /repos/{id}/search` — searches by meaning
- `list_repos()` — `GET /repos` — lists all analyzed repos

**How it connects:** This is the entry point. It calls `analyzer.py`, `graph.py`,
`embedder.py`, and `database.py` as needed for each endpoint.

---

### `tests/test_parser.py` — Parser Tests

Tests that the parser correctly extracts functions, classes, and imports from
Python and JavaScript code. Uses tiny code snippets written directly in the
test file — no actual repos needed.

### `tests/test_graph.py` — Graph Tests

Tests that the graph is built correctly (right edges, no self-loops) and that
PageRank correctly ranks the most-imported file highest.

### `tests/test_embedder.py` — Embedder Tests

Tests the numpy math (serialization, cosine similarity), plus one real model
test to verify that "login" and "authenticate" end up closer together in vector
space than "sort a list".

### `tests/test_rerun.py` — Re-Run Tests

Tests that hashing is deterministic, that changing a file changes its hash,
and that `walk_source_files` correctly skips `node_modules`, `venv`, etc.

---

## Key Concepts Explained Simply

### 1. Parsing into a Syntax Tree (AST)

**The idea:** When you read code as plain text, it's just a big string — you
can't easily find "the function named `login`." A parser reads that string and
builds a *tree* where every piece of code is a labeled node: "this is a
function definition, this is its name, this is its body."

**The analogy:** Imagine a recipe book. If you just have the text, finding all
recipes that use eggs means reading every word. But if someone has already
organized the book with a table of contents and labeled sections, you can jump
straight to "ingredients: eggs." The AST is that organized version of code.

**In RepoLens:** We use tree-sitter (a fast, reliable parser library) to parse
Python and JavaScript into ASTs. Then we walk the tree looking for nodes with
types like `function_definition` or `class_declaration`.

---

### 2. Dependency Graph

**The idea:** Draw a circle for every file. Draw an arrow from file A to file B
whenever A imports B. The result is a directed graph — a map of who depends on
whom.

**The analogy:** Think of a city's subway map. Each station is a file. Each
train line is an import. Some stations (like Central Station) have many lines
passing through them — those are your most important files.

**In RepoLens:** We use networkx to build this graph and then run PageRank on it.

---

### 3. Ranking by Importance (PageRank)

**The idea:** PageRank (Google's original algorithm) asks: "If you randomly
walked the graph, following arrows, which nodes would you visit most often?"
A node that many others point to gets visited more → higher rank.

**The analogy:** Imagine voting for "most important file." Every file that
imports another file is casting a vote for it. But some voters are themselves
important (lots of others import them), so their votes count more. The file
with the most weighted votes wins.

**In RepoLens:** Files like `utils.py` or `models.py` that are imported
everywhere get high PageRank scores and appear at the top of `/important`.

---

### 4. Embeddings and Meaning-Based Search

**The idea:** A word-search (CTRL+F) only finds exact matches. But if you
search for "authenticate user" you want to find `login_handler` even though
the words don't match. Embeddings solve this by turning text into numbers
in a way that similar meanings produce similar numbers.

**The analogy:** Imagine plotting every function on a giant map. Functions
that do similar things (login, auth, verify user) end up in the same
neighborhood on the map, even if they use different words. When you search,
we drop your query on the map and look at the nearest neighbors.

**The math:** The "distance" we use is cosine similarity — it measures the
angle between two vectors. An angle of 0° means identical meaning (score 1.0).
An angle of 90° means completely unrelated (score 0.0). We use dot product
because our vectors are pre-normalized (all have length 1), which makes
dot product equal to cosine similarity.

**In RepoLens:** We use the `all-MiniLM-L6-v2` model — a small, fast, local
model that runs entirely offline. It produces 384-number vectors for each
function/class. Searches take milliseconds once vectors are stored.

---

### 5. Hashing to Skip Unchanged Files

**The idea:** SHA-256 is a mathematical function that turns any file into a
unique 64-character string. If you change even one character in the file, the
hash changes completely (this is called an *avalanche effect*). If the hash
is the same, the file hasn't changed.

**The analogy:** Imagine you have 100 books and you want to know which ones
have been edited since last time. Instead of re-reading every book, you make
a "fingerprint" of each book (say, the sum of every letter's position in the
alphabet). If the fingerprint matches the stored one, the book hasn't changed.
SHA-256 is just a much more reliable version of this idea.

**In RepoLens:** Before parsing a file, we compute its SHA-256 hash and check
the database. If the hash matches what's stored, we skip parsing — saving
minutes on large repos with mostly-unchanged code.

---

## How the Files Talk to Each Other

```
Client
  |
  v
main.py  (receives HTTP requests)
  |
  v
analyzer.py  (orchestrates everything for /analyze)
  |-- utils.py      (clone repo, walk files, compute hashes)
  |-- parser.py     (tree-sitter: extract symbols and imports)
  |-- graph.py      (build dependency graph)
  |-- embedder.py   (compute and store meaning vectors)
  |-- database.py   (save everything to SQLite)
  
main.py also calls:
  |-- graph.py    (for /important endpoint)
  |-- embedder.py (for /search endpoint)
  |-- database.py (for /structure endpoint)
```

**The flow in one sentence:** The client talks to `main.py`, which delegates
to `analyzer.py` for analysis work, which in turn uses `utils.py`, `parser.py`,
`graph.py`, and `embedder.py` — each a specialist in one job — and saves
everything to the database via `database.py`.
