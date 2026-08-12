"""
llm.py — the single gate through which Lookout may call a language model.

Every LLM call in this repository goes through `ask()`. Nothing imports an SDK
and nothing reads an API key. The only backend is the `claude` CLI in print
mode (`claude -p`), which bills against the Claude.ai subscription rather than
metered API credit. See docs/llm-usage.md for the policy this file enforces.

Four guarantees:

  1. Subscription-only    — the backend is always `claude -p`. No `anthropic`
                            SDK, no ANTHROPIC_API_KEY, no HTTP client.
  2. Cached               — responses are keyed by sha256(model + prompt) under
                            vault/.llm-cache/. Re-running a pipeline over
                            unchanged input costs nothing.
  3. Never fatal          — a missing binary, a non-zero exit, or a timeout
                            returns the caller's `fallback` string. This mirrors
                            gather.py, where an unreachable source is recorded
                            as "absent" and the run still exits 0.
  4. Off by default       — `ask()` returns `fallback` without spawning anything
                            unless LOOKOUT_LLM=1. The nightly `lookout --all`
                            sweep therefore stays fully deterministic; enrichment
                            is opt-in per run.

Usage
-----
    import llm

    text = llm.ask(
        "Summarise this project in one sentence:\\n" + readme,
        fallback="`asset-studio` is a project tracked by Lookout.",
        purpose="one-liner",
    )

CLI (for checking the wiring):
    python llm.py --status
    LOOKOUT_LLM=1 python llm.py --ask "say hi"
"""
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent
DEFAULT_CACHE_DIR = REPO_ROOT / "vault" / ".llm-cache"

# Mechanical, well-bounded generation. Nothing Lookout asks for needs more.
DEFAULT_MODEL = "haiku"
DEFAULT_TIMEOUT = 120

ENV_ENABLE = "LOOKOUT_LLM"
ENV_MODEL = "LOOKOUT_LLM_MODEL"
ENV_TIMEOUT = "LOOKOUT_LLM_TIMEOUT"

# Populated by ask(); read by callers that want to report what a run did.
STATS = {"hits": 0, "misses": 0, "calls": 0, "failures": 0, "skipped": 0}


def enabled() -> bool:
    """True when LLM enrichment is switched on for this run."""
    return os.environ.get(ENV_ENABLE, "").strip() in ("1", "true", "yes", "on")


def available() -> bool:
    """True when the `claude` CLI is on PATH."""
    return shutil.which("claude") is not None


def _cache_key(model: str, prompt: str) -> str:
    return hashlib.sha256(f"{model}\n{prompt}".encode("utf-8")).hexdigest()


def _cache_path(cache_dir: Path, key: str) -> Path:
    return cache_dir / f"{key}.txt"


def ask(
    prompt: str,
    *,
    fallback: str,
    model: str | None = None,
    purpose: str = "",
    cache_dir: Path | None = None,
    timeout: int | None = None,
    use_cache: bool = True,
) -> str:
    """Ask the model for `prompt`, returning `fallback` if anything prevents it.

    `purpose` is a short label used only in the log line printed on a live call,
    so a run's output shows which stage spent tokens.

    This function never raises and never propagates a non-zero exit.
    """
    model = model or os.environ.get(ENV_MODEL) or DEFAULT_MODEL
    cache_dir = cache_dir or DEFAULT_CACHE_DIR
    if timeout is None:
        try:
            timeout = int(os.environ.get(ENV_TIMEOUT, DEFAULT_TIMEOUT))
        except ValueError:
            timeout = DEFAULT_TIMEOUT

    if not enabled():
        STATS["skipped"] += 1
        return fallback

    key = _cache_key(model, prompt)
    cached = _cache_path(cache_dir, key)
    if use_cache and cached.exists():
        try:
            STATS["hits"] += 1
            return cached.read_text(encoding="utf-8")
        except OSError:
            pass  # unreadable cache entry — fall through and regenerate

    if not available():
        STATS["failures"] += 1
        print("llm: `claude` not found on PATH — using deterministic fallback",
              file=sys.stderr)
        return fallback

    STATS["misses"] += 1
    STATS["calls"] += 1
    label = f" ({purpose})" if purpose else ""
    print(f"llm: calling claude -p --model {model}{label} …", file=sys.stderr)

    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--model", model],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        STATS["failures"] += 1
        print(f"llm: timed out after {timeout}s — using fallback", file=sys.stderr)
        return fallback
    except OSError as exc:
        STATS["failures"] += 1
        print(f"llm: could not run claude ({exc}) — using fallback", file=sys.stderr)
        return fallback

    if result.returncode != 0:
        STATS["failures"] += 1
        err = (result.stderr or "").strip().splitlines()
        detail = err[-1] if err else f"exit {result.returncode}"
        print(f"llm: call failed ({detail}) — using fallback", file=sys.stderr)
        return fallback

    text = (result.stdout or "").strip()
    if not text:
        STATS["failures"] += 1
        print("llm: empty response — using fallback", file=sys.stderr)
        return fallback

    if use_cache:
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            cached.write_text(text, encoding="utf-8")
        except OSError:
            pass  # cache is an optimisation, never a requirement

    return text


def status() -> dict:
    """Snapshot of the current LLM configuration, for `--status` and runbooks."""
    return {
        "enabled": enabled(),
        "claude_on_path": available(),
        "model": os.environ.get(ENV_MODEL) or DEFAULT_MODEL,
        "cache_dir": str(DEFAULT_CACHE_DIR),
        "cache_entries": (
            len(list(DEFAULT_CACHE_DIR.glob("*.txt")))
            if DEFAULT_CACHE_DIR.exists() else 0
        ),
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(prog="llm.py")
    parser.add_argument("--status", action="store_true",
                        help="print LLM configuration and exit")
    parser.add_argument("--ask", metavar="PROMPT",
                        help="send a prompt (requires LOOKOUT_LLM=1)")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    if args.status or not args.ask:
        for k, v in status().items():
            print(f"{k}: {v}")
        return

    print(ask(args.ask, fallback="(fallback — no LLM output)",
              model=args.model, purpose="cli"))


if __name__ == "__main__":
    main()
