# ADR-003 : Stratégie de retry pour les appels Microsoft Graph API

## Statut
Accepté — 2026-03-20

## Contexte
`src/graph.py` exécute des appels REST vers Microsoft Graph API pour lister notebooks, sections, pages, et
récupérer le contenu HTML. Sous charge soutenue (export de 100-150 pages), le serveur retourne des réponses
429 (rate limit) accompagnées d'un header `Retry-After`.

Trois problèmes structurels ont été identifiés dans la conception initiale :

1. **Récursion sur retry** : une approche récursive (`_request()` s'appelant elle-même) risque un stack
   overflow si la throttle dure plusieurs minutes (appels empilés).
2. **Confiance aveugle au `Retry-After`** : un serveur malveillant ou mal configuré peut imposer un délai
   arbitrairement long (ex. 3600 s), bloquant le process indéfiniment — vecteur de déni de service
   contrôlé par le serveur.
3. **SSRF via `@odata.nextLink`** : la pagination Graph retourne une URL absolue `@odata.nextLink`. Suivre
   cette URL sans validation ouvre un vecteur SSRF si la réponse est falsifiée ou interceptée.

## Décision

### 1. Retry itératif — boucle `for`, pas de récursion
```python
for attempt in range(_MAX_RETRIES):   # _MAX_RETRIES = 5
    response = await client.get(url, headers=headers)
    if response.status_code == 429:
        ...
        continue
    if response.status_code >= 400:
        raise GraphAPIError(...)
    return response
raise GraphAPIError(f"Rate limit exceeded after {_MAX_RETRIES} retries")
```
Une boucle `for` borne statiquement la profondeur de pile à 1. Cinq tentatives couvrent les pics de
throttle courts sans accumuler des appels.

### 2. Plafonnement du `Retry-After` à 60 secondes
```python
raw = response.headers.get("Retry-After", "1")
try:
    retry_after = min(float(raw), _MAX_RETRY_AFTER)   # _MAX_RETRY_AFTER = 60.0
except ValueError:
    retry_after = 1.0
```
Le plafond à 60 s est choisi par raisonnement depuis les faits : la documentation Microsoft Graph indique
des délais typiques de 1-30 s. Un délai > 60 s n'est pas légitime pour ce cas d'usage CLI. Les valeurs
non parsables (header absent, chaîne non numérique) tombent à 1 s par défaut.

### 3. Validation du `@odata.nextLink` avant suivi
```python
_TRUSTED_NEXTLINK_PREFIX = "https://graph.microsoft.com/"

if next_link and not next_link.startswith(_TRUSTED_NEXTLINK_PREFIX):
    raise GraphAPIError(f"Untrusted nextLink URL: {next_link}")
```
Toute URL de pagination qui ne pointe pas vers `graph.microsoft.com` est rejetée immédiatement. Cela
neutralise le vecteur SSRF sans surcoût algorithmique.

### 4. Toutes les erreurs remontent comme `GraphAPIError`
Les codes >= 400 (hors 429) lèvent `GraphAPIError` immédiatement, sans retry. Les retries épuisés
lèvent également `GraphAPIError`. Les appelants ont un seul type d'exception à intercepter.

## Implémentation
- `src/graph.py` : `_request()` (boucle itérative), `_fetch_paginated()` (validation nextLink)
- Constantes : `_MAX_RETRIES = 5`, `_MAX_RETRY_AFTER = 60.0`, `_TRUSTED_NEXTLINK_PREFIX`
- Chaque tentative 429 est loggée avec le numéro de tentative et le délai effectif

## Alternatives rejetées

| Alternative | Raison du rejet |
|---|---|
| **tenacity** (library) | Dépendance externe pour 15 lignes de logique bornée. YAGNI. |
| **Backoff exponentiel pur** | Microsoft fournit explicitement `Retry-After` — l'honorer est plus précis qu'un délai calculé heuristiquement. |
| **Pas de retry (fail immédiat sur 429)** | Rompt les exports batch normaux sous charge. Le throttle est une condition transitoire attendue. |
| **Retry récursif** | Risque de stack overflow sur throttle soutenu (N appels empilés = N frames). |
| **Faire confiance à `Retry-After` sans cap** | Vecteur DoS : le serveur contrôle la durée de blocage du process client. |

## Conséquences
- Comportement déterministe : au plus 5 tentatives, au plus 60 s de sleep par tentative → borne
  supérieure théorique de 5 x 60 = 300 s par URL.
- Pas de risque de stack overflow, quelle que soit la durée du throttle.
- SSRF neutralisé pour la pagination.
- Un seul type d'exception (`GraphAPIError`) pour tous les cas d'erreur API.

## Référence CDC
CDC §4.1 — Respect du rate limit : 4 req/s max, backoff exponentiel sur 429
