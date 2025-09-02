# Reddit Content Crawler

A sophisticated Python crawler for collecting content from Reddit using the official Reddit API. The crawler is designed to systematically collect posts and comments from any subreddits, with advanced language detection and filtering capabilities for any language or no language filtering.

## Features

- **🎯 Flexible Language Detection**: Advanced language detection using `langdetect` library with Unicode character analysis for languages with unique scripts (Greek, Russian, Arabic, Chinese, Japanese, Korean, Thai, Hindi)
- **📊 Dual Output Formats**: Saves data in both JSONL and Parquet formats for flexibility
- **🔄 Resumable Crawling**: Maintains state to resume interrupted crawls without duplication
- **📁 Run Management**: Organizes outputs in timestamped run folders with comprehensive metadata
- **🛡️ Rate Limiting**: Respectful API usage with configurable delays and retry logic
- **📝 Structured Logging**: Detailed logging with run tracking and multiple output destinations
- **⚙️ Flexible Configuration**: YAML-based configuration system for easy customization
- **🌳 Complete Comment Trees**: Expands all comment threads including nested replies

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd reddit_crawler
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up Reddit API credentials**:
   - Create a Reddit application at https://www.reddit.com/prefs/apps
   - Set environment variables:
   ```bash
   export REDDIT_CLIENT_ID="your_client_id"
   export REDDIT_CLIENT_SECRET="your_client_secret"
   export REDDIT_USER_AGENT="your-app-name:v1.0 (by u/yourusername)"
   ```

## Quick Start

1. **Configure the crawler** by editing `config.yaml` (see Configuration section below)
2. **Run the crawler**:
   ```bash
   python crawl_reddit.py
   ```
3. **Find your results** in the `reddit_dump/run_YYYYMMDD_HHMMSS_<uuid>/` directory

### Maximize Coverage (Batch Orchestrator)

Reddit's API limits each listing to roughly 1k items. To maximize coverage, a simple batch orchestrator runs the existing crawler multiple times per subreddit using different listing/timefilter combinations while de-duplicating posts across runs per subreddit.

Run it with your existing `config.yaml`:

```bash
python batch_crawl_reddit.py --config config.yaml
```

What it does:
- Runs per-subreddit, sequentially, keeping subreddits separate
- Cycles through combinations: `new`, `hot`, `rising`, `best`, `top:{hour,day,week,month,year,all}`, `controversial:{hour,day,week,month,year,all}`
- Shares a cumulative visited set per subreddit to avoid reprocessing the same post
- Leaves the original crawler code untouched

Failure handling:
- Each combo runs independently. If a combo fails, the batch continues to the next one and records the failure in `<subreddit>/batch_metadata.json`.

Customize combinations:

```bash
# Only specific combinations
python batch_crawl_reddit.py --config config.yaml --combos new top:month top:all

# Per-run limits are read from config: set `crawling.post_limit` in config.yaml
```

Outputs remain organized by the original crawler. Additionally, a persistent visited file per subreddit is kept at `reddit_dump/orchestrator_visited/<subreddit>_visited_posts.txt` to coordinate de-duplication across batch runs.
 
### Batch Output Structure

When using `batch_crawl_reddit.py`, outputs are grouped per subreddit:

```
reddit_dump/
├── AskReddit/
│   ├── config_used.yaml
│   ├── visited_posts.txt           # cumulative across all combos
│   ├── batch_metadata.json         # summary for all runs/combos
│   └── runs/
│       ├── combined/
│       │   └── comments.jsonl      # aggregated across all runs (deduped by comment_id)
│       ├── run_20250821_230523_397a4ebc_greece_new/
│       │   ├── comments.jsonl
│       │   ├── comments.parquet
│       │   ├── visited_posts.txt   # run-local; merged into subreddit-level visited
│       │   ├── crawler.log
│       │   └── metadata.json
│       └── run_...
└── athens/
    └── ...
```

The `runs/combined/comments.jsonl` aggregates all per-run `comments.jsonl` files for the subreddit and removes duplicates based on `comment_id`. A summary of the combination (total read and unique written) is recorded in `<subreddit>/batch_metadata.json`.

## Configuration

The crawler uses a YAML configuration file (`config.yaml`) for all settings. Here's a detailed breakdown of all configuration options:

### Subreddits Configuration
```yaml
subreddits:
  - "AskReddit"
  - "news"
  - "worldnews"
  - "technology"
```
- **Purpose**: List of subreddits to crawl
- **Format**: Array of subreddit names (without "r/" prefix)
- **Example**: `["AskReddit", "news"]` will crawl r/AskReddit and r/news

### Crawling Parameters
```yaml
crawling:
  listing: "new"          # Options: "new", "top", "hot", "rising"
  timefilter: "all"       # For top listing: "day", "week", "month", "year", "all"
  post_limit: null        # Number of posts to crawl per subreddit (null for unlimited)
  post_sleep: 0.4         # Delay between posts to avoid rate limiting
```

#### Detailed Options:
- **`listing`**: Determines how posts are sorted
  - `"new"`: Most recent posts first
  - `"top"`: Highest scoring posts (use with `timefilter`)
  - `"hot"`: Currently trending posts
  - `"rising"`: Posts gaining traction quickly

- **`timefilter`**: Time period for "top" listings
  - `"day"`: Top posts from last 24 hours
  - `"week"`: Top posts from last week
  - `"month"`: Top posts from last month
  - `"year"`: Top posts from last year
  - `"all"`: All-time top posts

- **`post_limit`**: Maximum posts per subreddit
  - `null` or `None`: No limit (crawl all available)
  - Integer: Specific number (e.g., `100` for 100 posts)

- **`post_sleep`**: Rate limiting delay
  - Float value in seconds (e.g., `0.4` = 400ms delay)
  - Prevents hitting Reddit's rate limits
  - Adjust based on your API limits

### Language Filtering
```yaml
language:
  # Target language for filtering (ISO 639-1 code, e.g., "en", "es", "fr", "el" for Greek)
  # Set to null or empty string to disable language filtering
  target_language: "en"  # "el" for Greek, "en" for English, "es" for Spanish, etc.
  
  # Comment-level filtering
  filter_comments_by_language: true
  
  # Post-level filtering  
  require_title_language: false
  require_op_language: false
  
  # Minimum ratio of target language characters in title (for languages with unique scripts)
  # Only used when target_language is set and the language has a unique character set
  title_min_language_ratio: 0.30
```

#### Language Detection Logic:

- **`target_language`**: Target language for filtering
  - Set to any ISO 639-1 language code ("en", "es", "fr", "el", "ru", "zh", etc.)
  - Set to `null` to disable all language filtering
  - Supports all languages recognized by `langdetect`

- **Comment-level filtering** (`filter_comments_by_language`):
  - `true`: Only saves comments detected as the target language
  - `false`: Saves all comments regardless of language

- **Post-level filtering**:
  - **`require_title_language`**: Filters posts based on title language
    - Uses `langdetect` with Unicode character analysis fallback
    - For languages with unique scripts (Greek, Russian, Arabic, Chinese, etc.)
  
  - **`require_op_language`**: Filters based on original post content
    - Combines title and selftext for analysis
    - Useful for text posts with substantial content

- **`title_min_language_ratio`**: Threshold for character-based detection
  - Range: 0.0 to 1.0 (0% to 100%)
  - `0.30` means 30% of alphabetic characters must be in the target language's script
  - Only used for languages with unique character sets (Greek, Russian, Arabic, etc.)
  - Used as fallback when `langdetect` fails

### Output Settings
```yaml
output:
  base_dir: "reddit_dump"  # Base directory for all runs
  buffer_size: 2000        # Write to disk every N comments
```

- **`base_dir`**: Root directory for all crawler outputs
  - Each run creates a subdirectory with timestamp and parameters
  - Example structure: `reddit_dump/run_20241201_143022_a1b2c3d4_AskReddit_new/`

- **`buffer_size`**: Memory management for large crawls
  - Comments are buffered in memory before writing to disk
  - Higher values = fewer disk writes, more memory usage
  - Lower values = more frequent saves, less memory usage

### Reddit API Configuration
```yaml
reddit_api:
  client_id_env: "REDDIT_CLIENT_ID"        # Environment variable for client ID
  client_secret_env: "REDDIT_CLIENT_SECRET" # Environment variable for client secret
  user_agent_env: "REDDIT_USER_AGENT"      # Environment variable for user agent
  request_timeout: 30                       # API request timeout in seconds
```

- **Environment Variable Mapping**: Allows customization of environment variable names
- **`request_timeout`**: Maximum time to wait for API responses
- **Default User Agent**: Used if environment variable is not set
  ```yaml
  default_user_agent: "reddit-crawler:v2.0 (by u/YOURUSER)"
  ```

## Output Structure

Each crawler run creates a unique directory with the following structure:

```
reddit_dump/
├── run_20241201_143022_a1b2c3d4_AskReddit_new/
│   ├── comments.jsonl          # All comments in JSONL format
│   ├── comments.parquet        # All comments in Parquet format
│   ├── visited_posts.txt       # List of processed post IDs
│   ├── crawler.log            # Detailed run logs
│   └── metadata.json          # Run statistics and configuration
└── run_20241201_150815_e5f6g7h8_news_top_week/
    └── ...
```

### File Descriptions:

- **`comments.jsonl`**: Line-delimited JSON with one comment per line
- **`comments.parquet`**: Compressed columnar format, efficient for analysis
- **`visited_posts.txt`**: State file for resuming interrupted crawls
- **`crawler.log`**: Detailed logs with timestamps and run tracking
- **`metadata.json`**: Complete run information including:
  - Start/end times and duration
  - Posts processed and comments collected
  - Exit status (completed/interrupted/error)
  - Configuration snapshot
  - List of all output files

## Data Schema

Each comment record contains the following fields:

### Post-level Information:
- `subreddit`: Subreddit name
- `post_id`: Unique Reddit post ID
- `permalink`: Full URL to the post
- `title`: Post title
- `selftext`: Post content (for text posts)
- `author_post`: Post author username
- `score_post`: Post score (upvotes - downvotes)
- `created_utc_post`: Post creation timestamp (UTC)
- `num_comments_post`: Total comment count
- `over_18`: NSFW flag

### Comment-level Information:
- `comment_id`: Unique comment ID
- `parent_id`: Parent comment or post ID
- `comment_author`: Comment author username
- `comment_body`: Comment text content
- `comment_score`: Comment score
- `created_utc_comment`: Comment creation timestamp (UTC)
- `depth`: Comment nesting level (0 = top-level)

## Usage Examples

### Basic Crawling
```bash
# Use default configuration
python crawl_reddit.py

# Use custom configuration file
python crawl_reddit.py --config my_config.yaml
```

### Configuration Examples

#### Crawl Recent English Posts from Multiple Subreddits:
```yaml
subreddits:
  - "AskReddit"
  - "news"
  - "technology"

crawling:
  listing: "new"
  post_limit: 50
  post_sleep: 0.5

language:
  target_language: "en"
  filter_comments_by_language: true
  require_title_language: true
```

#### Crawl Top Spanish Posts of the Week:
```yaml
subreddits:
  - "spain"
  - "es"

crawling:
  listing: "top"
  timefilter: "week"
  post_limit: 100

language:
  target_language: "es"
  filter_comments_by_language: true
  require_title_language: false
  require_op_language: true
```

#### Collect All Comments (Any Language):
```yaml
subreddits:
  - "AskReddit"
  - "worldnews"

crawling:
  listing: "hot"
  post_limit: 200

language:
  target_language: null  # No language filtering
  filter_comments_by_language: false
  require_title_language: false
  require_op_language: false
```

#### Language-Specific Examples:

**Greek Content:**
```yaml
language:
  target_language: "el"  # Greek
  filter_comments_by_language: true
  require_title_language: true
```

**French Content:**
```yaml
language:
  target_language: "fr"  # French
  filter_comments_by_language: true
  require_title_language: false
```

**Chinese Content:**
```yaml
language:
  target_language: "zh"  # Chinese
  filter_comments_by_language: true
  title_min_language_ratio: 0.50  # Higher threshold for character-based detection
```

## Advanced Features

### Resumable Crawling
The crawler automatically tracks visited posts in `visited_posts.txt`. If interrupted, it will skip already processed posts when restarted with the same configuration.

### Signal Handling
Gracefully handles Ctrl+C interruption:
- Completes processing of current post
- Saves all buffered data
- Updates metadata with "interrupted" status

### Retry Logic
Automatic retry for API failures with exponential backoff:
- Up to 5 attempts for comment expansion
- Configurable delays between retries
- Detailed error logging

### Memory Management
Intelligent buffering system:
- Processes comments in configurable batches
- Periodic disk writes to prevent memory overflow
- Efficient handling of large subreddits

## Monitoring and Debugging

### Log Levels
- **INFO**: General progress and statistics
- **DEBUG**: Detailed processing information
- **WARNING**: Non-fatal issues (e.g., failed comment expansion)
- **ERROR**: Fatal errors that stop the crawler

### Progress Tracking
- Real-time progress bars for each subreddit
- Periodic statistics in logs
- Final summary with total counts

### Troubleshooting

**Common Issues:**

1. **API Rate Limits**: Increase `post_sleep` value
2. **Memory Issues**: Decrease `buffer_size` value  
3. **Language Detection**: Adjust `title_min_language_ratio` or change `target_language`
4. **Missing Comments**: Check API credentials and subreddit accessibility
5. **No Language Filtering**: Set `target_language: null` to disable all language filters

## Dependencies

- **praw**: Reddit API wrapper
- **pandas**: Data manipulation and Parquet support
- **pyarrow**: Parquet file format support
- **tqdm**: Progress bars
- **tenacity**: Retry logic
- **langdetect**: Language detection
- **PyYAML**: Configuration file parsing

## License

[Add your license information here]

## Contributing

[Add contributing guidelines here]

## Support

[Add support information here]
