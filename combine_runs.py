#!/usr/bin/env python3
"""
Combine multiple crawler run directories into a single deduplicated output.

Rules:
- Determine first ownership of posts by scanning each run's `visited_posts.txt`.
  The earliest run to list a post ID is considered its owner; later runs are ignored
  for that post.
- Read each run's `comments.jsonl` (if present) and write only comments
  whose `post_id` is owned by that run.
- De-duplicate comments globally by `comment_id`.

Outputs are written to `<input_root>/combined/`:
- `comments.jsonl`: merged comments (deduped)
- `visited_posts.txt`: union of all post IDs (sorted)
- `summary.json`: simple stats and provenance

Usage:
  python combine_runs.py --root /absolute/path/to/reddit_dump/run1

Notes:
- This script does not modify existing runs.
- It is robust to missing files and malformed lines.
"""

import argparse
import json
import hashlib
from pathlib import Path
from typing import Dict, Set, List, Tuple


def discover_run_dirs(root: Path) -> List[Path]:
    """Find run directories under the given root.

    A run dir is any subdirectory starting with "run_".
    Sorted by name to approximate chronological order since names embed timestamps.
    """
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Root directory not found or not a directory: {root}")
    run_dirs = sorted([p for p in root.iterdir() if p.is_dir() and p.name.startswith("run_")])
    return run_dirs


def read_visited_posts(run_dir: Path) -> List[str]:
    statefile = run_dir / "visited_posts.txt"
    if not statefile.exists():
        return []
    try:
        return [x.strip() for x in statefile.read_text(encoding="utf-8").splitlines() if x.strip()]
    except Exception:
        return []


def build_post_ownership(run_dirs: List[Path]) -> Tuple[Dict[str, int], Set[str]]:
    """Return mapping of post_id -> index of owning run, and the union set of post ids.

    The first run (by order in run_dirs) that lists a post id becomes the owner.
    """
    owner: Dict[str, int] = {}
    union: Set[str] = set()
    for idx, rd in enumerate(run_dirs):
        for pid in read_visited_posts(rd):
            union.add(pid)
            if pid not in owner:
                owner[pid] = idx
    return owner, union


def combine_comments(
    run_dirs: List[Path],
    owner: Dict[str, int],
    out_comments_path: Path,
) -> Tuple[int, int]:
    """Write combined comments.jsonl, returning (total_read_lines, unique_written)."""
    out_comments_path.parent.mkdir(parents=True, exist_ok=True)
    comment_ids_seen: Set[str] = set()
    total_read = 0
    unique_written = 0

    with open(out_comments_path, "w", encoding="utf-8") as out_f:
        for idx, rd in enumerate(run_dirs):
            comments_file = rd / "comments.jsonl"
            if not comments_file.exists():
                continue
            try:
                with open(comments_file, "r", encoding="utf-8") as in_f:
                    for line in in_f:
                        line = line.rstrip("\n")
                        if not line:
                            continue
                        total_read += 1
                        # Parse JSON, fallback to hash-based key if malformed
                        try:
                            rec = json.loads(line)
                        except Exception:
                            key = hashlib.md5(line.encode("utf-8")).hexdigest()
                            if key in comment_ids_seen:
                                continue
                            comment_ids_seen.add(key)
                            out_f.write(line + "\n")
                            unique_written += 1
                            continue

                        # Ownership filter by post_id
                        post_id = rec.get("post_id")
                        if post_id is None:
                            # If missing, conservatively keep, dedup by comment_id
                            pass
                        else:
                            owner_idx = owner.get(post_id)
                            if owner_idx is not None and owner_idx != idx:
                                continue

                        # Deduplicate by comment_id if available, else by content hash
                        key = rec.get("comment_id")
                        if not key:
                            key = hashlib.md5(line.encode("utf-8")).hexdigest()
                        if key in comment_ids_seen:
                            continue
                        comment_ids_seen.add(key)
                        out_f.write(line + "\n")
                        unique_written += 1
            except Exception:
                # Skip unreadable files
                continue

    return total_read, unique_written


def write_union_visited(union: Set[str], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for pid in sorted(union):
            f.write(pid + "\n")


def write_summary(out_path: Path, data: dict) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Combine Reddit crawler runs with de-duplication")
    parser.add_argument(
        "--root",
        required=True,
        help="Root directory containing run_* subdirectories (e.g., /abs/path/reddit_dump/run1)",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    run_dirs = discover_run_dirs(root)
    if not run_dirs:
        raise SystemExit(f"No run_* directories found under: {root}")

    owner, union = build_post_ownership(run_dirs)

    combined_dir = root / "combined"
    combined_comments = combined_dir / "comments.jsonl"
    union_visited = combined_dir / "visited_posts.txt"
    summary_file = combined_dir / "summary.json"

    total_read, unique_written = combine_comments(run_dirs, owner, combined_comments)
    write_union_visited(union, union_visited)
    write_summary(
        summary_file,
        {
            "root": str(root),
            "num_runs": len(run_dirs),
            "runs": [p.name for p in run_dirs],
            "total_read": total_read,
            "unique_written": unique_written,
            "union_visited_count": len(union),
            "outputs": {
                "comments_jsonl": str(combined_comments),
                "visited_posts": str(union_visited),
            },
        },
    )


if __name__ == "__main__":
    main()


