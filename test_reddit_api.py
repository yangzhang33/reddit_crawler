import os
import praw

# Load credentials from environment
CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
USER_AGENT = os.getenv("REDDIT_USER_AGENT")

if not all([CLIENT_ID, CLIENT_SECRET, USER_AGENT]):
    raise ValueError("Please set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT as environment variables.")

# Initialize Reddit API
reddit = praw.Reddit(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    user_agent=USER_AGENT
)

# Test: fetch top 5 posts from r/greece
print("Testing Reddit API connection...\n")
subreddit = reddit.subreddit("greece")

for i, submission in enumerate(subreddit.hot(limit=5), start=1):
    print(f"{i}. {submission.title}  (score: {submission.score})")
print("\n✅ API connection successful!")
