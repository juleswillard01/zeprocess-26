# Agent SEDUCTION: Comprehensive Risk Analysis & Mitigations

**Document**: 06-seduction-agent-risks-deep-dive.md
**Date**: 14 mars 2026
**Audience**: Risk management, technical leads, stakeholders

---

## Risk Matrix Overview

```
IMPACT ↑
   |
   |  CRITICAL        HIGH           MEDIUM
   |  (Must Fix)      (Important)    (Monitor)
   |
   |  Hallucinations  Tone Failure   RAG Misses
   |  Budget Overspend Bot Detection Data Leak
   |  API Downtime    Poor Classify  Bad Prospect
   |
   |─────────────────────────────────────────► PROBABILITY
```

---

## Risk 1: RAG Hallucinations

**Risk**: Agent generates techniques or facts not present in training content

**Probability**: Medium (40%) — Medium (50%)
**Impact**: Medium (50%) — High (70%)
**Overall Risk Score**: 5.6/10

### Why It Happens
1. Claude-3.5-Sonnet sometimes extrapolates beyond context
2. Vague RAG chunks can lead to fabrication
3. Insufficient quality gate checks
4. Temperature too high (0.7+)

### Scenarios

#### Scenario A: Technique Hallucination
```
RAG Context: "L'authenticité est clé en approche"

User asks: "Faut-il je fasse de l'eye contact?"

Agent (HALLUCINATES): "Oui, 70% d'eye contact pendant 80% du temps,
sinon elle va penser que tu manques de confiance. C'est un fait prouvé."

Reality: The RAG says nothing about eye contact percentages.
The agent fabricated specificity.
```

#### Scenario B: Source Misattribution
```
RAG Context: [5 chunks from different videos]

Agent: "Comme j'en parlais dans le Module Psychologie..."

Reality: That module wasn't even in the RAG chunks.
Agent made up the source.
```

### Detection Strategy

#### Real-time (Quality Gate)
```python
async def check_hallucination(text: str, rag_chunks: list[RagChunk]) -> dict:
    """
    Use Claude to check if text is grounded in RAG content.
    """
    prompt = f"""
    Check if this response is grounded in the training content.

    Response:
    "{text}"

    Training Content:
    {format_rag_content(rag_chunks)}

    Questions to evaluate:
    1. Is every factual claim supported?
    2. Any specific numbers not in training?
    3. Any technique names not mentioned?
    4. Any sources cited correctly?

    Response JSON:
    {{
      "is_clean": bool,
      "hallucinations": ["claim1", "claim2"],
      "confidence": 0.0-1.0
    }}
    """

    result = await claude_invoke(prompt, model="claude-3-5-sonnet", temp=0.2)
    return json.loads(result)
```

#### Post-Mortem (Audit Trail)
```python
# After posting/sending:
if not quality_gate_result["is_clean"]:
    await postgres.store_hallucination_flag(
        run_id=state.run_id,
        text=state.output_text,
        rag_chunks=state.rag_chunks,
        confidence=quality_gate_result["confidence"],
        flagged_at=datetime.now()
    )

    # Alert team
    await slack.alert(
        channel="agent-risks",
        message=f"Potential hallucination in run {state.run_id}",
        severity="HIGH"
    )
```

### Mitigation Strategy

#### 1. Quality Gate (Reactive)
- ✅ Implemented in quality_gate_node
- Check: `hallucination_check.is_clean` must be True
- If fails: regenerate (max 2 retries) or fallback

#### 2. Temperature Tuning (Proactive)
```python
# In execute_node
if state.role == "RESPONDER":
    temperature = 0.5  # More deterministic
elif state.role == "CREATOR":
    temperature = 0.8  # More creative OK
elif state.role == "QUALIFIER":
    temperature = 0.3  # Very deterministic
```

#### 3. Constrained Output Format
```python
# Force tool use instead of free text
response = await claude_code_sdk.invoke(
    system_prompt="...",
    user_prompt="...",
    tools=[
        {
            "name": "cite_and_respond",
            "description": "Respond citing training sources",
            "schema": {
                "response": "string",
                "source_video": "string",
                "timestamp": "string"
            }
        }
    ]
)
```

#### 4. RAG Overlap Verification
```python
# Verify response overlaps with RAG content
def check_rag_overlap(response: str, rag_chunks: list[RagChunk]) -> float:
    """Measure overlap between response and training content."""

    response_embedding = embed(response)
    rag_embeddings = [embed(c.content) for c in rag_chunks]

    max_similarity = max(
        cosine_similarity(response_embedding, rag_emb)
        for rag_emb in rag_embeddings
    )

    return max_similarity  # Should be > 0.7 for responder
```

#### 5. Training Data Quality
```python
# Before adding chunk to pgvector:
async def validate_rag_chunk(chunk: RagChunk) -> bool:
    """Ensure RAG chunk is clean, factual, sourced."""

    # Check: source is known video
    if chunk.metadata["video_id"] not in known_videos:
        return False

    # Check: timestamp is valid
    if not is_valid_timestamp(chunk.metadata["timestamp"]):
        return False

    # Check: content is not duplicate
    existing = await postgres.find_similar_chunks(chunk.content, threshold=0.95)
    if existing:
        return False

    return True
```

### Monitoring & Alerts

```python
# Prometheus metrics
hallucination_rate = Counter(
    "agent_hallucination_detected",
    "Hallucinations caught by quality gate",
    ["role"]
)

# Alert if > 5% hallucination rate per day
if hallucinations_today / responses_today > 0.05:
    await alert_team("High hallucination rate detected")
```

---

## Risk 2: Tone Inconsistency

**Risk**: Agent responds in wrong tone (too corporate, wishy-washy, out of brand)

**Probability**: Medium (45%)
**Impact**: Medium (40%)
**Overall Risk Score**: 4.5/10

### Why It Happens
1. Inconsistent system prompt
2. Claude naturally defaults to formal/cautious tone
3. No tone classifier in quality gate
4. User expectation mismatch

### Scenarios

#### Scenario A: Too Formal
```
User: "C'est quoi la meilleure ouverture?"

GOOD: "Approche directe, sourire, eye contact. L'authenticité prime."

BAD: "In my professional assessment, there are several methodological approaches
to interpersonal initiation, each with varying degrees of efficacy..."
```

#### Scenario B: Too Wishy-Washy
```
GOOD: "L'escalade est simple: intérêt → kino → number → date."

BAD: "I think maybe it could be that escalation might involve, possibly, some forms
of physical contact, but I'm not entirely sure..."
```

### Detection Strategy

#### Tone Classifier
```python
async def classify_tone(text: str, expected_role: str) -> dict:
    """Classify tone alignment with brand voice."""

    tone_prompt = f"""
    Analyze this text for tone consistency with our brand.

    Text:
    "{text}"

    Brand Voice (Agent SEDUCTION):
    - Confident, direct
    - Authentic (no corporate speak)
    - Casual but intelligent
    - Affirms without hedging

    Expected role: {expected_role}

    Rate tone on 0.0-1.0 (1.0 = perfect alignment):

    Return JSON:
    {{
      "score": 0.0-1.0,
      "tone_markers": {{"formal": bool, "hedging": bool, "authentic": bool}},
      "issues": ["issue1"],
      "recommendation": "Keep|Rewrite|Fallback"
    }}
    """

    result = await claude_invoke(tone_prompt, model="claude-3-5-sonnet", temp=0.2)
    return json.loads(result)
```

### Mitigation Strategy

#### 1. System Prompt Pinning
```python
# Inject tone guidelines in every system prompt
TONE_GUIDELINES = """
## TON & PERSONNALITÉ

**Style**:
- Confident, direct, pas d'hésitations
- Français naturel (pas académique)
- Humour léger OK
- ZERO disclaimer ("je pense", "selon moi")

**Tone Markers to AVOID**:
✗ "I think" / "Je pense"
✗ "Maybe" / "Peut-être"
✗ "Could" / "Pourrait"
✗ "In my opinion" / "À mon avis"
✗ Corporate jargon
✗ Academic tone

**Tone Markers to SEEK**:
✓ "C'est..." / "It is..."
✓ "T'as..." / "You've..."
✓ Direct imperative
✓ Raw authenticity
✓ Casual but intelligent
"""
```

#### 2. Quality Gate Tone Check
```python
# In quality_gate_node:
quality_checks.append({
    "name": "tone_consistency",
    "passed": tone_result.score > 0.7,
    "score": tone_result.score
})

state.tone_confidence = tone_result.score

# If failed: regenerate or fallback
if tone_result.score < 0.7:
    if state.regenerate_count < 2:
        return "regenerate"
    else:
        return "fallback"
```

#### 3. Few-Shot Prompting
```python
# Add examples to every prompt
TONE_EXAMPLES = """
## EXEMPLAIRES BON TON

USER: "C'est quoi la meilleure ouverture?"

GOOD: "Approche directe, sourire, eye contact, puis observation simple.
L'authenticité prime sur la technique. Court, direct, pas hésitant."

BAD: "I think perhaps the best approach might be to consider authenticity,
which could be important in seduction contexts..."

---

USER: "Comment escalader avec une fille?"

GOOD: "Escalade = intérêt + kino progressive + qualification. Si elle répond bien,
tu vas chercher le nombre. Simple comme ça."

BAD: "Based on contemporary relationship research, escalation might involve several
gradual steps of physical proximity that could lead to..."

---
"""
```

#### 4. Tone Finetuning (Future)
```python
# If hallucination rate high, could finetune on tone examples
# Dataset: 500+ good/bad tone examples, labeled by human
```

### Monitoring

```python
# Track tone score by role
tone_scores_by_role = {
    "RESPONDER": [],   # target > 0.75
    "CREATOR": [],     # target > 0.80
    "QUALIFIER": []    # target > 0.70
}

# Daily report
print(f"RESPONDER avg tone: {mean(tone_scores_by_role['RESPONDER']):.2f}")
print(f"CREATOR avg tone: {mean(tone_scores_by_role['CREATOR']):.2f}")
print(f"QUALIFIER avg tone: {mean(tone_scores_by_role['QUALIFIER']):.2f}")

# Alert if avg < threshold
if mean(tone_scores) < 0.70:
    await alert_team("Tone consistency degrading")
```

---

## Risk 3: RAG Confidence Too Low

**Risk**: Agent can't find relevant training content for user's question

**Probability**: Medium (35%)
**Impact**: Low (30%)
**Overall Risk Score**: 3.2/10

### Why It Happens
1. RAG embeddings don't match user query
2. YouTube pipeline incomplete
3. Chunking strategy misses some topics
4. User asks something outside training scope

### Scenarios

#### Scenario A: No RAG Match
```
User: "Comment faire du cold approach en supermarché?"

RAG search returns 0 chunks (similarity < 0.6)

Agent has to respond without training content.
```

#### Scenario B: Low Similarity Match
```
User: "Que faire si elle teste ma confiance?"

Best RAG match: 0.52 similarity
(Threshold is 0.6, so technically no match)

Should agent use it anyway?
```

### Detection & Response Strategy

#### 1. Graceful Degradation
```python
# In contextualize_node:
if state.rag_confidence < 0.5:
    logger.warning(
        "LOW_RAG_CONFIDENCE",
        extra={
            "run_id": state.run_id,
            "rag_confidence": state.rag_confidence,
            "role": state.role
        }
    )

    # Decision by role
    if state.role == "RESPONDER":
        # Log warning, continue but flag for review
        state.error = None  # Don't fail
        # In quality gate, regenerate more aggressively

    elif state.role == "CREATOR":
        # Use fallback content (historical best posts)
        state.error = "LOW_RAG_CONFIDENCE"

    elif state.role == "QUALIFIER":
        # Still qualify, but no training context
        state.rag_chunks = []
```

#### 2. Fallback Strategy
```python
# Predefined fallback responses (for RESPONDER)
FALLBACK_RESPONSES = {
    "low_rag": (
        "C'est une excellente question! "
        "Je vais vérifier exactement ce qu'j'ai là-dessus et te revenir. "
        "Ping-moi demain 💪"
    ),
    "unknown_topic": (
        "Honnêtement, c'est pas vraiment mon domaine. "
        "Mais si tu m'expliques plus, peut-être que je peux aider."
    ),
}

if state.fallback_triggered:
    state.output_text = FALLBACK_RESPONSES["low_rag"]
    state.fallback_triggered = True
```

#### 3. RAG Pipeline Monitoring
```python
# Track RAG hit rate
rag_hit_rate = Counter("agent_rag_hits", "RAG search found matches", ["confidence_bucket"])

# Track topics with no coverage
missing_topics = []

if state.rag_confidence < 0.5:
    missing_topics.append({
        "query": state.message_text,
        "closest_similarity": state.rag_confidence,
        "timestamp": datetime.now()
    })

# Alert if > 20% of queries have no RAG match
daily_miss_rate = len(missing_topics) / daily_total_queries
if daily_miss_rate > 0.2:
    await alert_team("RAG coverage gap detected")
```

### Mitigation

#### 1. RAG Pipeline Improvement
- Add more YouTube videos (target: 100+ hours)
- Improve chunking strategy (semantic vs fixed-size)
- Add metadata (topic tags, difficulty level)
- Periodic embedding re-index

#### 2. Fallback Content Bank
```python
# Store historical best responses
BEST_RESPONSES = {
    "general_game": [...],
    "approach": [...],
    "escalation": [...],
    "mindset": [...],
}

# Use if RAG fails
if state.rag_confidence < 0.5 and state.role == "RESPONDER":
    topic = infer_topic(state.message_text)
    state.output_text = random.choice(BEST_RESPONSES[topic])
```

#### 3. User Feedback Loop
```python
# Ask user to rate response quality
# "Was this helpful? Yes / No / Partially"
# Use feedback to retrain RAG embeddings
```

---

## Risk 4: Budget Overspend

**Risk**: API costs exceed monthly budget (3000-10000€ shared across 3 agents)

**Probability**: Medium (30%)
**Impact**: High (60%)
**Overall Risk Score**: 4.2/10

### Budget Breakdown (Per Run)

| Component | Cost | Notes |
|-----------|------|-------|
| Claude-3.5-Sonnet (500 in tokens avg) | €0.0015 | ~5k per run |
| Claude-3.5-Sonnet (100 out tokens avg) | €0.0006 | ~1k per run |
| Per-run total | €0.0021 | |
| 1k runs/month | €2.10 | Small quota |
| 100k runs/month | €210 | Medium quota |

**Allocated budget for Agent SEDUCTION**: ~50€/month (out of 3000€ total for 3 agents)

### Scenarios

#### Scenario A: Exponential Token Growth
```
Week 1: 100 DMs/day → 2.10€
Week 2: 500 DMs/day → 10.50€
Week 3: 2000 DMs/day → 42€
Week 4: 10000 DMs/day → 210€

Monthly total: ~260€ (OVERSPEND)
```

#### Scenario B: Regen Loop Gone Wrong
```
Quality gate fails 50% of the time
→ Regenerate (consume 2x tokens)
→ If regenerates also fail (regenerate 2x more)
→ 1 DM could cost €0.01 instead of €0.002

10k DMs → €100 instead of €20
```

### Detection Strategy

#### Real-time Budget Tracking
```python
class BudgetTracker:
    def __init__(self, daily_limit_usd: float = 100.0):
        self.daily_limit = daily_limit_usd
        self.today_spent = 0.0
        self.today_runs = 0

    async def track_run(self, cost: float):
        self.today_spent += cost
        self.today_runs += 1

        if self.today_spent > self.daily_limit * 0.8:
            await alert_team(
                f"Budget warning: {self.today_spent:.2f}€ spent today "
                f"(80% of {self.daily_limit}€ daily limit)"
            )

        if self.today_spent > self.daily_limit:
            # Circuit breaker: stop accepting new requests
            raise BudgetExceededError(
                f"Daily budget exceeded: {self.today_spent:.2f}€"
            )

    def cost_per_run(self) -> float:
        return self.today_spent / self.today_runs if self.today_runs > 0 else 0
```

#### Cost Attribution
```python
# Track cost per role
costs_by_role = {
    "RESPONDER": [],    # Should be ~€0.002
    "CREATOR": [],      # Should be ~€0.003
    "QUALIFIER": [],    # Should be ~€0.001
}

# Track cost per regen
costs_by_regen_count = {
    0: [],  # No regens
    1: [],  # 1 regen
    2: [],  # 2 regens
}

# Alert if avg cost per run > €0.005
if mean(all_costs) > 0.005:
    await alert_team("Cost per run exceeding target")
```

### Mitigation Strategy

#### 1. Token Budgeting
```python
# Hard limit on tokens per request
MAX_TOKENS_PER_ROLE = {
    "RESPONDER": 200,   # Typical output ~100 tokens
    "CREATOR": 500,     # Posts are longer
    "QUALIFIER": 150,   # Classifier + response
}

# In execute_node:
response = await claude_invoke(
    max_tokens=MAX_TOKENS_PER_ROLE[state.role],
    ...
)
```

#### 2. Caching
```python
# Cache common queries (30 min TTL)
@lru_cache(maxsize=1000, ttl=30*60)
async def generate_cached_response(message_hash: str, role: str) -> str:
    """Cache responses to identical questions."""
    # Compute hash of (message + role)
    # If cached, return immediately (no API call)
    # Otherwise, call API and cache result
```

#### 3. Batch Processing
```python
# Instead of real-time, batch DMs every 5 minutes
async def batch_process_dms(batch_size: int = 100):
    """Process multiple DMs in single batch."""
    pending_dms = await get_pending_dms(limit=batch_size)

    for dm in pending_dms:
        await process_dm(dm)  # Each dm is still ~1 API call

    # But: deduplicate first
    deduplicated = deduplicate_by_intent(pending_dms)
    # Could reduce from 100 calls to 20 calls
```

#### 4. Model Downgrade (for non-critical)
```python
# Use cheaper model for some tasks
if state.role == "CREATOR" and not state.first_content_today:
    # First post of day: use sonnet (better quality)
    model = "claude-3-5-sonnet-20241022"
else:
    # Subsequent posts: use haiku (cheaper)
    model = "claude-3-5-haiku-20241022"  # 10x cheaper
```

#### 5. Circuit Breaker
```python
# Stop accepting new requests if budget exceeded
if budget_tracker.daily_spent > budget_tracker.daily_limit:
    # Queue DMs, process next day
    # OR redirect to fallback (no API call)
    await queue_pending_dms()
    state.error = "Daily budget limit reached"
    state.fallback_triggered = True
```

### Monitoring

```python
# Daily report
print(f"Today spent: ${today_spent:.2f}")
print(f"Daily limit: ${daily_limit:.2f}")
print(f"% of limit used: {(today_spent/daily_limit)*100:.1f}%")
print(f"Cost per run: ${cost_per_run:.4f}")
print(f"Runs processed: {today_runs}")
print(f"Avg cost per role:")
for role, costs in costs_by_role.items():
    if costs:
        print(f"  {role}: ${mean(costs):.4f}")
```

---

## Risk 5: Instagram Bot Detection

**Risk**: Instagram flags agent as bot and blocks DM responses

**Probability**: Low (15%)
**Impact**: Very High (80%)
**Overall Risk Score**: 3.4/10

### Why It Happens
1. Automated responses with consistent timing
2. Same response template for multiple users
3. Rapid DM volume
4. No human-like variation in response length/content

### Scenarios

#### Scenario A: Timing Pattern
```
Every DM gets response within exactly 30 seconds
Instagram algorithm detects pattern
→ Account flagged as bot
→ DM sending blocked
```

#### Scenario B: Template Detection
```
Agent sends same post script multiple times per week
Facebook Content ID detects duplicate uploads
→ Account flagged as spam
→ Reach limited
```

#### Scenario C: Volume Spike
```
Monday: 10 DMs
Tuesday: 500 DMs (viral post)
Wednesday: 2000 DMs

Instagram detects unnatural volume spike
→ Temporary action block
```

### Mitigation Strategy

#### 1. Response Timing Humanization
```python
import asyncio
import random

async def send_dm_humanized(dm_text: str, recipient_id: str):
    """Send DM with human-like delays."""

    # Random delay before sending (5 sec to 2 min)
    wait_time = random.uniform(5, 120)
    await asyncio.sleep(wait_time)

    # Send
    await instagram_api.send_dm(recipient_id, dm_text)

    # Log
    logger.info(f"DM sent with {wait_time:.1f}s delay")
```

#### 2. Response Variation
```python
# Don't send exact same response to all users
# Use prompt variation:
variation_prompts = [
    "Respond naturally, as if you're thinking",
    "Respond quickly and energetically",
    "Respond thoughtfully with detail",
]

response = await claude_invoke(
    system_prompt=system_prompt + random.choice(variation_prompts),
    ...
)

# Results in different length/style each time
```

#### 3. Content Upload Variation
```python
# Don't upload same caption format
# Vary: hook length, body structure, CTA style, hashtag count

# Example variations:
CAPTION_STYLES = [
    "hook_short",      # 5 words
    "hook_long",       # 15 words
    "hook_question",   # "Why do 90% fail?"
    "hook_statement",  # "Here's the truth:"
]

caption_style = random.choice(CAPTION_STYLES)

# Adjust template based on style
```

#### 4. Rate Limiting
```python
# Enforce max 1 DM per second (system-wide)
DM_RATE_LIMIT = 1  # per second

async def send_dm_rate_limited(recipient_id: str, text: str):
    """Send DM respecting rate limits."""

    await dm_rate_limiter.wait()  # Enforces 1/sec

    await instagram_api.send_dm(recipient_id, text)
```

#### 5. Account Health Monitoring
```python
# Track Instagram API response codes
class InstagramHealthMonitor:
    def __init__(self):
        self.errors = defaultdict(int)
        self.last_action_block = None

    async def check_health(self):
        """Check if account is flagged."""

        # Try sending test message to self
        response = await instagram_api.send_dm(
            self_user_id,
            "test message"
        )

        if response.status == 429:  # Rate limited
            self.errors["rate_limited"] += 1

        if response.status == 403:  # Forbidden (bot flag)
            self.errors["action_blocked"] += 1
            self.last_action_block = datetime.now()
            await alert_team("CRITICAL: Instagram action block detected")

        if self.errors["action_blocked"] > 0:
            return False  # Account compromised

        return True

# Check every hour
scheduler.every(1).hour.do(account_health_monitor.check_health)
```

### Monitoring

```python
# Track Instagram API responses
instagram_responses = Counter(
    "agent_instagram_api_responses",
    "Instagram API response codes",
    ["status_code"]
)

# Alert on 429 (rate limit) or 403 (action block)
if response.status == 429:
    await alert_team("Instagram rate limit hit")

if response.status == 403:
    await alert_team("CRITICAL: Instagram action block")
```

---

## Risk 6: Data Privacy / PII Leakage

**Risk**: Sensitive user data (DMs, classifications) exposed or logged unsafely

**Probability**: Low (20%)
**Impact**: Very High (90%)
**Overall Risk Score**: 4.2/10

### Scenarios

#### Scenario A: Logs Expose Sensitive Data
```python
# BAD: logs contain full DM text + user ID
logger.info(f"DM from {user_id}: {message_text}")
# If logs are shipped to unsecured external service → data breach

# GOOD: hash user IDs, truncate sensitive content
logger.info(
    "DM received",
    extra={
        "user_id_hash": hash(user_id),
        "message_length": len(message_text),
        "has_pii": detect_pii(message_text)
    }
)
```

#### Scenario B: Database Backup Exposed
```
PostgreSQL backup copied to unencrypted S3 bucket
→ Attacker downloads backup
→ Reads all DMs, classifications, user data
```

#### Scenario C: Error Response Leaks Data
```python
# BAD: error response includes internal details
try:
    result = await process_dm(dm)
except Exception as e:
    return {"error": str(e)}  # May contain sensitive data

# GOOD: generic error message
    return {"error": "Processing failed"}
    # Log details server-side only
```

### Mitigation Strategy

#### 1. Sensitive Data Detection
```python
import re

PII_PATTERNS = {
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "phone": r"\+?1?\d{9,15}",
    "credit_card": r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
}

def detect_pii(text: str) -> list[str]:
    """Detect PII in text."""
    found = []
    for pii_type, pattern in PII_PATTERNS.items():
        if re.search(pattern, text):
            found.append(pii_type)
    return found

# Use in intake node
if detect_pii(state.message_text):
    logger.warning(
        "PII detected in DM",
        extra={"pii_types": detect_pii(state.message_text)}
    )
    # May want to flag for manual review
```

#### 2. Encryption at Rest
```python
from cryptography.fernet import Fernet

# Encrypt sensitive columns
class EncryptedDM:
    def __init__(self, cipher: Fernet):
        self.cipher = cipher

    async def store_encrypted(self, dm: DM):
        """Store DM with encrypted message text."""

        encrypted_text = self.cipher.encrypt(dm.message_text.encode())

        await postgres.execute("""
            INSERT INTO instagram_dms (message_id, sender_id, message_text_encrypted)
            VALUES (%s, %s, %s)
        """, (dm.message_id, dm.sender_id, encrypted_text))

    async def retrieve_decrypted(self, dm_id: str) -> str:
        """Retrieve and decrypt DM."""

        row = await postgres.fetch_one(
            "SELECT message_text_encrypted FROM instagram_dms WHERE id = %s",
            (dm_id,)
        )

        return self.cipher.decrypt(row[0]).decode()
```

#### 3. Secure Logging
```python
import logging
from pythonjsonlogger import jsonlogger

# Use JSON logging with field masking
class MaskingFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)

        # Mask user IDs
        if "user_id" in log_record:
            log_record["user_id"] = hash_sensitive(log_record["user_id"])

        # Truncate message text
        if "message_text" in log_record:
            if len(log_record["message_text"]) > 50:
                log_record["message_text"] = log_record["message_text"][:50] + "..."

        # Remove full email addresses
        if "email" in log_record:
            log_record["email"] = "[REDACTED]"
```

#### 4. Database Encryption
```sql
-- PostgreSQL full-disk encryption
-- Storage: use encrypted volumes (EBS, GCP Persistent Disks)

-- Column-level encryption for most sensitive data
ALTER TABLE agent_conversations
ADD COLUMN state_json_encrypted BYTEA;

-- Row-level security
CREATE POLICY user_isolation ON agent_conversations
USING (sender_id = current_user_id);
```

#### 5. Access Control
```python
# RBAC: who can access what data?

ROLES = {
    "admin": ["read_all", "write_all", "export"],
    "analyst": ["read_analytics", "no_pii"],
    "support": ["read_own_user", "write_responses"],
    "api_service": ["read_for_rag", "no_pii"],
}

# Enforce in database
@app.get("/api/conversations")
async def get_conversations(current_user: User):
    if "read_all" not in current_user.permissions:
        raise HTTPException(403, "Forbidden")

    return await postgres.fetch_conversations()
```

#### 6. Data Retention Policy
```python
# Delete old data after N days
DATA_RETENTION_DAYS = {
    "raw_dms": 30,           # Delete after 30 days
    "agent_conversations": 90,  # Keep 90 days for analytics
    "prospect_classifications": 180,  # Keep 6 months for CRM
    "logs": 7,               # Keep 7 days for debugging
}

async def cleanup_old_data():
    """Daily cleanup job."""

    for table, days in DATA_RETENTION_DAYS.items():
        cutoff = datetime.now() - timedelta(days=days)

        await postgres.execute(f"""
            DELETE FROM {table}
            WHERE created_at < %s
        """, (cutoff,))

        logger.info(f"Cleaned {table} older than {days} days")

# Schedule daily at 2 AM
scheduler.every().day.at("02:00").do(cleanup_old_data)
```

### Monitoring

```python
# Track PII detection
pii_detected = Counter(
    "agent_pii_detected",
    "PII detected in DMs",
    ["pii_type"]
)

# Track database access
db_access_log = [
    {
        "user": user_id,
        "table": table,
        "action": "SELECT|INSERT|UPDATE|DELETE",
        "timestamp": datetime.now(),
        "rows_affected": count
    }
]

# Alert on suspicious access
if count > 10000:  # Large batch export
    await alert_security_team("Large database export detected")
```

---

## Risk Matrix Summary Table

| Risk | Probability | Impact | Score | Severity | Mitigation |
|------|-------------|--------|-------|----------|-----------|
| Hallucinations | 40% | 50% | 5.6/10 | HIGH | Quality gate + check_hallucination |
| Tone Failure | 45% | 40% | 4.5/10 | MEDIUM | Tone classifier + system prompt |
| Low RAG Coverage | 35% | 30% | 3.2/10 | MEDIUM | Graceful degrade + fallbacks |
| Budget Overspend | 30% | 60% | 4.2/10 | MEDIUM | Circuit breaker + caching |
| Bot Detection | 15% | 80% | 3.4/10 | MEDIUM | Humanize timing + variation |
| Data Privacy | 20% | 90% | 4.2/10 | HIGH | Encryption + RBAC + retention |

---

## Implementation Checklist

- [ ] Hallucination detection in quality_gate_node
- [ ] Tone classifier implemented
- [ ] RAG confidence monitoring
- [ ] Budget tracker with alerts
- [ ] Instagram rate limiting
- [ ] PII detection patterns
- [ ] Database encryption
- [ ] Access control (RBAC)
- [ ] Data retention policies
- [ ] Logging sanitization
- [ ] Daily monitoring dashboard
- [ ] Incident response playbook

---

**Next Step**: Implement risks #1 (Hallucinations) and #6 (Data Privacy) first, as they have highest severity.

**Questions/Updates**: Risk@megaquixai.local
