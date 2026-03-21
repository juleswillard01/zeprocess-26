# ADR-001 : Stratégie de gestion des tokens OAuth2

## Statut
Accepté — 2026-03-20

## Contexte
Le CLI OneNote Exporter doit s'authentifier auprès de Microsoft Graph API via Azure AD.
Plusieurs stratégies de gestion de tokens existent : stockage sur disque, keyring OS, mémoire seule.

## Décision
**Token en mémoire uniquement**, via MSAL `PublicClientApplication` et device code flow.

### Raisons (principes premiers)
1. **Sécurité** : Un token sur disque est un vecteur d'attaque. Un CLI batch n'a pas besoin de persistence entre sessions.
2. **Simplicité** : MSAL gère le refresh automatiquement tant que l'objet `PublicClientApplication` existe en mémoire.
3. **Conformité** : `Notes.Read` (lecture seule) — permissions minimales. Pas de `client_secret` nécessaire pour device code flow.
4. **Durée de vie** : Un export batch dure ~5-30 min. Le token expire après ~1h. Pas besoin de persist.

### Alternatives rejetées
- **Stockage disque (JSON/pickle)** : Risque de fuite si `.env` ou `io/` est exposé. Complexité de chiffrement.
- **OS Keyring** : Dépendance système (keyring, D-Bus), incompatible Docker facilement.
- **Client credentials flow** : Nécessite `client_secret`, plus complexe à configurer pour l'utilisateur final.

## Conséquences
- Chaque session CLI nécessite une ré-authentification via device code flow
- Le `PublicClientApplication` est instancié à chaque appel `authenticate()`
- Les tokens ne sont jamais écrits sur le filesystem
- Compatible Docker (pas de dépendance système pour keyring)

## Implémentation
- `src/auth.py` : `authenticate() -> str` retourne l'access token
- `src/config.py` : `AZURE_CLIENT_ID` et `AZURE_TENANT_ID` via pydantic-settings
- Scope : `Notes.Read` uniquement

## Référence CDC
CDC §1.1, §1.2
