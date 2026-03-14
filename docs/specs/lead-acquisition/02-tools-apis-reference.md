# Tools & APIs Reference : Agent LEAD ACQUISITION

**Document**: Tools and External Services Integration
**Status**: Production Reference
**Updated**: 14 mars 2026

---

## TABLE OF CONTENTS

1. [Source APIs](#source-apis)
2. [LLM Integration (Claude)](#llm-integration-claude)
3. [Database & Cache](#database--cache)
4. [Async Queue (Celery)](#async-queue-celery)
5. [Proxy & Selenium](#proxy--selenium)
6. [Compliance Tools](#compliance-tools)
7. [Observability Stack](#observability-stack)
8. [Rate Limits & Quotas](#rate-limits--quotas)

---

## SOURCE APIs

### 1. YouTube Data API v3

#### Authentication

```python
from google.oauth2 import service_account
from googleapiclient.discovery import build

SERVICE_ACCOUNT_FILE = '/secrets/youtube-sa-key.json'

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=['https://www.googleapis.com/auth/youtube.readonly']
)

youtube = build('youtube', 'v3', credentials=credentials)
```

#### Key Endpoints

**1. Search Videos by Channel**
```python
async def get_channel_videos(channel_id: str, max_results: int = 20) -> List[str]:
    """Get latest video IDs from a channel"""
    request = youtube.search().list(
        part='id',
        channelId=channel_id,
        order='date',
        maxResults=max_results,
        type='video'
    )
    response = await asyncio.to_thread(request.execute)
    return [item['id']['videoId'] for item in response['items']]
```

**2. Get Comments on Video**
```python
async def get_video_comments(video_id: str, max_results: int = 100) -> List[Dict]:
    """Extract commenters and comment text"""
    request = youtube.commentThreads().list(
        part='snippet',
        videoId=video_id,
        maxResults=min(max_results, 100),
        order='relevance',
        textFormat='plainText'
    )
    response = await asyncio.to_thread(request.execute)

    comments = []
    for thread in response.get('items', []):
        snippet = thread['snippet']['topLevelComment']['snippet']
        comments.append({
            'author': snippet['authorDisplayName'],
            'author_channel_url': snippet.get('authorChannelUrl'),
            'text': snippet['textDisplay'],
            'reply_count': thread['snippet']['totalReplyCount'],
            'like_count': snippet['likeCount']
        })
    return comments
```

**3. Get Channel Info**
```python
async def get_channel_info(channel_id: str) -> Dict:
    """Get channel metadata (bio, subscribers, etc.)"""
    request = youtube.channels().list(
        part='snippet,statistics',
        id=channel_id
    )
    response = await asyncio.to_thread(request.execute)

    if response['items']:
        channel = response['items'][0]
        return {
            'title': channel['snippet']['title'],
            'description': channel['snippet']['description'],
            'subscriber_count': int(channel['statistics'].get('subscriberCount', 0)),
            'video_count': int(channel['statistics'].get('videoCount', 0)),
            'view_count': int(channel['statistics'].get('viewCount', 0))
        }
    return {}
```

#### Quota Accounting

```
YouTube Data API v3 Quota:
- Free tier: 10,000 units/day
- Paid tier: up to 500M units/day

Unit cost per operation:
- search().list() = 100 units
- commentThreads().list() = 1 unit
- channels().list() = 1 unit
- videos().list() = 1 unit

Example daily budget:
- 20 search operations = 2,000 units
- 1,000 comment fetches = 1,000 units
- 100 channel lookups = 100 units
Total: 3,100/10,000 units (safe)
```

#### Error Handling

```python
async def youtube_api_call_with_retry(request, max_retries=3):
    """Exponential backoff retry for YouTube API"""
    for attempt in range(max_retries):
        try:
            response = await asyncio.to_thread(request.execute)
            return response
        except HttpError as e:
            if e.resp.status == 403:  # Quota exceeded
                wait = min(2 ** attempt * 60, 3600)  # up to 1 hour
                await asyncio.sleep(wait)
                continue
            elif e.resp.status == 404:  # Not found
                return None
            else:
                raise
    return None
```

---

### 2. Reddit API (PRAW)

#### Setup

```python
import praw

reddit = praw.Reddit(
    client_id=environ['REDDIT_CLIENT_ID'],
    client_secret=environ['REDDIT_CLIENT_SECRET'],
    user_agent='MegaQuixai/1.0 (by Jules)'
)
```

#### Key Operations

**1. Get Subreddit Comments**
```python
async def scrape_subreddit_comments(subreddit_name: str, limit: int = 100) -> List[Dict]:
    """Get recent comments from a subreddit"""
    subreddit = reddit.subreddit(subreddit_name)
    leads = []

    for submission in subreddit.new(limit=50):
        for comment in submission.comments.list():
            if comment.author and not comment.author.is_suspended:
                leads.append({
                    'source': 'reddit',
                    'username': comment.author.name,
                    'profile_url': f"https://reddit.com/user/{comment.author.name}",
                    'karma': comment.author.link_karma + comment.author.comment_karma,
                    'account_age_days': (datetime.now() - datetime.fromtimestamp(comment.author.created_utc)).days,
                    'comment_text': comment.body[:500],
                    'comment_score': comment.score
                })

    return leads[:limit]
```

**2. Get User Profile**
```python
async def get_reddit_user_profile(username: str) -> Dict:
    """Get detailed user profile"""
    try:
        user = await asyncio.to_thread(reddit.redditor, username)
        return {
            'username': user.name,
            'link_karma': user.link_karma,
            'comment_karma': user.comment_karma,
            'is_gold': user.is_gold,
            'is_mod': user.is_moderator() if hasattr(user, 'is_moderator') else False,
            'created_utc': user.created_utc
        }
    except Exception:
        return None
```

#### Rate Limits

```
PRAW Rate Limits (via Reddit API):
- 60 requests per minute
- Respect via: praw rate limiter (automatic)

No quota system like YouTube.
Strategy: Simple time-based throttling
```

---

### 3. Instagram (Selenium-based)

#### Setup & Dependencies

```bash
# Install dependencies
pip install selenium webdriver-manager playwright

# For headless browser
pip install playwright
python -m playwright install chromium
```

#### Scraper Implementation

```python
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import asyncio
from playwright.async_api import async_playwright

class InstagramScraper:
    def __init__(self, proxy_list: List[str]):
        self.proxy_list = proxy_list
        self.proxy_index = 0

    async def get_hashtag_posts(self, hashtag: str, limit: int = 20) -> List[Dict]:
        """Scrape posts from Instagram hashtag"""
        async with async_playwright() as p:
            proxy = self.proxy_list[self.proxy_index % len(self.proxy_list)]
            self.proxy_index += 1

            browser = await p.chromium.launch(
                proxy={'server': proxy},
                headless=True,
                args=['--disable-blink-features=AutomationControlled']
            )

            page = await browser.new_page()
            await page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })

            url = f"https://www.instagram.com/explore/tags/{hashtag}/"
            await page.goto(url, wait_until='networkidle')

            # Scroll to load posts
            posts = []
            for _ in range(3):  # Scroll 3 times
                await page.keyboard.press('End')
                await asyncio.sleep(2)

            # Extract post URLs
            post_elements = await page.query_selector_all('a[href*="/p/"]')
            for post_elem in post_elements[:limit]:
                href = await post_elem.get_attribute('href')
                if href:
                    posts.append(href)

            await browser.close()
            return posts

    async def get_post_comments(self, post_url: str) -> List[Dict]:
        """Get comments from a specific post"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(f"https://www.instagram.com{post_url}", wait_until='networkidle')
            await asyncio.sleep(2)

            comments = []

            # Extract comment elements
            comment_elements = await page.query_selector_all('[class*="Comment"]')
            for comment in comment_elements[:20]:
                try:
                    author = await comment.query_selector('a[title]')
                    author_name = await author.get_attribute('title') if author else None

                    text = await comment.inner_text()

                    if author_name:
                        comments.append({
                            'author': author_name,
                            'text': text[:200],
                            'profile_url': f"https://instagram.com/{author_name}"
                        })
                except Exception:
                    continue

            await browser.close()
            return comments

    async def get_user_profile(self, username: str) -> Dict:
        """Get user profile data"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(f"https://www.instagram.com/{username}/", wait_until='networkidle')
            await asyncio.sleep(1)

            try:
                # Extract bio
                bio_elem = await page.query_selector('[data-testid="user-profile-bio"]')
                bio = await bio_elem.inner_text() if bio_elem else ""

                # Extract follower count
                follower_text = await page.text_content('[aria-label*="followers"]')

                # Try to parse follower count
                followers = 0
                if follower_text:
                    import re
                    match = re.search(r'([\d,]+)', follower_text)
                    if match:
                        followers = int(match.group(1).replace(',', ''))

                profile = {
                    'username': username,
                    'bio': bio,
                    'followers': followers,
                    'profile_url': f"https://instagram.com/{username}"
                }

                await browser.close()
                return profile

            except Exception as e:
                await browser.close()
                return {}
```

#### Anti-Detection & Delays

```python
class InstagramAntiDetection:
    """Mimic human behavior to avoid Instagram detection"""

    @staticmethod
    async def add_human_delays():
        """Random delays between actions"""
        delay = random.uniform(3, 8)
        await asyncio.sleep(delay)

    @staticmethod
    async def random_scroll(page):
        """Simulate human scrolling"""
        for _ in range(random.randint(2, 5)):
            scroll_amount = random.randint(300, 800)
            await page.evaluate(f'window.scrollBy(0, {scroll_amount})')
            await asyncio.sleep(random.uniform(1, 3))

    @staticmethod
    def get_rotating_proxy() -> str:
        """Get next proxy from pool"""
        proxies = environ['INSTAGRAM_PROXY_LIST'].split(',')
        return random.choice(proxies)
```

#### Legal Limitations

⚠️ **Important Note**:
- Instagram **does not have an official public API** for this use case
- Browser automation is against Instagram's Terms of Service
- Risk: Account ban if detected
- Mitigation: Use only for research/demo, with proper proxies and delays

**Alternative**: Request Instagram's **Business API** for official access (requires business account)

---

### 4. Generic Forum Scraper

```python
class ForumScraper:
    """
    Generic scraper for forums (ProductHunt, HackerNews, etc.)
    Uses official APIs where available, RSS feeds otherwise.
    """

    async def scrape_product_hunt(self, category: str = "tech") -> List[Dict]:
        """ProductHunt API v2"""
        headers = {
            'Authorization': f"Bearer {environ['PRODUCTHUNT_TOKEN']}"
        }

        leads = []
        response = requests.get(
            f"https://api.producthunt.com/v2/posts",
            headers=headers,
            params={'order': 'newest', 'per_page': 50}
        )

        for post in response.json()['data']:
            # Extract maker profile
            maker = post['makers'][0]
            leads.append({
                'source': 'producthunt',
                'username': maker['name'],
                'profile_url': maker['profile_url'],
                'followers': maker.get('followers_count', 0),
                'bio': maker.get('headline', ''),
                'engagement_score': post['votes_count']
            })

        return leads

    async def scrape_hacker_news(self, min_score: int = 100) -> List[Dict]:
        """HackerNews API (no auth required)"""
        leads = []

        # Get top stories
        response = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json")
        story_ids = response.json()[:30]

        for story_id in story_ids:
            story = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json").json()

            if story.get('score', 0) >= min_score:
                # Get submitter
                submitter_id = story.get('by')
                submitter = requests.get(f"https://hacker-news.firebaseio.com/v0/user/{submitter_id}.json").json()

                leads.append({
                    'source': 'hackernews',
                    'username': submitter_id,
                    'profile_url': f"https://news.ycombinator.com/user?id={submitter_id}",
                    'karma': submitter.get('karma', 0),
                    'engagement_score': story['score']
                })

        return leads
```

---

## LLM INTEGRATION (CLAUDE)

### Anthropic API Setup

```python
from anthropic import Anthropic, HUMAN_PROMPT, AI_PROMPT

client = Anthropic(
    api_key=environ['ANTHROPIC_API_KEY'],
    # Optional: organization_id for billing
)
```

### ICP Scoring Endpoint

```python
class ICPScoringAPI:
    """
    Batch scoring with cost tracking
    """

    async def score_batch(self, profiles: List[Dict], icp_definition: str) -> List[Dict]:
        """Score multiple profiles in a single API call"""

        # Construct batch prompt
        profiles_text = "\n\n".join([
            f"Profile {i+1}:\n"
            f"Bio: {p.get('bio', 'N/A')[:300]}\n"
            f"Recent posts: {p.get('raw_content', '')[:500]}"
            for i, p in enumerate(profiles[:10])  # Batch up to 10 per call
        ])

        message = await client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            system=f"""
You are an expert B2B lead qualification analyst.
Score each profile against the ICP definition below.
Return JSON array with scores and reasoning.

ICP Definition:
{icp_definition}

Response format:
[
  {{"profile_index": 0, "score": 0.75, "reasoning": "...", "segments": [...]}},
  ...
]
""",
            messages=[{
                "role": "user",
                "content": f"Score these profiles:\n\n{profiles_text}"
            }]
        )

        # Parse response
        result_text = message.content[0].text
        results = json.loads(result_text)

        # Track cost
        cost = (message.usage.prompt_tokens * 0.003 + message.usage.completion_tokens * 0.015) / 1000
        await db.log_api_cost('claude_scoring', cost, len(profiles))

        return results
```

### Comment Generation Endpoint

```python
async def generate_comment(
    post_content: str,
    user_bio: str,
    variant: str,
    target_language: str = 'fr'
) -> str:
    """
    Generate contextual, authentic comment for a post
    """

    prompts = {
        'technical': f"""
Generate a short, technical comment (1-2 sentences max) in {target_language}.
This is a real comment on a social media post, not promotional.
Add genuine value or ask a thoughtful question.

Post: {post_content[:500]}
Author bio: {user_bio[:200]}

Requirements:
- Authentic, not generic
- Shows deep understanding of the topic
- 1-2 sentences max
- No emojis
- No hashtags
- No mentions of products/services
""",
        'engaging': f"""
Generate a warm, engaging comment (1-2 sentences) in {target_language}.
This should start a real conversation.

Post: {post_content[:500]}
Author bio: {user_bio[:200]}

Requirements:
- Relatable and human
- Ask a specific question based on their post
- 1-2 sentences
- Natural language
""",
        'casual': f"""
Generate a casual, friendly comment (1-2 sentences) in {target_language}.

Post: {post_content[:500]}

Requirements:
- Very informal tone
- Share a quick personal anecdote
- 1-2 sentences max
"""
    }

    response = await client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=100,
        messages=[{
            "role": "user",
            "content": prompts.get(variant, prompts['engaging'])
        }]
    )

    return response.content[0].text.strip()
```

### Bulk DM Draft

```python
async def draft_dm_message(
    lead: LeadData,
    context: str,  # e.g., "warm follow-up after comment"
    language: str = 'fr'
) -> str:
    """
    Draft personalized DM message for lead
    """

    response = await client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": f"""
Draft a personalized DM in {language} for this person.

Their profile:
- Name: {lead.username}
- Bio: {lead.bio[:200]}
- Recent interests: {lead.raw_content[:300]}

Context: {context}

Requirements:
- Personal, not templated
- 2-3 sentences max
- Reference something specific from their content
- Open-ended (asks for response)
- No product pitch
- No requests for anything yet
"""
        }]
    )

    return response.content[0].text.strip()
```

#### Cost Estimation

```
Claude 3.5 Sonnet pricing:
- Input: $0.003 per 1K tokens
- Output: $0.015 per 1K tokens

Average costs per operation:
- ICP scoring (1 profile): $0.001
- Comment generation: $0.0015
- DM draft: $0.002

Daily budget for 150 leads:
- Scoring 150 profiles: $0.15
- Comment generation: $0.30
- DM drafting (subset): $0.10
Total: ~$0.55/day
```

---

## DATABASE & CACHE

### PostgreSQL Connection

```python
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

# Connection string
DATABASE_URL = environ['DATABASE_URL']

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    echo=False,
    poolclass=NullPool,  # For async compatibility
    pool_size=20,
    max_overflow=40,
    pool_recycle=3600
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

async def get_db():
    """Async DB session context manager"""
    async with AsyncSession(engine) as session:
        yield session
```

### Redis Connection

```python
import aioredis

class RedisClient:
    def __init__(self, url: str = environ['REDIS_URL']):
        self.redis = None
        self.url = url

    async def connect(self):
        self.redis = await aioredis.from_url(
            self.url,
            encoding="utf8",
            decode_responses=True,
            max_connections=50
        )

    async def get(self, key: str) -> Optional[str]:
        return await self.redis.get(key)

    async def set(self, key: str, value: str, ttl: int = 3600):
        await self.redis.setex(key, ttl, value)

    async def incr(self, key: str):
        return await self.redis.incr(key)

    async def exists(self, key: str) -> bool:
        return bool(await self.redis.exists(key))

    async def delete(self, key: str):
        await self.redis.delete(key)

    async def hgetall(self, key: str) -> Dict:
        return await self.redis.hgetall(key)

    async def close(self):
        await self.redis.close()
```

### Bulk Operations Example

```python
async def bulk_dedup_check(lead_urls: List[str]) -> Dict[str, bool]:
    """Check multiple leads against dedup cache in O(n)"""
    redis = RedisClient()
    await redis.connect()

    results = {}
    for url in lead_urls:
        results[url] = await redis.exists(f"lead:{url}")

    await redis.close()
    return results
```

---

## ASYNC QUEUE (CELERY)

### Configuration

```python
# celery_config.py

import os
from celery import Celery

app = Celery('lead_acquisition')

app.conf.update(
    broker_url=os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    result_backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1'),
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_time_limit=300,  # 5 minutes hard limit
    task_soft_time_limit=280,  # 4.5 minutes soft limit
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=4,  # Prevent one worker from hogging tasks
    task_autoretry_for=(Exception,),
    task_retry_kwargs={'max_retries': 3, 'countdown': 60},  # Retry once per minute
)
```

### Task Definitions

```python
from celery import shared_task
from celery_config import app
import logging

logger = logging.getLogger(__name__)

# Follow action
@app.task(bind=True, max_retries=3)
async def follow_action(self, lead_id: str, ab_variant: str):
    """Follow a lead's account"""
    try:
        lead = await db.get_lead(lead_id)

        # Check rate limits
        if not await rate_limiter.check_rate_limit('instagram', 'follow'):
            raise self.retry(countdown=300)  # Retry in 5 mins

        # Add realistic delay
        await asyncio.sleep(random.uniform(5, 10))

        # Execute action
        success = await instagram_client.follow(lead.profile_url)

        # Log action
        await db.log_action(
            lead_id=lead_id,
            action_type='follow',
            action_status='success' if success else 'failed',
            ab_variant=ab_variant
        )

        return {'status': 'success', 'lead_id': lead_id}

    except Exception as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60)
        else:
            logger.error(f"Follow action failed for lead {lead_id}: {exc}")
            await db.log_action(
                lead_id=lead_id,
                action_type='follow',
                action_status='failed',
                error_message=str(exc)
            )

# Like action
@app.task(bind=True, max_retries=3)
async def like_action(self, lead_id: str, post_url: str, ab_variant: str):
    """Like a lead's recent post"""
    # Similar structure...
    pass

# Comment action
@app.task(bind=True, max_retries=3)
async def comment_action(self, lead_id: str, post_url: str, comment_text: str, ab_variant: str):
    """Post a comment on lead's post"""
    # Similar structure...
    pass

# DM action
@app.task(bind=True, max_retries=2)
async def dm_action(self, lead_id: str, message_text: str, ab_variant: str):
    """Send DM to lead"""
    # Similar structure...
    pass
```

### Workflow Scheduling

```python
from celery import group, chain, chord

async def schedule_outreach_sequence(lead_id: str, ab_variant: str):
    """
    Schedule full outreach sequence for a lead:
    1. Follow immediately
    2. Like posts after 24 hours
    3. Comment after 48 hours
    4. Send DM after 7 days (if engaged)
    """

    # Define sequence
    workflow = chain(
        # Step 1: Follow
        follow_action.s(lead_id, ab_variant),

        # Step 2: Like (24h later)
        group(
            like_action.s(lead_id, post_url_1, ab_variant),
            like_action.s(lead_id, post_url_2, ab_variant),
        ).apply_async(countdown=86400),  # 1 day

        # Step 3: Comment (48h later)
        comment_action.s(
            lead_id,
            selected_post_url,
            comment_text,
            ab_variant
        ).apply_async(countdown=172800),  # 2 days

        # Step 4: Check engagement then DM (7 days later)
        check_engagement.s(lead_id).apply_async(countdown=604800),  # 7 days
    )

    result = await asyncio.to_thread(workflow.apply_async)
    return result.id
```

---

## PROXY & SELENIUM

### Proxy Rotation

```python
class ProxyManager:
    """Rotate residential proxies to avoid bans"""

    def __init__(self, proxy_list: List[str]):
        self.proxies = proxy_list
        self.current_index = 0
        self.failed_proxies = set()

    def get_next_proxy(self) -> str:
        """Round-robin proxy selection"""
        while True:
            proxy = self.proxies[self.current_index % len(self.proxies)]
            self.current_index += 1

            if proxy not in self.failed_proxies:
                return proxy

            if len(self.failed_proxies) >= len(self.proxies):
                # All proxies failed, reset
                self.failed_proxies.clear()

    def mark_failed(self, proxy: str, duration_hours: int = 1):
        """Temporarily disable a proxy"""
        self.failed_proxies.add(proxy)
        # Reset after duration
        asyncio.create_task(self._reset_proxy(proxy, duration_hours * 3600))

    async def _reset_proxy(self, proxy: str, delay: int):
        await asyncio.sleep(delay)
        self.failed_proxies.discard(proxy)
```

### Selenium Browser Factory

```python
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

class SeleniumFactory:
    """Create browser instances with anti-detection"""

    @staticmethod
    def create_driver(proxy: str = None) -> webdriver.Chrome:
        options = Options()

        # Headless
        options.add_argument('--headless')

        # Anti-detection
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # Proxy
        if proxy:
            options.add_argument(f'--proxy-server={proxy}')

        # User Agent
        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        options.add_argument(f'user-agent={user_agent}')

        # Disable images (faster)
        options.add_argument('--blink-settings=imagesEnabled=false')

        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )

        # Stealth JavaScript injection
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => false})"
        )

        return driver
```

---

## COMPLIANCE TOOLS

### GDPR Deletion Handler

```python
class GDPRCompliance:
    """Handle GDPR Article 17 (Right to be Forgotten)"""

    async def process_deletion_request(self, lead_id: str, reason: str = "user_request"):
        """
        1. Stop all scheduled tasks
        2. Anonymize personal data
        3. Log deletion for audit
        """

        # 1. Cancel pending Celery tasks
        await celery_app.control.revoke(f"lead:{lead_id}", terminate=True)

        # 2. Anonymize in database
        await db.execute("""
            UPDATE leads SET
                username = CONCAT('deleted_', uuid()),
                bio = NULL,
                raw_content = NULL,
                profile_url = NULL
            WHERE id = %s
        """, [lead_id])

        # 3. Log deletion
        await db.log_compliance_action(
            lead_id=lead_id,
            action_type='gdpr_deletion',
            reason=reason,
            region='EU'
        )

        logger.info(f"GDPR deletion processed for lead {lead_id}")

    async def handle_deletion_request_email(self, email: str):
        """Process deletion request via email"""
        leads = await db.find_leads_by_email(email)
        for lead in leads:
            await self.process_deletion_request(lead.id, "gdpr_email_request")

```

### Consent Audit Trail

```python
class ConsentAudit:
    """Track all consent decisions for compliance"""

    async def log_contact_action(
        self,
        lead_id: str,
        action: str,  # 'contact_attempted', 'consent_requested', 'consent_given'
        legal_basis: str,  # 'GDPR Art. 6(1)(f)', etc.
        region: str = 'EU'
    ):
        """Log consent decision"""
        await db.execute("""
            INSERT INTO consent_audit
            (lead_id, action_type, legal_basis, region, created_at)
            VALUES (%s, %s, %s, %s, NOW())
        """, [lead_id, action, legal_basis, region])

    async def generate_compliance_report(self, region: str = 'EU') -> Dict:
        """Generate compliance report for audit"""
        report = await db.query(f"""
            SELECT
                action_type,
                COUNT(*) as count
            FROM consent_audit
            WHERE region = %s AND created_at > NOW() - INTERVAL 30 DAY
            GROUP BY action_type
        """, [region])

        return {
            'region': region,
            'report_date': datetime.now(),
            'actions': dict(report),
            'total_contacts_attempted': report.get('contact_attempted', 0)
        }
```

---

## OBSERVABILITY STACK

### LangFuse Integration

```python
from langfuse import Langfuse
from langfuse.decorators import observe

langfuse_client = Langfuse(
    public_key=environ['LANGFUSE_PUBLIC_KEY'],
    secret_key=environ['LANGFUSE_SECRET_KEY'],
    host="https://cloud.langfuse.com"  # or self-hosted
)

@observe()
async def process_lead_with_trace(lead_id: str):
    """Trace entire lead processing with LangFuse"""

    trace = langfuse_client.trace(
        name="lead_acquisition_full_flow",
        user_id=lead_id,
        tags=["production", "lead_acq"],
    )

    # Span 1: Enrichment
    with trace.span(name="enrich_profile") as span:
        enriched = await enricher.enrich(lead_id)
        span.end(
            output={"bio": enriched.bio[:50], "followers": enriched.followers},
            metadata={"platform": enriched.source_type}
        )

    # Span 2: ICP Scoring
    with trace.span(name="icp_scoring") as span:
        score_result = await icp_scorer.score(enriched)
        span.end(
            output={"score": score_result.score},
            usage={"prompt_tokens": 250, "completion_tokens": 150}
        )

    # Span 3: Outreach
    if score_result.score > 0.40:
        with trace.span(name="queue_outreach") as span:
            task_ids = await queue_outreach(lead_id)
            span.end(output={"task_ids": task_ids})

    return trace.id
```

### Prometheus Metrics

```python
from prometheus_client import Counter, Gauge, Histogram

# Metrics
leads_detected_counter = Counter(
    'leads_detected_total',
    'Total leads detected',
    ['source_type', 'region']
)

leads_qualified_gauge = Gauge(
    'leads_qualified_total',
    'Total qualified leads'
)

icp_score_histogram = Histogram(
    'icp_score_distribution',
    'Distribution of ICP scores',
    buckets=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
)

api_cost_counter = Counter(
    'api_cost_total_usd',
    'Total API costs in USD',
    ['provider']
)

# Usage
async def emit_metrics():
    leads_detected_counter.labels(
        source_type='instagram',
        region='EU'
    ).inc(5)

    icp_score_histogram.observe(0.75)
    api_cost_counter.labels(provider='anthropic').inc(0.15)
```

---

## RATE LIMITS & QUOTAS

### Summary Table

| Service | Limit | Check | Backoff |
|---------|-------|-------|---------|
| **YouTube Data API** | 10M units/day | Daily budget tracker | 1-3600s exponential |
| **Reddit PRAW** | 60 req/min | Built-in rate limiter | Automatic |
| **Instagram** | 200 req/hr | Token bucket (Redis) | 30-3600s |
| **Claude API** | $100/month (free tier) | Cost tracker | Alert only |
| **PostgreSQL** | 20 connections | Connection pooling | Queue |
| **Redis** | 50 concurrent | Max connections setting | Queue |

### Implementation Template

```python
class RateLimitEnforcer:

    LIMITS = {
        'youtube': {'unit_per_day': 10_000_000},
        'reddit': {'req_per_min': 60},
        'instagram': {'actions_per_hour': 200},
        'claude': {'dollars_per_month': 100},
    }

    async def check_and_enforce(self, service: str) -> bool:
        """Check quota, raise if exceeded"""
        limit_config = self.LIMITS[service]

        current = await redis.get(f"quota:{service}")
        max_quota = limit_config[list(limit_config.keys())[0]]

        if current and float(current) >= max_quota:
            await self._alert_quota_exceeded(service)
            return False

        return True
```

---

**End of Tools & APIs Reference**
