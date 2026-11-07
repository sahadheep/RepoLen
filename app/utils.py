import hashlib
import os
import shutil
from pathlib import Path

import git

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("GIT_TERMINAL_PROMPT", "0")

SKIP_DIRS = {
    "node_modules", ".git", "venv", ".venv", "env",
    "build", "dist", "__pycache__", ".pytest_cache",
    ".tox", "coverage", ".eggs", "*.egg-info",
    "target",
}

SUPPORTED_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
}

REPOS_DIR = Path(__file__).parent.parent / "repos"


def clone_repo(url: str) -> Path:
    REPOS_DIR.mkdir(exist_ok=True)

    clean = url.rstrip("/").replace("https://github.com/", "").replace("/", "__")
    clone_path = REPOS_DIR / clean

    if clone_path.exists():
        try:
            repo = git.Repo(clone_path)
            repo.remotes.origin.pull(kill_after_timeout=30)
            print(f"[GIT] Pulled latest: {clone_path}")
        except Exception as e:
            safe_msg = str(e).encode("ascii", errors="replace").decode("ascii")
            print(f"[GIT] Pull skipped ({safe_msg}), using existing checkout")
    else:
        try:
            git.Repo.clone_from(url, clone_path, depth=1)
            print(f"[GIT] Cloned {url} -> {clone_path}")
        except git.GitCommandError as e:
            safe_msg = str(e).encode("ascii", errors="replace").decode("ascii")
            if "not found" in safe_msg.lower() or "repository" in safe_msg.lower():
                raise ValueError(f"Repo not found or is private: {url}") from e
            raise ValueError(f"Git clone failed: {safe_msg}") from e

    return clone_path


def walk_source_files(root: Path) -> list[tuple[Path, str]]:
    results = []
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        if path.is_file():
            lang = SUPPORTED_EXTENSIONS.get(path.suffix.lower())
            if lang:
                results.append((path, lang))
    return results


def hash_file(path: Path) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


def delete_repo(clone_path: Path) -> None:
    if clone_path.exists():
        shutil.rmtree(clone_path)
