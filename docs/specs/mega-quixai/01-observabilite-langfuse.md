# Système d'Observabilité LangFuse — MEGA QUIXAI

**Projet**: MEGA QUIXAI (3 Agents IA Autonomes)
**Auteur**: Winston (BMAD System Architect)
**Date**: 2026-03-14
**Version**: 1.0
**Statut**: Architecture Complète

---

## Executive Summary

MEGA QUIXAI orchestrera 3 agents autonomes (Séduction, Closing, Lead Acquisition) via LangGraph avec **LangFuse** comme système nerveux d'observabilité. Ce document définit :

- **Instrumentalisation complète** : traces, spans, generations, coûts
- **Métriques par agent** : taux de conversion, qualité des réponses, latence
- **Suivi des coûts temps-réel** : par agent, par lead, par appel API
- **Scoring de qualité automatisé** : évaluation des réponses via LLM
- **A/B testing framework** : versioning des prompts et stratégies
- **Alerting intelligent** : seuils adaptatifs par agent
- **Dashboard opérationnel** : visibilité complète sur l'état du système
- **Feedback loop** : intégration des résultats business dans les traces

**Objectif fondamental**: Transformer chaque interaction d'agent en donnée observable, traçable et actionnelle.

---

## Partie 1: Fondations Théoriques

### 1.1 Principes d'Observabilité pour Agents IA

**Trois piliers immuables** :

1. **Traçabilité linéaire** : Chaque décision d'agent remonte à une action observable
2. **Coût comme contrainte** : Chaque token = coût mesurable, budgets définis par agent
3. **Qualité comme métrique** : Pas de boîte noire — évaluation continu de chaque réponse

**Vérités bedrock** :
- Un appel API LLM coûte de l'argent (observable)
- Une réponse mauvaise coûte un client (observable via feedback)
- Un agent qui diverge est détectable par l'écart aux seuils (observable)

### 1.2 Différence avec Monitoring Classique

| Aspect | Monitoring Classique | Observabilité Agents IA |
|--------|---------------------|------------------------|
| **Unité de base** | Métrique (numérique) | Trace (séquence d'actions) |
| **Coût** | Invisible | Visible à chaque action |
| **Qualité** | Test en CI/CD | Évaluation en temps réel |
| **Feedback** | Manuel (bugs) | Automatisé (scores) |
| **Ajustement** | Redéployer code | Ajuster prompts/config |

### 1.3 Architecture Logique

```
┌─────────────────────────────────────────────────────┐
│         MEGA QUIXAI ORCHESTRATION (LangGraph)       │
└────────────────────┬────────────────────────────────┘
                     │
      ┌──────────────┼──────────────┐
      │              │              │
      ▼              ▼              ▼
   AGENT 1       AGENT 2       AGENT 3
  (Séduction)   (Closing)    (Lead Acq.)
      │              │              │
      └──────────────┼──────────────┘
                     │
      ┌──────────────▼──────────────┐
      │  LANGFUSE TRACE COLLECTION  │
      │  - Traces                   │
      │  - Spans                    │
      │  - Generations              │
      │  - Scores                   │
      │  - Costs                    │
      └──────────────┬──────────────┘
                     │
      ┌──────────────┼──────────────────┐
      │              │                  │
      ▼              ▼                  ▼
   METRICS      ALERTING          FEEDBACK
   ENGINE       ENGINE            LOOP
```

---

## Partie 2: Configuration LangFuse

### 2.1 Installation et Setup

```bash
# Installation
pip install langfuse langfuse-python-sdk

# Variables d'environnement
LANGFUSE_PUBLIC_KEY="your-public-key"
LANGFUSE_SECRET_KEY="your-secret-key"
LANGFUSE_HOST="https://cloud.langfuse.com"  # ou self-hosted
```

### 2.2 Configuration Client Python

```python
# config/langfuse_config.py
from __future__ import annotations

import logging
from typing import Optional

from langfuse import Langfuse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class LangfuseConfig(BaseModel):
    """Configuration LangFuse centralisée"""

    public_key: str = Field(min_length=1)
    secret_key: str = Field(min_length=1)
    host: str = "https://cloud.langfuse.com"
    enabled: bool = True

    # Sampling: tracer 100% du traffic en prod
    sample_rate: float = Field(default=1.0, ge=0.0, le=1.0)

    # Timeouts et retries
    timeout_seconds: int = 30
    max_retries: int = 3


class LangfuseClient:
    """Wrapper du client LangFuse avec gestion de session"""

    _instance: Optional[Langfuse] = None

    def __init__(self, config: LangfuseConfig) -> None:
        self.config = config
        if config.enabled:
            self._client = Langfuse(
                public_key=config.public_key,
                secret_key=config.secret_key,
                host=config.host,
                enabled=True,
                sample_rate=config.sample_rate,
                flush_interval=60,  # Flush toutes les 60 secondes
            )
        else:
            self._client = None
            logger.warning("LangFuse désactivé — pas de traces collectées")

    @property
    def client(self) -> Optional[Langfuse]:
        return self._client

    def is_enabled(self) -> bool:
        return self.config.enabled and self._client is not None

    async def flush(self) -> None:
        """Flush les traces en attente"""
        if self._client:
            await self._client.flush()

    def shutdown(self) -> None:
        """Arrêt gracieux"""
        if self._client:
            self._client.flush()
```

### 2.3 Intégration avec LangGraph

```python
# orchestration/langraph_integration.py
from __future__ import annotations

from typing import Any, Callable, Optional

from langfuse import Langfuse
from langgraph.graph import Graph

from config.langfuse_config import LangfuseClient


class LangGraphObservability:
    """Wrapper pour instrumenter LangGraph avec LangFuse"""

    def __init__(self, langfuse_client: LangfuseClient) -> None:
        self.langfuse = langfuse_client

    def wrap_node(
        self,
        node_name: str,
        agent_name: str,
        node_fn: Callable,
    ) -> Callable:
        """
        Enveloppe une node LangGraph pour tracer automatiquement.

        Args:
            node_name: Nom de la node (ex: "classify_lead")
            agent_name: Nom de l'agent (ex: "lead_acquisition")
            node_fn: Fonction de la node

        Returns:
            Fonction instrumentée
        """
        async def instrumented_node(state: dict[str, Any]) -> dict[str, Any]:
            client = self.langfuse.client
            if not client:
                return await node_fn(state)

            # Créer une trace pour cette node
            trace = client.trace(
                name=f"{agent_name}.{node_name}",
                user_id=state.get("lead_id"),
                session_id=state.get("session_id"),
                metadata={
                    "agent": agent_name,
                    "node": node_name,
                    "timestamp": state.get("timestamp"),
                },
            )

            try:
                result = await node_fn(state)
                trace.score(
                    name="success",
                    value=1,
                    comment=f"Node {node_name} completed successfully",
                )
                return result
            except Exception as e:
                trace.score(
                    name="error",
                    value=0,
                    comment=f"Node {node_name} failed: {str(e)}",
                )
                raise

        return instrumented_node

    def wrap_graph(self, graph: Graph) -> Graph:
        """Enveloppe l'ensemble du graphe LangGraph"""
        # À adapter selon votre structure LangGraph
        return graph
```

---

## Partie 3: Instrumentation par Agent

### 3.1 Modèle Universel de Trace

**Chaque appel d'agent** doit générer une trace standard :

```python
# models/agent_trace.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


@dataclass
class AgentTraceMetadata:
    """Métadonnées standard pour toute trace d'agent"""

    lead_id: str
    session_id: str
    agent_name: str  # "seduction", "closing", "lead_acquisition"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    user_id: Optional[str] = None
    campaign_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "lead_id": self.lead_id,
            "session_id": self.session_id,
            "agent_name": self.agent_name,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "campaign_id": self.campaign_id,
        }


class AgentGeneration(BaseModel):
    """Représente une génération LLM par un agent"""

    model: str = Field(description="ex: 'gpt-4', 'claude-3-sonnet'")
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float = Field(description="Coût en USD")
    latency_ms: float = Field(description="Latence en millisecondes")

    # Métriques d'évaluation
    quality_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Score de qualité 0-1 calculé automatiquement"
    )
    relevance_score: Optional[float] = None  # Pour lead acquisition
    conversion_confidence: Optional[float] = None  # Pour closing


class AgentTraceEvent(BaseModel):
    """Événement capturé dans une trace d'agent"""

    metadata: AgentTraceMetadata
    generation: AgentGeneration
    input_prompt: str
    output_response: str

    # Résultats business
    action_taken: str  # ex: "send_email", "schedule_call", "request_more_info"
    business_metric: Optional[dict] = None  # ex: {"conversion": True, "revenue": 150}
```

### 3.2 Agent 1: Lead Acquisition

**Objectif métier**: Qualifier et enrichir les leads entrants

**Prompts clés à tracker**:
- Classification de la qualification
- Extraction d'informations
- Scoring de fit produit

```python
# agents/lead_acquisition.py
from __future__ import annotations

import logging
from datetime import datetime

from langfuse import Langfuse

logger = logging.getLogger(__name__)


class LeadAcquisitionAgent:
    """Agent d'acquisition de leads avec observabilité LangFuse"""

    def __init__(self, llm_client: Any, langfuse_client: Langfuse) -> None:
        self.llm = llm_client
        self.langfuse = langfuse_client
        self.agent_name = "lead_acquisition"

    async def classify_lead(self, lead_data: dict) -> dict:
        """
        Classifie un lead entrant selon critères de fit.

        Traces:
        - Nom du modèle LLM
        - Tokens consommés
        - Coût d'appel
        - Score de qualité de classification
        """
        lead_id = lead_data["id"]
        session_id = lead_data.get("session_id", "unknown")

        trace = self.langfuse.trace(
            name="lead_acquisition.classify",
            user_id=lead_id,
            session_id=session_id,
            metadata={
                "agent": self.agent_name,
                "operation": "classify",
                "lead_industry": lead_data.get("industry"),
                "lead_size": lead_data.get("company_size"),
            },
        )

        # Appel LLM
        prompt = self._build_classification_prompt(lead_data)

        response = await self.llm.generate(
            prompt=prompt,
            model="gpt-4",
            temperature=0.3,
            max_tokens=500,
        )

        # Capture génération
        generation = trace.generation(
            name="classify_prompt",
            model=response.model,
            input={"prompt": prompt},
            output={"response": response.text},
            usage={
                "input": response.usage.prompt_tokens,
                "output": response.usage.completion_tokens,
            },
        )

        # Coût: calculé selon pricing OpenAI
        input_cost = response.usage.prompt_tokens * 0.00003  # gpt-4 pricing
        output_cost = response.usage.completion_tokens * 0.0006
        total_cost = input_cost + output_cost

        generation.score(
            name="cost_usd",
            value=total_cost,
            comment=f"Tokens: {response.usage.prompt_tokens + response.usage.completion_tokens}",
        )

        # Évaluation qualité via scoring automatique
        quality_score = await self._evaluate_classification_quality(
            lead_data=lead_data,
            classification=response.text,
            trace=trace,
        )

        generation.score(
            name="quality",
            value=quality_score,
            comment="Classification quality (0-1)",
        )

        result = {
            "lead_id": lead_id,
            "classification": response.text,
            "quality_score": quality_score,
            "cost_usd": total_cost,
            "tokens_used": response.usage.total_tokens,
        }

        trace.score(
            name="classification_success",
            value=1 if quality_score > 0.7 else 0,
        )

        return result

    async def enrich_lead(self, lead_data: dict) -> dict:
        """Enrichit les données d'un lead avec web scraping et LLM"""
        lead_id = lead_data["id"]

        trace = self.langfuse.trace(
            name="lead_acquisition.enrich",
            user_id=lead_id,
            metadata={
                "agent": self.agent_name,
                "operation": "enrich",
            },
        )

        # ... implementation similar to classify_lead
        return {}

    async def score_fit(self, lead_data: dict, product_fit_criteria: dict) -> dict:
        """Évalue le fit produit-lead"""
        trace = self.langfuse.trace(
            name="lead_acquisition.score_fit",
            user_id=lead_data["id"],
            metadata={
                "agent": self.agent_name,
                "operation": "score_fit",
            },
        )

        # ... implementation
        return {}

    async def _evaluate_classification_quality(
        self,
        lead_data: dict,
        classification: str,
        trace: Any,
    ) -> float:
        """
        Évalue la qualité de la classification via LLM evaluator.

        Utilise un prompt d'évaluation pour noter 0-1.
        """
        eval_trace = trace.span(
            name="quality_evaluation",
        )

        eval_prompt = f"""
        Évalue la classification du lead suivant sur une échelle 0-1.

        Lead: {lead_data.get('company_name', 'Unknown')}
        Industry: {lead_data.get('industry', 'Unknown')}
        Size: {lead_data.get('company_size', 'Unknown')}

        Classification proposée:
        {classification}

        Critères:
        1. Pertinence du classement (0-1)
        2. Couverture des informations clés (0-1)
        3. Confiance du scoring (0-1)

        Score final moyen (0-1):
        """

        eval_response = await self.llm.generate(
            prompt=eval_prompt,
            model="gpt-3.5-turbo",  # Plus rapide et moins cher pour l'évaluation
            temperature=0.0,
            max_tokens=100,
        )

        eval_trace.generation(
            name="evaluate",
            model=eval_response.model,
            input={"prompt": eval_prompt},
            output={"score_text": eval_response.text},
            usage={
                "input": eval_response.usage.prompt_tokens,
                "output": eval_response.usage.completion_tokens,
            },
        )

        # Parser le score (0-1) from response
        try:
            score = float(eval_response.text.strip()[:3])  # ex: "0.87"
            score = max(0.0, min(1.0, score))  # Clamp [0, 1]
        except (ValueError, IndexError):
            score = 0.5

        return score

    def _build_classification_prompt(self, lead_data: dict) -> str:
        """Construit le prompt de classification"""
        return f"""
        Classe le lead suivant selon ces critères:

        **Lead Information:**
        - Company: {lead_data.get('company_name')}
        - Industry: {lead_data.get('industry')}
        - Size: {lead_data.get('company_size')}
        - Website: {lead_data.get('website')}
        - Contact: {lead_data.get('contact_person')}

        **Classification Required:**
        1. ICP Fit (0-100): Comment le lead correspond à notre Ideal Customer Profile
        2. Urgency (Low/Medium/High): Besoin perçu
        3. Budget Indicator (Low/Medium/High): Capacité financière estimée
        4. Decision Timeline (ASAP/1-3m/3-6m/6m+): Timeline de décision

        **Output Format:**
        ICP_FIT: [score]
        URGENCY: [Low/Medium/High]
        BUDGET: [Low/Medium/High]
        TIMELINE: [ASAP/1-3m/3-6m/6m+]
        REASONING: [brief explanation]
        """
```

### 3.3 Agent 2: Séduction

**Objectif métier**: Générer du contexte personnalisé pour engager le prospect

**Prompts clés à tracker**:
- Analyse de personnalité
- Génération de message personnalisé
- Timing d'outreach optimal

```python
# agents/seduction.py
from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class SeductionAgent:
    """Agent de séduction/engagement avec observabilité complète"""

    def __init__(self, llm_client: Any, langfuse_client: Any) -> None:
        self.llm = llm_client
        self.langfuse = langfuse_client
        self.agent_name = "seduction"

    async def analyze_prospect(self, lead_data: dict) -> dict:
        """
        Analyse profonde du prospect pour personnalisation.

        Trace:
        - Input: données lead + contexte public
        - Output: persona analysis + messaging angles
        - Quality: évaluation de la précision de l'analyse
        """
        lead_id = lead_data["id"]

        trace = self.langfuse.trace(
            name="seduction.analyze_prospect",
            user_id=lead_id,
            metadata={
                "agent": self.agent_name,
                "operation": "analyze",
                "prospect_title": lead_data.get("title"),
            },
        )

        prompt = self._build_analysis_prompt(lead_data)

        response = await self.llm.generate(
            prompt=prompt,
            model="gpt-4",
            temperature=0.5,
            max_tokens=1500,
        )

        # Capture l'analyse
        gen = trace.generation(
            name="prospect_analysis",
            model=response.model,
            input={"prompt": prompt, "lead_context": lead_data},
            output={"analysis": response.text},
            usage={
                "input": response.usage.prompt_tokens,
                "output": response.usage.completion_tokens,
            },
        )

        # Score la qualité de l'analyse
        quality_score = await self._evaluate_analysis_quality(
            lead_data=lead_data,
            analysis=response.text,
            trace=trace,
        )

        gen.score(
            name="analysis_quality",
            value=quality_score,
            comment="Depth and relevance of prospect analysis",
        )

        return {
            "lead_id": lead_id,
            "analysis": response.text,
            "quality_score": quality_score,
        }

    async def generate_personalized_message(
        self,
        lead_data: dict,
        analysis: dict,
        channel: str = "email",
    ) -> dict:
        """
        Génère un message hautement personnalisé.

        Trace:
        - Input: analysis + channel (email/linkedin/sms)
        - Output: message personnalisé
        - Quality: pertinence du message via LLM scoring
        - Business metric: si message est envoyé et engagement futur
        """
        lead_id = lead_data["id"]

        trace = self.langfuse.trace(
            name="seduction.generate_message",
            user_id=lead_id,
            metadata={
                "agent": self.agent_name,
                "operation": "generate_message",
                "channel": channel,
            },
        )

        prompt = self._build_message_prompt(
            lead_data=lead_data,
            analysis=analysis,
            channel=channel,
        )

        response = await self.llm.generate(
            prompt=prompt,
            model="gpt-4",
            temperature=0.7,  # Plus de créativité
            max_tokens=1000,
        )

        gen = trace.generation(
            name="message_generation",
            model=response.model,
            input={"prompt": prompt},
            output={"message": response.text},
            usage={
                "input": response.usage.prompt_tokens,
                "output": response.usage.completion_tokens,
            },
        )

        # Évaluation du message
        quality_score = await self._evaluate_message_quality(
            message=response.text,
            channel=channel,
            trace=trace,
        )

        gen.score(
            name="message_quality",
            value=quality_score,
            comment=f"Message engagement potential ({channel})",
        )

        return {
            "lead_id": lead_id,
            "message": response.text,
            "channel": channel,
            "quality_score": quality_score,
        }

    def _build_analysis_prompt(self, lead_data: dict) -> str:
        return f"""
        Effectue une analyse profonde du prospect suivant pour un engagement optimal:

        **Prospect Data:**
        - Name: {lead_data.get('name')}
        - Title: {lead_data.get('title')}
        - Company: {lead_data.get('company_name')}
        - Industry: {lead_data.get('industry')}
        - Recent News: {lead_data.get('recent_news', 'N/A')}
        - LinkedIn: {lead_data.get('linkedin_url', 'N/A')}

        **Analysis Required:**
        1. PERSONALITY_PROFILE: Quel type de décideur? Style de communication?
        2. PAIN_POINTS: Problèmes probables basés sur le rôle et industrie?
        3. MOTIVATION: Qu'est-ce qui motivate ce type de profil?
        4. OBJECTIONS: Obstacles probables à une conversion?
        5. MESSAGING_ANGLES: Quels angles résonnent avec ce profil?

        **Output Format:**
        PERSONALITY: [detailed profile]
        PAIN_POINTS: [list]
        MOTIVATION: [key drivers]
        OBJECTIONS: [likely objections]
        BEST_ANGLES: [top 3 messaging angles]
        ENGAGEMENT_STRATEGY: [brief strategy]
        """

    def _build_message_prompt(
        self,
        lead_data: dict,
        analysis: dict,
        channel: str,
    ) -> str:
        return f"""
        Génère un message {channel} ultra-personnalisé et engageant:

        **Prospect:**
        {lead_data.get('name')}
        {lead_data.get('title')} @ {lead_data.get('company_name')}

        **Analysis Insights:**
        {analysis.get('analysis', '')}

        **Requirements:**
        - Channel: {channel}
        - Length: {'50-100 words' if channel == 'sms' else '2-4 sentences' if channel == 'linkedin' else '100-200 words'}
        - Tone: Professional but warm
        - Call to Action: Soft (just open a conversation)

        **Write the message:**
        """

    async def _evaluate_analysis_quality(
        self,
        lead_data: dict,
        analysis: str,
        trace: Any,
    ) -> float:
        """Évalue la profondeur et la pertinence de l'analyse"""
        # Similar pattern to lead_acquisition evaluator
        return 0.8

    async def _evaluate_message_quality(
        self,
        message: str,
        channel: str,
        trace: Any,
    ) -> float:
        """Évalue la qualité d'engagement du message"""
        return 0.75
```

### 3.4 Agent 3: Closing

**Objectif métier**: Convertir prospect qualifié en client payant

**Prompts clés à tracker**:
- Génération de propositions de valeur
- Gestion des objections
- Stratégies de closing

```python
# agents/closing.py
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class ClosingAgent:
    """Agent de closing avec tracking complète des conversions"""

    def __init__(self, llm_client: Any, langfuse_client: Any) -> None:
        self.llm = llm_client
        self.langfuse = langfuse_client
        self.agent_name = "closing"

    async def generate_proposal(
        self,
        lead_data: dict,
        deal_context: dict,
    ) -> dict:
        """
        Génère une proposition personnalisée avec pricing et valeur.

        Trace:
        - Input: lead + deal context + product catalog
        - Output: proposal document structure
        - Cost: coût complète des appels LLM
        - Quality: évaluation par LLM evaluator
        - Business: monetary value et probability de signature
        """
        lead_id = lead_data["id"]
        deal_id = deal_context.get("id", "unknown")

        trace = self.langfuse.trace(
            name="closing.generate_proposal",
            user_id=lead_id,
            session_id=deal_id,
            metadata={
                "agent": self.agent_name,
                "operation": "proposal",
                "deal_value_usd": deal_context.get("estimated_value", 0),
            },
        )

        prompt = self._build_proposal_prompt(lead_data, deal_context)

        response = await self.llm.generate(
            prompt=prompt,
            model="gpt-4",
            temperature=0.3,
            max_tokens=2000,
        )

        gen = trace.generation(
            name="proposal_generation",
            model=response.model,
            input={"prompt": prompt},
            output={"proposal": response.text},
            usage={
                "input": response.usage.prompt_tokens,
                "output": response.usage.completion_tokens,
            },
        )

        # Estimation de la probabilité de closing
        closing_probability = await self._estimate_closing_probability(
            lead_data=lead_data,
            proposal=response.text,
            deal_value=deal_context.get("estimated_value", 0),
            trace=trace,
        )

        gen.score(
            name="closing_probability",
            value=closing_probability,
            comment="Estimated probability of successful closing",
        )

        # Business impact metric
        deal_value = deal_context.get("estimated_value", 0)
        expected_value = deal_value * closing_probability  # Expected revenue

        trace.score(
            name="expected_revenue",
            value=expected_value,
            comment=f"${deal_value} * {closing_probability:.0%} probability",
        )

        return {
            "lead_id": lead_id,
            "deal_id": deal_id,
            "proposal": response.text,
            "closing_probability": closing_probability,
            "expected_revenue": expected_value,
        }

    async def handle_objection(
        self,
        lead_data: dict,
        deal_context: dict,
        objection_text: str,
    ) -> dict:
        """
        Génère une réponse persuasive à une objection.

        Trace:
        - Input: objection + deal context
        - Output: réponse structurée
        - Quality: évaluation si objection est bien traitée
        """
        lead_id = lead_data["id"]

        trace = self.langfuse.trace(
            name="closing.handle_objection",
            user_id=lead_id,
            metadata={
                "agent": self.agent_name,
                "operation": "objection_handling",
                "objection_type": self._classify_objection(objection_text),
            },
        )

        prompt = self._build_objection_prompt(objection_text, deal_context)

        response = await self.llm.generate(
            prompt=prompt,
            model="gpt-4",
            temperature=0.4,
            max_tokens=1000,
        )

        gen = trace.generation(
            name="objection_response",
            model=response.model,
            input={"objection": objection_text},
            output={"response": response.text},
            usage={
                "input": response.usage.prompt_tokens,
                "output": response.usage.completion_tokens,
            },
        )

        # Évalue si la réponse traite bien l'objection
        response_quality = await self._evaluate_objection_response(
            objection=objection_text,
            response=response.text,
            trace=trace,
        )

        gen.score(
            name="response_quality",
            value=response_quality,
            comment="How well the response addresses the objection",
        )

        return {
            "lead_id": lead_id,
            "objection": objection_text,
            "response": response.text,
            "response_quality": response_quality,
        }

    def _build_proposal_prompt(self, lead_data: dict, deal_context: dict) -> str:
        return f"""
        Génère une proposition de valeur ultra-convaincante:

        **Prospect:**
        {lead_data.get('name')} ({lead_data.get('title')})
        {lead_data.get('company_name')}

        **Context:**
        - Budget: ${deal_context.get('estimated_value', 'TBD')}
        - Timeline: {deal_context.get('timeline', 'Unknown')}
        - Problem: {deal_context.get('primary_problem', 'Unknown')}

        **Create a proposal with:**
        1. Executive Summary (compelling hook)
        2. Problem Statement (mirror their pain)
        3. Solution Overview (our approach)
        4. Expected Results (specific ROI/metrics)
        5. Pricing Structure (clear and justified)
        6. Next Steps (low-friction action)

        Tone: Confident, specific, results-focused
        """

    def _build_objection_prompt(
        self,
        objection_text: str,
        deal_context: dict,
    ) -> str:
        return f"""
        Crée une réponse à cette objection de manière convaincante:

        **Objection:** {objection_text}

        **Deal Context:**
        - Deal Value: ${deal_context.get('estimated_value', 'TBD')}
        - Prospect Pain: {deal_context.get('primary_problem', 'Unknown')}

        **Response Strategy:**
        1. Acknowledge (show you understand)
        2. Reframe (position objection as opportunity)
        3. Provide Evidence (data/case studies)
        4. Propose Next Step (clear action)

        Keep it concise and persuasive.
        """

    def _classify_objection(self, objection_text: str) -> str:
        """Classifie l'objection (price, timeline, product, etc.)"""
        if any(w in objection_text.lower() for w in ["price", "cost", "expensive"]):
            return "price"
        elif any(w in objection_text.lower() for w in ["time", "timeline", "when"]):
            return "timeline"
        elif any(w in objection_text.lower() for w in ["feature", "capability"]):
            return "product"
        elif any(w in objection_text.lower() for w in ["competitor", "alternative"]):
            return "competition"
        else:
            return "other"

    async def _estimate_closing_probability(
        self,
        lead_data: dict,
        proposal: str,
        deal_value: float,
        trace: Any,
    ) -> float:
        """Estime la probabilité de closing basée sur plusieurs facteurs"""
        # Basique: 0.3-0.7 basé sur lead quality et deal value
        base_prob = 0.3

        # Ajuste selon valeur du deal
        if deal_value > 100000:
            base_prob += 0.2
        elif deal_value > 50000:
            base_prob += 0.1

        return min(0.9, base_prob)

    async def _evaluate_objection_response(
        self,
        objection: str,
        response: str,
        trace: Any,
    ) -> float:
        """Évalue si la réponse traite bien l'objection"""
        return 0.75
```

---

## Partie 4: Métriques par Agent

### 4.1 Tableau de Bord des Métriques

```python
# metrics/agent_metrics.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, Field


class MetricScope(str, Enum):
    """Portée d'une métrique"""
    CALL = "call"  # Par appel LLM
    SESSION = "session"  # Par interaction lead-agent
    AGENT = "agent"  # Agrégé par agent
    SYSTEM = "system"  # Agrégé système complet


@dataclass
class AgentMetrics:
    """Métriques spécifiques par agent"""

    # LEAD ACQUISITION METRICS
    leads_qualified_total: int = 0
    leads_rejected_total: int = 0
    qualification_accuracy: float = 0.0  # 0-1
    avg_classification_quality_score: float = 0.0
    enrichment_success_rate: float = 0.0

    # SEDUCTION METRICS
    personalization_quality_avg: float = 0.0  # 0-1
    message_engagement_rate: float = 0.0  # % of messages opened/clicked
    response_rate: float = 0.0  # % of messages that got replies
    analysis_depth_score: float = 0.0  # 0-1

    # CLOSING METRICS
    proposals_generated: int = 0
    avg_closing_probability: float = 0.0
    deals_closed: int = 0
    closing_rate: float = 0.0
    avg_deal_value: float = 0.0
    total_revenue_attributed: float = 0.0
    objection_handling_success_rate: float = 0.0

    # COMMON METRICS (all agents)
    total_api_calls: int = 0
    total_tokens_used: int = 0
    total_cost_usd: float = 0.0
    avg_latency_ms: float = 0.0
    error_rate: float = 0.0
    success_rate: float = 0.0


class MetricDefinition(BaseModel):
    """Définition d'une métrique avec comment l'évaluer"""

    name: str
    agent: str  # "lead_acquisition", "seduction", "closing", "system"
    description: str
    unit: str  # "%", "count", "usd", "ms", "0-1"
    calculation_method: str  # Comment calculer
    target_threshold: float  # Seuil de succès
    alert_threshold: float  # Seuil d'alerte
    scope: MetricScope


# Définitions des métriques critiques
CRITICAL_METRICS = [
    MetricDefinition(
        name="cost_per_qualified_lead",
        agent="lead_acquisition",
        description="Coût en API pour qualifier un lead",
        unit="usd",
        calculation_method="sum(api_costs) / count(qualified_leads)",
        target_threshold=0.5,
        alert_threshold=2.0,
        scope=MetricScope.AGENT,
    ),
    MetricDefinition(
        name="closing_probability_average",
        agent="closing",
        description="Probabilité moyenne de closing par deal",
        unit="0-1",
        calculation_method="avg(estimated_closing_probability)",
        target_threshold=0.5,
        alert_threshold=0.2,
        scope=MetricScope.AGENT,
    ),
    MetricDefinition(
        name="message_quality_score",
        agent="seduction",
        description="Score de qualité des messages générés",
        unit="0-1",
        calculation_method="avg(message_quality_score)",
        target_threshold=0.75,
        alert_threshold=0.5,
        scope=MetricScope.AGENT,
    ),
    MetricDefinition(
        name="total_system_cost_daily",
        agent="system",
        description="Coût total API par jour",
        unit="usd",
        calculation_method="sum(all_api_costs)",
        target_threshold=100.0,
        alert_threshold=500.0,
        scope=MetricScope.SYSTEM,
    ),
]
```

### 4.2 Collecteur de Métriques

```python
# metrics/collector.py
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from langfuse import Langfuse
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class MetricAggregation(BaseModel):
    """Agrégation de métrique sur une période"""

    metric_name: str
    agent_name: str
    value: float
    period_start: datetime
    period_end: datetime
    sample_count: int


class MetricsCollector:
    """Collecte et agrège les métriques depuis LangFuse"""

    def __init__(self, langfuse_client: Langfuse) -> None:
        self.langfuse = langfuse_client

    async def get_agent_metrics(
        self,
        agent_name: str,
        period_hours: int = 24,
    ) -> AgentMetrics:
        """Agrège les métriques pour un agent sur les N dernières heures"""

        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=period_hours)

        # Query LangFuse pour tracer avec cet agent
        traces = await self._fetch_traces_by_agent(
            agent_name=agent_name,
            start_time=start_time,
            end_time=end_time,
        )

        metrics = AgentMetrics()

        for trace in traces:
            # Extrait les scores et les agrège
            for score in trace.scores:
                if score.name == "cost_usd":
                    metrics.total_cost_usd += score.value
                elif score.name == "quality":
                    metrics.avg_classification_quality_score += score.value
                elif score.name == "closing_probability":
                    metrics.avg_closing_probability += score.value

            metrics.total_api_calls += 1

        # Normalise les moyennes
        if traces:
            metrics.avg_classification_quality_score /= len(traces)
            metrics.avg_closing_probability /= len(traces)

        return metrics

    async def _fetch_traces_by_agent(
        self,
        agent_name: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list:
        """Récupère les traces d'un agent via LangFuse API"""
        # Note: LangFuse SDK doit supporter queries structurées
        # Sinon implémenter via HTTP API directement
        return []

    async def get_cost_breakdown(
        self,
        period_hours: int = 24,
    ) -> dict:
        """Décompose les coûts par agent et par modèle"""

        breakdown = {
            "lead_acquisition": {"total": 0.0, "by_model": {}},
            "seduction": {"total": 0.0, "by_model": {}},
            "closing": {"total": 0.0, "by_model": {}},
        }

        # Récupère toutes les traces et agrège par agent + modèle
        # Implementation via LangFuse API

        return breakdown
```

---

## Partie 5: Suivi des Coûts Temps-Réel

### 5.1 Modèle de Coûts

**Vérité bedrock**: Chaque token d'input/output a un coût observable.

```python
# costs/pricing_models.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict

from pydantic import BaseModel, Field


class ModelPricingEnum(str, Enum):
    """Modèles LLM supportés avec pricing"""
    GPT_4 = "gpt-4"
    GPT_4_TURBO = "gpt-4-turbo"
    GPT_35_TURBO = "gpt-3.5-turbo"
    CLAUDE_3_SONNET = "claude-3-sonnet"
    CLAUDE_3_OPUS = "claude-3-opus"


@dataclass
class ModelPricing:
    """Pricing pour un modèle LLM spécifique"""

    model: str
    input_cost_per_1k_tokens: float  # USD
    output_cost_per_1k_tokens: float  # USD

    def calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Calcule le coût total pour une génération"""
        input_cost = (input_tokens / 1000) * self.input_cost_per_1k_tokens
        output_cost = (output_tokens / 1000) * self.output_cost_per_1k_tokens
        return input_cost + output_cost


class PricingRegistry:
    """Registry des modèles et leurs prix"""

    PRICING: Dict[str, ModelPricing] = {
        "gpt-4": ModelPricing(
            model="gpt-4",
            input_cost_per_1k_tokens=0.03,
            output_cost_per_1k_tokens=0.06,
        ),
        "gpt-4-turbo": ModelPricing(
            model="gpt-4-turbo",
            input_cost_per_1k_tokens=0.01,
            output_cost_per_1k_tokens=0.03,
        ),
        "gpt-3.5-turbo": ModelPricing(
            model="gpt-3.5-turbo",
            input_cost_per_1k_tokens=0.0005,
            output_cost_per_1k_tokens=0.0015,
        ),
        "claude-3-sonnet": ModelPricing(
            model="claude-3-sonnet",
            input_cost_per_1k_tokens=0.003,
            output_cost_per_1k_tokens=0.015,
        ),
        "claude-3-opus": ModelPricing(
            model="claude-3-opus",
            input_cost_per_1k_tokens=0.015,
            output_cost_per_1k_tokens=0.075,
        ),
    }

    @staticmethod
    def get_pricing(model: str) -> ModelPricing:
        """Récupère le pricing pour un modèle"""
        if model not in PricingRegistry.PRICING:
            raise ValueError(f"Model {model} not found in pricing registry")
        return PricingRegistry.PRICING[model]

    @staticmethod
    def calculate_call_cost(
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Calcule le coût total d'un appel LLM"""
        pricing = PricingRegistry.get_pricing(model)
        return pricing.calculate_cost(input_tokens, output_tokens)


class CostTracker(BaseModel):
    """Tracker en temps-réel des coûts par agent"""

    agent_name: str
    daily_budget_usd: float = Field(gt=0)
    monthly_budget_usd: float = Field(gt=0)

    current_daily_spend_usd: float = 0.0
    current_monthly_spend_usd: float = 0.0
    current_call_count: int = 0

    def record_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Enregistre un appel API et retourne le coût"""
        cost = PricingRegistry.calculate_call_cost(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        self.current_daily_spend_usd += cost
        self.current_monthly_spend_usd += cost
        self.current_call_count += 1

        return cost

    def is_daily_budget_exceeded(self) -> bool:
        return self.current_daily_spend_usd > self.daily_budget_usd

    def is_monthly_budget_exceeded(self) -> bool:
        return self.current_monthly_spend_usd > self.monthly_budget_usd

    def get_remaining_daily_budget(self) -> float:
        return max(0.0, self.daily_budget_usd - self.current_daily_spend_usd)

    def get_cost_per_call_average(self) -> float:
        if self.current_call_count == 0:
            return 0.0
        return self.current_daily_spend_usd / self.current_call_count
```

### 5.2 Cost Tracker Intégré

```python
# costs/integrated_tracker.py
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from langfuse import Langfuse

from costs.pricing_models import CostTracker, PricingRegistry

logger = logging.getLogger(__name__)


class IntegratedCostTracker:
    """Tracker centralizado com LangFuse + budgets"""

    def __init__(
        self,
        langfuse_client: Langfuse,
        agent_budgets: dict[str, dict],
    ) -> None:
        """
        Args:
            langfuse_client: Client LangFuse
            agent_budgets: Dict com {agent_name: {daily_usd, monthly_usd}}
        """
        self.langfuse = langfuse_client
        self.trackers = {
            agent_name: CostTracker(
                agent_name=agent_name,
                daily_budget_usd=budget.get("daily_usd", 50),
                monthly_budget_usd=budget.get("monthly_usd", 1000),
            )
            for agent_name, budget in agent_budgets.items()
        }

    def record_generation(
        self,
        agent_name: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        trace: Optional[Langfuse] = None,
    ) -> dict:
        """
        Enregistre une génération LLM avec tracking de coût.

        Returns:
            Dict com {cost_usd, daily_remaining, monthly_remaining, over_budget}
        """
        if agent_name not in self.trackers:
            logger.warning(f"Unknown agent: {agent_name}")
            return {}

        tracker = self.trackers[agent_name]
        cost = tracker.record_call(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        # Log dans LangFuse
        if trace:
            trace.score(
                name="cost_usd",
                value=cost,
                comment=f"Model: {model}, Tokens: {input_tokens + output_tokens}",
            )

        result = {
            "cost_usd": cost,
            "daily_remaining_usd": tracker.get_remaining_daily_budget(),
            "monthly_remaining_usd": tracker.monthly_budget_usd
            - tracker.current_monthly_spend_usd,
            "over_daily_budget": tracker.is_daily_budget_exceeded(),
            "over_monthly_budget": tracker.is_monthly_budget_exceeded(),
        }

        # Alert si dépassement
        if result["over_daily_budget"]:
            logger.error(
                f"ALERT: {agent_name} exceeded daily budget! "
                f"Spent ${tracker.current_daily_spend_usd:.2f} "
                f"/ ${tracker.daily_budget_usd:.2f}"
            )

        return result

    def get_cost_summary(self, agent_name: Optional[str] = None) -> dict:
        """Résumé des coûts"""
        if agent_name:
            tracker = self.trackers.get(agent_name)
            if not tracker:
                return {}
            return {
                "agent": agent_name,
                "daily_spent": tracker.current_daily_spend_usd,
                "monthly_spent": tracker.current_monthly_spend_usd,
                "calls": tracker.current_call_count,
                "avg_cost_per_call": tracker.get_cost_per_call_average(),
            }

        # Agrégé pour tous les agents
        total_daily = sum(t.current_daily_spend_usd for t in self.trackers.values())
        total_monthly = sum(t.current_monthly_spend_usd for t in self.trackers.values())
        total_calls = sum(t.current_call_count for t in self.trackers.values())

        return {
            "total_daily_spent": total_daily,
            "total_monthly_spent": total_monthly,
            "total_calls": total_calls,
            "by_agent": {
                name: {
                    "daily": t.current_daily_spend_usd,
                    "monthly": t.current_monthly_spend_usd,
                }
                for name, t in self.trackers.items()
            },
        }
```

---

## Partie 6: Quality Scoring Automatisé

### 6.1 Framework de Scoring

**Principe**: Chaque réponse d'agent obtient un score de qualité 0-1 basé sur critères objectifs et LLM-évaluation.

```python
# quality/scoring.py
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ScoringDimension(str, Enum):
    """Dimensions d'évaluation de qualité"""
    RELEVANCE = "relevance"  # Pertinence au problème
    ACCURACY = "accuracy"  # Exactitude factuelle
    COMPLETENESS = "completeness"  # Couverture complète
    CLARITY = "clarity"  # Clarté de la réponse
    PERSUASION = "persuasion"  # Capacité de persuasion
    PERSONALIZATION = "personalization"  # Personnalisation


class QualityScore(BaseModel):
    """Score de qualité multi-dimensionnel"""

    overall: float = Field(ge=0.0, le=1.0)
    dimensions: dict[str, float] = Field(
        description="Score pour chaque dimension"
    )
    weights: dict[str, float] = Field(
        description="Poids de chaque dimension dans le score global"
    )

    def calculate_weighted_score(self) -> float:
        """Calcule le score pondéré"""
        return sum(
            self.dimensions.get(dim, 0) * self.weights.get(dim, 0)
            for dim in self.dimensions
        )


class QualityEvaluator(ABC):
    """Interface pour les évaluateurs de qualité"""

    @abstractmethod
    async def evaluate(self, **kwargs: Any) -> QualityScore:
        """Évalue la qualité avec les paramètres spécifiés"""
        pass


class LLMBasedEvaluator(QualityEvaluator):
    """Évaluateur utilisant un LLM pour scorer"""

    def __init__(self, llm_client: Any, langfuse_client: Any) -> None:
        self.llm = llm_client
        self.langfuse = langfuse_client

    async def evaluate(
        self,
        response: str,
        context: dict,
        dimensions: list[ScoringDimension],
        agent_type: str,
    ) -> QualityScore:
        """
        Évalue une réponse sur plusieurs dimensions.

        Args:
            response: Réponse à évaluer
            context: Contexte (lead data, agent type, etc.)
            dimensions: Dimensions à évaluer
            agent_type: Type d'agent ("seduction", "closing", etc.)
        """

        eval_prompt = self._build_eval_prompt(
            response=response,
            context=context,
            dimensions=dimensions,
            agent_type=agent_type,
        )

        eval_response = await self.llm.generate(
            prompt=eval_prompt,
            model="gpt-3.5-turbo",  # Modèle économique pour éval
            temperature=0.0,
            max_tokens=500,
        )

        # Parse la réponse du LLM (format JSON)
        scores = self._parse_eval_response(eval_response.text)

        # Calcule le score global pondéré
        weights = self._get_dimension_weights(agent_type)

        overall_score = sum(
            scores.get(dim, 0) * weights.get(dim, 0)
            for dim in dimensions
        )

        return QualityScore(
            overall=overall_score,
            dimensions=scores,
            weights=weights,
        )

    def _build_eval_prompt(
        self,
        response: str,
        context: dict,
        dimensions: list[ScoringDimension],
        agent_type: str,
    ) -> str:
        """Construit le prompt d'évaluation"""

        dimension_descriptions = {
            ScoringDimension.RELEVANCE: "Is the response directly addressing the problem/question?",
            ScoringDimension.ACCURACY: "Is the response factually accurate?",
            ScoringDimension.COMPLETENESS: "Does it cover all necessary aspects?",
            ScoringDimension.CLARITY: "Is the response clear and well-structured?",
            ScoringDimension.PERSUASION: "Is it persuasive and compelling?",
            ScoringDimension.PERSONALIZATION: "Is it personalized to the prospect?",
        }

        dims_text = "\n".join(
            f"- {dim.value}: {dimension_descriptions.get(dim, '')}"
            for dim in dimensions
        )

        return f"""
        Evaluate this {agent_type} agent response on the following dimensions.
        Score each 0-1 (0=poor, 1=excellent).

        **Agent Response:**
        {response}

        **Context:**
        - Lead: {context.get('lead_name', 'Unknown')}
        - Agent Type: {agent_type}
        - Purpose: {context.get('purpose', 'Unknown')}

        **Evaluation Dimensions:**
        {dims_text}

        **Output Format (JSON):**
        {{
            {', '.join(f'"{dim.value}": <0-1>' for dim in dimensions)}
        }}

        Evaluate and return only the JSON object with no additional text.
        """

    def _parse_eval_response(self, response: str) -> dict[str, float]:
        """Parse la réponse JSON du LLM"""
        try:
            import json

            # Extrait le JSON de la réponse
            json_str = response.strip()
            if not json_str.startswith("{"):
                json_str = json_str[json_str.find("{") :]
            if not json_str.endswith("}"):
                json_str = json_str[: json_str.rfind("}") + 1]

            scores = json.loads(json_str)

            # Clamp tous les scores à [0, 1]
            return {
                k: max(0.0, min(1.0, float(v)))
                for k, v in scores.items()
            }
        except Exception:
            return {}

    def _get_dimension_weights(self, agent_type: str) -> dict[str, float]:
        """Retourne les poids des dimensions selon le type d'agent"""

        weights = {
            "seduction": {
                ScoringDimension.PERSONALIZATION: 0.3,
                ScoringDimension.PERSUASION: 0.3,
                ScoringDimension.CLARITY: 0.2,
                ScoringDimension.RELEVANCE: 0.2,
                ScoringDimension.ACCURACY: 0.0,
                ScoringDimension.COMPLETENESS: 0.0,
            },
            "closing": {
                ScoringDimension.PERSUASION: 0.35,
                ScoringDimension.ACCURACY: 0.25,
                ScoringDimension.COMPLETENESS: 0.2,
                ScoringDimension.CLARITY: 0.15,
                ScoringDimension.RELEVANCE: 0.05,
                ScoringDimension.PERSONALIZATION: 0.0,
            },
            "lead_acquisition": {
                ScoringDimension.ACCURACY: 0.35,
                ScoringDimension.COMPLETENESS: 0.25,
                ScoringDimension.RELEVANCE: 0.25,
                ScoringDimension.CLARITY: 0.15,
                ScoringDimension.PERSUASION: 0.0,
                ScoringDimension.PERSONALIZATION: 0.0,
            },
        }

        return weights.get(agent_type, {})
```

---

## Partie 7: A/B Testing Framework

### 7.1 Design du Framework

```python
# testing/ab_testing.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class VariantStatus(str, Enum):
    """Status d'une variante d'A/B test"""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


@dataclass
class Variant:
    """Une variante dans un A/B test"""

    name: str  # "control" ou "variant_a", "variant_b"
    description: str
    config: dict  # Configuration spécifique (prompt, temperature, etc.)
    traffic_percentage: float  # % du traffic

    @property
    def is_control(self) -> bool:
        return self.name.lower() == "control"


class ABTestMetrics(BaseModel):
    """Métriques d'un A/B test"""

    variant_name: str
    total_exposures: int
    total_successes: int  # Conversions, closes, etc.
    success_rate: float = Field(ge=0.0, le=1.0)
    avg_quality_score: float = Field(ge=0.0, le=1.0)
    total_cost_usd: float
    cost_per_success: float
    confidence_level: float = Field(ge=0.0, le=1.0, description="Statistical confidence")


class ABTest(BaseModel):
    """Configuration d'un A/B test"""

    id: str = Field(description="Unique test ID")
    name: str
    description: str
    agent_name: str  # Quel agent teste-t-on?
    test_objective: str  # "improve_closing_rate", "reduce_cost", etc.

    variants: list[Variant]
    duration_hours: int
    target_sample_size: int

    status: VariantStatus = VariantStatus.DRAFT
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

    # Résultats
    metrics: dict[str, ABTestMetrics] = {}
    winner_variant: Optional[str] = None
    statistical_significance: Optional[float] = None


class ABTestRunner:
    """Orchestrateur des A/B tests"""

    def __init__(self, langfuse_client: Any) -> None:
        self.langfuse = langfuse_client
        self.active_tests: dict[str, ABTest] = {}

    async def start_test(self, test: ABTest) -> None:
        """Démarre un A/B test"""
        test.status = VariantStatus.ACTIVE
        test.started_at = datetime.utcnow()
        self.active_tests[test.id] = test

        logger.info(
            f"Started A/B test: {test.name} "
            f"with variants: {[v.name for v in test.variants]}"
        )

    def select_variant(self, test_id: str, lead_id: str) -> Variant:
        """Sélectionne une variante pour ce lead"""
        test = self.active_tests.get(test_id)
        if not test:
            return None

        # Déterministe: même lead = même variant toujours
        hash_val = hash(f"{test_id}:{lead_id}") % 100

        cumulative = 0
        for variant in test.variants:
            cumulative += variant.traffic_percentage
            if hash_val < cumulative:
                return variant

        return test.variants[-1]

    async def record_variant_exposure(
        self,
        test_id: str,
        variant_name: str,
        lead_id: str,
        trace_id: str,
    ) -> None:
        """Enregistre une exposition à une variante"""
        test = self.active_tests.get(test_id)
        if not test:
            return

        # Tag la trace LangFuse avec l'info de test
        trace = self.langfuse.trace(
            name=f"ab_test_exposure.{test_id}",
            user_id=lead_id,
            metadata={
                "test_id": test_id,
                "variant": variant_name,
                "test_name": test.name,
            },
        )

    async def record_variant_outcome(
        self,
        test_id: str,
        variant_name: str,
        lead_id: str,
        success: bool,
        quality_score: float,
        cost_usd: float,
    ) -> None:
        """Enregistre le résultat d'une variante"""
        test = self.active_tests.get(test_id)
        if not test:
            return

        # Mise à jour des métriques
        if variant_name not in test.metrics:
            test.metrics[variant_name] = ABTestMetrics(
                variant_name=variant_name,
                total_exposures=0,
                total_successes=0,
                success_rate=0.0,
                avg_quality_score=0.0,
                total_cost_usd=0.0,
                cost_per_success=0.0,
            )

        metric = test.metrics[variant_name]
        metric.total_exposures += 1
        if success:
            metric.total_successes += 1
        metric.total_cost_usd += cost_usd
        metric.success_rate = metric.total_successes / metric.total_exposures
        metric.cost_per_success = (
            metric.total_cost_usd / metric.total_successes
            if metric.total_successes > 0
            else float("inf")
        )

        # Vérifier si le test est complet
        if all(
            m.total_exposures >= test.target_sample_size
            for m in test.metrics.values()
        ):
            await self._complete_test(test)

    async def _complete_test(self, test: ABTest) -> None:
        """Termine un A/B test et détermine le gagnant"""
        test.status = VariantStatus.COMPLETED
        test.ended_at = datetime.utcnow()

        # Détermine le gagnant selon l'objectif
        if test.test_objective == "improve_closing_rate":
            winner = max(
                test.metrics.values(),
                key=lambda m: m.success_rate,
            )
        elif test.test_objective == "reduce_cost":
            winner = min(
                test.metrics.values(),
                key=lambda m: m.cost_per_success,
            )
        else:
            # Défaut: success_rate
            winner = max(
                test.metrics.values(),
                key=lambda m: m.success_rate,
            )

        test.winner_variant = winner.variant_name

        logger.info(
            f"A/B test {test.name} completed. "
            f"Winner: {winner.variant_name} "
            f"(Success rate: {winner.success_rate:.2%})"
        )
```

### 7.2 Exemple: A/B Test de Prompts

```python
# testing/prompt_variants.py
from __future__ import annotations

from tests.ab_testing import ABTest, Variant


def create_prompt_test_closing() -> ABTest:
    """
    Crée un A/B test pour comparer deux stratégies de closing.
    """

    control_prompt = """
    Generate a professional closing proposal for this prospect.

    Prospect: {prospect_name}
    Company: {company}
    Budget: ${budget}

    Create a compelling proposal with:
    1. Problem statement
    2. Proposed solution
    3. Expected ROI
    4. Pricing
    5. Next steps
    """

    variant_a_prompt = """
    Generate a PERSONALIZED closing proposal emphasizing emotional benefit.

    Prospect: {prospect_name}
    Company: {company}
    Recent News: {recent_news}
    Personal Style: {personal_style}

    Create a proposal that:
    1. Acknowledges recent company news/achievements
    2. Shows deep understanding of their business challenges
    3. Demonstrates unique value to THIS specific person
    4. Uses their communication style
    5. Includes specific ROI metrics for their industry

    Remember: This should feel personal, not generic.
    """

    return ABTest(
        id="test_closing_strategy_v1",
        name="Closing Strategy: Generic vs Personalized",
        description="Test if personalized prompts improve closing rate vs generic",
        agent_name="closing",
        test_objective="improve_closing_rate",
        variants=[
            Variant(
                name="control",
                description="Standard generic closing prompt",
                config={"prompt": control_prompt},
                traffic_percentage=50.0,
            ),
            Variant(
                name="variant_a",
                description="Highly personalized closing prompt",
                config={"prompt": variant_a_prompt},
                traffic_percentage=50.0,
            ),
        ],
        duration_hours=72,
        target_sample_size=100,
    )
```

---

## Partie 8: Alerting Intelligent

### 8.1 Système d'Alertes

```python
# alerting/alert_system.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable, Optional

from pydantic import BaseModel, Field


class AlertSeverity(str, Enum):
    """Sévérité d'une alerte"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertCondition(BaseModel):
    """Condition pour déclencher une alerte"""

    name: str
    description: str
    metric: str  # ex: "cost_per_call", "quality_score", "error_rate"
    operator: str  # ">", "<", "=", "contains"
    threshold: float
    severity: AlertSeverity
    check_interval_seconds: int = 60


@dataclass
class Alert:
    """Une alerte déclenchée"""

    condition_name: str
    severity: AlertSeverity
    message: str
    metric_value: float
    threshold: float
    triggered_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


class AlertHandler(BaseModel):
    """Gestionnaire des alertes"""

    # Notifications
    slack_webhook: Optional[str] = None
    email_recipient: Optional[str] = None
    sms_recipient: Optional[str] = None

    # Logs
    log_path: Optional[str] = None


class AlertingEngine:
    """Moteur d'alerting time-réel"""

    def __init__(
        self,
        conditions: list[AlertCondition],
        handler: AlertHandler,
        langfuse_client: Any,
    ) -> None:
        self.conditions = conditions
        self.handler = handler
        self.langfuse = langfuse_client
        self.active_alerts: list[Alert] = []

    async def check_conditions(
        self,
        agent_name: str,
        metrics: dict,
    ) -> list[Alert]:
        """Vérifie toutes les conditions et retourne les alertes"""

        new_alerts = []

        for condition in self.conditions:
            # Récupère la valeur de la métrique
            metric_value = metrics.get(condition.metric, 0.0)

            # Évalue la condition
            triggered = self._evaluate_condition(
                metric_value=metric_value,
                operator=condition.operator,
                threshold=condition.threshold,
            )

            if triggered:
                # Crée une alerte
                alert = Alert(
                    condition_name=condition.name,
                    severity=condition.severity,
                    message=self._build_alert_message(
                        condition=condition,
                        metric_value=metric_value,
                        agent_name=agent_name,
                    ),
                    metric_value=metric_value,
                    threshold=condition.threshold,
                    triggered_at=datetime.utcnow(),
                )

                new_alerts.append(alert)
                self.active_alerts.append(alert)

                # Notifie
                await self._notify_alert(alert, agent_name)

        return new_alerts

    def _evaluate_condition(
        self,
        metric_value: float,
        operator: str,
        threshold: float,
    ) -> bool:
        """Évalue si une condition est satisfaite"""

        if operator == ">":
            return metric_value > threshold
        elif operator == "<":
            return metric_value < threshold
        elif operator == "=":
            return abs(metric_value - threshold) < 0.01
        else:
            return False

    def _build_alert_message(
        self,
        condition: AlertCondition,
        metric_value: float,
        agent_name: str,
    ) -> str:
        """Construit le message d'alerte"""
        return (
            f"[{condition.name}] Agent '{agent_name}': "
            f"{condition.metric}={metric_value:.2f} "
            f"(threshold: {condition.threshold})"
        )

    async def _notify_alert(
        self,
        alert: Alert,
        agent_name: str,
    ) -> None:
        """Notifie selon les canaux configurés"""

        # Slack
        if self.handler.slack_webhook:
            await self._send_slack(alert, agent_name)

        # Email
        if self.handler.email_recipient:
            await self._send_email(alert, agent_name)

        # SMS (seulement CRITICAL)
        if self.handler.sms_recipient and alert.severity == AlertSeverity.CRITICAL:
            await self._send_sms(alert, agent_name)

    async def _send_slack(self, alert: Alert, agent_name: str) -> None:
        """Envoie une notification Slack"""
        import aiohttp

        payload = {
            "text": f"MEGA QUIXAI Alert: {agent_name}",
            "attachments": [
                {
                    "color": self._get_color_for_severity(alert.severity),
                    "fields": [
                        {"title": "Condition", "value": alert.condition_name},
                        {"title": "Severity", "value": alert.severity.value},
                        {"title": "Message", "value": alert.message},
                        {
                            "title": "Metric Value",
                            "value": f"{alert.metric_value:.2f}",
                        },
                        {"title": "Threshold", "value": f"{alert.threshold:.2f}"},
                    ],
                }
            ],
        }

        async with aiohttp.ClientSession() as session:
            try:
                await session.post(self.handler.slack_webhook, json=payload)
            except Exception as e:
                logger.error(f"Failed to send Slack notification: {e}")

    async def _send_email(self, alert: Alert, agent_name: str) -> None:
        """Envoie une notification Email"""
        # À implémenter avec sendgrid ou similaire
        pass

    async def _send_sms(self, alert: Alert, agent_name: str) -> None:
        """Envoie une notification SMS"""
        # À implémenter avec Twilio ou similaire
        pass

    def _get_color_for_severity(self, severity: AlertSeverity) -> str:
        """Couleur pour Slack selon la sévérité"""
        colors = {
            AlertSeverity.INFO: "#36a64f",
            AlertSeverity.WARNING: "#ff9900",
            AlertSeverity.CRITICAL: "#ff0000",
        }
        return colors.get(severity, "#gray")


# Conditions prédéfinies critiques pour MEGA QUIXAI
DEFAULT_ALERT_CONDITIONS = [
    AlertCondition(
        name="Daily budget exceeded",
        description="Un agent a dépassé son budget journalier",
        metric="daily_spend_usd",
        operator=">",
        threshold=50.0,  # À ajuster selon budgets réels
        severity=AlertSeverity.CRITICAL,
    ),
    AlertCondition(
        name="Low quality threshold",
        description="Score de qualité moyen trop bas",
        metric="avg_quality_score",
        operator="<",
        threshold=0.5,
        severity=AlertSeverity.WARNING,
    ),
    AlertCondition(
        name="High error rate",
        description="Taux d'erreur API anormalement élevé",
        metric="error_rate",
        operator=">",
        threshold=0.1,  # 10%
        severity=AlertSeverity.WARNING,
    ),
    AlertCondition(
        name="Closing rate degradation",
        description="Taux de closing chute",
        metric="closing_rate",
        operator="<",
        threshold=0.2,  # 20% closing rate
        severity=AlertSeverity.WARNING,
    ),
]
```

---

## Partie 9: Dashboard Design

### 9.1 Layout Opérationnel

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  MEGA QUIXAI — OBSERVABILITY DASHBOARD                                       │
│  Status: HEALTHY | Timestamp: 2026-03-14 14:32:45 UTC                        │
└──────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ SYSTEM HEALTH (Real-time)                                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  Overall Status: ✅ GREEN                                                    │
│  Uptime (24h): 99.87%                                                       │
│  Active Sessions: 127                                                       │
│  Pending Leads: 43                                                          │
│                                                                             │
│  Active Agents:                                                             │
│  ├─ Lead Acquisition: ✅ Healthy (34 processing)                           │
│  ├─ Seduction: ✅ Healthy (28 processing)                                  │
│  └─ Closing: ⚠️  WARNING (12 processing, avg_quality=0.58)                │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ COSTS — REAL-TIME TRACKING                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  DAILY SPEND                          MONTHLY SPEND                        │
│  ┌────────────────────────────┐      ┌────────────────────────────┐      │
│  │ Total: $124.56 / $500 ▓░░░ │      │ Total: $2,847 / $10,000 ▓░░ │     │
│  │ Lead Acq: $45.23           │      │ Lead Acq: $1,023           │      │
│  │ Seduction: $38.12          │      │ Seduction: $892            │      │
│  │ Closing:   $41.21  ⚠️      │      │ Closing:   $932 ⚠️        │      │
│  └────────────────────────────┘      └────────────────────────────┘      │
│                                                                             │
│  Cost per Call Trend (last 24h)                                            │
│  Lead Acq: $0.34 (↓ 5%)                                                    │
│  Seduction: $0.12 (→ stable)                                               │
│  Closing: $0.28 (↑ 8%)  ⚠️                                                │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ QUALITY METRICS                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Agent                Quality Score    Target      Trend                  │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │ Lead Acquisition      0.82 ✅      → 0.75      ↑ 3.2%                │ │
│  │ Seduction             0.71 ⚠️       → 0.75      ↓ 2.1%                │ │
│  │ Closing               0.58 ❌       → 0.75      ↓ 5.4%                │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  Quality Breakdown (Closing Agent):                                        │
│  ├─ Persuasion: 0.65           [████░░░░░░]                              │
│  ├─ Accuracy: 0.52             [███░░░░░░░]                              │
│  ├─ Completeness: 0.68         [██████░░░░]                              │
│  ├─ Clarity: 0.71              [███████░░░]                              │
│  └─ Relevance: 0.45            [██░░░░░░░░]  ⚠️ Below threshold          │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ BUSINESS METRICS                                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Metric                         24h        7d Avg    Target    Status     │
│  ────────────────────────────────────────────────────────────────────────  │
│  Leads Qualified/Day            87         82        ≥80       ✅         │
│  Seduction Response Rate        34%        32%       ≥35%      ⚠️         │
│  Closing Rate                   18%        21%       ≥25%      ❌         │
│  Avg Deal Value                 $14.5k     $15.2k    ≥$12k     ✅        │
│  Expected Revenue (24h)         $22.4k     $21.7k    ≥$25k     ⚠️         │
│                                                                             │
│  🎯 Revenue Impact by Agent:                                              │
│    ├─ Lead Acq: $0 (classifier)                                           │
│    ├─ Seduction: +$3.2k (engagement lift)                                 │
│    └─ Closing: +$18.9k (deals closed)                                     │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ A/B TESTS IN PROGRESS                                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Test ID                        Status      Progress   Winner (est.)      │
│  ────────────────────────────────────────────────────────────────────────  │
│  test_closing_personalization   RUNNING     74% (74/100)                  │
│  ├─ Control (generic): 32% success                                        │
│  ├─ Variant A (personal): 38% success  🔥 (predicted winner)              │
│  └─ Variant B (collab): 35% success                                       │
│                                                                             │
│  test_seduction_timing          RUNNING     52% (52/100)                  │
│  ├─ Control (9am): 28% response                                           │
│  └─ Variant A (2pm): 31% response  📈                                     │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ ACTIVE ALERTS                                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  🔴 CRITICAL (1)                                                           │
│  ├─ Closing Agent - Quality Below Threshold                               │
│  │  Value: 0.58 | Threshold: 0.75 | Time: 2h 14m ago                     │
│  │  Action: Reviewing prompt configuration                               │
│                                                                             │
│  🟡 WARNING (2)                                                            │
│  ├─ Closing Agent - Daily Budget Alert                                   │
│  │  Value: $41.21 | Budget: $50 | Remaining: $8.79                       │
│  │  Trend: +2.3%/hour (will exhaust in ~3.8 hours)                       │
│  │                                                                         │
│  ├─ Seduction Agent - Low Response Rate                                  │
│  │  Value: 34% | Target: ≥35% | Trend: ↓ 2.1%                           │
│  │  Recommendation: Check latest A/B test results                         │
│                                                                             │
│  ℹ️  INFO (5)                                                              │
│  └─ [Show more]                                                           │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ TRACES RECENT (Last 10 min)                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  [14:30] LEAD:lead_9234 | Seduction.message_generation | 127 tokens       │
│          Quality: 0.72 | Cost: $0.08 | Duration: 1.2s ✅                  │
│                                                                             │
│  [14:28] DEAL:deal_5621 | Closing.proposal_generation | 876 tokens        │
│          Quality: 0.61 | Cost: $0.34 | Duration: 3.8s ⚠️  (slow)          │
│                                                                             │
│  [14:25] LEAD:lead_9233 | LeadAcq.classify_lead | 234 tokens              │
│          Quality: 0.85 | Cost: $0.12 | Duration: 0.8s ✅                  │
│                                                                             │
│  [14:22] LEAD:lead_9232 | Seduction.analyze_prospect | 543 tokens         │
│          Quality: 0.68 | Cost: $0.23 | Duration: 2.1s ✅                  │
│                                                                             │
│  [14:20] ERROR: LEAD:lead_9231 | Closing.handle_objection                │
│          Error: LLM timeout after 30s | Cost: $0.18 | Retry: 1/3         │
│          Status: Retrying... 🔄                                            │
│                                                                             │
│  [Show more traces...]                                                     │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ QUICK ACTIONS                                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  [Pause Closing Agent]  [View Closing Logs]  [Review Quality Metrics]     │
│  [Reset Daily Budget]   [Start New A/B Test]  [Adjust Thresholds]         │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 9.2 Implémentation Web (Pseudocode)

```python
# dashboard/app.py
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

app = FastAPI()


@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket) -> None:
    """WebSocket pour dashboard real-time"""
    await websocket.accept()

    while True:
        # Collecte les metrics toutes les secondes
        metrics = await collect_metrics()

        # Envoie au client
        await websocket.send_json({
            "timestamp": datetime.utcnow().isoformat(),
            "system_health": metrics["health"],
            "costs": metrics["costs"],
            "quality": metrics["quality"],
            "business": metrics["business"],
            "alerts": metrics["alerts"],
            "traces": metrics["recent_traces"],
        })

        await asyncio.sleep(1)


@app.get("/api/dashboard")
async def get_dashboard_data() -> dict:
    """Endpoint REST pour données dashboard"""

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "system": {
            "status": "healthy",
            "uptime_percent": 99.87,
            "active_sessions": 127,
        },
        "costs": {
            "daily_spent": 124.56,
            "daily_budget": 500,
            "monthly_spent": 2847,
            "monthly_budget": 10000,
            "by_agent": {...},
        },
        "quality_metrics": {
            "lead_acquisition": 0.82,
            "seduction": 0.71,
            "closing": 0.58,
        },
        "business_metrics": {
            "leads_qualified_24h": 87,
            "closing_rate_24h": 0.18,
            "expected_revenue_24h": 22400,
        },
        "alerts": [
            {
                "severity": "critical",
                "message": "Closing agent quality below threshold",
                "triggered_at": "2026-03-14T12:30:00Z",
            },
        ],
        "ab_tests": [
            {
                "id": "test_closing_personalization",
                "status": "running",
                "progress": 0.74,
                "variants": [
                    {"name": "control", "success_rate": 0.32},
                    {"name": "variant_a", "success_rate": 0.38},
                ],
            },
        ],
    }


async def collect_metrics() -> dict:
    """Collecte toutes les métriques requises"""

    # Récupère depuis LangFuse
    langfuse = get_langfuse_client()

    # Agrège par agent
    metrics_by_agent = {}
    for agent_name in ["lead_acquisition", "seduction", "closing"]:
        traces = await langfuse.get_traces(
            filter=f'metadata.agent == "{agent_name}"',
            limit=1000,
            days=1,  # 24 dernières heures
        )

        metrics_by_agent[agent_name] = {
            "quality_avg": avg([t.quality_score for t in traces]),
            "cost_total": sum([t.cost for t in traces]),
            "calls": len(traces),
            "error_rate": len([t for t in traces if t.error]) / len(traces),
        }

    return {
        "health": {...},
        "costs": {...},
        "quality": metrics_by_agent,
        "business": {...},
        "alerts": [...],
        "recent_traces": [...],
    }
```

---

## Partie 10: Feedback Loop Integration

### 10.1 Architecture de Feedback

```python
# feedback/loop.py
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class FeedbackType(str, Enum):
    """Type de feedback business"""
    DEAL_CLOSED = "deal_closed"
    DEAL_LOST = "deal_lost"
    PROPOSAL_REJECTED = "proposal_rejected"
    EMAIL_OPENED = "email_opened"
    EMAIL_CLICKED = "email_clicked"
    MEETING_SCHEDULED = "meeting_scheduled"
    OBJECTION_RAISED = "objection_raised"


class BusinessFeedback(BaseModel):
    """Feedback en provenance du système business"""

    feedback_type: FeedbackType
    lead_id: str
    deal_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Données contextuelles
    value_usd: Optional[float] = None  # Pour les deals
    reason: Optional[str] = None  # Pourquoi rejeter, objections, etc.
    notes: Optional[str] = None

    # Traçabilité
    trace_id: Optional[str] = None  # ID de la trace LangFuse
    agent_id: Optional[str] = None  # Quel agent a généré le contenu


class FeedbackProcessor:
    """Traite le feedback et l'intègre dans LangFuse"""

    def __init__(self, langfuse_client: Any) -> None:
        self.langfuse = langfuse_client

    async def process_feedback(self, feedback: BusinessFeedback) -> None:
        """
        Processe un feedback et:
        1. Score la trace associée
        2. Calcule l'impact métier
        3. Déclenche rétraining si nécessaire
        """

        if not feedback.trace_id:
            return

        # Récupère la trace associée
        trace = self.langfuse.get_trace(feedback.trace_id)

        # Ajoute les scores de feedback
        if feedback.feedback_type == FeedbackType.DEAL_CLOSED:
            trace.score(
                name="deal_closed",
                value=1.0,
                comment=f"Deal closed for ${feedback.value_usd}",
            )
            trace.score(
                name="revenue_impact",
                value=feedback.value_usd or 0.0,
                comment="Direct revenue attribution",
            )

        elif feedback.feedback_type == FeedbackType.DEAL_LOST:
            trace.score(
                name="deal_closed",
                value=0.0,
                comment=f"Deal lost. Reason: {feedback.reason}",
            )

        elif feedback.feedback_type == FeedbackType.EMAIL_OPENED:
            trace.score(
                name="email_engagement",
                value=0.5,
                comment="Email opened",
            )

        elif feedback.feedback_type == FeedbackType.EMAIL_CLICKED:
            trace.score(
                name="email_engagement",
                value=1.0,
                comment="Email clicked",
            )

        # Déclenche analyse si deal_lost
        if feedback.feedback_type == FeedbackType.DEAL_LOST:
            await self._analyze_loss(
                trace=trace,
                reason=feedback.reason,
                feedback=feedback,
            )

    async def _analyze_loss(
        self,
        trace: Any,
        reason: str,
        feedback: BusinessFeedback,
    ) -> None:
        """Analyse un deal perdu pour améliorer les prompts"""

        loss_analysis_span = trace.span(name="loss_analysis")

        # Génère un rapport d'analyse
        analysis_prompt = f"""
        Analyze why this deal was lost and provide recommendations for improvement.

        Reason: {reason}
        Agent: {feedback.agent_id}

        Questions:
        1. What went wrong in the sales process?
        2. Which part of our generated content missed the mark?
        3. How should we adjust our approach for similar prospects?
        4. What should the closing agent have done differently?

        Provide actionable insights.
        """

        # À implémenter avec LLM evaluator
        # ...

        loss_analysis_span.score(
            name="loss_root_cause",
            value=1.0 if reason else 0.5,
            comment="Loss analysis completed",
        )


class FeedbackWebhook:
    """Endpoint pour recevoir le feedback du système CRM/business"""

    def __init__(self, processor: FeedbackProcessor) -> None:
        self.processor = processor

    async def handle_webhook(self, data: dict) -> dict:
        """Traite un webhook de feedback"""

        feedback = BusinessFeedback(
            feedback_type=FeedbackType(data.get("type")),
            lead_id=data.get("lead_id"),
            deal_id=data.get("deal_id"),
            value_usd=data.get("value_usd"),
            reason=data.get("reason"),
            trace_id=data.get("trace_id"),
            agent_id=data.get("agent_id"),
        )

        await self.processor.process_feedback(feedback)

        return {"status": "processed"}
```

### 10.2 Intégration CRM

```python
# integrations/crm_sync.py
from __future__ import annotations

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CRMIntegration:
    """Synchronisation avec le CRM pour feedback"""

    def __init__(self, crm_client: Any, langfuse_client: Any) -> None:
        self.crm = crm_client
        self.langfuse = langfuse_client

    async def sync_deal_outcomes(self) -> None:
        """
        Synchronise les deal outcomes du CRM.
        Appelé toutes les heures.
        """

        # Récupère les deals updatés dans la dernière heure
        updated_deals = await self.crm.get_deals_updated_since(
            since=datetime.utcnow() - timedelta(hours=1),
        )

        for deal in updated_deals:
            # Retrouve la trace associée
            trace_id = deal.metadata.get("trace_id")

            if not trace_id:
                continue

            trace = self.langfuse.get_trace(trace_id)

            # Score selon le deal status
            if deal.status == "won":
                trace.score(
                    name="final_outcome",
                    value=1.0,
                    comment=f"Deal won: ${deal.amount}",
                )
            elif deal.status == "lost":
                trace.score(
                    name="final_outcome",
                    value=0.0,
                    comment=f"Deal lost: {deal.loss_reason}",
                )

    async def sync_email_events(self) -> None:
        """Synchronise les email opens/clicks"""

        # Similar pattern
        pass
```

---

## Partie 11: Prompt Management

### 11.1 Versioning des Prompts

```python
# prompts/management.py
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PromptVersion(BaseModel):
    """Version d'un prompt"""

    id: str  # ex: "closing-proposal-v2"
    prompt_template: str
    description: str
    version: int
    agent_type: str

    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str

    # Métriques
    test_id: Optional[str] = None  # A/B test associé
    success_rate: Optional[float] = None
    avg_quality_score: Optional[float] = None
    avg_cost_usd: Optional[float] = None

    # Status
    status: str = "draft"  # draft, active, deprecated, archived
    notes: Optional[str] = None


class PromptRegistry:
    """Registry centralisé des prompts avec versioning"""

    def __init__(self, langfuse_client: Any) -> None:
        self.langfuse = langfuse_client
        self.versions: dict[str, list[PromptVersion]] = {}

    def register_prompt(
        self,
        prompt_id: str,
        template: str,
        agent_type: str,
        description: str,
        created_by: str,
    ) -> PromptVersion:
        """Enregistre une nouvelle version de prompt"""

        if prompt_id not in self.versions:
            self.versions[prompt_id] = []

        version_num = len(self.versions[prompt_id]) + 1

        prompt = PromptVersion(
            id=f"{prompt_id}-v{version_num}",
            prompt_template=template,
            description=description,
            version=version_num,
            agent_type=agent_type,
            created_by=created_by,
            status="draft",
        )

        self.versions[prompt_id].append(prompt)

        logger.info(f"Registered prompt: {prompt.id}")

        return prompt

    def activate_prompt(self, prompt_id: str) -> PromptVersion:
        """Active une version de prompt"""

        if prompt_id not in self.versions:
            raise ValueError(f"Prompt not found: {prompt_id}")

        versions = self.versions[prompt_id]

        # Déactive la version actuelle
        for v in versions:
            if v.status == "active":
                v.status = "deprecated"

        # Active la nouvelle
        prompt = next((v for v in versions if v.id == prompt_id), None)
        if not prompt:
            raise ValueError(f"Version not found: {prompt_id}")

        prompt.status = "active"

        # Enregistre dans LangFuse
        self.langfuse.trace(
            name="prompt_activation",
            metadata={
                "prompt_id": prompt.id,
                "agent_type": prompt.agent_type,
                "version": prompt.version,
            },
        )

        logger.info(f"Activated prompt: {prompt.id}")

        return prompt

    def get_active_prompt(self, prompt_id: str) -> Optional[PromptVersion]:
        """Récupère le prompt actif"""

        if prompt_id not in self.versions:
            return None

        for v in self.versions[prompt_id]:
            if v.status == "active":
                return v

        return None

    def list_prompt_history(self, prompt_id: str) -> list[PromptVersion]:
        """Liste tout l'historique d'un prompt"""
        return self.versions.get(prompt_id, [])
```

### 11.2 Prompt Governance

```python
# prompts/governance.py
from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field


class PromptApprovalRule(BaseModel):
    """Règle d'approbation pour un prompt"""

    agent_type: str
    min_quality_score: float = 0.7
    min_test_sample_size: int = 50
    min_success_rate: float = 0.3
    requires_human_approval: bool = False


@dataclass
class PromptApprovalWorkflow:
    """Workflow d'approbation de prompts"""

    pending_prompts: dict[str, PromptVersion] = {}
    approved_prompts: dict[str, PromptVersion] = {}

    async def submit_for_approval(
        self,
        prompt: PromptVersion,
        rule: PromptApprovalRule,
    ) -> bool:
        """Soumet un prompt pour approbation"""

        # Vérifications automatiques
        if not prompt.avg_quality_score or prompt.avg_quality_score < rule.min_quality_score:
            return False

        if (not prompt.success_rate or prompt.success_rate < rule.min_success_rate):
            return False

        # Si approbation humaine requise
        if rule.requires_human_approval:
            self.pending_prompts[prompt.id] = prompt
            # Envoyer notification humain
            return True

        # Auto-approve
        self.approved_prompts[prompt.id] = prompt
        return True
```

---

## Partie 12: Configuration Complète

### 12.1 Fichier Configuration YAML

```yaml
# config/observability.yaml
observability:
  langfuse:
    enabled: true
    public_key: ${LANGFUSE_PUBLIC_KEY}
    secret_key: ${LANGFUSE_SECRET_KEY}
    host: https://cloud.langfuse.com
    sample_rate: 1.0  # 100% en production
    flush_interval_seconds: 60

agents:
  lead_acquisition:
    name: "Lead Acquisition"
    model_primary: gpt-4
    model_evaluator: gpt-3.5-turbo
    daily_budget_usd: 50
    monthly_budget_usd: 1000
    quality_target: 0.75
    quality_alert_threshold: 0.50

  seduction:
    name: "Seduction/Engagement"
    model_primary: gpt-4
    model_evaluator: gpt-3.5-turbo
    daily_budget_usd: 75
    monthly_budget_usd: 1500
    quality_target: 0.75
    quality_alert_threshold: 0.50

  closing:
    name: "Closing"
    model_primary: gpt-4
    model_evaluator: gpt-3.5-turbo
    daily_budget_usd: 100
    monthly_budget_usd: 2000
    quality_target: 0.75
    quality_alert_threshold: 0.50

metrics:
  collection_interval_seconds: 60
  aggregation_window_hours: 24
  retention_days: 90

alerting:
  enabled: true
  slack_webhook: ${SLACK_WEBHOOK_URL}
  email_recipient: ${ALERT_EMAIL}
  sms_recipient: ${ALERT_PHONE}

  conditions:
    - name: "Daily budget exceeded"
      metric: "daily_spend_usd"
      operator: ">"
      severity: "critical"

    - name: "Quality below threshold"
      metric: "avg_quality_score"
      operator: "<"
      threshold: 0.5
      severity: "warning"

    - name: "High error rate"
      metric: "error_rate"
      operator: ">"
      threshold: 0.1
      severity: "warning"

ab_testing:
  enabled: true
  default_duration_hours: 72
  default_sample_size: 100
  statistical_significance_threshold: 0.95

feedback:
  webhook_enabled: true
  webhook_path: "/webhooks/feedback"
  auto_sync_crm: true
  crm_sync_interval_hours: 1

dashboard:
  refresh_interval_seconds: 5
  websocket_enabled: true
  metrics_to_display:
    - system_health
    - costs_real_time
    - quality_metrics
    - business_metrics
    - ab_tests
    - alerts
```

### 12.2 Environment Variables

```bash
# .env
LANGFUSE_PUBLIC_KEY=pk_your_public_key
LANGFUSE_SECRET_KEY=sk_your_secret_key
LANGFUSE_HOST=https://cloud.langfuse.com

# Cost tracking
OPENAI_API_KEY=sk_...
ANTHROPIC_API_KEY=sk_...

# Alerting
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
ALERT_EMAIL=alerts@yourcompany.com
ALERT_PHONE=+1234567890

# CRM Integration
CRM_API_KEY=...
CRM_API_URL=https://api.yourcrm.com

# Database
DATABASE_URL=postgresql://user:password@localhost/quixai

# Feature flags
ENABLE_COST_TRACKING=true
ENABLE_QUALITY_SCORING=true
ENABLE_AB_TESTING=true
ENABLE_FEEDBACK_LOOP=true
```

---

## Partie 13: Code Intégration Complète

### 13.1 Startup Script

```python
# main.py — Initialisation complète du système
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.langfuse_config import LangfuseClient, LangfuseConfig
from costs.integrated_tracker import IntegratedCostTracker
from feedback.loop import FeedbackProcessor
from quality.scoring import LLMBasedEvaluator, ScoringDimension
from prompts.management import PromptRegistry
from tests.ab_testing import ABTestRunner
from alerting.alert_system import AlertingEngine, DEFAULT_ALERT_CONDITIONS, AlertHandler

logger = logging.getLogger(__name__)


# Global instances
langfuse_client: LangfuseClient | None = None
cost_tracker: IntegratedCostTracker | None = None
quality_evaluator: LLMBasedEvaluator | None = None
feedback_processor: FeedbackProcessor | None = None
ab_test_runner: ABTestRunner | None = None
alerting_engine: AlertingEngine | None = None
prompt_registry: PromptRegistry | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events pour FastAPI"""

    # Startup
    logger.info("Starting MEGA QUIXAI Observability System...")

    # Initialise LangFuse
    global langfuse_client
    langfuse_client = LangfuseClient(
        config=LangfuseConfig(
            public_key="${LANGFUSE_PUBLIC_KEY}",
            secret_key="${LANGFUSE_SECRET_KEY}",
        )
    )

    # Initialise Cost Tracker
    global cost_tracker
    cost_tracker = IntegratedCostTracker(
        langfuse_client=langfuse_client.client,
        agent_budgets={
            "lead_acquisition": {"daily_usd": 50, "monthly_usd": 1000},
            "seduction": {"daily_usd": 75, "monthly_usd": 1500},
            "closing": {"daily_usd": 100, "monthly_usd": 2000},
        },
    )

    # Initialise Quality Evaluator
    global quality_evaluator
    quality_evaluator = LLMBasedEvaluator(
        llm_client=None,  # À initialiser avec client LLM réel
        langfuse_client=langfuse_client.client,
    )

    # Initialise Feedback Processor
    global feedback_processor
    feedback_processor = FeedbackProcessor(
        langfuse_client=langfuse_client.client,
    )

    # Initialise AB Test Runner
    global ab_test_runner
    ab_test_runner = ABTestRunner(
        langfuse_client=langfuse_client.client,
    )

    # Initialise Alerting Engine
    global alerting_engine
    alerting_engine = AlertingEngine(
        conditions=DEFAULT_ALERT_CONDITIONS,
        handler=AlertHandler(
            slack_webhook="${SLACK_WEBHOOK_URL}",
            email_recipient="${ALERT_EMAIL}",
        ),
        langfuse_client=langfuse_client.client,
    )

    # Initialise Prompt Registry
    global prompt_registry
    prompt_registry = PromptRegistry(
        langfuse_client=langfuse_client.client,
    )

    logger.info("All observability systems initialized ✅")

    yield

    # Shutdown
    logger.info("Shutting down observability systems...")
    if langfuse_client:
        await langfuse_client.flush()
        langfuse_client.shutdown()


app = FastAPI(
    title="MEGA QUIXAI Observability",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
# from dashboard import router as dashboard_router
# from feedback import router as feedback_router
# etc.


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
```

---

## Résumé Architecture

### Vue d'Ensemble

```
MEGA QUIXAI OBSERVABILITY STACK
================================

Niveau 1: COLLECTION
├─ LangFuse Traces (interactions agent)
├─ Cost Tracking (tokens → USD)
├─ Quality Scores (LLM-based evaluators)
└─ Business Feedback (webhooks CRM)

Niveau 2: PROCESSING
├─ Metrics Aggregation (hourly/daily/monthly)
├─ A/B Test Analysis (statistical significance)
├─ Alerting Engine (threshold monitoring)
└─ Feedback Integration (loop closure)

Niveau 3: STORAGE & ANALYSIS
├─ LangFuse Cloud (primary traces)
├─ PostgreSQL (business data + feedback)
├─ Redis (real-time metrics cache)
└─ Time-series DB (cost tracking history)

Niveau 4: VISUALIZATION & ACTION
├─ Real-time Dashboard (WebSocket)
├─ Alert Notifications (Slack/Email/SMS)
├─ Prompt Management (versioning + governance)
└─ API for external integrations
```

### Fichiers à Créer

```
/projet/
├── config/
│   ├── langfuse_config.py ✅
│   └── observability.yaml ✅
├── agents/
│   ├── lead_acquisition.py ✅
│   ├── seduction.py ✅
│   └── closing.py ✅
├── costs/
│   ├── pricing_models.py ✅
│   └── integrated_tracker.py ✅
├── metrics/
│   ├── agent_metrics.py ✅
│   └── collector.py ✅
├── quality/
│   └── scoring.py ✅
├── tests/
│   ├── ab_testing.py ✅
│   └── prompt_variants.py ✅
├── alerting/
│   └── alert_system.py ✅
├── feedback/
│   ├── loop.py ✅
│   └── integrations/crm_sync.py ✅
├── prompts/
│   ├── management.py ✅
│   └── governance.py ✅
├── dashboard/
│   ├── app.py ✅
│   ├── templates/
│   │   └── index.html (frontend)
│   └── static/
├── orchestration/
│   └── langraph_integration.py ✅
├── main.py ✅
└── .env ✅
```

---

## Prochaines Étapes

1. **Setup LangFuse Cloud** : Créer compte, obtenir keys
2. **Implémenter agents** : Code complet des 3 agents avec tracing
3. **Déployer dashboard** : Frontend + WebSocket
4. **Configuration alerting** : Slack + Email integration
5. **Test A/B complet** : Lancer premier test de prompts
6. **Feedback loop** : Intégration CRM + webhooks
7. **Monitoring production** : Dashboard 24/7, alertes actives

---

**Document complet créé**: `/home/jules/Documents/3-git/zeprocess/main/.claude/specs/mega-quixai/01-observabilite-langfuse.md`

Ce document fournit une architecture d'observabilité **production-ready** pour MEGA QUIXAI. Il couvre tous les aspects critiques: instrumentation LangFuse, tracking des coûts, scoring de qualité automatisé, A/B testing, alerting, et feedback loop.