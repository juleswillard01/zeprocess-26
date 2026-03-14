# Agent CLOSING - Use Cases & Detailed Diagrams
## Real-world scenarios, decision trees, and visual flows

---

## Table of Contents
1. [Use Case Scenarios](#use-case-scenarios)
2. [Detailed Objection Decision Trees](#detailed-objection-decision-trees)
3. [Sequence Diagrams](#sequence-diagrams)
4. [Data Flow Diagrams](#data-flow-diagrams)
5. [Error Handling & Recovery](#error-handling--recovery)
6. [A/B Testing Matrix](#ab-testing-matrix)

---

## Use Case Scenarios

### Use Case 1: Ideal Path (High-Value Prospect)

**Prospect**: Sarah, VP of Sales at SaaS startup (Segment: high_value)
**Timeline**: 2 hours
**Outcome**: Conversion ($199)

```
10:00 AM
└─ Agent CLOSING receives Sarah from Agent SÉDUCTION
   ├─ Qualification Score: 0.82 (high)
   ├─ Pain Points: ["Sales process inefficiency", "Team management"]
   └─ Budget: $50k-100k/year (high_value segment)

10:05 AM
└─ INIT node fires
   ├─ Load: Segment rules (high_value positioning)
   ├─ RAG search: "sales automation for enterprise" → 3 results
   └─ Generate opening: "Hey Sarah, saw your background in scaling SaaS sales..."
   └─ Send via WhatsApp

10:15 AM [IMMEDIATE RESPONSE]
└─ Sarah replies: "Hey! Yeah, sales process is killing us. How does this work?"
   └─ Agent detects: POSITIVE ENGAGEMENT

10:20 AM
└─ CONVERSE node
   ├─ Classify: "question" ✓
   ├─ Generate response: "Great! Let me ask 2 quick Qs to understand..."
   └─ Send response

10:25 AM
└─ Sarah: "We have 5 sales reps. Using Salesforce. Main issue: lead qualification takes 2 days."
   └─ Agent: Extract context, update conversation history

10:30 AM
└─ CONVERSE continues (Turn 3)
   ├─ Generate response: "Got it. Here's what works for teams like yours..."
   └─ Suggest: "Ready to see pricing?"

10:35 AM [READY FOR OFFER]
└─ Sarah: "Sure, let me see what you have"
   └─ Agent detects: OFFER_PRESENTED signal

10:40 AM
└─ OFFER_PRESENTED node fires
   ├─ Calculate price: Base $199 × (1 - 0.05 qual_discount) × (1 - 0 objections) = $189
   ├─ Create Stripe session: $189/month
   ├─ Generate message: "For a team of 5, we recommend Premium..."
   └─ Send Stripe link via WhatsApp

10:45 AM [USER CLICKS LINK]
└─ Stripe checkout page opens
   ├─ Customer: sarah@startup.com
   ├─ Amount: $189
   └─ Expiration: 12:40 PM (24 hours)

11:00 AM [PAYMENT COMPLETED]
└─ Stripe webhook fires: checkout.session.completed
   ├─ Event: session.payment_status = "paid"
   ├─ Database: UPDATE prospects SET status='converted', final_amount=189
   ├─ Trigger: Agent FOLLOW (onboarding + upsell)
   └─ Analytics: Log conversion

CONVERSION METRICS:
├─ Conversation turns: 3
├─ API calls: 5 (3 LLM + 2 RAG)
├─ Tokens used: ~2100
├─ LLM cost: ~$0.006
├─ Time to conversion: 61 minutes
└─ Revenue: $189

```

---

### Use Case 2: Objection Path (Timing Concern)

**Prospect**: Marc, CMO at mid-market agency (Segment: mid_market)
**Timeline**: 4.5 hours (multi-day follow-up)
**Outcome**: Converted after timing reassurance ($99)

```
9:00 AM [DAY 1]
└─ Opening message sent to Marc

9:30 AM [45 MINUTES LATER]
└─ Marc replies: "Looks interesting but timing is bad. Q4 budget freeze."
   └─ Agent detects: OBJECTION (timing)

9:35 AM
└─ OBJECTION_HANDLING node fires
   ├─ Classify objection: "timing"
   ├─ RAG search: "How to start before budget year" → 4 results
   │  ├─ Video 1: "Implement 2-week trial before Q1 budget"
   │  ├─ Video 2: "Cost recovery in first month of usage"
   │  └─ Video 3: "Case study: Q4 setup, Q1 ROI"
   └─ Extract counter-arguments:
      ├─ "Trial starts now, payable Jan 1st"
      ├─ "Actually saves budget in Q4 by automating"
      └─ "Others start pilot, full deployment later"

9:40 AM
└─ Generate counter-argument:
   "Marc, that's actually the perfect timing. Here's why:

   Most teams do a 30-day pilot before full budget commitment.
   Trial starts now = zero cost. You see results in Dec.

   Then when Q1 budget opens, you're already trained + proven ROI.

   That's what got [Case Study] to commit. Want to try the pilot route?"

9:45 AM
└─ Marc replies: "Hmm, 30-day trial sounds more reasonable. What's the catch?"
   └─ Agent detects: OBJECTION PARTIALLY RESOLVED (willingness to reconsider)

9:50 AM
└─ CONVERSE continues
   ├─ Generate: "No catch! Here's the pilot terms: [30 days, free, see results]"
   └─ Prepare offer

10:00 AM
└─ Marc: "OK let's try it"
   └─ Agent detects: READY FOR OFFER

10:05 AM
└─ OFFER_PRESENTED
   ├─ Generate offer: Pilot pricing $0 (first 30 days), then $99/month
   ├─ Create Stripe session: $0 (trial link, no payment yet)
   └─ Send "Pilot access" link

[SAME DAY CONVERSION - but no payment yet]

---

[DAY 31]
└─ CRM reminder: Marc's pilot expires
   ├─ Agent FOLLOW sends: "30 days are up! Here's your results:"
   ├─ Show metrics
   └─ Offer full upgrade at $99/month

[DAY 31, 2PM]
└─ Marc: "Yeah let's do it. Worth it."
   └─ Payment link sent

[CONVERSION #2]
└─ Marc pays $99

METRICS:
├─ Objection type: timing
├─ Counter-argument success: YES (60% baseline)
├─ Total conversation turns: 5 (including follow-up)
├─ Days to final conversion: 31 (trial period)
├─ Revenue: $99
└─ Cost per lead: $0.18 (higher due to trial + follow-up)
```

---

### Use Case 3: Failed Objection (No Conversion)

**Prospect**: David, startup founder (Segment: startup)
**Timeline**: 3 days
**Outcome**: Declined (no conversion)

```
DAY 1, 10:00 AM
└─ Opening: "David, saw you're building in fintech. We help with sales..."

DAY 1, 10:30 AM
└─ David: "Interesting. How much is this?"

DAY 1, 10:35 AM
└─ OFFER immediately (David asked about price)
   ├─ Generate: "For startups like yours, we have $49/month plan"
   └─ Send Stripe link

DAY 1, 4:00 PM [NO PAYMENT]
└─ Agent LISTEN_RESPONSE waiting (timeout approaching)

DAY 2, 10:00 AM [24H LATER, NO PAYMENT]
└─ RELANCE #1 fires
   ├─ Reason: "Payment pending 24h+, gentle reminder"
   ├─ Message: "Hey David! Just checking—any questions about the $49 plan?"
   └─ Send

DAY 2, 2:00 PM
└─ David: "Price is too high for us right now. We're pre-revenue."
   └─ Agent detects: OBJECTION (price)

DAY 2, 2:15 PM
└─ OBJECTION_HANDLING
   ├─ RAG search: "bootstrap startup low budget solution"
   ├─ Counter: "I get it—pre-revenue is tough. Most startups in your position..."
   ├─ Offer alternative: "What if we did $9/month? Limited features, see if it helps."
   └─ Send

DAY 2, 4:00 PM
└─ David: "Still too much. Maybe later when we raise."
   └─ Agent detects: OBJECTION NOT RESOLVED
   └─ Severity: 0.9/1.0 (strong resistance)

DAY 2, 4:15 PM
└─ RELANCE #2 scheduled (72 hours)
   ├─ Reason: "objection_persist"
   ├─ Type: "Winback" (low likelihood, but track)
   └─ Next contact: DAY 5, 4:15 PM

DAY 5, 4:15 PM
└─ RELANCE #2 sent
   ├─ Message: "Hey David! Just keeping you on our radar..."
   └─ No response expected

[END - ARCHIVED AS "declined"]

METRICS:
├─ Objections: 2 (price, budget)
├─ Objections resolved: 0
├─ Conversions: 0
├─ Final status: declined
└─ Cost per lead: $0.12 (only 2 LLM calls, no payment processing)

INSIGHT: Pre-revenue startups may not be ideal segment. Consider:
  • Qualify harder (only post-revenue)
  • Or create free tier track (Agent FOLLOW)
```

---

### Use Case 4: No Response Path (Cold Lead)

**Prospect**: Lisa, small business owner (Segment: mid_market)
**Timeline**: 10 days (3 relances)
**Outcome**: Archived (no response)

```
DAY 1, 9:00 AM
└─ Opening sent to Lisa
   └─ "Hey Lisa, saw you run a local service business..."

DAY 2, 9:00 AM [24H LATER]
└─ No response
   └─ RELANCE #1 fired
      ├─ Delay: 24 hours
      ├─ Message: "Hi Lisa! Did my message come through? Just following up..."
      └─ Send via WhatsApp

DAY 3, 9:00 AM [STILL NO RESPONSE]
└─ RELANCE #2 fired
   ├─ Delay: 48 hours (from day 1)
   ├─ Message: "Lisa, no worries if you're busy. Leaving this here in case useful..."
   └─ Send

DAY 5, 9:00 AM [NO RESPONSE]
└─ RELANCE #3 fired
   ├─ Delay: 96 hours
   ├─ Message: "Last one from me. If you ever need [solution], let's connect."
   └─ Send

DAY 10
└─ Max relances reached (3)
   ├─ Status: ARCHIVED
   └─ Reason: No response, not a fit

METRICS:
├─ Response rate: 0%
├─ Conversation turns: 0
├─ Cost: $0 (no LLM calls, just templates)
└─ Insight: Consider "no response" as signal to improve opening + segment
```

---

## Detailed Objection Decision Trees

### Objection Type: PRICE

```
Prospect says: "That's expensive"
    │
    ├─→ QUESTION: "Expensive vs. what?"
    │   (Understand reference point)
    │
    ├─ Response options:
    │  ├─ "Compared to [competitor]?"
    │  │  └─ RAG search: "competitor benchmarking"
    │  │
    │  ├─ "vs. current solution cost?"
    │  │  └─ RAG search: "cost of doing nothing"
    │  │
    │  └─ "vs. time saved?"
    │     └─ Show ROI calculation
    │
    ├─ OUTCOMES:
    │  ├─ "Yeah, you're more expensive"
    │  │  └─ Counter: "Here's why we cost more: [features/quality/support]"
    │  │     └─ If prospect accepts → OFFER
    │  │     └─ If still no → RELANCE (3 days)
    │  │
    │  └─ "I don't have the budget right now"
    │     └─ Counter: "When does your budget open?"
    │        ├─ "3 months" → "Let me send you a reminder"
    │        ├─ "6 months" → "Let me check in Q2"
    │        └─ "Never" → ARCHIVE (low intent)


DECISION MATRIX:
┌────────────────────┬──────────────────┬─────────────────────────────┐
│ Prospect Says      │ LLM Classification│ Recommended Counter          │
├────────────────────┼──────────────────┼─────────────────────────────┤
│ "It's too much"    │ price_absolute   │ ROI breakdown + case study   │
│ "Can't afford"     │ price_budget     │ Payment plan option          │
│ "Cheaper elsewhere" │ price_competitive│ Competitor comparison + diff │
│ "Not in budget"    │ price_timing     │ Trial or deferred payment    │
│ "Free alternative" │ price_feature    │ Feature comparison + support │
└────────────────────┴──────────────────┴─────────────────────────────┘

RAG QUERIES BY TYPE:
├─ price_absolute:   "How to justify premium pricing to budget-conscious buyer"
├─ price_budget:     "Phased rollout saving budget in first month"
├─ price_competitive: "Why we're different from [competitor]"
├─ price_timing:     "Payment plans and deferred billing options"
└─ price_feature:    "Feature comparison with free alternatives"

SUCCESS RATES (TARGET):
├─ price_absolute:   65%
├─ price_budget:     55%
├─ price_competitive: 70%
├─ price_timing:     80% (most flexible)
└─ price_feature:    60%

ESCALATION:
├─ 1st objection → Counter with RAG
├─ 2nd objection → Offer discount (5-10%)
├─ 3rd objection → Offer payment plan
└─ 4th objection → RELANCE (3 days, different angle)
```

---

### Objection Type: TRUST / CREDIBILITY

```
Prospect says: "I don't know if I trust you / your company"
    │
    ├─ ROOT CAUSES:
    │  ├─ New company (unheard of)
    │  ├─ No social proof (no reviews)
    │  ├─ No reference customers
    │  └─ Complex product (doesn't understand)
    │
    ├─ COUNTER STRATEGY:
    │  ├─ RAG search: "Testimonials and social proof"
    │  │  └─ Result: [Case study 1, 2, 3]
    │  │
    │  ├─ Offer: "Speak with a customer"
    │  │  └─ Introduce live reference
    │  │
    │  ├─ Offer: "Money-back guarantee"
    │  │  └─ "Try 30 days, full refund if not happy"
    │  │
    │  └─ Offer: "Personal onboarding"
    │     └─ "I'll setup your account myself"
    │
    └─ RESOLUTION:
       ├─ Prospect wants to "see it working" → TRIAL
       ├─ Prospect wants "proof" → CASE STUDY + TESTIMONIAL
       ├─ Prospect wants "safety" → MONEY-BACK GUARANTEE
       └─ Prospect wants "support" → PREMIUM PACKAGE

SEVERITY SCALE:
├─ Mild (0.3-0.5): "How long have you been around?"
│  └─ Counter: Show founder story + timeline
│
├─ Medium (0.5-0.7): "Can you prove this works?"
│  └─ Counter: Case studies + demo
│
└─ High (0.7-1.0): "I need to check with my boss / lawyer / accountant"
   └─ Escalate: Offer to present to decision maker
```

---

### Objection Type: URGENCY / TIMING

```
Prospect says: "We're not ready now" / "Let's revisit in Q2"
    │
    ├─ ANALYSIS: Prospect has interest but no immediate pain
    │
    ├─ STRATEGY #1: Create urgency
    │  ├─ "Early adopter discount expires in [7 days]"
    │  ├─ "Limited spots for this month"
    │  └─ "Implement before [industry event]"
    │
    ├─ STRATEGY #2: Reduce commitment
    │  ├─ "Start with 30-day pilot, no payment"
    │  ├─ "Try for free, upgrade later"
    │  └─ "Month-to-month commitment (not annual)"
    │
    └─ STRATEGY #3: Schedule follow-up
       ├─ "When is good timing?"
       ├─ "Put this on your Q2 evaluation list"
       └─ "I'll send you a reminder in March"

RESPONSE PATTERNS:
├─ "We'll revisit in [timeframe]"
│  └─ RELANCE: Schedule reminder for exact date
│     └─ Track in CRM: scheduled_relance = Q2 2026-04-01
│
├─ "I need to talk to [other stakeholder]"
│  └─ ACTION: "Can I present to them together?"
│     └─ Escalate to decision maker conversation
│
└─ "We're evaluating [competitor]"
   └─ Counter: "What are you looking for? Maybe we're a better fit"
      └─ Competitive differentiation

DECISION: When to escalate to RELANCE vs. continue OFFER
├─ Escalate to RELANCE if:
│  ├─ Timeline is > 30 days away
│  ├─ Prospect says "don't bother me"
│  └─ No urgency signals detected
│
└─ Continue OFFER if:
   ├─ Timeline is < 14 days
   ├─ Prospect shows interest ("sounds good, just not now")
   └─ Create urgency angle works
```

---

## Sequence Diagrams

### Sequence: Happy Path Conversion

```
Prospect         WhatsApp      Agent CLOSING      LLM        Stripe
   │                │                │            │           │
   │                │                │            │           │
   │◄───opening msg──│◄───generated───│◄──prompt──│           │
   │                │                │            │           │
   │                │                │            │           │
   │─response msg──→│                │            │           │
   │                │                │            │           │
   │                ├─classify intent─────────────→           │
   │                │◄─"positive"─────────────────           │
   │                │                │            │           │
   │                │─generate response────────────→          │
   │                │◄─"Here's how it works"────────          │
   │                │                │            │           │
   │◄───agent msg───│◄───formatted───│            │           │
   │                │                │            │           │
   │                │                │            │           │
   │─more messages─→│                │            │           │
   │                │                │            │           │
   │[3 conversation turns]
   │                │                │            │           │
   │                │                │            │           │
   │◄────offer msg──│◄─stripe link───│◄──format──│           │
   │   with link    │                │            │           │
   │                │                ├───create session───────→
   │                │                │◄──session URL────────
   │                │                │            │           │
   │──click link───→│                │            │           │
   │                │                │            │────open────│
   │                │                │            │  checkout  │
   │                │                │            │   page     │
   │──enter card───→│                │            │            │
   │──submit────────→│                │            │            │
   │                │                │            │    pay     │
   │                │                │            │            │
   │                │                │◄──webhook: completed────│
   │                │                │            │           │
   │                │──log conversion               │           │
   │                │──update CRM                   │           │
   │                │──trigger Agent FOLLOW ───→   │           │
   │                │                │            │           │
   ✓ CONVERTED     ✓               ✓              ✓           ✓
```

---

### Sequence: Objection Path

```
Prospect         WhatsApp      Agent CLOSING      LLM        RAG
   │                │                │            │           │
   │◄───opening msg──│◄───generated───│            │           │
   │                │                │            │           │
   │─response: no   │                │            │           │
   │  thanks, too   │                │            │           │
   │  expensive────→│                │            │           │
   │                │                ├─classify──→│           │
   │                │                │◄"objection"│           │
   │                │                │            │           │
   │                │                ├─extract objection       │
   │                │                │                        │
   │                │                ├─RAG search─────────────→
   │                │                │  "overcome price objec" │
   │                │ ◄──results──────│◄───[Video 1, 2, 3]─────│
   │                │ (save context)  │            │           │
   │                │                │            │           │
   │                │                ├─generate counter───────→
   │                │                │            │           │
   │◄─counter msg───│◄─formatted msg──│◄──"Here's ROI calc"────│
   │   with RAG     │    + proof      │            │           │
   │   references   │                │            │           │
   │                │                │            │           │
   │─prospect       │                │            │           │
   │ considers...   │                │            │           │
   │                │                │            │           │
   │─"OK maybe"────→│                │            │           │
   │                │                ├─classify: "interested"─│
   │                │                │◄──────────ok────────────│
   │                │                │            │           │
   │                │◄─continue       │            │           │
   │                │  conversation──→│            │           │
   │                │                 │            │           │
   ✓ OBJECTION      ✓               ✓             ✓           ✓
     RESOLVED
```

---

## Data Flow Diagrams

### Complete Data Flow: Lead → Conversion

```
UPSTREAM (Agent SÉDUCTION)
└─ Qualified Lead (prospect profile)
   ├─ name, email, phone, whatsapp_id
   ├─ segment, pain_points, qualification_score
   └─ budget_range

       ↓

AGENT CLOSING ENTRY POINT
├─ [1. INIT Node]
│  ├─ Input: ProspectProfile
│  ├─ Actions:
│  │  ├─ Fetch segment rules
│  │  ├─ RAG search (3 context videos)
│  │  ├─ LLM generate opening
│  │  ├─ Message queue send
│  │  └─ Update CRM (first_message_sent_at)
│  └─ Output: ClosingState (stage="opening_sent")
│
├─ [2. LISTEN_RESPONSE]
│  ├─ Wait for WhatsApp response (48h timeout)
│  ├─ Input: Message from prospect
│  ├─ Actions:
│  │  ├─ Add to message history
│  │  └─ Classify: positive|question|objection|disinterest
│  └─ Output: Route to CONVERSE or RELANCE
│
├─ [3. CONVERSE Node]
│  ├─ Multi-turn conversation
│  ├─ Input: Prospect message
│  ├─ Actions:
│  │  ├─ LLM classify intent
│  │  ├─ If objection → Route to OBJECTION_HANDLING
│  │  ├─ Else: Generate response
│  │  ├─ Message queue send
│  │  ├─ conversation_turns++
│  │  └─ Check: ready for offer?
│  └─ Output: ClosingState (stage="conversing" or "offer_presented")
│
├─ [4. OBJECTION_HANDLING Node]
│  ├─ Input: Detected objection
│  ├─ Actions:
│  │  ├─ Classify objection type (price|timing|trust|urgency)
│  │  ├─ RAG search counter-arguments
│  │  ├─ LLM generate counter-arg
│  │  ├─ Message queue send
│  │  └─ Add to detected_objections (resolved=False)
│  └─ Output: ClosingState (stage="objection_handling")
│     ├─ If resolved → Route to CONVERSE
│     └─ If not → Route to RELANCE
│
├─ [5. OFFER_PRESENTED Node]
│  ├─ Input: Prospect ready for pricing
│  ├─ Actions:
│  │  ├─ Calculate price (segment × qual_discount × objection_discount)
│  │  ├─ Stripe create_checkout_session
│  │  ├─ LLM generate offer message
│  │  ├─ Message queue send (with Stripe link)
│  │  └─ Start payment monitoring (webhook)
│  └─ Output: ClosingState (stage="payment_pending")
│
└─ [6. CONVERTED or RELANCE]
   ├─ If payment received:
   │  ├─ Stripe webhook: checkout.session.completed
   │  ├─ Update CRM (converted=True, final_amount, stripe_id)
   │  ├─ Log metrics (tokens, api_calls, rag_searches)
   │  ├─ Trigger Agent FOLLOW (onboarding)
   │  └─ ClosingState (stage="converted")
   │
   └─ If no payment:
      ├─ Scheduler: Check at 24h
      ├─ If still pending:
      │  ├─ RELANCE node sends reminder
      │  └─ Retry Stripe link
      └─ If declined:
         ├─ RELANCE scheduler (72h, 7d)
         └─ ClosingState (stage="declined")

DATABASE UPDATES:
├─ prospects table
│  ├─ first_message_sent_at ← INIT
│  ├─ status ← CONVERSE / OFFER / CONVERTED
│  └─ updated_at ← each node
│
├─ conversations table
│  ├─ messages[] ← append each LLM response
│  ├─ stage ← current stage
│  ├─ objections[] ← OBJECTION_HANDLING
│  └─ proposed_offer ← OFFER_PRESENTED
│
└─ closing_metrics table
   ├─ conversation_turns ← CONVERSE increments
   ├─ api_calls ← count each LLM/RAG call
   ├─ total_tokens ← sum from LLM
   ├─ conversion_achieved ← True/False
   └─ final_amount ← Stripe amount

EXTERNAL API CALLS:
├─ Anthropic (Claude)
│  ├─ /messages (generate, classify, extract)
│  └─ Cost tracking: tokens × $0.003/1k
│
├─ pgvector (RAG)
│  ├─ search (semantic similarity)
│  └─ No cost (local database)
│
├─ Twilio WhatsApp
│  ├─ /Messages (send)
│  └─ Cost: $0.01 per message (inbound) + $0.005 per (outbound)
│
├─ Stripe
│  ├─ /checkout/sessions (create, retrieve)
│  ├─ /webhooks (payment status)
│  └─ Cost: 2.9% + $0.30 per transaction
│
└─ LangFuse (observability)
   ├─ Log traces, spans, metrics
   └─ No cost (free tier)
```

---

## Error Handling & Recovery

### Error Scenarios

```
SCENARIO 1: LLM API Timeout
└─ Probability: 2%
├─ Detection: Exception: APITimeoutError after 30s
├─ Recovery:
│  ├─ Retry 1: Wait 5s, try again
│  ├─ Retry 2: Wait 10s, try again
│  ├─ Retry 3: Wait 30s, try again
│  └─ Max retries reached: Fall back to template
└─ Fallback: Use pre-written response template

SCENARIO 2: WhatsApp Send Fails
└─ Probability: 1%
├─ Detection: Twilio API error (network, rate limit)
├─ Recovery:
│  ├─ Exponential backoff: 1s, 2s, 4s
│  ├─ Retry up to 3x
│  └─ Max retries: Queue for manual review
└─ Action: Human reviews failed message in dashboard

SCENARIO 3: Stripe Session Creation Fails
└─ Probability: 0.5%
├─ Detection: stripe.error.APIError
├─ Recovery:
│  ├─ Retry immediately (session was likely created)
│  ├─ Verify session exists in database
│  └─ If exists: Send existing link
└─ Fallback: Manual Stripe link generation

SCENARIO 4: Payment Webhook Lost
└─ Probability: 0.1% (Stripe retries 3 days)
├─ Detection: Payment shows in Stripe, not in CRM
├─ Recovery:
│  ├─ Daily reconciliation: Query Stripe for unprocessed payments
│  ├─ Match session_id to prospect
│  ├─ Manually update CRM
│  └─ Trigger Agent FOLLOW
└─ Prevention: Idempotent webhook handler (check if already processed)

SCENARIO 5: Prospect Stuck in "Conversing"
└─ Probability: 5%
├─ Detection: State unchanged for 7 days
├─ Recovery:
│  ├─ Timeout trigger: Max conversation time = 7 days
│  ├─ Auto-escalate to RELANCE
│  └─ Send: "Still interested in solving [pain_point]?"
└─ Result: Either reengagement or archive

CODE EXAMPLE: Error Handling in Node
```python
async def node_with_retry(state: ClosingState, llm: LLMInterface):
    max_retries = 3
    backoff = [1, 5, 10]  # seconds

    for attempt in range(max_retries):
        try:
            response, tokens = await llm.generate(
                template="conversation_response",
                variables={...}
            )
            state.api_calls_count += 1
            return response

        except APITimeoutError as e:
            if attempt < max_retries - 1:
                wait_time = backoff[attempt]
                logger.warning(f"Timeout, retrying in {wait_time}s")
                await asyncio.sleep(wait_time)
            else:
                # Use template fallback
                logger.error(f"Max retries exceeded, using template")
                response = FALLBACK_TEMPLATES["conversation_response"]
                state.last_error = f"LLM timeout, used template"
                return response

        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            state.last_error = str(e)
            state.retry_count += 1
            if state.retry_count > state.max_retries:
                raise
            return None
```

---

## A/B Testing Matrix

### Experiment #1: Opening Message Variants

```
HYPOTHESIS: Personalized pain-point opening has higher response rate than generic

TEST DESIGN:
├─ Control (Template A): Generic "Hey [name], here's what we do"
│  └─ Expected response rate: 30%
│
├─ Test 1 (Template B): Specific pain-point angle
│  ├─ "Hey [name], saw you mention [pain_point] in your profile..."
│  └─ Expected response rate: 40% (33% lift)
│
└─ Test 2 (Template C): Social proof angle
   ├─ "Hey [name], we just helped [similar_company] with [pain_point]..."
   └─ Expected response rate: 45% (50% lift)

SAMPLE SIZE: 100 prospects per variant (300 total)
DURATION: 2 weeks
METRICS:
├─ Response rate (primary)
├─ Objection rate (secondary)
└─ Conversion rate (tertiary)

DECISION RULE:
├─ Winning variant: Highest response rate + statistical significance (p < 0.05)
└─ Rollout: 100% to new prospects
```

### Experiment #2: Objection Counter Variants

```
OBJECTION TYPE: PRICE (highest volume)

HYPOTHESIS: Specific ROI calculation beats vague value propositions

TEST DESIGN:
├─ Control: Generic "Here's the value you get"
├─ Test 1: Specific ROI calculation
│  ├─ "At current productivity, you're wasting $X/month"
│  ├─ "Our solution saves that amount in Y months"
│  └─ "That's ${saved} net benefit per year"
│
├─ Test 2: Comparison to competitor
│  ├─ "Most teams pay $X for [competitor]"
│  ├─ "We're Y% cheaper with Z% better features"
│  └─ "That's why {case} switched"
│
└─ Test 3: Payment plan option
   ├─ "Can't do lump sum? Let's break it up"
   ├─ "3 payments of $X starting in 30 days"
   └─ "Zero interest, zero risk"

SAMPLE SIZE: 50 prospects per variant (200 total)
DURATION: 4 weeks
METRIC: Objection resolution rate (resolved=True)

BASELINE: ~60% (current)
TARGET: 70%+ (meaningful lift)

ANALYSIS:
├─ Chi-square test for independence
├─ Logistic regression (objection type × variant)
└─ Effect size (Cohen's h)
```

### Experiment #3: Offer Timing

```
QUESTION: When is best time to present offer?

HYPOTHESIS: Offer after 2-3 conversation turns gets best conversion

CONTROL: Current logic (offer after turn 3)

TEST VARIANTS:
├─ Early (Turn 2):  "Let me show you pricing"
│  ├─ Pros: Faster deal cycle
│  └─ Cons: Might seem rushed
│
├─ Medium (Turn 3): Current approach
│  └─ Baseline
│
├─ Late (Turn 4):  Let conversation develop more
│  ├─ Pros: More rapport, context
│  └─ Cons: Longer sales cycle
│
└─ Intelligent: Detect "ready signals" in text
   ├─ Keywords: "cost", "pricing", "how much"
   └─ Offer immediately on signal

METRICS:
├─ Conversion rate (primary)
├─ Avg turns to offer
├─ Payment completion rate
└─ Customer lifetime value

SUCCESS CRITERIA:
└─ Variant with 5%+ conversion lift (vs. control)
```

---

## Configuration & Tuning

### Segment-Level Tuning

```json
{
  "high_value": {
    "max_conversation_turns": 5,
    "rag_search_top_k": 5,
    "offer_discount_max": 0.1,
    "relance_delays": [24, 72, 240],
    "expected_objections": ["price", "trust", "integration"],
    "premium_support": true
  },
  "mid_market": {
    "max_conversation_turns": 3,
    "rag_search_top_k": 3,
    "offer_discount_max": 0.15,
    "relance_delays": [24, 48, 168],
    "expected_objections": ["timing", "price", "urgency"],
    "premium_support": false
  },
  "startup": {
    "max_conversation_turns": 2,
    "rag_search_top_k": 2,
    "offer_discount_max": 0.25,
    "relance_delays": [24, 48],
    "expected_objections": ["price", "trust", "timing"],
    "trial_option": true,
    "trial_length_days": 30
  }
}
```

---

**Next Document**: Deployment & Operations

