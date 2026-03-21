# OneNote AI Kit — Brainstorm Créatif

_Document de travail — Mars 2026_

---

## 1. Noms de produit

| # | Nom | Domaine .com | Domaine .io | Force marketing | Risque trademark |
|---|-----|-------------|-------------|-----------------|-----------------|
| 1 | **NoteToAI** | Probablement libre | Probablement libre | Clair, descriptif, verbe d'action — idéal pour le SEO "notes to AI" | Faible — générique |
| 2 | **OneNoteKit** | Probablement pris | Libre probable | Reconnaissable grâce à "OneNote" mais dangereux | Élevé — "OneNote" est une marque Microsoft |
| 3 | **NoteForge** | Pris (forge = usine, pop) | Probablement libre | Connotation puissance + fabrication, mémorable | Moyen — "forge" utilisé dans plusieurs SaaS |
| 4 | **BrainDump** | Pris | Pris | Fort, viscéral, mémorable — mais trop familier pour B2B | Faible — terme courant, mais peu sérieux |
| 5 | **NoteHarvest** | Probablement libre | Libre probable | Évoque la récolte, la valeur extraite — bon pour le storytelling | Faible — original |
| 6 | **NoteMiner** | Probablement libre | Libre probable | Extraction + données = mining, aligné avec le use case | Faible — générique mais précis |
| 7 | **OneExtract** | Libre probable | Libre probable | Verbe d'action clair, mais peu mémorable | Faible — trop technique |
| 8 | **NoteFlow** | Pris (flows = tendance) | Probablement pris | Fluide, moderne — mais surexploité dans la catégorie productivity | Moyen — collision possible |
| 9 | **MindExport** | Probablement libre | Libre probable | Évoque l'export de la pensée — original, différenciant | Faible — bonne combinaison |
| 10 | **NoteVault** | Probablement pris | Libre probable | Sécurité + stockage — bon pour l'angle "protéger sa connaissance" | Moyen — "vault" très utilisé (1Password, etc.) |

**Recommandation** : `NoteHarvest` ou `MindExport` — originaux, disponibles probables, storytelling naturel. Éviter `OneNoteKit` (risque Microsoft).

---

## 2. USP — Unique Selling Proposition

### Formulation principale
> **"Turn years of OneNote notes into AI-ready knowledge in minutes."**

### Variantes par segment

**Consultants**
- "Transformez vos livrables OneNote en base de connaissance interrogeable — sans changer votre workflow."
- "Vos 5 ans de notes de mission deviennent un assistant qui répond comme vous."
- "Export structuré, batch par client, prêt pour Claude ou GPT — en une commande."

**Coaches**
- "Chaque session de coaching documentée dans OneNote devient matière première pour vos formations."
- "Identifiez les patterns de vos clients sur 100 sessions en 10 minutes, pas 10 heures."
- "Votre méthode est dans vos notes. Sortez-la et vendez-la."

**Chercheurs / académiques**
- "De la prise de notes terrain à la synthèse IA — sans perdre la provenance de chaque information."
- "100 pages d'entretiens qualtatifs → thèmes, contradictions, citations clés en un pipeline."
- "La littérature que vous avez annotée pendant 3 ans, enfin interrogeable de façon systématique."

---

## 3. Pre-Prompting Framework — 20 Templates

### Format de chaque template
`Nom | Description | Variables d'entrée | Format de sortie`

---

### Catégorie A — Synthèse

**A1 — Executive Summary**
- Description : Résumé exécutif d'une section ou d'un lot de pages en 500 mots maximum, orienté décision.
- Variables d'entrée : `{section_title}`, `{page_content}`, `{audience}` (ex. : DG, client, équipe)
- Format de sortie : Texte structuré — Contexte (50 mots) + Points clés (3 bullets) + Recommandation (1 phrase)

**A2 — Bullet Point Digest**
- Description : Extraction des 10 points les plus importants par section, classés par impact décroissant.
- Variables d'entrée : `{section_content}`, `{focus_area}` (optionnel : thème prioritaire)
- Format de sortie : Liste numérotée 1-10, chaque item ≤ 20 mots, avec tag de catégorie `[Fait | Décision | Risque | Action]`

**A3 — Progressive Summary**
- Description : Résumé itératif — chaque nouveau lot de pages enrichit le résumé précédent sans le remplacer.
- Variables d'entrée : `{previous_summary}`, `{new_pages_content}`, `{batch_number}`
- Format de sortie : Résumé mis à jour + section "Nouvelles informations ajoutées" + delta marqué en **gras**

**A4 — Comparative Analysis**
- Description : Confrontation de 2 sections ou périodes pour identifier convergences, divergences et évolutions.
- Variables d'entrée : `{section_A}`, `{section_B}`, `{comparison_axis}` (ex. : approche, résultats, recommandations)
- Format de sortie : Tableau 3 colonnes (Section A | Section B | Delta) + paragraphe de synthèse

---

### Catégorie B — Q&A / Knowledge Retrieval

**B5 — Factual Q&A**
- Description : Répond à une question factuelle en se limitant strictement au contenu des notes — sans inférence externe.
- Variables d'entrée : `{question}`, `{notes_content}`, `{strict_mode: true/false}`
- Format de sortie : Réponse directe + citation exacte (page source, date si disponible) + mention "Non trouvé dans les notes" si absent

**B6 — Gap Analysis**
- Description : Identifie ce qui devrait être dans les notes selon le contexte mais qui est absent ou incomplet.
- Variables d'entrée : `{expected_topics}`, `{notes_content}`, `{domain}` (ex. : suivi de projet, coaching, recherche)
- Format de sortie : Liste des lacunes avec niveau de criticité `[Critique | Important | Mineur]` + suggestion de documentation

**B7 — Contradiction Detector**
- Description : Détecte les affirmations contradictoires entre pages ou sections, avec localisation précise.
- Variables d'entrée : `{notes_content}`, `{date_range}` (optionnel)
- Format de sortie : Tableau (Affirmation 1 | Source | Affirmation 2 | Source | Nature du conflit) + recommandation de résolution

**B8 — Timeline Reconstruction**
- Description : Reconstitue une chronologie d'événements, décisions ou évolutions à partir de notes non ordonnées.
- Variables d'entrée : `{notes_content}`, `{entity}` (ex. : projet, client, concept)
- Format de sortie : Frise chronologique en Markdown (date | événement | notes associées), avec incertitudes signalées `[date approximative]`

---

### Catégorie C — Création de contenu

**C9 — Flashcard Generator**
- Description : Transforme les concepts clés en flashcards recto/verso compatibles Anki.
- Variables d'entrée : `{notes_content}`, `{difficulty_level}` (débutant/intermédiaire/expert), `{card_count}` (max)
- Format de sortie : CSV exportable — colonnes `Front;Back;Tags;Deck` — encodage UTF-8

**C10 — Quiz Generator**
- Description : Génère un QCM avec 4 choix par question, réponse correcte identifiée, explication fournie.
- Variables d'entrée : `{notes_content}`, `{question_count}`, `{domain}`, `{language: fr/en}`
- Format de sortie : JSON structuré `{question, options[A-D], correct_answer, explanation, source_page}`

**C11 — Action Item Extractor**
- Description : Extrait toutes les tâches, décisions à prendre et engagements pris dans les notes.
- Variables d'entrée : `{notes_content}`, `{filter_by_owner}` (optionnel), `{date_range}` (optionnel)
- Format de sortie : Tableau Markdown (Action | Owner | Deadline | Statut `[Ouvert | Fait | En cours]` | Source)

**C12 — Meeting Minutes Formatter**
- Description : Restructure des notes brutes de réunion en compte-rendu professionnel standardisé.
- Variables d'entrée : `{raw_notes}`, `{meeting_date}`, `{participants}`, `{meeting_type}` (ex. : comité, atelier, bilatéral)
- Format de sortie : CR formaté — Présents | Ordre du jour | Décisions prises | Actions (owner + deadline) | Prochaine réunion

---

### Catégorie D — Coaching / Formation

**D13 — Framework Extractor**
- Description : Identifie et nomme la méthode ou le framework implicitement utilisé dans les notes de pratique.
- Variables d'entrée : `{practitioner_notes}`, `{domain}` (coaching, consulting, pédagogie)
- Format de sortie : Nom du framework proposé + description en 3 étapes + exemples tirés des notes + degré de confiance `[Fort | Modéré | Faible]`

**D14 — Pattern Recognition**
- Description : Détecte les comportements, thèmes ou situations récurrents sur un corpus de notes multi-sessions.
- Variables d'entrée : `{session_notes}`, `{subject}` (client, projet, équipe), `{min_occurrences: 3}`
- Format de sortie : Liste de patterns (nom | fréquence | première occurrence | dernière occurrence | extrait représentatif)

**D15 — Progress Tracker**
- Description : Mesure l'évolution d'un sujet ou d'une compétence dans le temps à partir de notes datées.
- Variables d'entrée : `{notes_with_dates}`, `{tracked_dimension}` (ex. : confiance, maîtrise d'un sujet, score KPI)
- Format de sortie : Courbe d'évolution en ASCII/Markdown + jalons clés + analyse narrative de la progression

**D16 — Client Profile Builder**
- Description : Construit une fiche synthétique d'un client ou coaché à partir de l'ensemble de ses notes de session.
- Variables d'entrée : `{client_session_notes}`, `{include_verbatims: true/false}`
- Format de sortie : Fiche structurée — Contexte | Objectifs déclarés | Axes de travail | Points forts | Points de vigilance | Verbatims clés

---

### Catégorie E — Business / Consulting

**E17 — Deliverable Accelerator**
- Description : Génère un premier draft de livrable (rapport, note de synthèse, présentation) à partir des notes de mission.
- Variables d'entrée : `{mission_notes}`, `{deliverable_type}` (rapport, slides, note), `{target_audience}`, `{page_limit}`
- Format de sortie : Draft structuré avec placeholder `[À COMPLÉTER]` pour les sections nécessitant validation client

**E18 — RFP Response Generator**
- Description : Produit une réponse à appel d'offres en mappant les exigences RFP sur les références et méthodes des notes.
- Variables d'entrée : `{rfp_requirements}`, `{company_notes}` (références, méthodes, équipe), `{tone}` (formel/conseil)
- Format de sortie : Document de réponse sectionné suivant la structure du RFP + table de conformité exigences/réponses

**E19 — Knowledge Base Builder**
- Description : Transforme un corpus de notes en FAQ structurée, prête à alimenter un wiki ou une base de support.
- Variables d'entrée : `{notes_content}`, `{audience}` (interne/client), `{max_entries}`, `{language}`
- Format de sortie : Liste de Q&A triées par thème, format Markdown avec ancres, niveau de confiance par réponse

**E20 — Competitive Intelligence Digest**
- Description : Consolide et structure les informations concurrentielles dispersées dans les notes en veille actionnable.
- Variables d'entrée : `{competitive_notes}`, `{competitors_list}`, `{time_period}`
- Format de sortie : Tableau de positionnement (concurrent | force | faiblesse | mouvement récent) + signaux d'alerte prioritaires

---

## 4. Canaux de distribution créatifs

### "Export Challenge" — Post viral LinkedIn
Angle narratif : "J'ai exporté 1163 pages de OneNote en 5 minutes. Voici ce que Claude m'a dit de mes 5 dernières années de travail."

Mécanique virale :
- Post de résultats réels (screenshot de l'arbre hiérarchique + 3 insights inattendus générés par l'IA)
- Call-to-action : "Et toi, combien de pages as-tu dans OneNote ?" — crée de l'interaction et de la curiosité
- Suite en thread : les 5 templates les plus utiles pour analyser ses propres notes
- Hashtags cibles : #pkm #productivite #IA #onenote #claudeai

### Template marketplace
- **PromptBase** : Vendre les 20 templates individuellement à 1,99–4,99 USD chacun. Pack complet à 29 USD.
- **FlowGPT** : Version gratuite des 5 templates les plus populaires pour générer du trafic vers le repo/produit payant.
- **Notion template gallery** : Bundle "OneNote → Notion + IA" avec le workflow complet documenté.

### YouTube tutorial — "OneNote → Claude en 3 étapes"
Format : 8 minutes, screen recording, pas de montage complexe.
- Étape 1 (2 min) : Installer le CLI, configurer Azure AD (démystifier la friction)
- Étape 2 (2 min) : Mapper la hiérarchie, sélectionner les sections
- Étape 3 (4 min) : Coller dans Claude avec un template, montrer le résultat en direct
- Description YouTube : lien direct vers le repo GitHub + template pack gratuit en échange d'email

### Partenariat communautés coaches
- Cibler les communautés ICF (International Coaching Federation) et communautés "coaching professionnel" francophones
- Proposition : "Certification OneNote AI Kit Partner" — les coaches qui documentent leur méthode avec l'outil peuvent afficher un badge
- Mécanique : webinaire gratuit "Valoriser vos notes de coaching avec l'IA" → lead magnet → upsell template pack pro

---

## 5. Features "wow" potentielles

### Visual Diff entre deux exports
Comparer deux snapshots de la même section OneNote à des dates différentes. Affiche en rouge ce qui a disparu, en vert ce qui a été ajouté. Use case : voir comment une stratégie client a évolué sur 12 mois. Implémentation : diff textuel ligne par ligne avec rendu HTML coloré.

### Auto-tagging des pages via Claude
Après export, pipeline automatique qui soumet chaque page à Claude avec un prompt de classification. Retourne un `tags.json` avec thèmes, entités, sentiment, et importance estimée. Transforme un corpus non structuré en corpus indexable sans effort manuel.

### "Knowledge Graph" — Relations entre concepts
Extraction des entités (personnes, projets, concepts, dates) et construction d'un graphe de relations. Exportable en format compatible Obsidian, Neo4j, ou visualisation D3.js simple. Répond à "Quelles notes mentionnent à la fois le client X et le projet Y ?"

### Export vers Obsidian vault
Conversion automatique du HTML OneNote en Markdown propre avec wikilinks `[[concept]]` générés depuis l'auto-tagging. Préserve la hiérarchie notebook/section/page comme structure de dossiers. Un des use cases les plus demandés par la communauté PKM.

### Slack bot — `/note query`
Commande Slack qui interroge un export mis en cache : `/note query "quand est-ce qu'on a parlé du budget Q3 ?"`. Répond avec la citation exacte + lien vers la page OneNote originale. Idéal pour les équipes consulting qui partagent une base de notes commune.

---

## 6. Anti-patterns à éviter

### Ne pas builder un "chat with your docs"
Le marché est saturé : Notion AI, Mem.ai, Obsidian Copilot, ChatPDF, et 50+ autres font déjà ça. La différence de ce produit est le pipeline d'extraction structuré depuis OneNote + les templates métier — pas l'interface de chat. Rester sur le CLI et les exports batch.

### Ne pas viser le SaaS avant la validation PMF
Le SaaS implique auth, facturation, infrastructure, support, RGPD, onboarding — soit 3-6 mois de travail avant d'avoir le moindre euro. D'abord : 10 clients payants en direct (Gumroad, virement, peu importe). Si la douleur est réelle, le CLI suffit pour l'instant.

### Ne pas over-engineer le CLI avant d'avoir des paying customers
Le CLI actuel fait ce qu'il faut. Éviter d'ajouter des interfaces graphiques, des dashboards, des modes d'export exotiques sans validation terrain. Chaque feature doit répondre à une demande explicite d'un utilisateur existant.

### Ne pas ignorer la friction Azure AD
L'inscription sur Azure AD + création d'une app + device code flow est le principal point de friction. Un utilisateur sur deux abandonnera à cette étape sans guide clair. Investir dans une documentation step-by-step avec screenshots et une checklist de débogage des erreurs courantes (AADSTS50011, consentement admin requis, etc.) avant toute autre feature.

---

_Ce document est un artefact vivant — à enrichir après les premiers retours terrain._
