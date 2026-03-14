# YouTube RAG Pipeline POC - Structured Implementation Plan

## Executive Summary

**Current Status**: Pre-upload phase. 47 media files (975 MB) downloaded to `/home/jules/Documents/3-git/zeprocess/main/data/raw/ddp-garconniere/`. Python scripts ready (srt_download.py, embed_ingest.py, mcp_server.py). pgvector DB running on localhost:5432.

**Critical Blocker**: YouTube upload automation requires OAuth2 credentials (Google Cloud project + API credentials). No existing Google API credentials found in system.

**Estimated Timeline**:
- YouTube upload: 2-4 hours (depending on upload approach)
- Auto-caption generation: 2-24 hours (YouTube's automatic timeline)
- SRT download + embedding ingestion: 1-2 hours (fully automated)
- MCP server setup: 30 mins

---

## Part 1: Current State Analysis

### What's DONE ✅

1. **Media Collection** (975 MB, 47 files)
   - Location: `/home/jules/Documents/3-git/zeprocess/main/data/raw/ddp-garconniere/`
   - Content: 9 training modules (French dating/seduction course)
   - Files: .TS, .ts, .mp4, .m4a, .MP3 formats
   - Ready for: YouTube upload

2. **Python Project** (uv-managed)
   - Root: `/home/jules/Documents/3-git/zeprocess/main/`
   - Python: 3.12+
   - Dependencies: mcp, sentence-transformers, psycopg, srt, requests, etc.

3. **pgvector Database**
   - Running: Docker container on localhost:5432
   - DB: `rag_videos`
   - Schema: `videos` table, `video_embeddings` table with pgvector column
   - Status: ✅ Ready

4. **Scripts (All Tested)**
   - `srt_download.py`: yt-dlp-based SRT downloader (French auto-subs)
   - `embed_ingest.py`: SRT → chunks → sentence-transformers embeddings → pgvector
   - `search_videos.py`: Semantic search endpoint
   - `mcp_server.py`: MCP server with tools: `search_videos`, `list_videos`, `get_video_context`

### What's NOT DONE ❌

1. **YouTube Upload** (BLOCKER #1)
   - No auth credentials (OAuth2 token, API key, or YouTube account auth)
   - 47 files not yet uploaded
   - Requires: Google Cloud project setup OR browser automation

2. **Auto-Caption Generation**
   - Depends on YouTube having videos + time to auto-generate (usually 1-24h)
   - Can't download SRTs until captions exist

3. **SRT Download & Embedding Ingestion**
   - Blocked until YouTube videos exist and captions are ready
   - Scripts ready; just needs execution after captions appear

4. **MCP Server Integration**
   - Script ready; needs Claude Code config update

---

## Part 2: Blockers & Solutions

### BLOCKER #1: YouTube Upload Authentication

**Problem**: No Google API credentials found in system.

**Evidence**:
- Searched: `/home/jules/.config/`, `/home/jules/.local/`, `~/.env*`, project root
- Found: Only venv type stubs, no actual credentials

**Three Approaches Ranked by Effort**:

#### Approach A (Recommended): `youtube-upload` CLI Tool + OAuth2
**Effort**: 2-3 hours
**Steps**:
1. Create Google Cloud project (5 mins) → enable YouTube Data API v3
2. Create OAuth2 credentials (5 mins) → download JSON
3. Install `youtube-upload` package (1 min)
4. Run one-time auth flow (10 mins) → saves refresh token locally
5. Batch upload via script (1-2 hours for 47 files)

**Pros**:
- Fully automated after auth flow
- No Selenium/browser overhead
- Can batch upload with retry logic
- Standard, battle-tested tool

**Cons**:
- Requires Google Cloud project setup
- One-time OAuth2 consent flow (but repeatable)

**Recommended For**: This project (you likely have Google account)

#### Approach B: YouTube Data API v3 + Custom Python Client
**Effort**: 3-4 hours
**Steps**:
1. Same as Approach A (cloud setup)
2. Use `google-auth-oauthlib` + `google-auth-httplib2`
3. Implement resumable upload handler (for large files)
4. Batch wrapper with retry/state tracking

**Pros**:
- Full control over upload logic
- Can integrate MCP tool

**Cons**:
- More code to maintain
- Resumable upload protocol is complex

**Recommended For**: If you want in-process upload (not CLI tool)

#### Approach C: Selenium/Playwright Browser Automation
**Effort**: 4-6 hours
**Steps**:
1. Install Selenium or Playwright
2. Script: login → upload form fill → submit
3. Handle:
   - CAPTCHA/MFA if needed
   - Thumbnail upload
   - Description/title setting
   - Waiting for success page
4. Batch with parallelization

**Pros**:
- No API credentials needed (uses account)
- Mimics real user (less detection risk)

**Cons**:
- Fragile (YouTube UI changes break it)
- Slow (browser overhead per upload)
- MFA handling complex
- Can trigger YouTube's automation detection

**Recommended For**: If no Google Cloud project available

---

### BLOCKER #2: YouTube Auto-Captions Timing

**Problem**: Can't predict when captions will be ready.

**Solution**:
- YouTube usually generates auto-captions within 1-4 hours for French content
- In rare cases, can take up to 24 hours
- Mitigation: Upload all files in batch, then check caption status in loop

**Implementation**: Add `check_caption_status.py` script that:
1. Polls each video's caption availability
2. Tracks status in DB
3. Once all captions ready → trigger SRT download

---

## Part 3: Recommended Implementation Path

### Phase 1: Setup (30 mins)
- [ ] Create Google Cloud project
- [ ] Enable YouTube Data API v3
- [ ] Create OAuth2 credentials (save JSON)
- [ ] Commit credentials JSON to `.gitignore` (never commit!)

### Phase 2: YouTube Upload (1-2 hours)
- [ ] Install `youtube-upload` package (via uv)
- [ ] Create `youtube_uploader.py` script:
  - Scans `/data/raw/ddp-garconniere/`
  - Runs `youtube-upload` for each file
  - Saves video_id → DB
  - Applies metadata (title, description, playlist, unlisted)
- [ ] Run batch upload
- [ ] Verify all videos appear on YouTube (unlisted link)

### Phase 3: Wait for Captions (2-24 hours)
- [ ] Create `check_captions.py` script:
  - Polls each video for caption availability
  - Logs when captions appear
  - Triggers Phase 4 when all ready
- [ ] Monitor status (can run in background)

### Phase 4: Download SRTs + Embed (1-2 hours)
- [ ] Generate YouTube URLs from DB (video_ids)
- [ ] Run `srt_download.py` in batch mode
- [ ] Run `embed_ingest.py` in batch mode
- [ ] Verify pgvector has embeddings for all videos

### Phase 5: MCP Server Setup (30 mins)
- [ ] Create `.claude/mcp.json` config
- [ ] Register `mcp_server.py` as tool provider
- [ ] Test in Claude Code

---

## Part 4: Detailed Scripts Needed

### 1. `youtube_uploader.py` (CRITICAL)
```
Purpose: Batch upload 47 files to YouTube as unlisted videos
Input: Scan /data/raw/ddp-garconniere/ for media files
Output: DB with video_id, youtube_url, file_name, upload_status
Tools: youtube-upload CLI wrapper, psycopg
Key Features:
  - Retry logic (YouTube API rate limits)
  - State tracking (resume if interrupted)
  - Metadata: title (auto-generated from filename), description, playlist, unlisted
  - Logging to file + DB
```

### 2. `check_captions.py` (HELPER)
```
Purpose: Poll YouTube for auto-generated caption availability
Input: DB with list of video_ids
Output: Logs + DB status update
Tools: youtube_dl library OR YouTube Data API
Key Features:
  - Polls every 5 mins (configurable)
  - Exits once all captions ready
  - Logs which videos have captions
```

### 3. `youtube_urls_to_db.py` (UTILITY)
```
Purpose: Convert uploaded video_ids to full YouTube URLs
Input: video_ids from youtube_uploader.py
Output: youtube_url in DB
Note: Simple utility to populate videos.youtube_url column
```

### 4. Update `srt_download.py` (MINOR)
```
Current: Takes command-line YouTube URL or file
Needed: Add batch mode that reads from DB
Example: python srt_download.py --batch (reads all videos.youtube_url from DB)
```

### 5. Update `embed_ingest.py` (MINOR)
```
Current: Takes individual SRT path
Needed: Add batch mode for all SRTs in /data/srt/
Example: python embed_ingest.py --batch
```

---

## Part 5: Environment Setup Checklist

### Dependencies to Add (via uv)
```bash
uv add google-auth-oauthlib google-auth-httplib2  # If using API approach
# OR
uv add youtube-upload  # If using CLI tool
```

### Environment Variables Needed
```bash
GOOGLE_APPLICATION_CREDENTIALS=~/.config/google/youtube-api.json  # Path to OAuth JSON
# OR store in .env (not committed)
```

### Database Prep
```sql
-- Already exists, but verify columns:
-- videos: id, title, youtube_url, file_path, upload_status
-- video_embeddings: id, video_id, text, start_time, end_time, embedding
```

---

## Part 6: Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| YouTube API quota exceeded | Upload blocked | Use `youtube-upload` tool (handles rate limiting) |
| Captions not auto-generated | Pipeline stuck | Manual fallback: use local Whisper (slower) |
| Authentication expires | Process fails | Refresh token stored; script handles refresh |
| File encoding issues | Upload fails | Normalize video formats in upload script |
| Network interruption during upload | Partial uploads | State tracking in DB; resume from last video |
| YouTube Content ID flag | Videos blocked | Monitor; if flagged, videos in unlisted mode not monetized (safe) |

---

## Part 7: Git Workflow

### Branch: `youtube/batch-upload`
```bash
git switch -c youtube/batch-upload main
# Implement Phase 1-2 scripts
# Commit: feat(youtube): add batch uploader + OAuth setup
# PR to main
```

### Branch: `youtube/caption-sync`
```bash
git switch -c youtube/caption-sync main
# Implement Phase 3-4 scripts
# Commit: feat(youtube): add caption checker + SRT batch download
# PR to main
```

### Branch: `mcp/server-config`
```bash
git switch -c mcp/server-config main
# Add .claude/mcp.json config
# Commit: feat(mcp): register video-rag server
# PR to main
```

---

## Part 8: Success Criteria

- [ ] All 47 videos uploaded to YouTube (unlisted)
- [ ] Each video has auto-generated French captions visible
- [ ] All SRTs downloaded to `/data/srt/`
- [ ] All embeddings ingested into pgvector (47 video records in DB)
- [ ] `search_videos()` returns meaningful results
- [ ] MCP server registered in Claude Code
- [ ] Documentation updated in README

---

## Part 9: Commands for Execution (PHASE BY PHASE)

### Phase 1: Google Cloud Setup (Manual, ~30 mins)
```bash
# 1. Go to https://console.cloud.google.com/
# 2. Create new project: "YouTube RAG POC"
# 3. Enable API: YouTube Data API v3
# 4. Create OAuth 2.0 Client ID (Desktop app)
# 5. Download JSON → ~/.config/google/youtube-api.json
# 6. Export path:
export GOOGLE_APPLICATION_CREDENTIALS=~/.config/google/youtube-api.json
```

### Phase 2: Install youtube-upload
```bash
cd /home/jules/Documents/3-git/zeprocess/main
uv add youtube-upload
# First run: youtube-upload --help (authenticates)
```

### Phase 3: Run Batch Uploader
```bash
cd /home/jules/Documents/3-git/zeprocess/main
python scripts/youtube_uploader.py \
  --input-dir data/raw/ddp-garconniere \
  --playlist "DDP Garçonnière" \
  --description "Training module on dating/relationships" \
  --unlisted
```

### Phase 4: Check Captions
```bash
cd /home/jules/Documents/3-git/zeprocess/main
python scripts/check_captions.py --poll-interval 5 --wait-all
```

### Phase 5: Download SRTs + Ingest
```bash
cd /home/jules/Documents/3-git/zeprocess/main
python scripts/srt_download.py --batch
python scripts/embed_ingest.py --batch
```

### Phase 6: Test MCP Server
```bash
cd /home/jules/Documents/3-git/zeprocess/main
mcp run scripts/mcp_server.py
# Test: search_videos "technique de séduction"
```

---

## Part 10: Recommended NEXT IMMEDIATE STEP

**Action**: Decide on YouTube upload approach (A, B, or C from Blocker #1 section).

**If choosing Approach A** (recommended):
1. Create Google Cloud project (30 mins, manual)
2. Download credentials JSON
3. Create `youtube_uploader.py` script
4. Test with 1-2 files first
5. Batch remaining 45 files

**If choosing Approach C** (no Google setup):
1. Install Selenium/Playwright
2. Create browser automation script
3. Test with 1-2 files
4. Batch remaining 45 files
5. Monitor for automation detection

---

## Part 11: File Structure After Completion

```
/home/jules/Documents/3-git/zeprocess/main/
├── data/
│   ├── raw/
│   │   └── ddp-garconniere/  (47 media files)
│   ├── srt/  (47 .srt files, auto-generated by Phase 4)
│   └── embeddings/  (pgvector indexed, can be backed up)
├── scripts/
│   ├── srt_download.py  (existing, updated for batch)
│   ├── embed_ingest.py  (existing, updated for batch)
│   ├── mcp_server.py  (existing)
│   ├── youtube_uploader.py  (NEW)
│   ├── check_captions.py  (NEW)
│   └── youtube_urls_to_db.py  (NEW)
├── .claude/
│   ├── 00-youtube-rag-pipeline-plan.md  (this file)
│   └── mcp.json  (NEW, MCP server config)
├── pyproject.toml  (updated dependencies)
└── README.md  (updated with pipeline docs)
```

---

## Summary Table: Effort & Dependencies

| Phase | Task | Effort | Blocker | Notes |
|-------|------|--------|---------|-------|
| 1 | Google Cloud Setup | 30 min | None | Manual (one-time) |
| 2 | YouTube Upload | 1-2 hrs | Phase 1 | Approach A recommended |
| 3 | Caption Polling | 2-24 hrs | Phase 2 | YouTube's timing, not ours |
| 4 | SRT + Embedding | 1-2 hrs | Phase 3 | Fully automated |
| 5 | MCP Server | 30 min | Phase 4 | Configuration only |
| **Total** | **Hands-on** | **~3 hrs** | Phase 1 | Plus 2-24h waiting for captions |

