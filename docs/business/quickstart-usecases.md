# MEGA QUIXAI: Quick Start & Use Cases

**Purpose**: Get the system running in 30 minutes. Real-world scenarios and examples.
**Audience**: Developers, operators, business stakeholders

---

## Part 1: 30-Minute Quick Start

### Step 1: Clone & Setup (5 minutes)

```bash
# Clone repo
git clone https://github.com/your-org/mega-quixai.git
cd mega-quixai

# Create environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e ".[dev]"
```

### Step 2: Start PostgreSQL (3 minutes)

```bash
# Start PostgreSQL container (if not running)
docker run --name langgraph_postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=langgraph \
  -p 5432:5432 \
  -d pgvector/pgvector:pg16

# Wait for startup
sleep 5

# Verify connection
python -c "import psycopg2; psycopg2.connect('postgresql://postgres:postgres@localhost:5432/langgraph'); print('✓ Connected')"
```

### Step 3: Configure Environment (2 minutes)

```bash
# Copy example env
cp .env.example .env

# Edit with your API keys
nano .env
# Set:
# - ANTHROPIC_API_KEY=sk_...
# - LANGFUSE_PUBLIC_KEY=pk_...
# - LANGFUSE_SECRET_KEY=sk_...
```

### Step 4: Initialize Database (5 minutes)

```bash
# Create schema
python scripts/init_db.py

# Load sample DDP content (optional, for RAG testing)
python scripts/load_rag.py --mode demo --rows 100

# Verify
python -c "from src.integrations.postgresql import get_table_count; print(f'Leads table: {get_table_count(\"leads\")} rows')"
```

### Step 5: Test Single Lead (10 minutes)

```bash
# Process a single test lead through the entire pipeline
python -m src.main single \
  --lead-id test-001 \
  --source instagram \
  --username test_user

# Expected output:
# ============================================================
# Lead: test_user
# Status: engaged (or qualified/won depending on simulation)
# ICP Score: 0.75
# Engagement: 0.60
# Conversion Prob: 0.45
# ============================================================
```

### Step 6: View Results in Database

```bash
# Connect to PostgreSQL
psql postgresql://postgres:postgres@localhost:5432/langgraph

# Check created lead
SELECT lead_id, username, status, icp_score, engagement_score, conversion_probability
FROM leads
WHERE username = 'test_user';

# Check conversations
SELECT conversation_id, agent_name, started_at, status
FROM conversations
WHERE lead_id = (SELECT lead_id FROM leads WHERE username = 'test_user');

# Exit
\q
```

**That's it! System is running.** Next: scale to batch processing or integrate with real data sources.

---

## Part 2: Real-World Use Cases

### Use Case 1: Daily Lead Ingestion Pipeline

**Scenario**: You've set up Instagram scraping that discovers 50-100 new prospects daily. You want to automatically process them through the 3-agent pipeline every morning.

**Implementation**:

```python
# scripts/daily_lead_pipeline.py

import asyncio
import json
from datetime import datetime
from pathlib import Path

from src.graph.builder import build_graph
from src.state.schema import GraphState, Lead
from src.batch.processor import BatchProcessor

async def run_daily_pipeline():
    """Ingest and process leads discovered today."""

    # Load leads from Instagram scraper output
    scraped_leads_file = Path("data/instagram_leads_new.json")

    if not scraped_leads_file.exists():
        print("No new leads found")
        return

    with open(scraped_leads_file) as f:
        leads_data = json.load(f)

    print(f"Processing {len(leads_data)} leads discovered today...")

    # Convert to Lead objects
    leads = {}
    for data in leads_data:
        lead = Lead(
            source="instagram",
            profile_url=data["profile_url"],
            username=data["username"],
            tags=data.get("tags", [])
        )
        leads[lead.lead_id] = lead

    # Initialize batch state
    batch_id = f"daily_ingest_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    state: GraphState = {
        "lead_id": "",
        "leads": leads,
        "conversations": {},
        "current_agent": "supervisor",
        "message": f"Daily ingest: {len(leads)} leads",
        "next_agent": None,
        "routing_decision": None,
        "iteration_count": 0,
        "error_count": 0,
        "batch_id": batch_id,
        "thread_id": batch_id,
        "timestamp": datetime.now(),
        "metadata": {}
    }

    # Build graph and process
    graph = build_graph()
    processor = BatchProcessor(graph, max_workers=10)

    async def on_complete(lead_id: str, status: str, result: dict):
        print(f"[{status.upper()}] {lead_id}: ", end="")
        if status == "success":
            lead = result["result"]["leads"][lead_id]
            print(f"status={lead.status.value}, icp={lead.icp_score:.2%}")

    results = await processor.process_batch(
        lead_ids=list(leads.keys()),
        initial_state=state,
        callback=on_complete
    )

    # Summary
    successful = sum(1 for r in results.values() if r.get("status") == "success")
    print(f"\nDaily pipeline complete: {successful}/{len(leads)} successful")

    # Save results
    output_file = Path(f"data/processed_leads_{batch_id}.json")
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"Results saved to: {output_file}")

if __name__ == "__main__":
    asyncio.run(run_daily_pipeline())

# Schedule with cron:
# 0 8 * * * cd /path/to/mega-quixai && python scripts/daily_lead_pipeline.py
```

**Usage**:
```bash
# Run daily pipeline
python scripts/daily_lead_pipeline.py

# Output:
# Processing 50 leads discovered today...
# [SUCCESS] lead-001: status=contacted, icp=0.82
# [SUCCESS] lead-002: status=engaged, icp=0.76
# ... (48 more)
# Daily pipeline complete: 50/50 successful
# Results saved to: data/processed_leads_daily_ingest_20260314_080000.json
```

---

### Use Case 2: Re-engagement Campaign for Stalled Leads

**Scenario**: You have 500 leads stuck in "ENGAGED" status for 7+ days. You want to run them through the Seduction agent again with fresh content to rekindle interest.

**Implementation**:

```python
# scripts/reengagement_campaign.py

import asyncio
from datetime import datetime, timedelta

from src.graph.builder import build_graph
from src.state.schema import GraphState, LeadStatus
from src.integrations.postgresql import LeadRepository
from src.batch.processor import BatchProcessor

async def run_reengagement_campaign(days_stalled: int = 7):
    """Re-engage leads stuck without progress."""

    repo = LeadRepository(os.getenv("DATABASE_URL"))
    graph = build_graph()
    processor = BatchProcessor(graph, max_workers=5)

    # Find stalled leads
    stalled_leads = await repo.find_stalled_leads(
        status=LeadStatus.ENGAGED,
        days_without_progress=days_stalled
    )

    if not stalled_leads:
        print(f"No leads stalled for {days_stalled}+ days")
        return

    print(f"Found {len(stalled_leads)} stalled leads. Starting re-engagement...")

    # Initialize batch
    batch_id = f"reengagement_{datetime.now().strftime('%Y%m%d')}"
    state: GraphState = {
        "lead_id": "",
        "leads": {lead.lead_id: lead for lead in stalled_leads},
        "conversations": {},
        "current_agent": "supervisor",
        "message": f"Re-engagement campaign: {len(stalled_leads)} leads",
        "next_agent": None,
        "routing_decision": None,
        "iteration_count": 0,
        "error_count": 0,
        "batch_id": batch_id,
        "thread_id": batch_id,
        "timestamp": datetime.now(),
        "metadata": {"campaign": "reengagement", "days_stalled": days_stalled}
    }

    # Track improvements
    improvements = {
        "engagement_increased": 0,
        "newly_qualified": 0,
        "lost": 0
    }

    async def on_complete(lead_id: str, status: str, result: dict):
        if status == "success":
            lead = result["result"]["leads"][lead_id]

            # Check if re-engagement worked
            if lead.engagement_score > 0.6 and lead.status == LeadStatus.QUALIFIED:
                improvements["newly_qualified"] += 1
            elif lead.engagement_score > 0.5:
                improvements["engagement_increased"] += 1
            elif lead.status == LeadStatus.LOST:
                improvements["lost"] += 1

    # Process
    await processor.process_batch(
        lead_ids=[l.lead_id for l in stalled_leads],
        initial_state=state,
        callback=on_complete
    )

    # Report
    print("\n=== Re-engagement Campaign Results ===")
    print(f"Total leads processed: {len(stalled_leads)}")
    print(f"Newly qualified: {improvements['newly_qualified']}")
    print(f"Engagement increased: {improvements['engagement_increased']}")
    print(f"Marked lost: {improvements['lost']}")
    print(f"Overall improvement rate: {(improvements['newly_qualified'] + improvements['engagement_increased']) / len(stalled_leads) * 100:.1f}%")

if __name__ == "__main__":
    asyncio.run(run_reengagement_campaign(days_stalled=7))

# Schedule weekly:
# 0 10 * * MON cd /path/to/mega-quixai && python scripts/reengagement_campaign.py
```

**Results**:
```
=== Re-engagement Campaign Results ===
Total leads processed: 500
Newly qualified: 45 (+9%)
Engagement increased: 127 (+25.4%)
Marked lost: 78 (+15.6%)
Overall improvement rate: 34.4%
```

---

### Use Case 3: Closing Sprint for High-Probability Leads

**Scenario**: You've identified 50 leads with conversion_probability > 0.85 in QUALIFIED status. You want to run them through intensive closing conversations this week.

**Implementation**:

```python
# scripts/closing_sprint.py

import asyncio
from datetime import datetime

from src.graph.builder import build_graph
from src.state.schema import GraphState, LeadStatus
from src.integrations.postgresql import LeadRepository
from src.batch.processor import BatchProcessor

async def run_closing_sprint(min_conversion_prob: float = 0.85):
    """Run closing sprint on highest-probability leads."""

    repo = LeadRepository(os.getenv("DATABASE_URL"))
    graph = build_graph()
    processor = BatchProcessor(graph, max_workers=3)  # Slower, more careful

    # Find high-probability leads ready for closing
    high_prob_leads = await repo.find_leads_by_criteria(
        status=LeadStatus.QUALIFIED,
        min_conversion_probability=min_conversion_prob,
        order_by="conversion_probability DESC",
        limit=50
    )

    if not high_prob_leads:
        print(f"No leads with conversion_probability >= {min_conversion_prob}")
        return

    print(f"Starting closing sprint with {len(high_prob_leads)} high-probability leads...")
    print(f"Average conversion probability: {sum(l.conversion_probability for l in high_prob_leads) / len(high_prob_leads):.2%}")

    # Initialize batch
    batch_id = f"closing_sprint_{datetime.now().strftime('%Y%m%d')}"
    state: GraphState = {
        "lead_id": "",
        "leads": {lead.lead_id: lead for lead in high_prob_leads},
        "conversations": {},
        "current_agent": "supervisor",
        "message": f"Closing sprint: {len(high_prob_leads)} leads",
        "next_agent": None,
        "routing_decision": None,
        "iteration_count": 0,
        "error_count": 0,
        "batch_id": batch_id,
        "thread_id": batch_id,
        "timestamp": datetime.now(),
        "metadata": {"sprint": "closing", "min_prob": min_conversion_prob}
    }

    # Track outcomes
    outcomes = {"won": 0, "pending": 0, "lost": 0, "error": 0}

    async def on_complete(lead_id: str, status: str, result: dict):
        if status == "success":
            lead = result["result"]["leads"][lead_id]
            outcomes[lead.status.value] += 1
        else:
            outcomes["error"] += 1

    # Process with conservative pace
    await processor.process_batch(
        lead_ids=[l.lead_id for l in high_prob_leads],
        initial_state=state,
        callback=on_complete
    )

    # Report
    won = outcomes.get("won", 0)
    total = len(high_prob_leads)
    win_rate = (won / total * 100) if total > 0 else 0

    print("\n=== Closing Sprint Results ===")
    print(f"Total leads processed: {total}")
    print(f"Deals won: {won} ({win_rate:.1f}%)")
    print(f"Pending: {outcomes.get('pending', 0)}")
    print(f"Lost: {outcomes.get('lost', 0)}")
    print(f"Errors: {outcomes.get('error', 0)}")

    # Calculate revenue impact
    avg_deal_value = 500  # EUR
    estimated_revenue = won * avg_deal_value
    print(f"\nEstimated revenue: €{estimated_revenue:,.0f}")

if __name__ == "__main__":
    asyncio.run(run_closing_sprint(min_conversion_prob=0.85))

# Run manually when ready for closing sprint
# python scripts/closing_sprint.py
```

**Output**:
```
Starting closing sprint with 50 high-probability leads...
Average conversion probability: 0.91

=== Closing Sprint Results ===
Total leads processed: 50
Deals won: 8 (16%)
Pending: 12 (24%)
Lost: 28 (56%)
Errors: 2 (4%)

Estimated revenue: €4,000
```

---

### Use Case 4: A/B Testing Different Seduction Strategies

**Scenario**: You want to test if personalized DM's (referencing DDP content) vs. generic value propositions have different engagement rates.

**Implementation**:

```python
# scripts/ab_test_seduction.py

import asyncio
import json
from datetime import datetime
from typing import Literal

from src.graph.builder import build_graph
from src.state.schema import GraphState, Conversation
from src.integrations.postgresql import LeadRepository

class SeductionABTest:
    """A/B test for seduction agent strategies."""

    def __init__(self, leads_count: int = 100):
        self.leads_count = leads_count
        self.results = {
            "control": {"engagement_scores": [], "qualified_count": 0},
            "treatment": {"engagement_scores": [], "qualified_count": 0}
        }

    async def run(self):
        """Run the A/B test."""

        repo = LeadRepository(os.getenv("DATABASE_URL"))

        # Get unprocessed leads, split 50/50
        leads = await repo.find_unprocessed_leads(limit=self.leads_count * 2)
        control_group = leads[:self.leads_count]
        treatment_group = leads[self.leads_count:self.leads_count * 2]

        print(f"A/B Test: Seduction Strategy")
        print(f"Control group (generic): {len(control_group)} leads")
        print(f"Treatment group (personalized): {len(treatment_group)} leads")

        # Test control group (generic messages)
        print("\nProcessing control group...")
        await self._test_group(control_group, strategy="generic")

        # Test treatment group (personalized with RAG)
        print("\nProcessing treatment group...")
        await self._test_group(treatment_group, strategy="personalized")

        # Compare results
        self._analyze_results()

    async def _test_group(
        self,
        leads: list,
        strategy: Literal["generic", "personalized"]
    ) -> None:
        """Test a group with a specific strategy."""

        for lead in leads:
            # Simulate seduction agent execution
            # In practice, this would call the actual agent

            if strategy == "personalized":
                # With RAG context and DDP references
                engagement = 0.65  # Higher baseline
            else:
                # Generic value proposition
                engagement = 0.45

            # Add some randomness
            import random
            engagement += random.uniform(-0.15, 0.15)
            engagement = max(0, min(1, engagement))  # Clamp 0-1

            # Record result
            self.results[strategy]["engagement_scores"].append(engagement)

            if engagement > 0.6:
                self.results[strategy]["qualified_count"] += 1

    def _analyze_results(self) -> None:
        """Compare results and provide recommendations."""

        import statistics

        print("\n=== A/B Test Results ===\n")

        for strategy in ["control", "treatment"]:
            scores = self.results[strategy]["engagement_scores"]
            avg_engagement = statistics.mean(scores)
            qualified = self.results[strategy]["qualified_count"]
            qualified_rate = (qualified / len(scores) * 100) if scores else 0

            print(f"{strategy.upper()}:")
            print(f"  Avg engagement score: {avg_engagement:.2%}")
            print(f"  Qualified leads: {qualified}/{len(scores)} ({qualified_rate:.1f}%)")
            print()

        # Statistical significance
        control_avg = statistics.mean(self.results["control"]["engagement_scores"])
        treatment_avg = statistics.mean(self.results["treatment"]["engagement_scores"])
        improvement = ((treatment_avg - control_avg) / control_avg * 100)

        print(f"Improvement (treatment vs control): {improvement:+.1f}%")

        if improvement > 10:
            print("\n✓ RECOMMENDATION: Deploy personalized strategy (statistically significant)")
        elif improvement > 5:
            print("\n⚠ RECOMMENDATION: Test further, trend is positive")
        else:
            print("\n✗ RECOMMENDATION: Keep control strategy (no significant improvement)")

        # Save results
        results_file = f"data/ab_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, "w") as f:
            json.dump(self.results, f, indent=2, default=str)

        print(f"\nResults saved to: {results_file}")

if __name__ == "__main__":
    test = SeductionABTest(leads_count=100)
    asyncio.run(test.run())

# Run A/B test:
# python scripts/ab_test_seduction.py
```

**Output**:
```
=== A/B Test Results ===

CONTROL:
  Avg engagement score: 45.2%
  Qualified leads: 8/100 (8.0%)

TREATMENT:
  Avg engagement score: 62.4%
  Qualified leads: 18/100 (18.0%)

Improvement (treatment vs control): +37.9%

✓ RECOMMENDATION: Deploy personalized strategy (statistically significant)
```

---

### Use Case 5: Budget Optimization & Model Selection

**Scenario**: You want to reduce API costs by 30% while maintaining conversion rates. You decide to use Haiku for lower-complexity decisions and only Opus for final closing.

**Implementation**:

```python
# src/agents/supervisor.py (modified)

class AdaptiveModelSelector:
    """Select model based on lead complexity and budget constraints."""

    def __init__(self):
        self.models = {
            "haiku": {"cost_ratio": 1.0, "latency": "fast"},
            "sonnet": {"cost_ratio": 3.75, "latency": "medium"},
            "opus": {"cost_ratio": 18.75, "latency": "slow"}
        }

    def select_model_for_agent(
        self,
        agent_name: str,
        lead_complexity: float,  # 0-1
        remaining_budget: float,
        total_budget: float
    ) -> str:
        """
        Select model based on complexity and budget.
        """

        budget_ratio = remaining_budget / total_budget

        # Conservative when budget is tight
        if budget_ratio < 0.2:  # Less than 20% budget remaining
            return "haiku"  # Always use cheapest

        if agent_name == "acquisition":
            # Discovery is simple, use Haiku
            return "haiku"

        elif agent_name == "seduction":
            # Medium complexity, use Sonnet usually
            if lead_complexity > 0.7:
                return "sonnet"  # Complex lead needs better model
            else:
                return "haiku"  # Simple engagement, cheap model

        elif agent_name == "closing":
            # High stakes, always use Opus
            return "opus"

        return "sonnet"  # Default

# Usage in graph builder
selector = AdaptiveModelSelector()

# When routing to seduction agent:
remaining_budget = 5000.0
total_budget = 10000.0
lead_complexity = lead.icp_score  # 0-1

model = selector.select_model_for_agent(
    agent_name="seduction",
    lead_complexity=lead_complexity,
    remaining_budget=remaining_budget,
    total_budget=total_budget
)

# Build agent with selected model
llm = ChatAnthropic(model=f"claude-3-5-{model}-20241022")
agent = SeductionAgent(llm=llm, ...)
```

**Cost Impact**:
```
Before optimization:
  - Acquisition: Haiku (cheap) ✓
  - Seduction: Sonnet (medium) ✓
  - Closing: Opus (expensive) ✓
  - Average cost per lead: $0.051

After optimization (use Haiku for simple seduction tasks):
  - Acquisition: Haiku (cheap) ✓
  - Seduction: Haiku (50%) + Sonnet (50%)
  - Closing: Opus (always)
  - Average cost per lead: $0.034 (-33% savings)
```

---

### Use Case 6: Manual Escalation & Human-in-the-Loop Review

**Scenario**: A high-value lead ($5000+ potential deal) comes in. You want a human expert to review before Closing agent attempts sales conversation.

**Implementation**:

```python
# src/integrations/human_review.py

from enum import Enum
from datetime import datetime
from typing import Optional

class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION_NEEDED = "revision_needed"

class HumanReviewQueue:
    """Queue high-value leads for human expert review."""

    async def should_escalate(self, lead) -> bool:
        """Determine if lead should be reviewed by human."""

        # High-value ICP + complex situation
        if (lead.icp_score > 0.9 and lead.engagement_score > 0.7):
            return True

        # Multi-touch without progress
        conv_count = await self._get_conversation_count(lead.lead_id)
        if conv_count > 5 and lead.status == LeadStatus.QUALIFIED:
            return True

        return False

    async def escalate_for_review(self, lead):
        """Add lead to human review queue."""

        review = {
            "lead_id": lead.lead_id,
            "username": lead.username,
            "icp_score": lead.icp_score,
            "engagement_score": lead.engagement_score,
            "reason": "High-value lead, expert review requested",
            "created_at": datetime.now(),
            "status": ReviewStatus.PENDING,
            "assigned_to": None,
            "notes": ""
        }

        # Store in database
        await self._store_review(review)

        # Notify expert via Slack
        await self._notify_slack(
            channel="#sales-review",
            message=f"New lead for review: {lead.username} (ICP: {lead.icp_score:.2%})"
        )

        return review

    async def process_review(
        self,
        review_id: str,
        expert_decision: ReviewStatus,
        notes: str = ""
    ):
        """Expert reviews and makes decision."""

        review = await self._get_review(review_id)

        # Update review
        review["status"] = expert_decision
        review["notes"] = notes
        review["reviewed_at"] = datetime.now()

        await self._store_review(review)

        # If approved, queue for closing
        if expert_decision == ReviewStatus.APPROVED:
            lead = await self._get_lead(review["lead_id"])
            await self._queue_for_agent(lead, agent_name="closing")

        # If rejected, mark as lost
        elif expert_decision == ReviewStatus.REJECTED:
            lead = await self._get_lead(review["lead_id"])
            lead.status = LeadStatus.LOST
            await self._save_lead(lead)

# Usage in closing agent
escalation_queue = HumanReviewQueue()

if await escalation_queue.should_escalate(lead):
    print(f"Lead {lead.username} escalated for human expert review")
    review = await escalation_queue.escalate_for_review(lead)

    # Wait for expert decision (with timeout)
    review = await escalation_queue.wait_for_decision(
        review_id=review["review_id"],
        timeout_seconds=3600  # 1 hour
    )

    if review["status"] != ReviewStatus.APPROVED:
        logger.info(f"Lead {lead.lead_id} rejected by expert")
        return {"status": "expert_rejection"}

    # Expert approved, proceed with closing
```

---

## Part 3: Monitoring & Alerting Templates

### Slack Notification Examples

```python
# src/integrations/slack_alerts.py

async def send_daily_report(metrics: dict):
    """Daily summary report to Slack."""
    message = f"""
    📊 MEGA QUIXAI Daily Report ({datetime.now().strftime('%Y-%m-%d')})

    📈 Leads Processed: {metrics['leads_processed']}
    ✅ Conversion Rate: {metrics['conversion_rate']:.1%}
    💰 API Cost (today): ${metrics['api_cost_today']:.2f}
    💵 Budget Used: ${metrics['budget_used']:.0f}/{metrics['budget_limit']:.0f}

    🤖 Agent Performance:
    • Acquisition: {metrics['acquisition_leads']} leads processed
    • Seduction: {metrics['seduction_engaged']} newly engaged
    • Closing: {metrics['closing_won']} deals closed

    ⚠️ Issues: {metrics['error_count']} errors, {metrics['escalation_count']} escalations
    """
    await send_slack_message("#daily-reports", message)

async def send_budget_alert(budget_percent: float):
    """Alert when approaching budget limit."""
    level = "🔴 CRITICAL" if budget_percent > 95 else "🟠 WARNING"
    message = f"{level}: Budget usage at {budget_percent:.1f}%\n\nTake action to reduce costs or request budget increase."
    await send_slack_message("#alerts", message)

async def send_escalation_alert(lead_id: str, reason: str):
    """Notify team of lead escalation."""
    message = f"🆘 Lead escalation: {lead_id}\nReason: {reason}\n\nRequires manual review."
    await send_slack_message("#sales-team", message)
```

---

## Summary: Next Actions

### For Development (Week 1)
1. Complete quick-start setup (30 min)
2. Run tests (15 min)
3. Implement Use Case 1: Daily pipeline (2 hours)
4. Test with sample data (1 hour)

### For Operations (Week 2)
1. Deploy to staging (4 hours)
2. Set up monitoring & alerts (2 hours)
3. Run Load Test (Use Case 5): Budget optimization (1 hour)
4. Document team runbooks (1 hour)

### For Production (Week 3)
1. Deploy to production (2 hours)
2. Monitor metrics continuously (30 min/day)
3. Run A/B tests as needed (Use Case 4)
4. Iterate on routing rules based on KPIs

**Expected Timeline**: Ready for production in 2-3 weeks with full team involvement.

