# Vision — OneNote Exporter

## Objectif
Extraire sélectivement les pages OneNote (branche Aurélien de The Process)
via Microsoft Graph API et les exporter en PDF pour ingestion par Claude.

## Contexte
- The Process est un projet de formation avec deux branches : Gebert (day game, Tinder) et Aurélien (night game, codes parisiens)
- Le contenu source est dans OneNote, organisé en sections et sous-dossiers
- L'objectif est de créer un "dossier Aurélien" structuré comme le dossier Gebert existant
- Les PDF sont donnés à Claude en lots de ~100-150 pages pour analyse et structuration

## Contraintes
- L'utilisateur est sur Linux
- L'utilisateur a un abonnement Microsoft 365 à 10€/mois (Azure AD inclus)
- Pas de téléchargement de l'app OneNote — tout via API Graph
- Le mapping de hiérarchie avec comptage de pages est essentiel pour planifier les lots

## Workflow utilisateur cible
1. `make tree` → affiche l'arbre OneNote avec comptage de pages
2. L'utilisateur sélectionne les sections à exporter
3. `make export` → exporte les pages sélectionnées en PDF
4. L'utilisateur donne les PDF à Claude pour construire le dossier Aurélien
