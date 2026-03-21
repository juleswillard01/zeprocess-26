# ADR-005 : Conception du batch export de pages OneNote

## Statut
Accepté — 2026-03-20

## Contexte
L'outil doit exporter 100-150 pages OneNote par session en PDF.
Trois contraintes fondamentales imposent des choix non triviaux :

1. **Rate limit Microsoft Graph** : 4 req/s max (CDC §4.1). Un dépassement provoque des 429 avec
   backoff, rallongeant considérablement la durée totale.
2. **Titres de pages arbitraires** : OneNote autorise `/`, `\`, `..`, `<`, `>` et tout caractère
   Unicode dans les titres. Sans sanitisation, la construction de chemins de fichiers est un vecteur
   d'injection et de traversée de répertoire.
3. **Résilience** : Un export de 150 pages dure ~40 secondes minimum. Une page échouée (contenu
   corrompu, timeout) ne doit pas annuler les 149 autres déjà authentifiées.

## Décision

### 1. Signature `list[tuple[str, str]]` pour les pages
`export_batch` accepte `pages: list[tuple[str, str]]` — chaque élément est `(page_id, page_title)`.

Un tuple à deux champs est le type le plus simple qui encode exactement ce que l'on sait : l'identifiant
Graph et le titre d'affichage. Un dataclass ou Pydantic model ajouterait de l'overhead de définition
sans apporter de validation (page_id et page_title sont tous deux des chaînes opaques côté client).

### 2. Rate limiting séquentiel par `asyncio.sleep(1.0 / rate_limit)`
Les pages sont exportées séquentiellement. Entre chaque page (sauf la dernière), on attend
`1.0 / rate_limit` secondes (défaut : 250 ms pour 4 req/s).

Le sleep est calculé depuis les principes premiers : le rate limit est exprimé en requêtes/seconde ;
l'inverse donne l'intervalle minimal entre requêtes. Le skip du sleep après le dernier élément évite
d'allonger inutilement la fin du batch.

### 3. Guard contre la traversée de répertoire via `Path.is_relative_to()`
Après construction du chemin PDF (`output_dir / filename`), les deux chemins sont résolus
(`Path.resolve()`) avant le test `resolved_pdf.is_relative_to(resolved_output)`. Un titre
`../../etc/passwd` serait transformé en chemin absolu hors de `output_dir` — le test lève alors
`ValueError` avant toute écriture.

### 4. Sanitisation des noms de fichiers par regex `[^\w\s-]`
`sanitize_filename()` applique `re.sub(r"[^\w\s-]", "", title)` puis normalise les espaces.
La whitelist (alphanumérique, espace, tiret) est plus sûre qu'une blacklist de caractères interdits.

### 5. Isolation des erreurs — chaque page est indépendante
`export_page_to_pdf` capture toutes les exceptions et retourne un `ExportResult(success=False)`.
L'échec d'une page n'interrompt pas la boucle principale dans `export_batch`. L'objet `ExportReport`
agrège les compteurs `exported` et `failed`.

### 6. `errors.log` écrit uniquement en cas d'échec
Le fichier `io/exports/errors.log` est créé seulement si `failed > 0`. Un export entièrement réussi
ne crée pas de fichier vide.

## Alternatives rejetées

| Alternative | Raison du rejet |
|---|---|
| `asyncio.gather()` pour exports concurrents | Dépasse immédiatement le rate limit de 4 req/s. |
| `Page` dataclass comme paramètre | Sur-ingénierie pour 2 champs. Le tuple est idiomatique Python. |
| `os.path.commonpath()` pour la traversée | `Path.is_relative_to()` (Python 3.9+) est explicite sur l'intention. |
| Abortage sur première erreur | Gaspille la session authentifiée (~1h de validité). |
| Blacklist de caractères dans les noms | Impossible d'anticiper tous les caractères dangereux par FS. La whitelist est déterministe. |

## Conséquences
- Durée d'export prévisible : `n / rate_limit` secondes minimum pour `n` pages (hors conversion PDF).
- Pas d'écriture en dehors de `output_dir`, même avec des titres de pages malveillants.
- Un export partiel est toujours exploitable : les pages réussies sont disponibles immédiatement.
- `errors.log` fournit un audit complet des pages échouées avec leur message d'erreur.
- La propriété `success_rate` de `ExportReport` permet à la CLI d'afficher un résumé lisible.

## Implémentation
- `src/exporter.py` : `export_batch()`, `export_page_to_pdf()`, `sanitize_filename()`, `ExportReport`, `ExportResult`
- Dossier de sortie par défaut : `io/exports/` (configurable via `--output-dir`)
- Log d'erreurs : `io/exports/errors.log` (créé uniquement si `failed > 0`)

## Référence CDC
CDC §4.1 (rate limit 4 req/s, backoff sur 429), §4.2 (PDF, nommage `{ordre}_{titre}.pdf`, dossier `io/exports/`), §4.3 (rapport final, `errors.log`)
