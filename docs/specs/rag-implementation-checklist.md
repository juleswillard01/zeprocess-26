# RAG Implementation Checklist - 4 Week Sprint

## Week 1: Database & Chunking

### Day 1-2: PostgreSQL + pgvector Setup
- [ ] Install PostgreSQL 14+ with pgvector extension
- [ ] Create database `rag_videos`
- [ ] Run schema creation (Part 1.1 from knowledge-base-rag-architecture.md)
- [ ] Create indexes (embeddings, full-text search, trigram)
- [ ] Test connectivity: `psql -d rag_videos -c "SELECT 1"`

### Day 3-4: Chunking Service Implementation
- [ ] Create `scripts/chunking_service.py`
- [ ] Test on 5 SRT files
- [ ] Verify chunk types are classified correctly
- [ ] Validate chunk durations (30-180 seconds)
- [ ] Calculate total chunks from all SRT files

### Day 5: Validation
- [ ] Run batch chunking on full SRT directory
- [ ] Verify no parsing errors
- [ ] Print statistics by chunk type
- [ ] Sample 5 chunks manually for quality

---

## Week 2: Embedding & Search

### Day 1-2: Embedding Pipeline
- [ ] Create `scripts/embedding_service.py`
- [ ] Download embedding model (all-MiniLM-L6-v2)
- [ ] Test embedding 10 sample texts
- [ ] Verify embedding dimensions (384 for MiniLM)
- [ ] Implement database batch embedding

### Day 3-4: Hybrid Search
- [ ] Create `scripts/search_service.py`
- [ ] Test semantic search (pgvector cosine distance)
- [ ] Test keyword search (PostgreSQL FTS)
- [ ] Implement hybrid search (weighted combination)
- [ ] Test on sample queries in French

### Day 5: Integration
- [ ] Embed 100-500 chunks in database
- [ ] Run test queries on each search method
- [ ] Validate result quality manually
- [ ] Measure latency (target: <200ms)

---

## Week 3: Agent Integration & MCP

### Day 1-2: Update MCP Server
- [ ] Backup existing `mcp_server.py`
- [ ] Implement new search tools in MCP
- [ ] Add search_content tool
- [ ] Add search_objections tool
- [ ] Add list_videos tool
- [ ] Add get_video_transcript tool

### Day 3-4: Agent Integration
- [ ] Create `scripts/agent_integration.py`
- [ ] Implement AgentContext class
- [ ] Add message logging
- [ ] Add chunk tracking
- [ ] Write integration examples

### Day 5: Testing
- [ ] Start MCP server: `python scripts/mcp_server.py`
- [ ] Test search_content tool manually
- [ ] Test with each agent type (prospection, qualification, closing)
- [ ] Verify results are agent-appropriate
- [ ] Document any issues

---

## Week 4: Feedback Loop & Optimization

### Day 1-2: Feedback Collection
- [ ] Create `scripts/feedback_service.py`
- [ ] Implement log_retrieval method
- [ ] Implement record_conversion method
- [ ] Create feedback schema in database
- [ ] Test logging with sample conversations

### Day 3-4: Analytics & Reports
- [ ] Create `scripts/analytics.py`
- [ ] Implement chunk_performance query
- [ ] Implement agent_performance query
- [ ] Add recommendation generation
- [ ] Create weekly report generator

### Day 5: Production Readiness
- [ ] Set up logging infrastructure
- [ ] Create operational runbook
- [ ] Schedule weekly optimization job
- [ ] Monitor for 1 week
- [ ] Document improvements found

---

## Code Quality Gates

Before deploying to production:

### Correctness
- [ ] All database queries tested
- [ ] Search results validated manually
- [ ] No SQL injection vectors
- [ ] Proper error handling throughout

### Performance
- [ ] Search latency < 200ms (p95)
- [ ] Embedding batch time reasonable
- [ ] Database queries have indexes
- [ ] No N+1 query patterns

### Observability
- [ ] All tools logged with timestamps
- [ ] Error messages are informative
- [ ] Metrics collected (latency, quality)
- [ ] Weekly reports generated

### Documentation
- [ ] Schema documented with descriptions
- [ ] API signatures clear
- [ ] Usage examples provided
- [ ] Runbooks written

---

## Success Metrics

### Technical
| Metric | Target | Measurement |
|--------|--------|-------------|
| Search latency | <200ms p95 | `rag_events.retrieval_time_ms` |
| Embedding quality | NDCG@5 > 0.7 | Manual relevance judgment |
| Index coverage | >90% chunks embedded | SQL count check |
| Availability | 99.5% uptime | Monitoring alerts |

### Business
| Metric | Baseline | Target | Measurement |
|--------|----------|--------|-------------|
| Qualified leads | TBD | +25% | `conversions` table |
| Agent satisfaction | N/A | >4/5 | Surveys |
| Query usefulness | N/A | >70% | `rag_events.was_useful` |

---

## Risk Mitigation

### Risk: Chunking breaks semantics
**Mitigation**: Semantic boundary detection, manual QA on 5% of chunks

### Risk: Embedding model too slow
**Mitigation**: Benchmark all-MiniLM vs multilingual-e5, use CPU with batch processing

### Risk: Database becomes bottleneck
**Mitigation**: Monitor query times, add connection pooling, shard by domain if needed

### Risk: Agents over-rely on wrong chunks
**Mitigation**: Feedback loop quickly identifies issues, weekly retuning

---

## Dependencies

### Python Packages
```
psycopg[binary]==3.1.0      # PostgreSQL
pgvector==0.1.8             # pgvector support
sentence-transformers==2.2.2 # embeddings
mcp==0.1.0                   # MCP server
srt==2.0.0                   # SRT parsing
```

### System
- PostgreSQL 14+ with pgvector
- Python 3.10+
- 8GB RAM minimum
- CPU or NVIDIA GPU optional (GPU improves embedding speed 10x)

---

## Timeline & Milestones

```
Week 1: Foundation
  Mon-Tue: DB setup
  Wed-Thu: Chunking
  Fri: Validation
  MILESTONE: 10K chunks ready

Week 2: Intelligence
  Mon-Tue: Embeddings
  Wed-Thu: Search
  Fri: Integration test
  MILESTONE: Hybrid search working

Week 3: Agents
  Mon-Tue: MCP update
  Wed-Thu: Agent integration
  Fri: Agent testing
  MILESTONE: All 3 agents can retrieve

Week 4: Optimization
  Mon-Tue: Feedback system
  Wed-Thu: Analytics
  Fri: Go-live
  MILESTONE: Production deployment
```

---

## Rollback Plan

If major issues discovered:

1. **Database corruption**: Restore from backup, replay from last good checkpoint
2. **Bad embeddings**: Re-embed with corrected model
3. **Broken MCP**: Revert to old mcp_server.py
4. **Search quality poor**: Adjust weights, add more training data
5. **Agent confusion**: Implement guardrails, add validation

**Estimated rollback time**: <30 minutes

---

## Post-Launch Optimization (Month 2+)

- [ ] Analyze conversion metrics by chunk type
- [ ] Identify underperforming content areas
- [ ] Fine-tune embedding model on domain-specific pairs
- [ ] Optimize index parameters (IVFFlat lists, HNSW m/ef)
- [ ] Expand to more content categories
- [ ] Scale to production-grade infrastructure

---

## Sign-Off

When all checklist items complete:

**Week 1 Complete**: Database ready
**Week 2 Complete**: Search working
**Week 3 Complete**: Agents integrated
**Week 4 Complete**: Feedback loop operational

**Production Ready**: All checklists passed + 1 week stable operation

---

**Document Version**: 1.0
**Created**: 2026-03-14
**Last Updated**: 2026-03-14
**Status**: Ready for implementation
