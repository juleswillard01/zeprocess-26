# ADR-006 : Cache de la hiérarchie OneNote

## Statut
Accepté — 2026-03-20

## Contexte

Construire l'arbre de hiérarchie OneNote (notebooks → section groups → sections → pages) nécessite de
nombreux appels à Graph API. Pour un notebook de 10 sections et ~300 pages, cela représente ~100 requêtes
API, soit environ 25 secondes à 4 req/s.

Le workflow typique enchaîne `make tree` (exploration) puis `make export` (sélection et téléchargement).
Sans cache, ces deux commandes re-traversent intégralement l'API, doublant inutilement la charge et la
latence. Par ailleurs, une écriture interrompue (Ctrl-C, crash) ne doit pas laisser un fichier cache
corrompu qui bloquerait les runs suivants.

## Décision

Quatre choix techniques composent la décision :

### 1. Écriture atomique via tmp + rename

`_save_cache` écrit d'abord dans `cache_file.with_suffix(".tmp")`, puis appelle `Path.rename()`. Sur
POSIX, `rename()` est atomique au niveau syscall : le fichier de destination passe en un coup de l'ancien
contenu au nouveau, sans état intermédiaire visible. Un processus interrompu entre les deux opérations
laisse au pire un `.tmp` orphelin, jamais un `hierarchy.json` partiel.

### 2. TTL via `st_mtime`

La fraîcheur du cache est mesurée par `time.time() - cache_file.stat().st_mtime`. Aucun champ `created_at`
n'est stocké dans le JSON. Le mtime est une vérité filesystem qui ne peut pas être désynchronisée du
contenu du fichier.

### 3. Récupération silencieuse sur corruption

`_load_cache` intercepte `json.JSONDecodeError` et `KeyError`. Dans les deux cas, la fonction retourne
`None`, ce qui déclenche un re-fetch API. Le cache dégradé est ignoré, pas bloquant.

### 4. `page_ids` inclus dans le cache

`HierarchyNode.page_ids` stocke la liste des identifiants Graph de chaque page d'une section. Ces IDs
sont sérialisés dans le cache via `_serialize_nodes` / `_deserialize_nodes`. La commande `export` peut
ainsi récupérer directement les IDs depuis le cache, sans ré-appeler les endpoints de listing de pages.

## Alternatives rejetées

- **SQLite** : Adapté à des données tabulaires ou relationnelles. La hiérarchie OneNote est un arbre
  JSON ; l'overhead de schéma et de dépendance est injustifié pour un document unique.
- **Sérialisation binaire Python** : Non lisible humainement, fragile aux changements de version de
  dataclass, et constitue un risque de sécurité si le fichier cache était issu d'une source non fiable.
- **Timestamp explicite dans le JSON** : Ajoute un champ `created_at` redondant avec le mtime.
  Introduit un risque de désynchronisation (copie du fichier, touch, etc.).
- **`page_ids` absents du cache** : Forcerait un appel Graph pour lister les pages à chaque `export`,
  même lorsque la hiérarchie est en cache — contredit l'objectif principal du cache.
- **Lock file pour accès concurrent** : Le CLI est mono-processus et mono-utilisateur. L'atomicité de
  `rename()` suffit ; un verrou ajouterait de la complexité sans bénéfice mesurable.

## Conséquences

- La commande `make tree` est instantanée sur cache valide (zéro appel API).
- La commande `make export` utilise les `page_ids` en cache et n'appelle les endpoints de pages que
  pour récupérer le contenu HTML, pas les métadonnées de listing.
- Un cache corrompu (écriture interrompue, modification manuelle) est détecté silencieusement et
  remplacé par un re-fetch.
- Le fichier `io/cache/hierarchy.json` est lisible et modifiable manuellement pour le débogage.
- L'option `--no-cache` court-circuite intégralement `_load_cache` et `_save_cache` pour forcer
  un refresh complet.
- Le TTL par défaut (3600 s) est configurable via `settings.cache_ttl_seconds` sans modification de code.

## Implémentation

- `src/hierarchy.py` : `_load_cache(cache_file, ttl)`, `_save_cache(cache_file, nodes)`,
  `HierarchyNode.page_ids`, `HierarchyNode.total_pages`
- `src/config.py` : `cache_dir` (défaut `io/cache/`), `cache_ttl_seconds` (défaut `3600`)
- Cache path résolu : `settings.cache_dir / "hierarchy.json"`

## Référence CDC

CDC §2.3 — Cache hiérarchie dans `io/cache/hierarchy.json`, TTL configurable, option `--no-cache`
