#!/usr/bin/env python3
"""
Batch orchestrator to maximize posts per subreddit by combining multiple
listing/timefilter runs of the existing crawler while de-duplicating posts.

- Reads base settings from a config file (subreddits, language filters, etc.)
- Runs the existing `GreekRedditCrawler` many times per subreddit with
  different (listing, timefilter) combinations
- Shares a cumulative `visited_posts.txt` across runs for each subreddit to
  avoid processing the same post multiple times
- Keeps each subreddit separate

Usage:
  python batch_crawl_reddit.py --config config.yaml

Notes:
- This script does not modify the existing crawler code. It imports and uses it.
- It writes a temporary config per run and pre-seeds a visited file in the
  new run directory before calling `crawler.run()` to ensure de-duplication.
"""

import argparse
import os
import json
import shutil
import hashlib
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any, Set
import yaml
from datetime import datetime

from crawl_reddit_greek import GreekRedditCrawler

# Monkey-patch: extend supported listings without modifying core crawler file
def _patched_get_posts_stream(self, subreddit, listing: str, timefilter: Optional[str], limit):
    try:
        if listing == "new":
            return subreddit.new(limit=limit)
        if listing == "hot":
            return subreddit.hot(limit=limit)
        if listing == "rising":
            return subreddit.rising(limit=limit)
        if listing == "best":
            return subreddit.best(limit=limit)
        if listing == "controversial":
            # timefilter can be: hour, day, week, month, year, all
            return subreddit.controversial(time_filter=(timefilter or "all"), limit=limit)
        # default to top
        return subreddit.top(time_filter=(timefilter or "all"), limit=limit)
    except Exception:
        # Fallback to top if anything unexpected happens
        return subreddit.top(time_filter=(timefilter or "all"), limit=limit)


# Apply the monkey patch so batch runs can use extended listings
GreekRedditCrawler.get_posts_stream = _patched_get_posts_stream


def load_base_config(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def write_temp_config(
    base_config: Dict[str, Any],
    subreddit: str,
    listing: str,
    timefilter: Optional[str],
    tmp_dir: Path,
) -> Path:
    cfg = dict(base_config)

    # Ensure required sections exist
    cfg.setdefault("crawling", {})

    # Subreddit per run (keep each subreddit separate)
    cfg["subreddits"] = [subreddit]

    # Override crawling parameters for this run
    cfg["crawling"]["listing"] = listing
    if timefilter is not None:
        cfg["crawling"]["timefilter"] = timefilter
    # Do not override post_limit; keep the value from base_config

    tmp_dir.mkdir(parents=True, exist_ok=True)
    name = f"tmp_{subreddit}_{listing}_{timefilter or 'none'}.yaml"
    path = tmp_dir / name
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)
    return path


def seed_visited(run_dir: Path, visited_ids: Set[str]) -> None:
    if not visited_ids:
        return
    run_dir.mkdir(parents=True, exist_ok=True)
    statefile = run_dir / "visited_posts.txt"
    # If pre-existing, merge to avoid losing any in-flight state
    existing: Set[str] = set()
    if statefile.exists():
        existing = set(x.strip() for x in statefile.read_text(encoding="utf-8").splitlines() if x.strip())
    merged = existing | visited_ids
    with open(statefile, "w", encoding="utf-8") as f:
        for pid in sorted(merged):
            f.write(pid + "\n")


def read_visited(run_dir: Path) -> Set[str]:
    statefile = run_dir / "visited_posts.txt"
    if not statefile.exists():
        return set()
    return set(x.strip() for x in statefile.read_text(encoding="utf-8").splitlines() if x.strip())


def get_default_combinations() -> List[Tuple[str, Optional[str]]]:
    # Expanded combinations for maximum coverage
    combos: List[Tuple[str, Optional[str]]] = []
    # Non-timefiltered listings
    combos.extend([
        ("new", None),
        ("hot", None),
        ("rising", None),
        ("best", None),
    ])
    # Timefiltered listings for top and controversial
    timefilters = ["hour", "day", "week", "month", "year", "all"]
    for tf in timefilters:
        combos.append(("top", tf))
    for tf in timefilters:
        combos.append(("controversial", tf))
    return combos


def main():
    parser = argparse.ArgumentParser(description="Batch orchestrator for Greek Reddit crawler")
    parser.add_argument("--config", default="config.yaml", help="Base configuration file path")
    # Post limit is read from the config under crawling.post_limit
    parser.add_argument(
        "--combos",
        nargs="*",
        help=(
            "Optional custom combinations as listing[:timefilter], e.g. 'new' 'top:month'. "
            "If omitted, a sensible default set is used."
        ),
    )
    args = parser.parse_args()

    base_cfg_path = Path(args.config)
    base_cfg = load_base_config(base_cfg_path)

    # Determine subreddits to process (keep them separate) strictly from config
    subreddits_cfg = base_cfg.get("subreddits")
    if not isinstance(subreddits_cfg, list) or not subreddits_cfg:
        raise ValueError("Config error: 'subreddits' must be a non-empty list of subreddit names")
    subreddits: List[str] = [s.strip() for s in subreddits_cfg if isinstance(s, str) and s.strip()]
    if not subreddits:
        raise ValueError("Config error: 'subreddits' list contains no valid subreddit names")

    # Determine combinations
    if args.combos:
        combos: List[Tuple[str, Optional[str]]] = []
        for token in args.combos:
            if ":" in token:
                listing, tf = token.split(":", 1)
                combos.append((listing.strip(), tf.strip()))
            else:
                combos.append((token.strip(), None))
    else:
        combos = get_default_combinations()

    tmp_cfg_dir = Path(".batch_tmp_configs")
    base_output_dir = Path(base_cfg.get("output", {}).get("base_dir", "reddit_greek_dump"))
    base_output_dir.mkdir(parents=True, exist_ok=True)

    # Announce plan
    print("Subreddits:", ", ".join(f"r/{s}" for s in subreddits))
    combos_str = ", ".join(
        f"{lst}:{tf}" if tf is not None else f"{lst}" for (lst, tf) in combos
    )
    print("Combinations:", combos_str)
    print("Output root:", str(base_output_dir))
    print("Note: duplicates are avoided via a shared visited set per subreddit.\n")

    # Batch timestamp to differentiate outputs per run of this orchestrator
    batch_ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    for subreddit in subreddits:
        print(f"=== Processing subreddit: r/{subreddit} ===")
        # Prepare subreddit root folder and runs folder
        subreddit_root_dir = base_output_dir / f"{subreddit}_{batch_ts}"
        runs_dir = subreddit_root_dir / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)

        # Copy the base config used
        try:
            shutil.copy2(str(base_cfg_path), str(subreddit_root_dir / "config_used.yaml"))
        except Exception:
            pass

        # Load cumulative visited for this subreddit (persisted between batch runs)
        cum_visited_file = subreddit_root_dir / "visited_posts.txt"
        cumulative_visited: Set[str] = set()
        if cum_visited_file.exists():
            cumulative_visited = set(
                x.strip() for x in cum_visited_file.read_text(encoding="utf-8").splitlines() if x.strip()
            )
        print(f"Initial visited for r/{subreddit}: {len(cumulative_visited)} posts")

        # Collect global metadata for this subreddit
        batch_runs_meta = []

        for (listing, timefilter) in combos:
            print(f"-- Combo: listing={listing}, timefilter={timefilter or 'n/a'}")

            # Build temporary config for this run
            tmp_cfg_path = write_temp_config(
                base_config=base_cfg,
                subreddit=subreddit,
                listing=listing,
                timefilter=timefilter,
                tmp_dir=tmp_cfg_dir,
            )

            # Initialize crawler to discover run_dir, then seed visited before run
            crawler = GreekRedditCrawler(str(tmp_cfg_path))
            print(f"   Seeding visited into run dir ({len(cumulative_visited)} ids)")
            seed_visited(crawler.run_dir, cumulative_visited)

            # Execute run, but continue to next combo on failure
            run_status = "completed"
            run_error: Optional[str] = None
            try:
                crawler.run()
            except KeyboardInterrupt:
                raise
            except Exception as e:
                run_status = "error"
                run_error = str(e)
                print(f"   Combo failed: {e}")

            # Move the run directory under subreddit runs folder
            run_dir_basename = os.path.basename(str(crawler.run_dir))
            dest_run_dir = runs_dir / run_dir_basename
            try:
                shutil.move(str(crawler.run_dir), str(dest_run_dir))
            except Exception:
                # If move fails, keep original location
                dest_run_dir = Path(crawler.run_dir)

            # Merge newly visited into cumulative set (read from destination)
            run_visited = read_visited(dest_run_dir)
            before = len(cumulative_visited)
            cumulative_visited |= run_visited
            added = len(cumulative_visited) - before
            print(f"   Visited added this run: {added}, total for r/{subreddit}: {len(cumulative_visited)}")

            # Record per-run metadata entry
            entry = {
                "listing": listing,
                "timefilter": timefilter,
                "visited_added": added,
                "run_dir": str(dest_run_dir),
                "status": run_status,
            }
            if run_error:
                entry["error"] = run_error
            batch_runs_meta.append(entry)

        # Persist cumulative visited for this subreddit
        with open(cum_visited_file, "w", encoding="utf-8") as f:
            for pid in sorted(cumulative_visited):
                f.write(pid + "\n")
        # Combine all run comments into runs/combined/comments.jsonl (dedupe by comment_id)
        combined_dir = runs_dir / "combined"
        combined_dir.mkdir(parents=True, exist_ok=True)
        combined_file = combined_dir / "comments.jsonl"
        comment_ids_seen = set()
        total_read = 0
        unique_written = 0
        run_comment_files = sorted(runs_dir.glob("run_*/comments.jsonl"))
        print(f"Combining {len(run_comment_files)} run comment files for r/{subreddit} ...")
        with open(combined_file, "w", encoding="utf-8") as out_f:
            for cf in run_comment_files:
                try:
                    with open(cf, "r", encoding="utf-8") as in_f:
                        for line in in_f:
                            line = line.rstrip("\n")
                            if not line:
                                continue
                            total_read += 1
                            try:
                                rec = json.loads(line)
                            except Exception:
                                # Fallback: keep unknown lines uniquely by hash
                                key = hashlib.md5(line.encode("utf-8")).hexdigest()
                                if key in comment_ids_seen:
                                    continue
                                comment_ids_seen.add(key)
                                out_f.write(line + "\n")
                                unique_written += 1
                                continue
                            key = rec.get("comment_id")
                            if not key:
                                key = hashlib.md5(line.encode("utf-8")).hexdigest()
                            if key in comment_ids_seen:
                                continue
                            comment_ids_seen.add(key)
                            out_f.write(line + "\n")
                            unique_written += 1
                except FileNotFoundError:
                    continue
        print(f"Combined comments written: {unique_written} (from {total_read} read)")

        # Write batch metadata for this subreddit
        batch_meta = {
            "subreddit": subreddit,
            "combinations": [
                {"listing": lst, "timefilter": tf} for (lst, tf) in combos
            ],
            "total_unique_posts": len(cumulative_visited),
            "runs": batch_runs_meta,
            "combined": {
                "comments_file": str(combined_file),
                "total_read": total_read,
                "unique_written": unique_written,
            },
        }
        with open(subreddit_root_dir / "batch_metadata.json", "w", encoding="utf-8") as f:
            json.dump(batch_meta, f, ensure_ascii=False, indent=2)

        print(f"=== Finished r/{subreddit}. Total unique posts visited: {len(cumulative_visited)} ===")


if __name__ == "__main__":
    main()


