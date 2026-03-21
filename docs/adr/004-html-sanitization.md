# ADR-004 : Sanitisation HTML avant conversion WeasyPrint

## Statut
Accepté — 2026-03-20

## Contexte
Les pages OneNote sont retournées par Graph API sous forme de HTML arbitraire.
WeasyPrint, utilisé pour la conversion HTML → PDF (CDC §4.2), n'exécute pas
JavaScript, mais il **suit les URLs externes** présentes dans les balises `<link>`,
`<iframe>`, `<object>` et `<embed>`. Cela crée un vecteur SSRF : un notebook
partagé contenant des références malveillantes pourrait déclencher des requêtes
réseau vers des services internes lors de la génération PDF.

Par ailleurs, la présence de balises `<script>` dans le HTML OneNote constitue un
risque de défense en profondeur : même si WeasyPrint ne les exécute pas aujourd'hui,
un changement de moteur de rendu futur pourrait l'exposer.

## Décision
Appliquer une **sanitisation par expressions régulières** sur le HTML brut avant
tout passage à WeasyPrint. Cinq catégories de balises sont supprimées :

| Balise | Raison |
|--------|--------|
| `<script>` | Prévention d'exécution JS (défense en profondeur) |
| `<iframe>` | Blocage du chargement d'URLs externes |
| `<object>` | Blocage de l'embarquement de ressources externes |
| `<embed>` | Idem, variante auto-fermante |
| `<link>` | Blocage des feuilles de style externes et chaînes `@import` CSS (SSRF) |

Les flags `re.DOTALL | re.IGNORECASE` sont appliqués sur toutes les expressions pour
gérer les balises multi-lignes et les variations de casse.

### Raisons (principes premiers)
1. **Threat model** : WeasyPrint résout les URLs ; un HTML non filtré provenant
   d'une source externe est une entrée non fiable par définition.
2. **Minimalisme** : Supprimer les balises dangereuses est l'opération la plus simple
   qui neutralise le vecteur d'attaque identifié.
3. **Proportionnalité** : Le contenu OneNote légitime n'utilise pas `<script>`,
   `<iframe>`, `<object>` ni `<embed>`. Supprimer ces balises ne casse aucun cas
   d'usage documenté.
4. **Coût** : O(n) par motif, négligeable pour des pages OneNote (<100 KB typiques).

## Alternatives rejetées

- **Bibliothèque `bleach`** : Tire `html5lib` comme dépendance lourde. Conçu pour
  l'assainissement d'entrées utilisateur dans des contextes web (allowlist complète).
  Surdimensionné pour un filtrage ciblé sur 5 balises dans un contexte CLI batch.

- **`lxml` + XSLT** : Ajoute une dépendance C, complexifie le build Docker, et
  nécessite un HTML valide (les pages OneNote ne le sont pas toujours).

- **DOMPurify via `pydomprify`** : Écosystème JavaScript, invocation via subprocess ;
  complexité disproportionnée et surface d'attaque élargie.

- **Approche par liste blanche** : Plus sûre sur le principe, mais risque de casser
  le formatage légitime OneNote (tableaux, divs de mise en page, attributs `data-`
  spécifiques). Le bénéfice marginal ne justifie pas la régression fonctionnelle.

- **Aucune sanitisation** : Inacceptable. WeasyPrint suit les URLs des balises
  `<link>` et `<iframe>`, ce qui constitue un SSRF démontrable.

## Conséquences

- Le HTML transmis à WeasyPrint est exempt des 5 vecteurs identifiés.
- Aucune dépendance supplémentaire n'est introduite.
- Les styles inline et les URIs `data:` ne sont pas filtrés (risque résiduel
  accepté pour du contenu OneNote).
- La fonction `_sanitize_html` est pure et testable sans I/O.
- Si un besoin de sanitisation plus riche émerge (ex. : attributs `on*`, `href`
  javascript:), la migration vers `bleach` peut se faire sans changer la signature
  de l'appelant.

## Implémentation

- `src/exporter.py` : fonction `_sanitize_html(html: str) -> str`, appelée
  systématiquement avant `HTML(string=...).write_pdf(...)`.

## Référence CDC
CDC §4.2 — Conversion PDF (HTML → PDF via WeasyPrint), sécurité export
