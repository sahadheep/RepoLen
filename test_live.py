"""Quick integration test that hits the live server."""
import httpx, json, sys

BASE = "http://localhost:8000"

# Test structure
print("=== STRUCTURE (first 2 files) ===")
r = httpx.get(f"{BASE}/repos/1/structure", timeout=30)
data = r.json()
for f in data["files"][:2]:
    print(f"  {f['path']} ({f['language']}): {len(f['symbols'])} symbols, {len(f['imports'])} imports")
    for s in f["symbols"][:3]:
        print(f"    {s['kind']:8} {s['name']} (lines {s['start_line']}-{s['end_line']})")
print()

# Test important
print("=== IMPORTANT FILES (top 5) ===")
r = httpx.get(f"{BASE}/repos/1/important", timeout=30)
data = r.json()
for f in data["files"][:5]:
    print(f"  #{f['rank']} {f['path']} (score={f['score']})")
print()

# Test search
print("=== SEARCH: where is HTTP session handling? ===")
r = httpx.post(
    f"{BASE}/repos/1/search",
    json={"query": "where is HTTP session handling?", "top_k": 3},
    timeout=60,
)
data = r.json()
for res in data["results"]:
    print(f"  [{res['score']:.4f}] {res['file_path']} -> {res['kind']} {res['symbol_name']} (L{res['start_line']})")
    print(f"    Snippet: {res['snippet'][:80]}...")
print()

# Test re-run
print("=== RE-RUN (should skip all files) ===")
r = httpx.post(f"{BASE}/analyze", json={"url": "https://github.com/psf/requests"}, timeout=300)
print(r.json()["message"])
