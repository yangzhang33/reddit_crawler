# Reddit Greek Content Crawler

A sophisticated Python crawler for collecting Greek content from Reddit using the official Reddit API. The crawler is designed to systematically collect posts and comments from Greek subreddits, with advanced language detection and filtering capabilities.

## Features

- **🎯 Targeted Language Detection**: Advanced Greek language detection using both `langdetect` library and Unicode character analysis
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
   python crawl_reddit_greek.py
   ```
3. **Find your results** in the `reddit_greek_dump/run_YYYYMMDD_HHMMSS_<uuid>/` directory

## Configuration

The crawler uses a YAML configuration file (`config.yaml`) for all settings. Here's a detailed breakdown of all configuration options:

### Subreddits Configuration
```yaml
subreddits:
  - "greece"
  - "athens"
  - "thessaloniki"
  - "cyprus"
```
- **Purpose**: List of subreddits to crawl
- **Format**: Array of subreddit names (without "r/" prefix)
- **Example**: `["greece", "athens"]` will crawl r/greece and r/athens

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
  filter_greek_comments: true    # Only keep Greek comments
  require_greek_title: false     # Require Greek text in post titles
  require_greek_op: false        # Require Greek text in original post content
  title_min_greek_ratio: 0.30    # Minimum ratio of Greek characters for titles
```

#### Language Detection Logic:
- **Comment-level filtering** (`filter_greek_comments`):
  - `true`: Only saves comments detected as Greek by `langdetect`
  - `false`: Saves all comments regardless of language

- **Post-level filtering**:
  - **`require_greek_title`**: Filters posts based on title language
    - Uses both `langdetect` and Greek character ratio
    - Falls back to Unicode analysis if `langdetect` fails
  
  - **`require_greek_op`**: Filters based on original post content
    - Combines title and selftext for analysis
    - Useful for text posts with substantial content

- **`title_min_greek_ratio`**: Threshold for Greek character detection
  - Range: 0.0 to 1.0 (0% to 100%)
  - `0.30` means 30% of alphabetic characters must be Greek
  - Used as fallback when `langdetect` fails

### Output Settings
```yaml
output:
  base_dir: "reddit_greek_dump"  # Base directory for all runs
  buffer_size: 2000              # Write to disk every N comments
```

- **`base_dir`**: Root directory for all crawler outputs
  - Each run creates a subdirectory with timestamp and parameters
  - Example structure: `reddit_greek_dump/run_20241201_143022_a1b2c3d4_greece_new/`

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
  default_user_agent: "greek-subreddits-miner:v2.0 (by u/YOURUSER)"
  ```

## Output Structure

Each crawler run creates a unique directory with the following structure:

```
reddit_greek_dump/
├── run_20241201_143022_a1b2c3d4_greece_new/
│   ├── comments.jsonl          # All comments in JSONL format
│   ├── comments.parquet        # All comments in Parquet format
│   ├── visited_posts.txt       # List of processed post IDs
│   ├── crawler.log            # Detailed run logs
│   └── metadata.json          # Run statistics and configuration
└── run_20241201_150815_e5f6g7h8_athens_top_week/
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
python crawl_reddit_greek.py

# Use custom configuration file
python crawl_reddit_greek.py --config my_config.yaml
```

### Configuration Examples

#### Crawl Recent Posts from Multiple Subreddits:
```yaml
subreddits:
  - "greece"
  - "athens"
  - "thessaloniki"

crawling:
  listing: "new"
  post_limit: 50
  post_sleep: 0.5

language:
  filter_greek_comments: true
  require_greek_title: true
```

#### Crawl Top Posts of the Week:
```yaml
subreddits:
  - "greece"

crawling:
  listing: "top"
  timefilter: "week"
  post_limit: 100

language:
  filter_greek_comments: true
  require_greek_title: false
  require_greek_op: true
```

#### Collect All Comments (Any Language):
```yaml
subreddits:
  - "greece"

crawling:
  listing: "hot"
  post_limit: 200

language:
  filter_greek_comments: false
  require_greek_title: false
  require_greek_op: false
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
3. **Language Detection**: Adjust `title_min_greek_ratio`
4. **Missing Comments**: Check API credentials and subreddit accessibility

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
