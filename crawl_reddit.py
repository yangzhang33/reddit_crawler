#!/usr/bin/env python3
"""
Crawl Greek subreddits via the official Reddit API and save *all comments*.
- Configurable via YAML file
- Resumable with run-specific folders (keeps a visited-posts state file)
- Expands full comment trees (replace_more(limit=None))
- Writes both JSONL and Parquet
- Structured logging with run tracking
- Language control:
   * Post-level: require Greek title and/or OP (configurable)
   * Comment-level: keep only Greek comments (configurable)
"""

import os
import json
import time
import sys
import signal
import re
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Dict, Any
import pandas as pd
import yaml
from tqdm import tqdm
from tenacity import retry, wait_exponential, stop_after_attempt

import praw
from praw.models import MoreComments
from langdetect import detect, LangDetectException


class RedditCrawlerConfig:
    """Configuration management for Reddit crawler."""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
            
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def get(self, key_path: str, default=None):
        """Get configuration value using dot notation (e.g., 'crawling.listing')."""
        keys = key_path.split('.')
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value


class RunMetadata:
    """Manages run metadata and statistics."""
    
    def __init__(self, run_id: str, run_dir: Path, config: Dict[str, Any]):
        self.run_id = run_id
        self.run_dir = run_dir
        self.config_snapshot = config.copy()
        self.start_time = datetime.now(timezone.utc)
        self.end_time = None
        self.duration = None
        self.posts_processed = 0
        self.comments_collected = 0
        self.exit_status = "running"
        self.files_written = []
        
    def add_file(self, filepath: Path):
        """Record a file that was written during this run."""
        self.files_written.append(str(filepath))
        
    def finish(self, exit_status: str = "completed"):
        """Mark the run as finished and calculate duration."""
        self.end_time = datetime.now(timezone.utc)
        self.duration = (self.end_time - self.start_time).total_seconds()
        self.exit_status = exit_status
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration,
            "posts_processed": self.posts_processed,
            "comments_collected": self.comments_collected,
            "exit_status": self.exit_status,
            "files_written": self.files_written,
            "config_snapshot": self.config_snapshot
        }
        
    def save(self):
        """Save metadata to JSON file."""
        metadata_file = self.run_dir / "metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        self.add_file(metadata_file)


class GreekRedditCrawler:
    """Main crawler class with structured logging and run management."""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = RedditCrawlerConfig(config_path)
        self.run_id = self._generate_run_id()
        self.run_dir = self._setup_run_directory()
        self.metadata = RunMetadata(self.run_id, self.run_dir, self.config.config)
        self.logger = self._setup_logging()
        self.reddit = None
        self.stop_flag = {"stop": False}
        
        # Language detection patterns
        self._greek_re = re.compile(r'[\u0370-\u03FF\u1F00-\u1FFF]')
        
    def _generate_run_id(self) -> str:
        """Generate unique run ID using timestamp and UUID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_uuid = str(uuid.uuid4())[:8]
        return f"{timestamp}_{short_uuid}"
        
    def _generate_descriptive_folder_name(self) -> str:
        """Generate descriptive folder name with run parameters."""
        # Get configuration details
        subreddits = self.config.get("subreddits", ["greece"])
        listing = self.config.get("crawling.listing", "top")
        timefilter = self.config.get("crawling.timefilter", "all")
        post_limit = self.config.get("crawling.post_limit", 100)
        
        # Create subreddit string (limit length for very long lists)
        if len(subreddits) <= 3:
            subs_str = "+".join(subreddits)
        else:
            subs_str = f"{'+'.join(subreddits[:2])}+{len(subreddits)-2}more"
        
        # Limit subreddit string length to avoid filesystem issues
        if len(subs_str) > 30:
            subs_str = subs_str[:27] + "..."
            
        # Build folder name components
        components = [f"run_{self.run_id}", subs_str, listing]
        
        # Add timefilter label for listings that support it (include 'all')
        if listing in ("top", "controversial"):
            if timefilter is not None:
                components.append(timefilter)
            
        # Add post limit if it's not unlimited (None)
        if post_limit is not None:
            components.append(f"limit{post_limit}")
            
        return "_".join(components)
    
    def _setup_run_directory(self) -> Path:
        """Create run-specific directory structure with descriptive name."""
        base_dir = Path(self.config.get("output.base_dir", "reddit_greek_dump"))
        folder_name = self._generate_descriptive_folder_name()
        run_dir = base_dir / folder_name
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir
        
    def _setup_logging(self) -> logging.Logger:
        """Setup structured logging with run ID."""
        logger = logging.getLogger(f"reddit_crawler_{self.run_id}")
        logger.setLevel(logging.INFO)
        
        # Clear any existing handlers
        logger.handlers.clear()
        
        # File handler
        log_file = self.run_dir / "crawler.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(
            f'[{self.run_id[:8]}] %(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        self.metadata.add_file(log_file)
        return logger
        
    def _init_reddit(self) -> praw.Reddit:
        """Initialize Reddit API client."""
        client_id = os.getenv(
            self.config.get("reddit_api.client_id_env", "REDDIT_CLIENT_ID")
        )
        client_secret = os.getenv(
            self.config.get("reddit_api.client_secret_env", "REDDIT_CLIENT_SECRET")
        )
        user_agent = os.getenv(
            self.config.get("reddit_api.user_agent_env", "REDDIT_USER_AGENT"),
            self.config.get("default_user_agent", "reddit-crawler:v2.0")
        )
        
        if not client_id or not client_secret or "YOUR_" in (client_id + client_secret):
            self.logger.error("Please set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET environment variables")
            sys.exit(1)
            
        self.logger.info(f"Initializing Reddit API client with user agent: {user_agent}")
        
        return praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
            requestor_kwargs={"timeout": self.config.get("reddit_api.request_timeout", 30)},
        )
        
    def greek_char_ratio(self, text: str) -> float:
        """Approximate ratio of Greek letters among alphabetic characters."""
        if not text:
            return 0.0
        greek = len(self._greek_re.findall(text))
        letters = sum(ch.isalpha() for ch in text)
        return 0.0 if letters == 0 else greek / letters

    def looks_greek(self, text: str) -> bool:
        """Language check: try langdetect, fallback to Unicode range heuristic."""
        if not text:
            return False
        try:
            if detect(text) == "el":
                return True
        except LangDetectException:
            pass
        threshold = self.config.get("language.title_min_greek_ratio", 0.30)
        return self.greek_char_ratio(text) >= threshold

    def is_greek(self, text: str) -> bool:
        """Comment-level check (langdetect only; short comments may be shaky)."""
        if not text:
            return False
        try:
            return detect(text) == "el"
        except LangDetectException:
            return False
            
    def load_visited_posts(self) -> set:
        """Load previously visited post IDs."""
        statefile = self.run_dir / "visited_posts.txt"
        if statefile.exists():
            visited = set(x.strip() for x in statefile.read_text().splitlines() if x.strip())
            self.logger.info(f"Loaded {len(visited)} previously visited posts")
            return visited
        return set()

    def append_visited_post(self, post_id: str):
        """Record a post as visited."""
        statefile = self.run_dir / "visited_posts.txt"
        with open(statefile, "a", encoding="utf-8") as f:
            f.write(post_id + "\n")
        self.metadata.add_file(statefile)

    def write_jsonl(self, rows: List[Dict], dest: Path):
        """Write comments to JSONL file."""
        with open(dest, "a", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        self.metadata.add_file(dest)

    def write_parquet(self, rows: List[Dict], dest: Path):
        """Write comments to Parquet file."""
        if not rows:
            return
        df = pd.DataFrame(rows)
        if dest.exists():
            old = pd.read_parquet(dest)
            df = pd.concat([old, df], ignore_index=True)
        df.to_parquet(dest, index=False)
        self.metadata.add_file(dest)

    @retry(wait=wait_exponential(multiplier=1, min=2, max=30), stop=stop_after_attempt(5))
    def expand_comments(self, submission):
        """Expand all comments in a submission with retry logic."""
        submission.comments.replace_more(limit=None)

    def get_posts_stream(self, subreddit, listing: str, timefilter: str, limit):
        """Get posts stream based on listing type."""
        if listing == "new":
            return subreddit.new(limit=limit)
        elif listing == "hot":
            return subreddit.hot(limit=limit)
        elif listing == "rising":
            return subreddit.rising(limit=limit)
        else:  # default to top
            return subreddit.top(time_filter=timefilter, limit=limit)

    def process_subreddit(self, subreddit_name: str, visited: set, 
                         rows_buffer: List[Dict]) -> List[Dict]:
        """Process a single subreddit and return updated buffer."""
        subreddit = self.reddit.subreddit(subreddit_name)
        
        listing = self.config.get("crawling.listing", "top")
        timefilter = self.config.get("crawling.timefilter", "all")
        post_limit = self.config.get("crawling.post_limit", 100)
        
        self.logger.info(f"Crawling r/{subreddit_name} ({listing}, timefilter={timefilter}, limit={post_limit})")
        
        posts_stream = self.get_posts_stream(subreddit, listing, timefilter, post_limit)
        
        for submission in tqdm(posts_stream, desc=f"r/{subreddit_name}"):
            if self.stop_flag["stop"]:
                break
                
            if submission.id in visited:
                continue
                
            # Post-level language filtering
            title_ok = self.looks_greek(submission.title or "")
            if self.config.get("language.require_greek_title", True) and not title_ok:
                self.append_visited_post(submission.id)
                continue
                
            if self.config.get("language.require_greek_op", False):
                op_text = f"{submission.title or ''} {submission.selftext or ''}".strip()
                if not self.looks_greek(op_text):
                    self.append_visited_post(submission.id)
                    continue
            
            # Base post information
            base_data = {
                "subreddit": subreddit_name,
                "post_id": submission.id,
                "permalink": "https://www.reddit.com" + submission.permalink,
                "title": submission.title or "",
                "selftext": submission.selftext or "",
                "author_post": str(submission.author) if submission.author else "[deleted]",
                "score_post": submission.score,
                "created_utc_post": float(submission.created_utc),
                "num_comments_post": int(submission.num_comments or 0),
                "over_18": bool(submission.over_18),
            }
            
            # Expand comments
            try:
                self.expand_comments(submission)
                self.logger.debug(f"Expanded comments for post {submission.id}")
            except Exception as e:
                self.logger.warning(f"Failed to expand comments for {submission.id}: {e}")
                self.append_visited_post(submission.id)
                continue
                
            # Process comments
            comments_added = 0
            for comment in submission.comments.list():
                if isinstance(comment, MoreComments):
                    continue
                    
                body = comment.body or ""
                if self.config.get("language.filter_greek_comments", True) and body and not self.is_greek(body):
                    continue
                    
                comment_data = {
                    **base_data,
                    "comment_id": comment.id,
                    "parent_id": comment.parent_id,
                    "comment_author": str(comment.author) if comment.author else "[deleted]",
                    "comment_body": body,
                    "comment_score": comment.score,
                    "created_utc_comment": float(comment.created_utc),
                    "depth": int(getattr(comment, "depth", 0) or 0),
                }
                rows_buffer.append(comment_data)
                comments_added += 1
                
            self.metadata.posts_processed += 1
            self.metadata.comments_collected += comments_added
            self.append_visited_post(submission.id)
            
            if comments_added > 0:
                self.logger.debug(f"Added {comments_added} comments from post {submission.id}")
                
            # Rate limiting
            time.sleep(self.config.get("crawling.post_sleep", 0.4))
            
            # Periodic buffer flush
            buffer_size = self.config.get("output.buffer_size", 2000)
            if len(rows_buffer) >= buffer_size:
                self._flush_buffer(rows_buffer)
                
        return rows_buffer
        
    def _flush_buffer(self, rows_buffer: List[Dict]):
        """Flush comment buffer to disk."""
        if not rows_buffer:
            return
            
        jsonl_file = self.run_dir / "comments.jsonl"
        parquet_file = self.run_dir / "comments.parquet"
        
        self.write_jsonl(rows_buffer, jsonl_file)
        self.write_parquet(rows_buffer, parquet_file)
        
        self.logger.info(f"Flushed {len(rows_buffer)} comments to disk")
        rows_buffer.clear()
        
    def _setup_signal_handler(self):
        """Setup graceful shutdown on SIGINT."""
        def handle_sigint(signum, frame):
            self.stop_flag["stop"] = True
            self.logger.info("Received SIGINT, stopping after current post...")
        signal.signal(signal.SIGINT, handle_sigint)
        
    def run(self):
        """Main crawler execution."""
        try:
            self.logger.info(f"Starting Reddit crawler run {self.run_id}")
            self.logger.info(f"Output directory: {self.run_dir}")
            
            self._setup_signal_handler()
            self.reddit = self._init_reddit()
            visited = self.load_visited_posts()
            rows_buffer = []
            
            subreddits = self.config.get("subreddits", ["greece"])
            self.logger.info(f"Crawling subreddits: {subreddits}")
            
            for subreddit_name in subreddits:
                if self.stop_flag["stop"]:
                    break
                    
                rows_buffer = self.process_subreddit(subreddit_name, visited, rows_buffer)
                
                # Flush after each subreddit
                self._flush_buffer(rows_buffer)
                
            # Final flush
            self._flush_buffer(rows_buffer)
            
            self.metadata.finish("completed")
            self.logger.info(f"Crawl completed. Posts: {self.metadata.posts_processed}, "
                           f"Comments: {self.metadata.comments_collected}")
            
        except KeyboardInterrupt:
            self.metadata.finish("interrupted")
            self.logger.info("Crawl interrupted by user")
        except Exception as e:
            self.metadata.finish("error")
            self.logger.error(f"Crawl failed with error: {e}", exc_info=True)
            raise
        finally:
            self.metadata.save()
            self.logger.info(f"Run metadata saved to {self.run_dir / 'metadata.json'}")


def main():
    """Entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Crawl Greek Reddit content")
    parser.add_argument("--config", default="config.yaml", 
                       help="Configuration file path (default: config.yaml)")
    args = parser.parse_args()
    
    crawler = GreekRedditCrawler(args.config)
    crawler.run()


if __name__ == "__main__":
    main()