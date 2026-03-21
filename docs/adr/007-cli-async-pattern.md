# ADR-007 : Patron async du CLI — Click synchrone + asyncio.run() multiple

## Statut
Accepté — 2026-03-20

## Contexte
Le CLI utilise Click, un framework synchrone. Le client Microsoft Graph (`GraphClient`) est
entièrement async (basé sur `httpx.AsyncClient`). L'authentification via MSAL est synchrone.
Cette frontière sync/async doit être traversée dans chaque commande Click sans introduire
de gestionnaire d'event loop global ni de dépendance runtime supplémentaire.

Trois commandes (`auth`, `tree`, `export`) ont des profils différents :
- `auth` : entièrement synchrone
- `tree` : sync (authenticate) → async (build_tree) → async (client.close)
- `export` : sync (authenticate) → async (build_tree) → sync (confirm) → async (export_batch) → async (client.close)

## Décision

### 1. Multiples `asyncio.run()` par commande (pas d'event loop global)
Chaque bloc async est encapsulé dans son propre `asyncio.run()`. Aucun event loop n'est
créé au démarrage du processus ni partagé entre commandes.

Raison fondamentale : Click exécute une seule commande par invocation CLI. Il n'y a pas
d'event loop concurrent existant. `asyncio.run()` crée, exécute, et détruit un event loop
propre — c'est le comportement correct pour des appels séquentiels depuis un contexte sync.

### 2. `click.echo()` à la place de `print()`
Toutes les sorties passent par `click.echo()`. Les erreurs utilisent `err=True` pour
écrire sur stderr.

Raison fondamentale : `print()` écrit toujours sur stdout. Click's `CliRunner` (utilisé dans
les tests) capture `click.echo()` mais pas `print()` de façon transparente. La séparation
stdout/stderr est nécessaire pour les pipelines shell.

### 3. Exceptions typées uniquement (`AuthenticationError`, `ValueError`)
Seules les exceptions attendues et documentées sont capturées. Les exceptions inattendues
se propagent avec leur traceback complet.

Raison fondamentale : un `except Exception` masque les bugs. Les deux exceptions capturées
couvrent les cas d'utilisation légitimes (token expiré, config manquante). Tout le reste est
une erreur de programmation qui doit être visible.

### 4. `click.confirm()` avant export > 200 pages
Un prompt de confirmation bloque l'export `--all` si le nombre de pages dépasse 200.

Raison fondamentale : CDC §3.2 l'exige explicitement. Sur le plan pratique, un export de
200+ pages peut durer plusieurs minutes et consommer des ressources significatives.

### 5. Bloc `finally` pour la fermeture du client
`asyncio.run(client.close())` est placé dans un bloc `finally` de chaque commande utilisant
`GraphClient`.

Raison fondamentale : `httpx.AsyncClient` maintient un pool de connexions TCP. Si le programme
se termine sans appeler `close()`, les connexions restent ouvertes jusqu'à expiration du timeout
OS. Le bloc `finally` garantit la fermeture même en cas d'exception dans le corps de la commande.

## Alternatives rejetées

| Alternative | Raison du rejet |
|---|---|
| `asyncio.run()` unique englobant toute la commande | Nécessiterait de rendre `authenticate()` (MSAL) async ou d'utiliser `loop.run_in_executor()` — complexité inutile |
| Event loop global créé au niveau du groupe Click | Risque de conflits si Click réutilise le process entre tests ; teardown imprévisible |
| `anyio` / `trio` | Runtime async alternatif sans bénéfice identifié pour des appels API séquentiels ; dépendance additionnelle |
| `print()` pour les sorties | Non capturé par `CliRunner`, pas de support stderr natif |
| Confirmation automatique désactivée | Contraire au CDC §3.2 ; dangereux pour les exports batch de grande taille |
| `except Exception` générique | Masque les bugs de programmation ; interdit par les règles Python du projet |

## Conséquences

- Frontière sync/async claire et localisée : chaque `asyncio.run()` est visible et isolé
- Chaque commande est testable indépendamment avec `CliRunner` sans configuration globale
- La fermeture des ressources est garantie via `finally`
- Les erreurs inattendues remontent avec leur traceback complet — débogage facilité
- Multiples `asyncio.run()` dans une même commande sont acceptables car il n'existe pas
  d'event loop concurrent dans un CLI synchrone

## Référence CDC
CDC §5.1 (commandes `tree`, `export`, `auth`), §5.2 (options globales `--no-cache`, `--verbose`),
§3.2 (confirmation obligatoire si > 200 pages avec `--all`)
