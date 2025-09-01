# Changelog

All notable changes to the Greek Reddit Content Crawler will be documented in this file.
## [2.1.0] - 2025-08-21

### Added
- Batch orchestrator `batch_crawl_reddit.py` to maximize post coverage per subreddit
  - Runs the existing crawler across multiple listing/timefilter combinations
  - De-duplicates posts per subreddit via a shared visited set
  - Organizes outputs under `output.base_dir/<subreddit>/`, including:
    - `config_used.yaml`, `visited_posts.txt`, `batch_metadata.json`, and per-run folders in `runs/`
  - Keeps subreddits separate and leaves the core crawler code unchanged
  - Supports custom combinations via `--combos`; post limits are read from config
  - Adds `runs/combined/comments.jsonl` per subreddit, deduplicated by `comment_id`
  - Extends default batch combos to include: `new`, `hot`, `rising`, `best`, `top:{hour,day,week,month,year,all}`, `controversial:{hour,day,week,month,year,all}`
  - Continues to next combo on failure and records per-combo status in `batch_metadata.json`


The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2024-12-01

### Added
- **Configuration Management**: Complete YAML-based configuration system
  - Externalized all user settings to `config.yaml`
  - Support for custom configuration file paths via `--config` argument
  - Dot-notation configuration access (e.g., `crawling.listing`)
  
- **Run Management System**: Unique run tracking and organization
  - Auto-generated run IDs using timestamp + UUID format (`YYYYMMDD_HHMMSS_uuid8`)
  - Run-specific folder structure: `reddit_greek_dump/run_<run_id>/`
  - Isolated outputs per run for better organization and analysis
  
- **Comprehensive Metadata Tracking**: Detailed run statistics and configuration snapshots
  - `metadata.json` file in each run folder containing:
    - Run timing (start/end time, duration)
    - Statistics (posts processed, comments collected)
    - Exit status tracking (completed/interrupted/error)
    - Complete configuration snapshot for reproducibility
    - List of all files written during the run
  
- **Structured Logging System**: Professional logging with run tracking
  - Run-specific logger instances with unique identifiers
  - Dual output: console (with run ID prefix) and file logging
  - Detailed log files saved in each run folder (`crawler.log`)
  - Appropriate log levels (INFO, DEBUG, WARNING, ERROR)
  - Timestamp formatting and structured log messages
  
- **Object-Oriented Architecture**: Modular and maintainable code structure
  - `RedditCrawlerConfig` class for configuration management
  - `RunMetadata` class for run statistics and metadata
  - `GreekRedditCrawler` main class with clean separation of concerns
  - Better error handling and resource management
  
- **Enhanced Command-Line Interface**:
  - Argument parser for configuration file specification
  - Better help text and usage information

### Changed
- **Complete Code Restructure**: Migrated from script-based to class-based architecture
  - All global variables moved to configuration management
  - Functions reorganized into logical class methods
  - Improved code maintainability and testability
  
- **Configuration System**: All hardcoded values externalized
  - Subreddit lists now configurable via YAML
  - Crawling parameters (listing, timefilter, limits) configurable
  - Language filtering options configurable
  - Output settings configurable
  - API settings configurable with environment variable mapping
  
- **Output Organization**: New file structure for better run management
  - Outputs now organized by run in separate folders
  - State files (visited_posts.txt) are run-specific
  - Logs are isolated per run for easier debugging
  - Metadata provides complete run context
  
- **Logging Improvements**: Enhanced from basic print statements
  - Structured logging with proper levels
  - Run ID tracking in all log messages
  - File and console logging with different formatters
  - Progress tracking with meaningful log messages
  
- **Error Handling**: More robust error management
  - Better exception handling with proper logging
  - Graceful shutdown improvements
  - Resource cleanup in finally blocks
  - Metadata tracking of exit conditions

### Improved
- **Language Detection**: Enhanced Greek language detection logic
  - Maintained existing langdetect + Unicode fallback approach
  - Configurable thresholds for language detection
  - Better separation of post-level vs comment-level detection
  
- **Performance**: Optimized buffer management and I/O operations
  - Configurable buffer sizes
  - Efficient batch processing
  - Better memory management with proper cleanup
  
- **Rate Limiting**: Enhanced API respectfulness
  - Configurable sleep intervals
  - Better retry logic with tenacity decorators
  - Improved error handling for rate limit scenarios
  
- **Resumability**: Enhanced state management
  - Run-specific state tracking
  - Better handling of interrupted runs
  - Clear separation of run states

### Technical Details
- **Dependencies Added**:
  - `pyyaml`: For YAML configuration file parsing
  - Enhanced use of existing dependencies (pandas, tqdm, tenacity)
  
- **File Structure Changes**:
  ```
  Before:
  reddit_greek_dump/
  ├── comments.jsonl
  ├── comments.parquet
  └── visited_posts.txt
  
  After:
  reddit_greek_dump/
  ├── run_20241201_143022_a1b2c3d4/
  │   ├── comments.jsonl
  │   ├── comments.parquet
  │   ├── visited_posts.txt
  │   ├── crawler.log
  │   └── metadata.json
  └── run_20241201_150815_e5f6g7h8/
      └── ...
  ```
  
- **Configuration Migration**:
  - All constants moved from script to `config.yaml`
  - Environment variable handling centralized
  - Default values provided for all configuration options

### Breaking Changes
- **Configuration Required**: Script now requires `config.yaml` file
- **Output Structure**: New folder structure breaks compatibility with v1.x output parsing
- **Command Line**: New argument structure (though backward compatible for basic usage)
- **Dependencies**: New required dependency on `pyyaml`

### Migration Guide from v1.x
1. **Install new dependency**: `pip install pyyaml`
2. **Create configuration file**: Use provided `config.yaml` template
3. **Update scripts**: Any scripts parsing output files need to account for new folder structure
4. **Environment variables**: No changes needed for Reddit API credentials

## [1.0.0] - 2024-11-XX (Previous Version)

### Features (Original Implementation)
- Basic Reddit API crawling for Greek subreddits
- Language detection using langdetect + Unicode fallbacks
- JSONL and Parquet output formats
- Basic resumability with visited posts tracking
- Comment tree expansion with retry logic
- Configurable post and comment level filtering
- Rate limiting with sleep intervals
- Signal handling for graceful shutdown

### Limitations (Addressed in v2.0.0)
- Hardcoded configuration values
- Single output directory structure
- Basic print-based logging
- No run tracking or metadata
- Monolithic script structure
- Limited error handling and recovery
