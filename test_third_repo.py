"""Test with a third repo: a small pure-Python project (httpie CLI tool)."""
import httpx, json

BASE = "http://localhost:8000"

print("=== ANALYZING THIRD REPO: httpie/httpie (medium Python) ===")
r = httpx.post(
    f"{BASE}/analyze",
    json={"url": "https://github.com/httpie/httpie"},
    timeout=300,
)
data = r.json()
print(json.dumps(data, indent=2))

if "repo_id" not in data:
    print("ERROR:", data)
    exit(1)

repo_id = data["repo_id"]

print(f"\n=== STRUCTURE: first 3 files ===")
r = httpx.get(f"{BASE}/repos/{repo_id}/structure", timeout=30)
files = r.json()["files"]
for f in files[:3]:
    print(f"  {f['path']} ({f['language']}): {len(f['symbols'])} symbols")

print(f"\n=== IMPORTANT: top 5 ===")
r = httpx.get(f"{BASE}/repos/{repo_id}/important", timeout=30)
for f in r.json()["files"][:5]:
    print(f"  #{f['rank']} {f['path']} (score={f['score']})")

print(f"\n=== SEARCH: where are HTTP headers processed? ===")
r = httpx.post(
    f"{BASE}/repos/{repo_id}/search",
    json={"query": "where are HTTP headers processed?", "top_k": 3},
    timeout=60,
)
for res in r.json()["results"]:
    print(f"  [{res['score']:.4f}] {res['file_path']} -> {res['kind']} {res['symbol_name']}")

print(f"\n=== RE-RUN (should skip everything) ===")
r = httpx.post(f"{BASE}/analyze", json={"url": "https://github.com/httpie/httpie"}, timeout=300)
print(r.json()["message"])
