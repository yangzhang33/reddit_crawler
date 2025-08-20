# Reddit Greek Content Crawler

A Python script to crawl Greek subreddits via the official Reddit API and extract all comments with advanced language filtering capabilities.

## Features

### Core Functionality
- **Resumable crawling**: Maintains state to avoid reprocessing posts across runs
- **Full comment tree expansion**: Uses `replace_more(limit=None)` to get all nested comments
- **Dual output formats**: Saves data in both JSONL and Parquet formats
- **Language filtering**: Multi-level Greek language detection and filtering
- **Rate limiting**: Built-in delays to respect Reddit API limits
- **Graceful shutdown**: CTRL+C handling with proper state saving

### Language Control
- **Post-level filtering**: Filter posts by Greek title and/or original post content
- **Comment-level filtering**: Keep only Greek comments (configurable)
- **Dual detection methods**: 
  - Primary: `langdetect` library for accurate language detection
  - Fallback: Unicode range analysis for Greek characters (Ω, α, β, etc.)

### Data Collection
- **Comprehensive metadata**: Post details, comment trees, scores, timestamps, authors
- **Batch processing**: Efficient memory usage with configurable buffer sizes
- **Error handling**: Robust retry mechanisms with exponential backoff

## Requirements

### Dependencies
```bash
pip install praw pandas langdetect tqdm tenacity
```

### Required packages:
- `praw` - Reddit API wrapper
- `pandas` - Data manipulation and Parquet export
- `langdetect` - Language detection
- `tqdm` - Progress bars
- `tenacity` - Retry mechanisms

## Setup

### 1. Reddit API Credentials
You need to create a Reddit application to get API credentials:

1. Go to [Reddit App Preferences](https://www.reddit.com/prefs/apps)
2. Click "Create App" or "Create Another App"
3. Choose "script" as the app type
4. Note down your `client_id` and `client_secret`

### 2. Environment Variables
Set your Reddit API credentials as environment variables:

```bash
export REDDIT_CLIENT_ID="your_client_id_here"
export REDDIT_CLIENT_SECRET="your_client_secret_here" 
export REDDIT_USER_AGENT="your-app-name:v1.0 (by u/yourusername)"
```

Or source the provided setup file:
```bash
source setup
```

### 3. Test Connection
Verify your API setup works:
```bash
python test_reddit_api.py
```

## Configuration

### Basic Settings
Edit the configuration section in `crawl_reddit_greek.py`:

```python
# Subreddits to crawl
GREEK_SUBS = [
    "greece",  # Add more: "athens", "thessaloniki", "cyprus", etc.
]

# Crawling parameters
LISTING = "top"          # "new" | "top" | "hot" | "rising"
TIMEFILTER = "all"       # For top(): "day"|"week"|"month"|"year"|"all"
POST_LIMIT = 100         # None = get as many as Reddit returns (~1k max)
```

## Crawling Parameters Explained

### LISTING Parameter
The `LISTING` parameter determines **how Reddit sorts and returns posts**:

#### `"new"` - Chronological Order
- **What it does**: Gets posts sorted by creation time (newest first)
- **Best for**: 
  - Comprehensive data collection over time
  - Custom date range filtering
  - Getting all posts regardless of popularity
- **Characteristics**: 
  - Returns posts in chronological order
  - Includes low-engagement posts
  - Most reliable for complete coverage
- **Example use case**: "Get all posts from the last 6 months"

#### `"top"` - Highest Scoring Posts
- **What it does**: Gets posts with the highest scores (upvotes - downvotes)
- **Best for**: 
  - High-quality, popular content
  - Community highlights and trending topics
  - Analysis of what resonates with users
- **Characteristics**: 
  - Filtered by engagement quality
  - Requires `TIMEFILTER` to specify time period
  - May miss newer posts that haven't gained traction yet
- **Example use case**: "Get the most popular Greek posts from last year"

#### `"hot"` - Currently Trending
- **What it does**: Gets posts that are currently trending (Reddit's algorithm)
- **Best for**: 
  - Real-time popular content
  - Current discussions and trends
  - Recent posts with high engagement velocity
- **Characteristics**: 
  - Dynamic ranking based on recent activity
  - Balances recency with engagement
  - Changes frequently throughout the day
- **Example use case**: "Get what's trending right now in Greek subreddits"

#### `"rising"` - Gaining Momentum
- **What it does**: Gets posts that are quickly gaining upvotes
- **Best for**: 
  - Early trending content
  - Posts about to become popular
  - Catching discussions as they develop
- **Characteristics**: 
  - Identifies posts with increasing engagement
  - Often newer posts with strong early performance
  - Good for finding emerging topics
- **Example use case**: "Catch trending Greek discussions early"

### TIMEFILTER Parameter
The `TIMEFILTER` parameter **only applies to `LISTING = "top"`** and specifies the time window for finding top posts:

#### Available Options:
- **`"hour"`** - Top posts from the last hour
- **`"day"`** - Top posts from the last 24 hours  
- **`"week"`** - Top posts from the last 7 days
- **`"month"`** - Top posts from the last 30 days
- **`"year"`** - Top posts from the last 365 days
- **`"all"`** - Top posts of all time (subreddit's entire history)

#### Important Notes:
- **Ignored for other listings**: `TIMEFILTER` has no effect when `LISTING` is `"new"`, `"hot"`, or `"rising"`
- **Efficiency consideration**: Shorter timefilters (`"day"`, `"week"`) return fewer posts but are more focused
- **Historical data**: Use `"all"` to get the most upvoted posts in subreddit history

### POST_LIMIT Parameter
The `POST_LIMIT` parameter controls **how many posts to process per subreddit**:

#### Numeric Values (e.g., `100`, `500`, `1000`):
- **What it does**: Limits crawling to exactly N posts per subreddit
- **Best for**: 
  - Testing and development
  - Quick samples
  - Rate limit management
  - Focused analysis
- **Memory impact**: Lower limits use less memory and complete faster
- **Example**: `POST_LIMIT = 50` gets exactly 50 posts from each subreddit

#### `None` Value:
- **What it does**: Gets as many posts as Reddit's API will return
- **Best for**: 
  - Comprehensive data collection
  - Research requiring complete datasets
  - Long-running collection jobs
- **Limitations**: 
  - Reddit typically caps at ~1000 posts per API call
  - For `"top"` with `TIMEFILTER = "all"`, may get the top 1000 posts ever
  - For `"new"`, gets ~1000 most recent posts
- **Resource impact**: Uses more memory, takes longer, higher API usage

## Parameter Combination Strategies

### For Complete Historical Data:
```python
LISTING = "new"          # Chronological order
TIMEFILTER = "all"       # Ignored for "new", but keep for clarity
POST_LIMIT = None        # Get everything available
```

### For Popular Content Analysis:
```python
LISTING = "top"          # Highest scoring posts
TIMEFILTER = "year"      # Last 12 months
POST_LIMIT = None        # All top posts in timeframe
```

### For Quick Testing:
```python
LISTING = "hot"          # Current trending
TIMEFILTER = "all"       # Ignored for "hot"
POST_LIMIT = 10          # Just 10 posts for testing
```

### For Current Events Monitoring:
```python
LISTING = "rising"       # Gaining momentum
TIMEFILTER = "all"       # Ignored for "rising"  
POST_LIMIT = 100         # Reasonable sample size
```

### For Specific Time Analysis:
```python
LISTING = "top"          # Quality content
TIMEFILTER = "month"     # Last 30 days only
POST_LIMIT = None        # All top posts from last month
```

### Language Filtering
```python
# Comment-level language filter
LANG_FILTER_GREEK = True   # Keep only comments detected as Greek

# Post-level language gating
REQUIRE_GREEK_TITLE = True     # Require Greek title to process post
REQUIRE_GREEK_OP = False       # Also require Greek in post content
TITLE_MIN_GREEK_RATIO = 0.30   # Fallback Greek character ratio threshold
```

### Performance Tuning
```python
POST_SLEEP = 0.4         # Delay between posts (avoid rate limits)
REQUEST_TIMEOUT = 30     # API request timeout
buffer_size = 2000       # Comments per batch write
```

## Usage

### Basic Crawling
```bash
python crawl_reddit_greek.py
```

### Resume Interrupted Crawling
The script automatically resumes from where it left off using the `visited_posts.txt` state file.

### Stop Gracefully
Press `CTRL+C` to stop after the current post completes processing.

## Output Files

The script creates a `reddit_greek_dump/` directory with:

### Data Files
- **`comments.jsonl`** - Line-delimited JSON format, human-readable
- **`comments.parquet`** - Columnar format, efficient for analysis
- **`visited_posts.txt`** - State file for resumable crawling

### Data Schema
Each comment record contains:

#### Post-level fields:
- `subreddit` - Subreddit name
- `post_id` - Reddit post ID
- `permalink` - Full Reddit URL
- `title` - Post title
- `selftext` - Post content (for text posts)
- `author_post` - Post author username
- `score_post` - Post score/upvotes
- `created_utc_post` - Post creation timestamp
- `num_comments_post` - Total comment count
- `over_18` - NSFW flag

#### Comment-level fields:
- `comment_id` - Unique comment ID
- `parent_id` - Parent comment/post ID
- `comment_author` - Comment author username
- `comment_body` - Comment text content
- `comment_score` - Comment score/upvotes
- `created_utc_comment` - Comment creation timestamp
- `depth` - Nesting level in comment tree

## Language Detection Details

### Detection Methods
1. **Primary**: `langdetect` library
   - Probabilistic detection based on character n-grams
   - Works well for longer texts
   - May struggle with very short comments

2. **Fallback**: Unicode range analysis
   - Counts Greek Unicode characters (U+0370-U+03FF, U+1F00-U+1FFF)
   - Calculates ratio of Greek to total alphabetic characters
   - Reliable for texts with mixed languages

### Language Filtering Levels
1. **Post-level**: Filters entire posts based on title/content
2. **Comment-level**: Individual comment filtering after post selection

## Error Handling

### Robust Retry Logic
- API timeouts: Exponential backoff with 5 retry attempts
- Rate limiting: Built-in delays between requests
- Network issues: Automatic retry with increasing wait times

### Graceful Degradation
- Failed comment expansion: Skip post but continue crawling
- Language detection errors: Fall back to Unicode analysis
- Missing data: Handle deleted posts/comments gracefully

## Performance Considerations

### Memory Usage
- Batch processing with configurable buffer sizes
- Periodic writes to prevent memory buildup
- Efficient data structures for large comment trees

### API Limits
- Respects Reddit's rate limiting
- Configurable delays between requests
- Timeout handling for slow responses

### Storage Efficiency
- Parquet format for analytical workloads
- JSONL for streaming/processing
- Incremental writes to handle interruptions

## Troubleshooting

### Common Issues

#### API Authentication Errors
```
Please set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET env vars.
```
**Solution**: Verify your environment variables are set correctly.

#### Rate Limiting (429 errors)
**Solution**: Increase `POST_SLEEP` value or reduce `POST_LIMIT`.

#### Language Detection Issues
**Solution**: Adjust `TITLE_MIN_GREEK_RATIO` or disable strict filtering temporarily.

#### Memory Issues
**Solution**: Reduce `buffer_size` or `POST_LIMIT` values.

### Debug Mode
Add print statements or reduce limits for testing:
```python
POST_LIMIT = 5  # Test with fewer posts
LANG_FILTER_GREEK = False  # Disable filtering for debugging
```

## Example Usage Scenarios

### 1. Collect All Greek Comments
```python
LANG_FILTER_GREEK = True
REQUIRE_GREEK_TITLE = True
POST_LIMIT = None  # Get everything
```

### 2. Quick Sample Collection
```python
POST_LIMIT = 50
LANG_FILTER_GREEK = False  # Get all comments for analysis
```

### 3. Specific Time Period
```python
LISTING = "top"
TIMEFILTER = "month"  # Last month's top posts
```

## Data Analysis

### Loading Data
```python
import pandas as pd

# Load from Parquet (recommended)
df = pd.read_parquet('reddit_greek_dump/comments.parquet')

# Or from JSONL
df = pd.read_json('reddit_greek_dump/comments.jsonl', lines=True)
```

### Basic Statistics
```python
print(f"Total comments: {len(df)}")
print(f"Unique posts: {df['post_id'].nunique()}")
print(f"Date range: {df['created_utc_comment'].min()} to {df['created_utc_comment'].max()}")
```

## Contributing

Feel free to extend the crawler by:
- Adding more Greek subreddits to `GREEK_SUBS`
- Implementing additional language detection methods
- Adding data export formats
- Improving error handling and logging

## License

This project is for educational and research purposes. Please respect Reddit's API terms of service and rate limits.
