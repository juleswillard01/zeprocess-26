# ADR-008 : Singleton de configuration via `@cache` et `click.echo`

## Statut
Accepté — 2026-03-20

## Contexte
Plusieurs modules (`auth.py`, `cli.py`, `hierarchy.py`, `exporter.py`) ont besoin d'accéder à la
configuration applicative (`Settings`). L'instanciation de `Settings` lit le fichier `.env` et
valide les types via pydantic-settings — une opération I/O non négligeable qui, répétée à chaque
appel, serait coûteuse et pourrait produire un état incohérent si `.env` venait à être modifié en
cours d'exécution.

Par ailleurs, du code précoce utilisait `print()` pour l'affichage utilisateur, ce qui pose des
problèmes de testabilité et de gestion des flux (stdout/stderr).

## Décision

### 1. `@cache` sur `get_settings()`
`functools.cache` (Python 3.9+, équivalent à `@lru_cache(maxsize=None)`) garantit que `Settings`
est instancié exactement une fois par processus. Le choix d'une fonction plutôt qu'un attribut
de module-level permet l'initialisation paresseuse et le remplacement en test via
`get_settings.cache_clear()`.

```python
from functools import cache
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    azure_client_id: str = ""
    azure_tenant_id: str = "common"
    export_output_dir: Path = Path("io/exports")
    cache_dir: Path = Path("io/cache")
    graph_rate_limit: int = 4
    cache_ttl_seconds: int = 3600
    max_pages: int = 150
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

@cache
def get_settings() -> Settings:
    return Settings()
```

### 2. `click.echo()` à la place de `print()`
Tout affichage utilisateur dans `auth.py` et `cli.py` passe par `click.echo()`.
Click gère l'encodage, le flush, et la redirection vers stderr (`err=True`), et est
interceptable par `CliRunner` dans les tests.

## Alternatives rejetées

| Alternative | Raison du rejet |
|---|---|
| `SETTINGS = Settings()` au niveau module | Exécuté à l'import — impossible de surcharger `.env` entre tests sans monkeypatching lourd |
| Singleton via metaclass | Sur-ingénierie pour un objet de configuration sans comportement |
| `@lru_cache(maxsize=1)` | Fonctionnellement identique à `@cache` mais moins lisible ; `@cache` est la forme canonique depuis Python 3.9 |
| Injection de dépendance explicite | Verbeux, pollue les signatures, sans bénéfice ici puisque la config est globalement stable |
| `print()` pour l'affichage | Non interceptable dans les tests, pas de support stderr, comportement d'encodage variable selon le terminal |

## Conséquences

- `Settings` est lu et validé une seule fois — fail-fast sur mauvaise configuration dès le premier
  accès.
- Les tests peuvent réinitialiser le singleton via `get_settings.cache_clear()` pour injecter des
  valeurs différentes (ex. : `monkeypatch.setenv` + `cache_clear()`).
- Le fichier `.env` est lu de façon paresseuse : l'import de `config.py` ne déclenche pas d'I/O.
- Tout affichage CLI est testable via `CliRunner.invoke()` sans capturer `sys.stdout` manuellement.
- Aucune dépendance supplémentaire — `functools.cache` est stdlib, `click.echo` est déjà requis
  par click.

## Référence CDC
CDC §1.2 (configuration via .env), §6.2 (qualité et testabilité)
