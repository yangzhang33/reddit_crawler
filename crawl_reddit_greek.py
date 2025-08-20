#!/usr/bin/env python3
"""
Crawl Greek subreddits via the official Reddit API and save *all comments*.
- Resumable (keeps a visited-posts state file)
- Expands full comment trees (replace_more(limit=None))
- Writes both JSONL and Parquet
- Language control:
   * Post-level: require Greek title and/or OP (configurable)
   * Comment-level: keep only Greek comments (configurable)
"""

import os, json, time, sys, signal, re
from pathlib import Path
from typing import Iterable, List, Dict
import pandas as pd
from tqdm import tqdm
from tenacity import retry, wait_exponential, stop_after_attempt

import praw
from praw.models import MoreComments
from langdetect import detect, LangDetectException

# ---------- USER CONFIG ----------
GREEK_SUBS = [
    "greece",  # add more: "athens", "thessaloniki", "cyprus", ...
]

LISTING = "top"          # "new" | "top" | "hot" | "rising"
TIMEFILTER = "all"       # for top(): "day"|"week"|"month"|"year"|"all"
POST_LIMIT = 100          # None = as many as Reddit returns (often ~1k per listing)

# Comment-level language filter
LANG_FILTER_GREEK = True   # keep only comments detected as Greek

# --- Post-level language gating (OP only) ---
REQUIRE_GREEK_OP = False       # if True, require OP (title+selftext) to look Greek
TITLE_MIN_GREEK_RATIO = 0.30   # fallback threshold on Greek codepoints if detector is unsure

OUTDIR = Path("reddit_greek_dump")
STATEFILE = OUTDIR / "visited_posts.txt"  # to avoid reprocessing posts across runs
JSONL_FILE = OUTDIR / "comments.jsonl"
PARQUET_FILE = OUTDIR / "comments.parquet"

# Fill these via environment variables
CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "YOUR_ID")
CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "YOUR_SECRET")
USER_AGENT = os.getenv("REDDIT_USER_AGENT", "greek-subreddits-miner:v1.0 (by u/YOURUSER)")
REQUEST_TIMEOUT = 30

# polite delay between posts to avoid 429s
POST_SLEEP = 0.4
# ---------- END USER CONFIG ----------

# --- Language helpers ---
_greek_re = re.compile(r'[\u0370-\u03FF\u1F00-\u1FFF]')

def greek_char_ratio(text: str) -> float:
    """Approximate ratio of Greek letters among alphabetic characters."""
    if not text:
        return 0.0
    greek = len(_greek_re.findall(text))
    letters = sum(ch.isalpha() for ch in text)
    return 0.0 if letters == 0 else greek / letters

def looks_greek(text: str, ratio_threshold: float = TITLE_MIN_GREEK_RATIO) -> bool:
    """Language check: try langdetect, fallback to Unicode range heuristic."""
    if not text:
        return False
    try:
        if detect(text) == "el":
            return True
    except LangDetectException:
        pass
    return greek_char_ratio(text) >= ratio_threshold

def is_greek(text: str) -> bool:
    """Comment-level check (langdetect only; short comments may be shaky)."""
    if not text:
        return False
    try:
        return detect(text) == "el"
    except LangDetectException:
        return False

# --- IO helpers ---
def ensure_outdir():
    OUTDIR.mkdir(parents=True, exist_ok=True)

def load_state() -> set:
    if STATEFILE.exists():
        return set(x.strip() for x in STATEFILE.read_text().splitlines() if x.strip())
    return set()

def append_state(post_id: str):
    with open(STATEFILE, "a", encoding="utf-8") as f:
        f.write(post_id + "\n")

def rows_to_parquet(rows: List[Dict], dest: Path):
    if not rows:
        return
    df = pd.DataFrame(rows)
    if dest.exists():
        old = pd.read_parquet(dest)
        df = pd.concat([old, df], ignore_index=True)
    df.to_parquet(dest, index=False)

def write_jsonl(rows: List[Dict], dest: Path):
    with open(dest, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def batched(iterable: Iterable, n: int) -> Iterable[List]:
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= n:
            yield batch
            batch = []
    if batch:
        yield batch

# --- Reddit setup ---
def init_reddit() -> praw.Reddit:
    if "YOUR_ID" in CLIENT_ID or "YOUR_SECRET" in CLIENT_SECRET:
        print("Please set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET env vars.", file=sys.stderr)
        sys.exit(1)
    return praw.Reddit(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        user_agent=USER_AGENT,
        requestor_kwargs={"timeout": REQUEST_TIMEOUT},
    )

@retry(wait=wait_exponential(multiplier=1, min=2, max=30), stop=stop_after_attempt(5))
def expand_comments(submission):
    submission.comments.replace_more(limit=None)

def stream_posts(subreddit, listing: str, timefilter: str, limit):
    if listing == "new":
        return subreddit.new(limit=limit)
    if listing == "hot":
        return subreddit.hot(limit=limit)
    if listing == "rising":
        return subreddit.rising(limit=limit)
    return subreddit.top(time_filter=timefilter, limit=limit)

# --- Main ---
def main():
    ensure_outdir()
    visited = load_state()
    reddit = init_reddit()

    # Graceful stop (CTRL+C)
    stop_flag = {"stop": False}
    def handle_sigint(signum, frame):
        stop_flag["stop"] = True
        print("\nStopping after current post…", flush=True)
    signal.signal(signal.SIGINT, handle_sigint)

    total_rows_buffer = []
    rows_buffer = []
    buffer_size = 2000  # write every N comments

    for sub in GREEK_SUBS:
        subreddit = reddit.subreddit(sub)
        print(f"\n>>> Crawling r/{sub} ({LISTING}, timefilter={TIMEFILTER}, limit={POST_LIMIT})")
        for submission in tqdm(stream_posts(subreddit, LISTING, TIMEFILTER, POST_LIMIT), desc=f"r/{sub}"):
            if stop_flag["stop"]:
                break
            if submission.id in visited:
                continue

            # --- Post-level Greek gate (OP only) BEFORE expanding comments ---
            if REQUIRE_GREEK_OP:
                op_text = f"{submission.title or ''} {(submission.selftext or '')}".strip()
                if not looks_greek(op_text):
                    append_state(submission.id)
                    continue

            # Base fields per post
            title_text = submission.title or ""
            base = {
                "subreddit": sub,
                "post_id": submission.id,
                "permalink": "https://www.reddit.com" + submission.permalink,
                "title": title_text,
                # "title_greek_ratio": greek_char_ratio(title_text),
                "selftext": submission.selftext or "",
                "author_post": str(submission.author) if submission.author else "[deleted]",
                "score_post": submission.score,
                "created_utc_post": float(submission.created_utc),
                "num_comments_post": int(submission.num_comments or 0),
                "over_18": bool(submission.over_18),
            }

            # Expand full comment tree
            try:
                expand_comments(submission)
            except Exception as e:
                print(f"  ! replace_more failed for {submission.id}: {e}")
                append_state(submission.id)
                continue

            # Flatten all comments (optionally keep only Greek)
            for c in submission.comments.list():
                if isinstance(c, MoreComments):
                    continue
                body = c.body or ""
                if LANG_FILTER_GREEK and body and not is_greek(body):
                    continue
                row = {
                    **base,
                    "comment_id": c.id,
                    "parent_id": c.parent_id,
                    "comment_author": str(c.author) if c.author else "[deleted]",
                    "comment_body": body,
                    "comment_score": c.score,
                    "created_utc_comment": float(c.created_utc),
                    "depth": int(getattr(c, "depth", 0) or 0),
                }
                rows_buffer.append(row)
                total_rows_buffer.append(row)

            append_state(submission.id)
            time.sleep(POST_SLEEP)

            # periodic writes
            if len(rows_buffer) >= buffer_size:
                write_jsonl(rows_buffer, JSONL_FILE)
                rows_to_parquet(rows_buffer, PARQUET_FILE)
                rows_buffer.clear()

        # flush after each subreddit
        if rows_buffer:
            write_jsonl(rows_buffer, JSONL_FILE)
            rows_to_parquet(rows_buffer, PARQUET_FILE)
            rows_buffer.clear()

        if stop_flag["stop"]:
            break

    print(f"\nDone. Wrote {len(total_rows_buffer)} comments this run.")
    print(f"Files:\n- {JSONL_FILE}\n- {PARQUET_FILE}\n- {STATEFILE} (resume state)")

if __name__ == "__main__":
    main()
