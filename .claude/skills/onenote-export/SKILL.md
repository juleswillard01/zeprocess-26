# OneNote Export Skill

## Domain Knowledge

### Microsoft Graph OneNote API
- Base URL: `https://graph.microsoft.com/v1.0/me/onenote`
- Auth: OAuth2 with delegated permissions (`Notes.Read`, `Notes.Read.All`)
- Device code flow recommended for CLI tools (no browser redirect needed)
- Page content returned as HTML with OneNote-specific `data-` attributes
- Images/attachments are separate binary resources, fetched via resource URL
- Rate limit: ~4 requests/second; use exponential backoff on 429 responses

### Hierarchy Endpoints
```
GET /notebooks                           → list all notebooks
GET /notebooks/{id}/sectionGroups        → nested section groups
GET /notebooks/{id}/sections             → direct sections
GET /sections/{id}/pages                 → pages in section
GET /pages/{id}/content                  → page HTML content
```

### Key Patterns
- Always paginate: use `$top` and `$skip` or `@odata.nextLink`
- Use `$select=id,title,createdDateTime` to minimize payload
- Page content is HTML — convert to PDF via `weasyprint` or `playwright`
- Store hierarchy as a tree structure for user selection

### Export Strategy
1. Fetch full hierarchy tree (notebooks → sections → pages metadata)
2. Display tree with page counts per section
3. User selects sections/pages to export
4. Fetch page HTML content for selected pages
5. Convert HTML → PDF (one PDF per page)
6. Name files: `{section_name}/{page_order}_{page_title}.pdf`

### Common Pitfalls
- Access tokens expire after ~1 hour — implement refresh
- Some pages have embedded objects (OneNote ink) that don't convert well to HTML
- `@odata.nextLink` URLs are absolute — don't prepend base URL
- Section groups can be nested recursively — use recursive traversal
