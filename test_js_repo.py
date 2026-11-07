"""Test with a JS repo (expressjs/express) and a medium Python repo."""
import httpx, json

BASE = "http://localhost:8000"

# Test with a JavaScript repo
print("=== ANALYZING JS REPO: expressjs/express ===")
r = httpx.post(
    f"{BASE}/analyze",
    json={"url": "https://github.com/expressjs/express"},
    timeout=300,
)
data = r.json()
print(json.dumps(data, indent=2))
repo_id = data["repo_id"]

print(f"\n=== IMPORTANT FILES in express (repo #{repo_id}) ===")
r = httpx.get(f"{BASE}/repos/{repo_id}/important", timeout=30)
for f in r.json()["files"][:5]:
    print(f"  #{f['rank']} {f['path']} (score={f['score']})")

print(f"\n=== SEARCH: where is route middleware handled? ===")
r = httpx.post(
    f"{BASE}/repos/{repo_id}/search",
    json={"query": "where is route middleware handled?", "top_k": 3},
    timeout=60,
)
for res in r.json()["results"]:
    print(f"  [{res['score']:.4f}] {res['file_path']} -> {res['kind']} {res['symbol_name']} (L{res['start_line']})")
