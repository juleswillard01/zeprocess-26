# ICP Scoring & Lead Qualification Strategy

**Document**: Ideal Customer Profile Definition & Semantic Matching
**Status**: Production Configuration Template
**Updated**: 14 mars 2026

---

## TABLE OF CONTENTS

1. [ICP Definition Framework](#icp-definition-framework)
2. [Scoring Engine Logic](#scoring-engine-logic)
3. [Semantic Matching Examples](#semantic-matching-examples)
4. [A/B Testing Strategies](#ab-testing-strategies)
5. [Configuration Files](#configuration-files)

---

## ICP DEFINITION FRAMEWORK

### What is an ICP?

An **Ideal Customer Profile** is a detailed description of the perfect customer for your product. It includes:
- **Demographics**: Role, company size, industry
- **Firmographics**: Revenue, growth rate, funding
- **Behavioral**: Pain points, buying patterns, technology adoption
- **Psychographics**: Values, ambitions, risk tolerance

### MEGA QUIXAI Use Case: SaaS B2B Seduction & Sales

Since MEGA QUIXAI focuses on **B2B business automation** (agents for outreach, sales, etc.), the ICP would target:

#### Persona: Growth-Minded Founder/CEO

```yaml
ICP_PROFILE:
  role:
    - CEO / Founder
    - VP Sales
    - Marketing Director (for high-growth SaaS)
    - Operations Manager (enterprise looking to automate)

  company_characteristics:
    industry:
      - SaaS
      - EdTech
      - E-commerce
      - B2B Services
    company_size:
      min_employees: 10
      max_employees: 500
    revenue:
      min_annual: €250k
      max_annual: €50M

  pain_points:
    - "Manual outreach is killing our sales efficiency"
    - "Can't scale customer acquisition without hiring"
    - "Need to personalize at scale"
    - "Too much time on admin tasks"
    - "Struggling with sales conversion"

  buying_signals:
    - Active on LinkedIn / Twitter (looking for solutions)
    - Shares content about sales automation
    - Comments on discussions about lead gen
    - Follows influencers in growth/sales space
    - Mentions frustration about manual processes

  technology_adoption:
    - Uses CRM (Salesforce, HubSpot, Pipedrive)
    - Active in startup ecosystem (AngelList, ProductHunt)
    - Early adopter (has tried multiple tools)
    - Technical enough to integrate APIs

  budget_authority:
    - Budget: €1k-50k/month for tools
    - Decision maker or strong influencer
    - ROI-focused (wants to see conversion metrics)

  engagement_profile:
    - Active: posts/comments at least 2-3x per week
    - Thoughtful content: not just memes, substantive takes
    - Network size: 500+ connections (credibility signal)
    - Response rate: likely to reply to relevant messages
```

---

## SCORING ENGINE LOGIC

### 3-Tier Scoring System

```
┌──────────────────────────────────────────────┐
│   ICP Score Calculation (0.0 - 1.0)          │
├──────────────────────────────────────────────┤
│                                              │
│  1. Primary Signals (40% weight)            │
│     ├─ Role match (+0.25)                   │
│     ├─ Company size match (+0.15)           │
│     └─ Pain point relevance (+0.10)         │
│                                              │
│  2. Behavioral Signals (35% weight)         │
│     ├─ Engagement level (+0.15)             │
│     ├─ Content sentiment (+0.10)            │
│     ├─ Network quality (+0.10)              │
│                                              │
│  3. Contextual Signals (25% weight)         │
│     ├─ Recent activity (+0.10)              │
│     ├─ Industry relevance (+0.10)           │
│     └─ Language/geography match (+0.05)     │
│                                              │
│  Final Score = (P*0.40) + (B*0.35) + (C*0.25) │
│                                              │
└──────────────────────────────────────────────┘
```

### Tier 1: Primary Signals (40% weight)

#### 1.1 Role Match

```python
ROLE_SIGNALS = {
    'founder': {
        'weight': 1.0,
        'keywords': [
            'founder', 'ceo', 'co-founder',
            'building', 'startup', 'entrepreneur',
            'établi mon business', 'mon startup'
        ],
        'platforms': ['linkedin', 'twitter', 'producthunt']
    },
    'vp_sales': {
        'weight': 0.85,
        'keywords': [
            'vp sales', 'head of sales', 'sales director',
            'sales ops', 'head of growth',
            'directeur commercial', 'chef ventes'
        ],
    },
    'marketing_director': {
        'weight': 0.7,
        'keywords': [
            'marketing director', 'vp marketing', 'head of marketing',
            'growth manager', 'demand generation',
            'directeur marketing', 'growth hacking'
        ],
    },
    'operations': {
        'weight': 0.6,
        'keywords': [
            'operations manager', 'ops director',
            'process automation', 'business analyst',
            'responsable opérations'
        ],
    }
}

def score_role_match(profile_bio: str, profile_posts: List[str]) -> float:
    """Score how well profile matches target roles"""
    content = f"{profile_bio} {' '.join(profile_posts)}"
    content_lower = content.lower()

    role_score = 0.0
    max_weight = 0.0

    for role, config in ROLE_SIGNALS.items():
        for keyword in config['keywords']:
            if keyword in content_lower:
                role_score += config['weight']
                max_weight = max(max_weight, config['weight'])

    # Normalize: perfect score = 1.0
    return min(role_score / (max_weight or 1.0), 1.0) if max_weight else 0.0
```

#### 1.2 Company Size Match

```python
def extract_company_size_signals(profile_bio: str) -> Optional[int]:
    """
    Infer company size from bio.
    Return estimated headcount.
    """
    import re

    bio_lower = profile_bio.lower()

    # Pattern 1: Explicit mention
    match = re.search(r'(\d+)\+?\s*(people|employees|équipe|team)', bio_lower)
    if match:
        return int(match.group(1))

    # Pattern 2: Size indicators
    size_indicators = {
        'startup': 5,
        'small team': 3,
        '10-person': 10,
        'bootstrapped': 5,
        'series a': 20,
        'series b': 50,
        'scale-up': 50,
        'scaleup': 50,
        'enterprise': 500,
    }

    for indicator, size in size_indicators.items():
        if indicator in bio_lower:
            return size

    return None

def score_company_size(profile_bio: str) -> float:
    """
    Score company size fit.
    Target: 10-500 employees
    """
    estimated_size = extract_company_size_signals(profile_bio)

    if not estimated_size:
        return 0.5  # Neutral if unknown

    # Linear scoring: perfect at 50 employees
    min_size, target_size, max_size = 10, 50, 500

    if estimated_size < min_size:
        return estimated_size / min_size * 0.3  # Too small
    elif estimated_size > max_size:
        return max(0.2, 1.0 - (estimated_size - max_size) / max_size)
    else:
        # Sweet spot
        if estimated_size < target_size:
            return 0.7 + (estimated_size / target_size) * 0.3
        else:
            return 1.0 - (estimated_size - target_size) / (max_size - target_size) * 0.3

    return min(estimated_size, 1.0)
```

#### 1.3 Pain Point Relevance

```python
PAIN_POINTS = {
    'sales_efficiency': {
        'weight': 1.0,
        'keywords': [
            'sales automation', 'lead generation', 'outreach',
            'conversion rate', 'sales funnel', 'closing deals',
            'prospection', 'qualification', 'pipeline'
        ]
    },
    'scaling_growth': {
        'weight': 0.9,
        'keywords': [
            'scale', 'growth', 'expansion', 'growth hacking',
            'acquisition', 'viral', 'croissance', 'scaling',
            'hypergrowth'
        ]
    },
    'time_management': {
        'weight': 0.7,
        'keywords': [
            'time management', 'automation', 'efficiency',
            'workflow', 'process improvement', 'bottleneck',
            'productivité', 'efficacité'
        ]
    },
    'personalization_at_scale': {
        'weight': 0.8,
        'keywords': [
            'personalization', 'personalized', 'at scale',
            'bulk', 'mass outreach', 'personalisé',
            'tailored'
        ]
    }
}

def score_pain_point_match(profile_bio: str, recent_posts: List[str]) -> float:
    """Score relevance of profile's pain points to our product"""
    content = f"{profile_bio} {' '.join(recent_posts)}".lower()

    pain_score = 0.0
    weights = []

    for pain, config in PAIN_POINTS.items():
        for keyword in config['keywords']:
            if keyword in content:
                pain_score += config['weight']
                weights.append(config['weight'])

    if not weights:
        return 0.0

    # Normalize: average weight of matched pain points
    avg_weight = sum(weights) / len(weights)
    match_count = len(weights)

    # More pain points = stronger signal
    return min(avg_weight * (1.0 + match_count * 0.1), 1.0)
```

### Tier 2: Behavioral Signals (35% weight)

#### 2.1 Engagement Level

```python
def score_engagement_level(profile_data: Dict) -> float:
    """
    Measure how active and engaged the profile is.
    Factors:
    - Posts per week
    - Comments per week
    - Response rate (estimated)
    """

    followers = profile_data.get('followers', 0)
    posts_last_30d = profile_data.get('posts_count', 0)
    comments_last_30d = profile_data.get('comments_count', 0)
    engagement_rate = profile_data.get('engagement_rate', 0.0)

    # Sub-scores
    posting_frequency = min(posts_last_30d / 30, 1.0)  # 1+ post per day = perfect
    comment_activity = min(comments_last_30d / 30, 1.0)  # 1+ comment per day = perfect
    engagement = min(engagement_rate * 10, 1.0)  # Engagement rates typically < 10%

    # Weights: we want people who actively engage
    final_score = (
        posting_frequency * 0.4 +
        comment_activity * 0.35 +
        engagement * 0.25
    )

    return final_score
```

#### 2.2 Content Sentiment & Quality

```python
from textblob import TextBlob

def score_content_sentiment(recent_posts: List[str]) -> float:
    """
    Analyze sentiment of recent posts.
    We want:
    - Positive (not negative/complaining)
    - Thoughtful (not just memes/links)
    - Industry-relevant (not off-topic)
    """

    if not recent_posts:
        return 0.5

    sentiments = []
    for post in recent_posts:
        blob = TextBlob(post)
        sentiment = blob.sentiment.polarity  # -1.0 (negative) to 1.0 (positive)
        sentiments.append(sentiment)

    avg_sentiment = sum(sentiments) / len(sentiments)

    # We want slightly positive or neutral, not negative
    # -0.5 to 0.5 is good range
    if avg_sentiment < -0.5:
        return 0.2  # Too negative
    elif avg_sentiment < 0:
        return 0.5
    elif avg_sentiment < 0.5:
        return 0.8
    else:
        return 0.9  # Very positive
```

#### 2.3 Network Quality

```python
def score_network_quality(profile_data: Dict) -> float:
    """
    Score the quality of someone's network.
    Signals:
    - Follower count (more = better influence)
    - Follower-to-following ratio (selective = better)
    - Verification status (if applicable)
    """

    followers = profile_data.get('followers', 0)
    following = profile_data.get('following', 1)  # Avoid division by zero
    is_verified = profile_data.get('is_verified', False)

    # Follower tier score
    if followers >= 10000:
        follower_score = 1.0
    elif followers >= 5000:
        follower_score = 0.9
    elif followers >= 1000:
        follower_score = 0.8
    elif followers >= 500:
        follower_score = 0.6
    elif followers >= 100:
        follower_score = 0.4
    else:
        follower_score = 0.2

    # Ratio score: 2:1 to 5:1 is healthy
    ratio = followers / following if following > 0 else 0
    if ratio < 1:
        ratio_score = 0.3
    elif ratio < 2:
        ratio_score = 0.6
    elif ratio < 5:
        ratio_score = 0.9
    else:
        ratio_score = 0.7  # Too selective, maybe not engaging

    # Verification boost
    verification_score = 1.0 if is_verified else 0.8

    final_score = (
        follower_score * 0.5 +
        ratio_score * 0.3 +
        verification_score * 0.2
    )

    return min(final_score, 1.0)
```

### Tier 3: Contextual Signals (25% weight)

#### 3.1 Recent Activity

```python
from datetime import datetime, timedelta

def score_recent_activity(profile_data: Dict) -> float:
    """
    Penalize inactive profiles.
    Score based on last post/activity.
    """

    last_activity = profile_data.get('last_activity_date')
    if not last_activity:
        return 0.5  # Unknown

    days_ago = (datetime.now() - last_activity).days

    if days_ago <= 7:
        return 1.0  # Very active
    elif days_ago <= 30:
        return 0.8
    elif days_ago <= 90:
        return 0.5
    elif days_ago <= 180:
        return 0.2
    else:
        return 0.0  # Dormant
```

#### 3.2 Industry Relevance

```python
RELEVANT_INDUSTRIES = [
    'SaaS',
    'B2B',
    'EdTech',
    'E-commerce',
    'Digital Services',
    'Marketing Tech',
    'Sales Tech',
    'Automation',
    'AI/ML',
    'Consulting',
    'Agency'
]

def score_industry_relevance(profile_bio: str, profile_posts: List[str]) -> float:
    """
    Check if profile is in relevant industry.
    """
    content = f"{profile_bio} {' '.join(profile_posts)}".lower()

    relevance_score = 0.0
    for industry in RELEVANT_INDUSTRIES:
        if industry.lower() in content:
            relevance_score = 1.0
            break

    # If no explicit match, check for implicit signals
    if relevance_score == 0.0:
        implicit_signals = [
            'founder', 'ceo', 'startup', 'tech',
            'growth', 'sales', 'innovation'
        ]
        signal_count = sum(1 for s in implicit_signals if s in content)
        relevance_score = min(signal_count / len(implicit_signals), 0.7)

    return relevance_score
```

#### 3.3 Language & Geography

```python
def score_language_geography(profile_data: Dict) -> float:
    """
    Score based on language/geography match.
    Our product: French-speaking market first
    """

    language = profile_data.get('language', 'unknown')
    region = profile_data.get('region', 'unknown')

    language_score = 0.0
    if language in ['fr', 'en']:
        language_score = 1.0
    elif language in ['de', 'es', 'it']:
        language_score = 0.7
    else:
        language_score = 0.3

    # Geography bonus for France/Benelux/Switzerland
    region_score = 0.0
    if region in ['FR', 'BE', 'CH', 'LU']:
        region_score = 1.0
    elif region in ['EU']:
        region_score = 0.7
    else:
        region_score = 0.5

    return language_score * 0.6 + region_score * 0.4
```

---

## COMPLETE SCORING ALGORITHM

### Integration Example

```python
class ICPScorer:
    """
    Complete ICP scoring system.
    Combines all signals into final score.
    """

    async def score_profile(self, profile: LeadData) -> ScoringResult:
        """
        Main scoring function.
        Returns: score (0-1), reasoning, segments
        """

        # Tier 1: Primary Signals (40%)
        role_score = score_role_match(profile.bio, profile.recent_posts)
        size_score = score_company_size(profile.bio)
        pain_score = score_pain_point_match(profile.bio, profile.recent_posts)

        primary_score = (
            role_score * 0.25 +
            size_score * 0.15 +
            pain_score * 0.10
        )

        # Tier 2: Behavioral Signals (35%)
        engagement_score = score_engagement_level(profile.metadata)
        sentiment_score = score_content_sentiment(profile.recent_posts)
        network_score = score_network_quality(profile.metadata)

        behavioral_score = (
            engagement_score * 0.15 +
            sentiment_score * 0.10 +
            network_score * 0.10
        )

        # Tier 3: Contextual Signals (25%)
        activity_score = score_recent_activity(profile.metadata)
        industry_score = score_industry_relevance(profile.bio, profile.recent_posts)
        lang_score = score_language_geography(profile.metadata)

        contextual_score = (
            activity_score * 0.10 +
            industry_score * 0.10 +
            lang_score * 0.05
        )

        # Final score
        final_score = primary_score + behavioral_score + contextual_score

        # Generate reasoning
        reasoning = self._generate_reasoning(
            role_score, size_score, pain_score,
            engagement_score, sentiment_score, network_score,
            activity_score, industry_score, lang_score
        )

        # Identify segments
        segments = self._identify_segments(
            role_score, engagement_score, network_score
        )

        return ScoringResult(
            score=min(final_score, 1.0),
            confidence=self._calculate_confidence(profile),
            reasoning=reasoning,
            segments=segments
        )

    def _identify_segments(self, *scores) -> List[str]:
        """Tag profile with buyer segments"""
        segments = []

        if scores[0] > 0.8:  # Role
            segments.append('decision_maker')
        if scores[4] > 0.7:  # Sentiment
            segments.append('growth_minded')
        if scores[5] > 0.8:  # Network
            segments.append('influencer')
        if scores[2] > 0.7:  # Pain point
            segments.append('pain_point_match')
        if scores[3] > 0.7:  # Engagement
            segments.append('active_user')

        return segments
```

---

## SEMANTIC MATCHING EXAMPLES

### Example 1: Strong Match (Score: 0.82)

**Profile Data:**
```
Name: Marie Dubois
Bio: "CEO at TechScaleup (25 people). Obsessed with growth.
      Using AI to automate sales. 🚀 Investor"
Followers: 2,400
Posts/month: 8
Engagement rate: 4.2%
Recent posts:
1. "Our conversion rate jumped 35% this quarter - automated our outreach 🎯"
2. "If you're still doing manual cold outreach in 2026, you're losing."
3. "Just closed 3 enterprise deals. The difference? Personalization at scale."
```

**Scoring Breakdown:**
```
Primary Signals (40%):
├─ Role: 0.95 (CEO = perfect match)
├─ Company size: 0.90 (25 people = ideal range)
└─ Pain points: 0.92 (growth, automation, sales, conversion)
   → Primary Score: 0.92

Behavioral Signals (35%):
├─ Engagement: 0.85 (8 posts/month, 4.2% engagement)
├─ Sentiment: 0.88 (positive, solution-focused)
└─ Network: 0.78 (2.4k followers, decent ratio)
   → Behavioral Score: 0.83

Contextual Signals (25%):
├─ Recent activity: 0.95 (multiple posts this week)
├─ Industry: 0.95 (tech, startup, AI explicitly mentioned)
└─ Language: 1.0 (French, France-based)
   → Contextual Score: 0.97

FINAL SCORE: (0.92 × 0.40) + (0.83 × 0.35) + (0.97 × 0.25) = 0.894
```

**Recommendation**: 🟢 **HIGH PRIORITY** - Contact immediately with technical/growth angle

---

### Example 2: Moderate Match (Score: 0.58)

**Profile Data:**
```
Name: Alex Martin
Bio: "Marketing enthusiast. Building a content agency.
      Interested in growth tactics."
Followers: 850
Posts/month: 4
Engagement rate: 1.8%
Last activity: 18 days ago
Recent posts: Mix of personal, marketing tips, and retweets
```

**Scoring Breakdown:**
```
Primary Signals (40%):
├─ Role: 0.5 (marketing tangent, not direct sales)
├─ Company size: 0.35 (agency, likely smaller)
└─ Pain points: 0.55 (some growth signals, but vague)
   → Primary Score: 0.47

Behavioral Signals (35%):
├─ Engagement: 0.55 (4 posts/month = moderate)
├─ Sentiment: 0.62 (positive but not deeply engaged)
└─ Network: 0.58 (850 followers, reasonable)
   → Behavioral Score: 0.58

Contextual Signals (25%):
├─ Recent activity: 0.60 (18 days = somewhat active)
├─ Industry: 0.65 (marketing tech tangent)
└─ Language: 0.90 (French, France-based)
   → Contextual Score: 0.72

FINAL SCORE: (0.47 × 0.40) + (0.58 × 0.35) + (0.72 × 0.25) = 0.57
```

**Recommendation**: 🟡 **MONITOR** - Queue for lower-priority outreach, test with 'engaging' variant

---

### Example 3: Poor Match (Score: 0.28)

**Profile Data:**
```
Name: Jean Dupont
Bio: "Photographer. Love nature and travel. 📸"
Followers: 120
Posts/month: 2
Engagement rate: 0.8%
Last activity: 92 days ago
Recent posts: Mostly vacation photos, travel tips
```

**Scoring Breakdown:**
```
Primary Signals (40%):
├─ Role: 0.0 (photographer ≠ CEO/founder)
├─ Company size: 0.15 (solopreneur)
└─ Pain points: 0.05 (no business/growth signals)
   → Primary Score: 0.07

Behavioral Signals (35%):
├─ Engagement: 0.2 (2 posts/month = low)
├─ Sentiment: 0.7 (positive but irrelevant)
└─ Network: 0.3 (120 followers, low influence)
   → Behavioral Score: 0.4

Contextual Signals (25%):
├─ Recent activity: 0.1 (92 days = dormant)
├─ Industry: 0.0 (no business/tech signal)
└─ Language: 0.9 (French-based)
   → Contextual Score: 0.33

FINAL SCORE: (0.07 × 0.40) + (0.4 × 0.35) + (0.33 × 0.25) = 0.23
```

**Recommendation**: 🔴 **DISCARD** - Not a fit, move on

---

## A/B TESTING STRATEGIES

### Variant Selection Logic

The A/B testing uses **Thompson Sampling** (multi-armed bandit) to balance:
- **Exploration**: Try new variants to discover better approaches
- **Exploitation**: Use the best-performing variant for the majority

```python
class ThompsonSamplingStrategy:
    """
    Contextual bandit for variant selection.
    Learns which variant works best per segment.
    """

    def __init__(self):
        # Initialize: Beta(α, β) for each variant
        # Start with uniform prior
        self.variants = {
            'technical': {'alpha': 1, 'beta': 1},
            'engaging': {'alpha': 1, 'beta': 1},
            'casual': {'alpha': 1, 'beta': 1}
        }

    def select_variant_for_segment(self, segment: str, icp_score: float) -> str:
        """
        Select variant for a lead based on:
        1. Segment (e.g., 'influencer', 'decision_maker')
        2. ICP score (confidence level)
        3. Historical performance
        """

        # Sample from Beta distribution for each variant
        samples = {}
        for variant, params in self.variants.items():
            sample = numpy.random.beta(params['alpha'], params['beta'])
            samples[variant] = sample

        # Add exploration bonus for low-confidence leads
        if icp_score < 0.5:
            # More exploration: add noise
            for variant in samples:
                samples[variant] *= 1.2  # 20% boost to exploration

        # Select highest sampled value
        selected = max(samples, key=samples.get)
        return selected

    def update_with_result(self, variant: str, result: bool):
        """Update posterior after observing result"""
        if result:
            self.variants[variant]['alpha'] += 1
        else:
            self.variants[variant]['beta'] += 1

        # Log for analysis
        logger.info(f"Updated {variant}: α={self.variants[variant]['alpha']}, β={self.variants[variant]['beta']}")
```

### Variant Performance Example (7-day window)

```
TECHNICAL variant:
├─ Follows initiated: 145
├─ Follow-through (liked/commented): 62 (42%)
├─ DM sent: 15
├─ DM replies: 4 (27%)
└─ Posterior: Beta(5, 8)  [converged to ~38% success]

ENGAGING variant:
├─ Follows initiated: 128
├─ Follow-through: 48 (38%)
├─ DM sent: 12
├─ DM replies: 3 (25%)
└─ Posterior: Beta(4, 6)  [converged to ~40% success]

CASUAL variant:
├─ Follows initiated: 97
├─ Follow-through: 22 (23%)
├─ DM sent: 8
├─ DM replies: 0 (0%)
└─ Posterior: Beta(2, 8)  [converged to ~20% success]

RECOMMENDATION:
- Allocate 50% to 'engaging' (best performer so far)
- Allocate 40% to 'technical' (stable second place)
- Allocate 10% to 'casual' (exploration only, low return)
```

---

## CONFIGURATION FILES

### icp.yaml (Product Configuration)

```yaml
# ICP Definition for MEGA QUIXAI
# Product: Autonomous AI agents for business (lead gen, sales, conversion)

product:
  name: "MEGA QUIXAI"
  category: "B2B SaaS - Business Automation"
  target_market: "European SaaS/High-Growth"
  languages:
    - "French"
    - "English"

ideal_customer_profile:

  primary_personas:

    - name: "Growth-Minded Founder"
      weight: 0.45
      roles: ["CEO", "Founder", "Co-founder"]
      industries: ["SaaS", "EdTech", "E-commerce", "Digital Services"]
      company_size:
        min: 10
        max: 500
      revenue_range:
        min: "€250k"
        max: "€50M"
      pain_points:
        - "Manual sales outreach is unscalable"
        - "Can't personalize at scale"
        - "Sales team is expensive and slow"
        - "Lead qualification is manual"
        - "Customer acquisition cost is high"
      buying_signals:
        - "Talks about growth, scaling"
        - "Active on LinkedIn/Twitter"
        - "Comments on sales/automation content"
        - "Has CRM but underutilizes it"
        - "Early adopter mindset"
      tech_adoption: "high"
      budget_authority: "direct"
      expected_deal_size: "€5k-50k"

    - name: "VP Sales / Head of Growth"
      weight: 0.35
      roles: ["VP Sales", "Head of Growth", "Sales Director", "Growth Manager"]
      industries: ["SaaS", "Digital Services", "B2B"]
      company_size:
        min: 20
        max: 500
      pain_points:
        - "Need to scale sales without hiring"
        - "Sales reps waste time on admin"
        - "Lead qualification bottleneck"
        - "Conversion rates are plateauing"
      buying_signals:
        - "Posts about sales metrics, conversion"
        - "Follows sales automation tools"
        - "Comments on founder/growth discussions"
      budget_authority: "influencer"
      expected_deal_size: "€10k-100k"

  secondary_personas:

    - name: "Marketing Director"
      weight: 0.15
      roles: ["Marketing Director", "VP Marketing", "Head of Demand Gen"]
      industries: ["SaaS", "Tech"]
      pain_points:
        - "Demand generation is expensive"
        - "Low conversion from MQL to SQL"
        - "Lead nurturing is manual"
      buying_signals:
        - "Discusses marketing automation"
        - "Active in growth/marketing communities"

    - name: "Operations Manager"
      weight: 0.05
      roles: ["Operations Manager", "Process Automation Lead"]
      industries: ["Any B2B"]
      pain_points:
        - "Too many manual business processes"
        - "Need to improve efficiency"

scoring_weights:
  primary_signals: 0.40
  behavioral_signals: 0.35
  contextual_signals: 0.25

thresholds:
  discard: 0.40
  monitor: 0.40
  contact: 0.60
  priority: 0.80

keywords:
  pain_point_matched:
    - "sales automation"
    - "lead generation"
    - "scaling"
    - "conversion"
    - "personalization"
    - "outreach"
  industry_matched:
    - "SaaS"
    - "B2B"
    - "EdTech"
    - "startup"
    - "tech"
  negative_signals:
    - "not hiring"
    - "closed"
    - "acquired"
    - "shutting down"
    - "bankrupt"
```

### scoring_config.json

```json
{
  "scoring_engine": {
    "model": "claude-3-5-sonnet-20241022",
    "temperature": 0.2,
    "max_tokens": 500,
    "system_prompt_template": "templates/icp_scoring_prompt.txt"
  },
  "tiers": {
    "primary_signals": {
      "weight": 0.40,
      "components": {
        "role_match": 0.25,
        "company_size": 0.15,
        "pain_point": 0.10
      }
    },
    "behavioral_signals": {
      "weight": 0.35,
      "components": {
        "engagement": 0.15,
        "sentiment": 0.10,
        "network": 0.10
      }
    },
    "contextual_signals": {
      "weight": 0.25,
      "components": {
        "activity": 0.10,
        "industry": 0.10,
        "language": 0.05
      }
    }
  },
  "thresholds": {
    "discard": {
      "min_score": 0.0,
      "max_score": 0.40,
      "action": "discard"
    },
    "monitor": {
      "min_score": 0.40,
      "max_score": 0.60,
      "action": "queue_low_priority"
    },
    "contact": {
      "min_score": 0.60,
      "max_score": 0.80,
      "action": "standard_outreach"
    },
    "priority": {
      "min_score": 0.80,
      "max_score": 1.0,
      "action": "aggressive_outreach"
    }
  },
  "ab_testing": {
    "algorithm": "thompson_sampling",
    "variants": [
      {
        "name": "technical",
        "description": "Technical angle, solution-focused",
        "initial_alpha": 1,
        "initial_beta": 1
      },
      {
        "name": "engaging",
        "description": "Relationship-first, warm tone",
        "initial_alpha": 1,
        "initial_beta": 1
      },
      {
        "name": "casual",
        "description": "Informal, peer-to-peer",
        "initial_alpha": 1,
        "initial_beta": 1
      }
    ],
    "exploration_bonus_low_confidence": 1.2
  }
}
```

---

**End of ICP Scoring & Lead Qualification Strategy**
