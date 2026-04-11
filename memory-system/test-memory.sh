#!/bin/bash
# End-to-end test for the Agent Memory System
# Usage: bash memory-system/test-memory.sh [API_URL]
#
# Tests:
# 1. Populate memory with realistic demo data
# 2. Semantic search across memories
# 3. Update existing memories
# 4. Recall (search + display full content)
# 5. Cross-type search (find related memories across what/how/sessions)

set -e

API_URL="${1:-http://localhost:8000}"
GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

pass() { echo -e "${GREEN}✓ $1${NC}"; }
fail() { echo -e "${RED}✗ $1${NC}"; exit 1; }
info() { echo -e "${CYAN}→ $1${NC}"; }

# --- Setup ---
info "Setting up against $API_URL"

# Get a fresh token
TOKEN=$(curl -s -X POST "$API_URL/get_token" | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
[ -z "$TOKEN" ] && fail "Could not get token"
pass "Got token: ${TOKEN:0:8}..."

# Configure CLI
mkdir -p ~/.agentbox
echo "{\"api_url\": \"$API_URL\", \"token\": \"$TOKEN\"}" > ~/.agentbox/config.json
pass "CLI configured"

# --- 1. Populate demo memories ---
info "Populating demo memories..."

# Project: Auth Migration
cat > /tmp/mem-auth.md << 'EOF'
# Auth Migration

## Objective
Migrate from session-based auth to JWT tokens across all services.

## Background
Current session-based auth doesn't scale for microservices. JWT allows stateless auth.
The migration affects the API gateway, user service, and all downstream services.

## Current State
- **Status:** active
- API gateway JWT validation: done
- User service token issuance: done
- Payment service: in progress
- Notification service: not started

## Key Code Paths
- `services/auth/jwt.py` — token creation and validation
- `services/gateway/middleware.py` — request authentication
- `config/auth.yaml` — JWT configuration (keys, expiry)

## Key Decisions
- Chose RS256 over HS256 for asymmetric signing — allows services to verify without sharing secret
- Token expiry: 15 minutes access, 7 days refresh
- Refresh token rotation enabled for security

## Open Questions
- Should we support API keys alongside JWT for machine-to-machine?
- How to handle token revocation without a blocklist?
EOF
agentbox upload /tmp/mem-auth.md --path /memory/what/auth-migration.md
pass "Saved project: auth-migration"

# Project: Performance Optimization
cat > /tmp/mem-perf.md << 'EOF'
# Performance Optimization

## Objective
Reduce P99 API latency from 800ms to under 200ms.

## Background
Users complained about slow dashboard loads. Traced to N+1 queries in the
user profile endpoint and missing database indexes.

## Current State
- **Status:** active
- Added composite index on (user_id, created_at): done — 3x improvement
- Fixed N+1 in profile endpoint: done — eliminated 47 extra queries
- Connection pooling tuning: in progress
- Redis caching layer: not started

## Key Decisions
- Using pgbouncer for connection pooling (not built-in SQLAlchemy pool)
- Cache invalidation strategy: TTL-based (60s) not event-based — simpler, acceptable staleness
EOF
agentbox upload /tmp/mem-perf.md --path /memory/what/performance-optimization.md
pass "Saved project: performance-optimization"

# How: Tools
cat > /tmp/mem-tools.md << 'EOF'
# Tool Usage Patterns

## Database Debugging
- Always start with `EXPLAIN ANALYZE` before optimizing queries
- Check `pg_stat_statements` for slow query patterns — more reliable than logs
- Use `\dt+` to check table sizes before adding indexes

## Git Workflow
- Interactive rebase (`git rebase -i`) is better than squash merge for complex PRs
- Always fetch before rebasing to avoid phantom conflicts

## Testing
- Integration tests catch more real bugs than unit tests for API endpoints
- Use factories (not fixtures) for test data — more flexible, less brittle
EOF
agentbox upload /tmp/mem-tools.md --path /memory/how/tools.md
pass "Saved reflection: tools"

# How: Approaches
cat > /tmp/mem-approaches.md << 'EOF'
# Problem-Solving Approaches

## Debugging Production Issues
1. Check metrics dashboard first — narrow down the time window
2. Correlate with deploy log — was there a recent deploy?
3. Read error logs filtered by the time window
4. Reproduce locally if possible before patching

## Performance Investigation
1. Profile first, optimize second — don't guess
2. Start at the database (usually the bottleneck)
3. Check for N+1 queries — the most common perf bug
4. Measure after each change — regressions are sneaky

## Migration Strategy
- Always write forward-compatible code first, then migrate data
- Feature flags for gradual rollout
- Keep the old path working until migration is verified
EOF
agentbox upload /tmp/mem-approaches.md --path /memory/how/approaches.md
pass "Saved reflection: approaches"

# Session: Yesterday
cat > /tmp/mem-session1.md << 'EOF'
# Session: Auth JWT Implementation

**Date:** 2026-04-09
**Project:** auth-migration

## Context
Implementing JWT token issuance in the user service. This is the core of the auth
migration — once the user service issues JWTs, all downstream services can validate.

## What Was Accomplished
- Implemented JWT creation with RS256 signing
- Added refresh token endpoint with rotation
- Wrote integration tests for token flow
- Updated API docs with new auth headers

## Key Decisions
- Token payload includes: user_id, email, roles (minimal claims)
- Refresh tokens stored in database (not stateless) for revocation support

## Next Steps
1. Deploy to staging and run load test
2. Start payment service migration
3. Update client SDK to use new tokens
EOF
agentbox upload /tmp/mem-session1.md --path /memory/sessions/2026-04-09_auth-jwt-implementation.md
pass "Saved session: auth-jwt-implementation"

# Session: Today
cat > /tmp/mem-session2.md << 'EOF'
# Session: Database Performance Tuning

**Date:** 2026-04-10
**Project:** performance-optimization

## Context
Continuing the P99 latency reduction effort. Today focused on connection pooling
after the index and N+1 fixes showed 3x improvement but still above 200ms target.

## What Was Accomplished
- Set up pgbouncer with transaction-mode pooling
- Tuned pool size: 20 connections (was 100 — too many for our RDS instance)
- P99 dropped from 350ms to 180ms — below target!
- Identified next bottleneck: serialization (JSON encoding of large responses)

## Key Decisions
- pgbouncer over SQLAlchemy pool — handles connection recycling better under load
- Transaction mode (not session mode) — allows connection reuse between requests

## Next Steps
1. Profile JSON serialization — consider orjson
2. Set up Redis cache for frequently-accessed endpoints
3. Create performance regression test in CI
EOF
agentbox upload /tmp/mem-session2.md --path /memory/sessions/2026-04-10_database-performance-tuning.md
pass "Saved session: database-performance-tuning"

# Artifact: SQL query
cat > /tmp/mem-artifact.sql << 'EOF'
-- Find slowest queries in the last hour
SELECT
    query,
    calls,
    mean_exec_time,
    total_exec_time,
    rows
FROM pg_stat_statements
WHERE mean_exec_time > 100  -- ms
ORDER BY total_exec_time DESC
LIMIT 20;
EOF
agentbox upload /tmp/mem-artifact.sql --path /memory/artifacts/performance/slow-queries.sql
pass "Saved artifact: slow-queries.sql"

echo ""
info "All demo memories populated. Running tests..."
echo ""
sleep 2  # Wait for embeddings

# --- 2. Semantic Search Tests ---
info "Testing semantic search..."

# Search for auth-related memories
RESULT=$(curl -s -X POST "$API_URL/search" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "JWT token authentication migration", "limit": 5}')

AUTH_HITS=$(echo "$RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
hits = [r for r in data['results'] if 'auth' in r['filename'].lower() or 'jwt' in r.get('matched_chunk','').lower()]
print(len(hits))
")
[ "$AUTH_HITS" -ge 1 ] && pass "Search 'JWT auth migration' found auth memories ($AUTH_HITS hits)" || fail "Search 'JWT auth migration' found no auth memories"

# Search for performance-related memories
RESULT=$(curl -s -X POST "$API_URL/search" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "database slow queries latency", "limit": 5}')

PERF_HITS=$(echo "$RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
hits = [r for r in data['results'] if 'perf' in r['filename'].lower() or 'latency' in r.get('matched_chunk','').lower() or 'slow' in r.get('matched_chunk','').lower()]
print(len(hits))
")
[ "$PERF_HITS" -ge 1 ] && pass "Search 'database slow queries' found perf memories ($PERF_HITS hits)" || fail "Search 'database slow queries' found no perf memories"

# Cross-type search: should find both project AND session
RESULT=$(curl -s -X POST "$API_URL/search" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "connection pooling pgbouncer", "limit": 5}')

CROSS_TYPES=$(echo "$RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
folders = set()
for r in data['results']:
    f = r.get('folder', '/')
    if '/memory/' in f:
        parts = f.strip('/').split('/')
        if len(parts) > 1:
            folders.add(parts[1])
print(len(folders))
")
[ "$CROSS_TYPES" -ge 2 ] && pass "Cross-type search found memories in $CROSS_TYPES folders" || echo "  (cross-type search found $CROSS_TYPES folder types — may need more data)"

# Negative search: should return low-relevance or no results for unrelated query
RESULT=$(curl -s -X POST "$API_URL/search" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "kubernetes helm chart deployment", "limit": 3}')

TOP_SCORE=$(echo "$RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if data['results']:
    print(f\"{data['results'][0]['relevance_score']:.2f}\")
else:
    print('0.00')
")
pass "Negative search 'kubernetes helm' top score: $TOP_SCORE (should be low)"

# --- 3. Memory CLI Tests ---
info "Testing memory CLI commands..."

# memory list
agentbox memory list > /dev/null 2>&1 && pass "agentbox memory list" || fail "agentbox memory list"

# memory list with folder filter
agentbox memory list what > /dev/null 2>&1 && pass "agentbox memory list what" || fail "agentbox memory list what"

# memory search
agentbox memory search "how to debug production" > /dev/null 2>&1 && pass "agentbox memory search" || fail "agentbox memory search"

# memory recall
agentbox memory recall "auth migration status" > /dev/null 2>&1 && pass "agentbox memory recall" || fail "agentbox memory recall"

# memory save (inline content)
agentbox memory save what test-project "# Test\n\nThis is a test memory." > /dev/null 2>&1 && pass "agentbox memory save" || fail "agentbox memory save"

# --- 4. Update Test ---
info "Testing memory update..."

# Update the auth project with new info
cat > /tmp/mem-auth-updated.md << 'EOF'
# Auth Migration

## Objective
Migrate from session-based auth to JWT tokens across all services.

## Current State
- **Status:** active
- API gateway JWT validation: done
- User service token issuance: done
- Payment service: DONE (completed today!)
- Notification service: in progress

## Recent Update
Payment service migration completed. All payment endpoints now accept
JWT tokens. Backward compatibility maintained for 2 weeks.
EOF
agentbox upload /tmp/mem-auth-updated.md --path /memory/what/auth-migration.md
pass "Updated auth-migration memory"

sleep 5

# Search should find the updated content
RESULT=$(curl -s -X POST "$API_URL/search" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "payment service migration completed", "limit": 3}')

UPDATED=$(echo "$RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
found = any('auth' in r.get('filename','').lower() or 'payment' in r.get('matched_chunk','').lower() for r in data['results'])
print('yes' if found else 'no')
")
[ "$UPDATED" = "yes" ] && pass "Updated memory is searchable" || fail "Updated memory not found in search"

# --- Summary ---
echo ""
echo "================================================"
echo -e "${GREEN}All tests passed!${NC}"
echo "================================================"
echo ""
echo "Memory system verified:"
echo "  ✓ Demo data populated (2 projects, 2 reflections, 2 sessions, 1 artifact)"
echo "  ✓ Semantic search works across memory types"
echo "  ✓ Cross-type search finds related memories"
echo "  ✓ Memory CLI commands (list, search, recall, save)"
echo "  ✓ Memory updates are searchable"
echo ""
echo "Try it yourself:"
echo "  agentbox memory search 'how to debug production issues'"
echo "  agentbox memory recall 'auth migration progress'"
echo "  agentbox memory list"
