# ADR-002 : Remédiation Vague 3 — Sécurité et Qualité

## Statut
Accepté — 2026-03-20

## Contexte
La revue de code de l'implémentation Vague 2 du OneNote Exporter (audit de sécurité + quality gate 75%) a
identifié **4 issues CRITICAL** et **10 issues HIGH** bloquant le passage au gate 75%.

### Issues CRITICAL
1. **Path traversal** dans `exporter.py` : un nom de page contenant `../../` permettait d'écrire un PDF
   hors du répertoire de sortie autorisé.
2. **SSRF via `@odata.nextLink`** dans `graph.py` : les URLs de pagination renvoyées par l'API n'étaient
   pas validées — un attaquant contrôlant une réponse Graph pouvait rediriger les requêtes vers une cible
   arbitraire.
3. **Absence de sanitization HTML** avant passage à WeasyPrint : le contenu HTML OneNote (contrôlé par
   l'utilisateur ou potentiellement altéré) pouvait contenir des balises `<script>`, `<iframe>`,
   `<object>`, `<embed>`, `<link>` injectées dans le PDF.
4. **Retry récursif** dans le client Graph : la stratégie de backoff utilisait la récursivité, exposant
   le programme à un stack overflow sur des séquences prolongées de réponses 429.

### Issues HIGH (résumé)
Bare `except` clauses, absence de validation des inputs config, absence de sleep entre requêtes batch,
risque de corruption du fichier cache JSON, tokens potentiellement inclus dans les logs, timeouts
hardcodés, gestion d'erreur absente dans le CLI, absence de confirmation au-delà de 200 pages,
`print()` au lieu de `logging`, `get_settings()` non singleton.

## Décision
Toutes les 14 issues ont été rémédiées en Vague 3+4. Les décisions architecturales sont :

### 1. Guard path traversal (`exporter.py`)
Après résolution des chemins via `Path.resolve()`, vérification que le PDF de destination est bien
contenu dans le répertoire de sortie : `resolved_pdf.is_relative_to(resolved_output)`.
Levée d'une `ValueError` explicite si la condition n'est pas respectée.

### 2. Validation `nextLink` SSRF (`graph.py`)
Introduction d'une constante `_TRUSTED_NEXTLINK_PREFIX = "https://graph.microsoft.com/"`.
Tout `@odata.nextLink` ne débutant pas par ce préfixe est rejeté avec `GraphAPIError`.
Principe premier : une URL de pagination Graph légitime ne peut qu'être relative à `graph.microsoft.com`.

### 3. Sanitization HTML avant WeasyPrint (`exporter.py`)
Stripping par regex des balises dangereuses (`script`, `iframe`, `object`, `embed`, `link`) avant
conversion. Approche minimaliste : pas de dépendance externe, le contenu OneNote légitime n'utilise
pas ces balises.

### 4. Retry itératif avec cap (`graph.py`)
Remplacement de la récursion par une boucle `for attempt in range(MAX_RETRIES)` (max 5 tentatives).
Le header `Retry-After` est respecté mais plafonné à 60 secondes pour éviter les blocages indéfinis.

### 5. Exceptions typées
Tous les `except Exception` et `except:` nus remplacés par des types spécifiques
(`AuthenticationError`, `ValueError`, `json.JSONDecodeError`, `KeyError`).

### 6. Validation config Pydantic
`pydantic-settings BaseSettings` valide tous les champs de configuration au démarrage.
Un `AZURE_CLIENT_ID` vide lève une `ValueError` immédiatement — fail fast.

### 7. Rate limit sleep batch (`exporter.py`)
`asyncio.sleep(1.0 / rate_limit)` intercalé entre chaque requête de contenu de page en mode batch,
respectant la limite ~4 req/s de Microsoft Graph (CDC §4.1).

### 8. Cache atomique (`hierarchy.py`)
Écriture du cache JSON via un fichier temporaire suivi d'un `rename()` atomique
(`tmp_path.rename(cache_path)`). Élimine le risque de fichier JSON tronqué en cas d'interruption.

### 9. Sécurité des tokens
Les access tokens ne transitent jamais par le logger. Seul le header `Authorization: Bearer <token>`
les utilise.

### 10. Singleton `get_settings()`
Décorateur `@functools.cache` sur `get_settings()` : une seule instance `Settings` par processus.
Évite des lectures répétées de `.env` et garantit la cohérence entre modules.

## Alternatives rejetées

| Alternative | Raison du rejet |
|---|---|
| WAF / proxy pour SSRF | Sur-ingénierie pour un CLI single-user. La validation de préfixe est suffisante. |
| `bleach` ou `lxml` pour HTML sanitization | Dépendance lourde pour un besoin simple. Le contenu OneNote légitime n'emploie pas les balises supprimées. |
| `tenacity` pour le retry | Dépendance externe pour remplacer ~15 lignes. YAGNI. |
| Keyring OS pour cache token | Déjà rejeté en ADR-001 ; incompatible Docker. |

## Conséquences
- 131 tests passent, couverture 96%
- 0 erreur pyright strict, 0 erreur ruff
- Toutes les issues CRITICAL et HIGH résolues
- Légère augmentation de la verbosité du code (`is_relative_to`, boucle retry) compensée par la
  lisibilité des exceptions explicites
- Aucune dépendance externe ajoutée

## Implémentation
- `src/exporter.py` : path traversal guard, sanitization HTML, sleep batch
- `src/graph.py` : SSRF nextLink guard, retry itératif, exceptions typées
- `src/hierarchy.py` : cache atomique
- `src/config.py` : validation Pydantic, singleton `get_settings()`
- `src/cli.py` : confirmation >200 pages, `click.echo` au lieu de `print()`

## Référence CDC
CDC §1.1 (sécurité auth), §2.3 (cache), §4.1 (rate limit), §4.2 (export PDF), §6.2 (qualité)
