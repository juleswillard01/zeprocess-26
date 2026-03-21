# Règle : Sécurité

## Secrets
- JAMAIS de secrets dans le code source
- JAMAIS commit `.env` ou fichiers contenant des tokens
- Tokens OAuth stockés en mémoire uniquement, jamais sur disque
- `.gitignore` DOIT exclure `.env`, `.env.*`, `io/cache/tokens*`

## Authentification
- Device code flow uniquement (pas de client_secret pour CLI)
- Refresh token automatique avant expiration (~1h)
- Permissions minimales : `Notes.Read` suffit (pas `Notes.ReadWrite`)

## API Microsoft Graph
- Respecter les headers `Retry-After` sur 429
- Ne jamais logger les access tokens
- Valider les URLs `@odata.nextLink` (doivent pointer vers graph.microsoft.com)

## Dépendances
- Vérifier avec `pip-audit` avant chaque release
- Pas de dépendances avec des CVE connues non résolues

## Exports PDF
- Ne pas inclure de métadonnées utilisateur dans les PDF exportés
- Sanitizer le HTML OneNote avant conversion (XSS dans le contenu)
