# Scaling Plan: 1 Million Users

## Current State Analysis

### Current Architecture Limitations
- **In-memory sessions** - Single process, no persistence
- **Synchronous execution** - Blocks on each request
- **Single server** - No horizontal scaling
- **No caching** - Every request hits external APIs
- **No rate limiting** - No protection against abuse
- **No user management** - Single user CLI
- **No database** - All data in memory
- **No load balancing** - Single point of failure

## Target Requirements

### Scale Metrics
- **1,000,000 users**
- **Peak load**: 100,000 concurrent users
- **Requests/second**: 10,000+ RPS
- **Response time**: <500ms (p95)
- **Availability**: 99.9% (8.76 hours downtime/year)
- **Context storage**: 10MB per user (10TB total)

## Architecture Redesign

### 1. Application Layer

#### Current: Single Python CLI
```python
# Current: src/main.py - Single process
orchestrator = Orchestrator()
orchestrator.authenticate()
orchestrator.process_command(command)
```

#### New: Microservices Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway (Kong/Envoy)                 │
│  - Rate limiting, Auth, Routing, SSL termination           │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
┌───────▼───────┐ ┌────▼──────┐ ┌────▼──────┐
│  Intent API   │ │ Gmail API │ │Calendar API│
│  Service      │ │  Service  │ │  Service  │
└───────┬───────┘ └────┬──────┘ └────┬──────┘
        │              │              │
        └──────────────┼──────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
┌───────▼───────┐ ┌────▼──────┐ ┌────▼──────┐
│ Session API   │ │ Workflow  │ │ Drive API │
│  Service      │ │  Engine   │ │  Service  │
└───────┬───────┘ └────┬──────┘ └────┬──────┘
```

**Service Breakdown:**
1. **Intent Service** - Handles OpenAI calls, intent parsing
2. **Gmail Service** - Gmail API operations
3. **Calendar Service** - Calendar API operations
4. **Drive Service** - Drive API operations
5. **Session Service** - Manages user sessions and context
6. **Workflow Service** - Multi-service workflow orchestration
7. **Auth Service** - User authentication, OAuth management

**Technology Stack:**
- **Language**: Python 3.10+ (FastAPI/Flask) or Go (for high performance)
- **Framework**: FastAPI (async, high performance) or Go microservices
- **Containerization**: Docker + Kubernetes
- **API Gateway**: Kong, Envoy, or AWS API Gateway

### 2. Data Storage Architecture

#### Session & Context Storage

**Option A: Redis (Primary) + PostgreSQL (Secondary)**
```
Redis Cluster:
- Active sessions (1M users × 10KB = 10GB)
- Hot context (last 10 commands per user)
- TTL: 24 hours
- Replication: 3 replicas per shard
- Sharding: By user_id hash

PostgreSQL:
- Long-term session history
- User preferences
- Command history archive
- Context snapshots
```

**Redis Cluster Design:**
```python
# Session storage in Redis
session_key = f"session:{user_id}:{session_id}"
redis.setex(
    session_key,
    ttl=86400,  # 24 hours
    value=json.dumps({
        "history": last_10_commands,
        "references": context_references,
        "started_at": timestamp
    })
)

# Context storage (compressed)
context_key = f"context:{user_id}"
redis.setex(
    context_key,
    ttl=604800,  # 7 days
    value=compress(json.dumps(large_context))
)
```

**PostgreSQL Schema:**
```sql
-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE,
    google_user_id VARCHAR(255),
    created_at TIMESTAMP,
    last_active TIMESTAMP,
    preferences JSONB,
    INDEX idx_email (email),
    INDEX idx_google_user_id (google_user_id)
);

-- Sessions table
CREATE TABLE sessions (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    command_count INTEGER,
    INDEX idx_user_id (user_id),
    INDEX idx_started_at (started_at)
);

-- Command history (partitioned by month)
CREATE TABLE command_history (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES sessions(id),
    user_id UUID REFERENCES users(id),
    command TEXT,
    service VARCHAR(50),
    intent VARCHAR(100),
    parameters JSONB,
    result JSONB,
    success BOOLEAN,
    timestamp TIMESTAMP,
    INDEX idx_user_timestamp (user_id, timestamp),
    INDEX idx_session_id (session_id)
) PARTITION BY RANGE (timestamp);

-- Context snapshots (for large context)
CREATE TABLE context_snapshots (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    context_data JSONB,
    compressed BOOLEAN,
    created_at TIMESTAMP,
    INDEX idx_user_id (user_id)
);
```

**Option B: Multi-Tier Storage**
```
L1 Cache (Redis): 
- Active sessions (last 1 hour)
- Hot data (10M keys × 10KB = 100GB)

L2 Cache (Redis + Compression):
- Recent sessions (last 24 hours)
- Compressed context

L3 Storage (PostgreSQL + TimescaleDB):
- Long-term history
- Analytics data
- Time-series for monitoring

L4 Archive (S3/Cloud Storage):
- Old sessions (>30 days)
- Backup snapshots
```

#### Database Selection

**Primary Database: PostgreSQL**
- **Why**: ACID compliance, JSON support, mature ecosystem
- **Scaling**: Read replicas, connection pooling, sharding
- **Size**: 1M users × 10MB = 10TB (with compression: 2-3TB)

**Caching Layer: Redis Cluster**
- **Why**: Sub-millisecond latency, pub/sub for real-time
- **Setup**: 6-node cluster (3 masters, 3 replicas)
- **Memory**: 500GB total (with replication)
- **Sharding**: Consistent hashing by user_id

**Time-Series Data: TimescaleDB**
- **Why**: Optimized for analytics, monitoring
- **Use**: Command metrics, API usage, error tracking

**Object Storage: S3/Cloud Storage**
- **Why**: Cost-effective for archives
- **Use**: Old session backups, logs

### 3. Caching Strategy

#### Multi-Level Caching

```python
# L1: In-memory (application level)
@lru_cache(maxsize=10000)
def get_user_preferences(user_id: str):
    return redis.get(f"prefs:{user_id}")

# L2: Redis (hot data)
def get_session_context(user_id: str):
    # Check Redis first
    context = redis.get(f"session:{user_id}")
    if context:
        return json.loads(context)
    
    # Fallback to PostgreSQL
    context = db.get_session_context(user_id)
    # Cache in Redis for 1 hour
    redis.setex(f"session:{user_id}", 3600, json.dumps(context))
    return context

# L3: CDN (for static responses)
# Cache common intents, templates
```

**Cache Invalidation Strategy:**
```python
# Cache tags
cache.set("user:123", data, tags=["user:123", "session:abc"])

# Invalidate on update
cache.invalidate_tags(["user:123"])

# TTL-based expiration
cache.set("context:123", data, ttl=3600)  # 1 hour
```

#### Cached Data Types
1. **User Preferences** - TTL: 1 hour
2. **Active Sessions** - TTL: 24 hours
3. **Intent Patterns** - TTL: 1 day (common commands)
4. **API Responses** - TTL: 5 minutes (for read operations)
5. **OAuth Tokens** - TTL: 1 hour (refresh before expiry)

### 4. Message Queue & Async Processing

#### Architecture
```
┌─────────────┐
│  API Gateway │
└──────┬───────┘
       │
       ▼
┌─────────────┐      ┌──────────────┐
│  Fast API    │─────▶│  RabbitMQ /  │
│  Services   │      │  Kafka       │
└─────────────┘      └──────┬───────┘
                             │
                ┌────────────┼────────────┐
                │            │            │
         ┌──────▼───┐  ┌─────▼────┐  ┌───▼────┐
         │ Intent   │  │ Gmail    │  │Calendar│
         │ Worker   │  │ Worker   │  │ Worker │
         └──────────┘  └──────────┘  └────────┘
```

**Message Queue: RabbitMQ or Kafka**
- **RabbitMQ**: Better for request/response, simpler
- **Kafka**: Better for high throughput, event streaming

**Queue Design:**
```python
# Priority queues
HIGH_PRIORITY_QUEUE = "intent.high"      # Real-time commands
NORMAL_QUEUE = "intent.normal"            # Standard commands
BATCH_QUEUE = "intent.batch"              # Bulk operations

# Dead letter queue for failures
DLQ = "intent.dlq"
```

**Async Processing:**
```python
# FastAPI async endpoint
@app.post("/api/v1/command")
async def process_command(request: CommandRequest):
    # Queue for async processing
    task_id = await queue.enqueue(
        queue="intent.normal",
        task="process_intent",
        data=request.dict(),
        priority=request.priority
    )
    
    # Return immediately
    return {
        "task_id": task_id,
        "status": "queued",
        "poll_url": f"/api/v1/tasks/{task_id}"
    }

# Worker processes
@worker.task(queue="intent.normal")
async def process_intent(command_data):
    # Heavy processing here
    result = await orchestrator.process_command(command_data)
    return result
```

### 5. Database Sharding Strategy

#### Sharding by User ID

```python
# Consistent hashing
def get_shard(user_id: str, num_shards: int = 100) -> int:
    hash_value = hashlib.md5(user_id.encode()).hexdigest()
    shard_id = int(hash_value, 16) % num_shards
    return shard_id

# Shard distribution
# 1M users / 100 shards = 10,000 users per shard
# Each shard: PostgreSQL instance or separate database
```

**Shard Configuration:**
```
Shard 0-9:    PostgreSQL Cluster 1 (Primary + 2 replicas)
Shard 10-19:  PostgreSQL Cluster 2
...
Shard 90-99:  PostgreSQL Cluster 10
```

**Shard Routing:**
```python
class ShardRouter:
    def __init__(self):
        self.shards = {
            i: f"postgresql://shard-{i//10}/db"
            for i in range(100)
        }
    
    def get_connection(self, user_id: str):
        shard_id = get_shard(user_id)
        return self.shards[shard_id]
```

### 6. Load Balancing & High Availability

#### Load Balancer Configuration
```
┌─────────────────┐
│   CloudFlare    │  (CDN, DDoS protection)
└────────┬────────┘
         │
┌────────▼────────┐
│   AWS ALB /     │  (Application Load Balancer)
│   Nginx LB      │  - Health checks
└────────┬────────┘  - SSL termination
         │
    ┌────┴────┐
    │         │
┌───▼───┐ ┌───▼───┐
│  API  │ │  API  │  (Multiple instances)
│  Pod 1│ │  Pod 2│  - Auto-scaling
└───────┘ └───────┘  - Health checks
```

**Load Balancer Features:**
- **Health checks**: Every 30 seconds
- **Sticky sessions**: For WebSocket connections
- **SSL termination**: TLS 1.3
- **Rate limiting**: Per IP, per user
- **Circuit breaker**: Fail fast on errors

#### Auto-Scaling Strategy

**Kubernetes HPA (Horizontal Pod Autoscaler):**
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: intent-service
spec:
  minReplicas: 10
  maxReplicas: 100
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  - type: Pods
    pods:
      metric:
        name: requests_per_second
      target:
        type: AverageValue
        averageValue: "100"
```

**Scaling Triggers:**
- CPU > 70%: Scale up
- Memory > 80%: Scale up
- Queue depth > 1000: Scale up workers
- RPS > 100 per pod: Scale up

### 7. API Response Optimization

#### Response Time Targets
- **Intent parsing**: <200ms (p95)
- **Gmail operations**: <300ms (p95)
- **Calendar operations**: <250ms (p95)
- **Drive operations**: <400ms (p95)
- **Total end-to-end**: <500ms (p95)

#### Optimization Strategies

**1. Parallel API Calls**
```python
# Sequential (current)
gmail_result = await gmail_service.search()
calendar_result = await calendar_service.list_events()

# Parallel (optimized)
gmail_result, calendar_result = await asyncio.gather(
    gmail_service.search(),
    calendar_service.list_events()
)
```

**2. Request Batching**
```python
# Batch multiple user requests
async def batch_process_commands(commands: List[Command]):
    # Process in parallel batches of 10
    batches = [commands[i:i+10] for i in range(0, len(commands), 10)]
    results = await asyncio.gather(*[
        process_batch(batch) for batch in batches
    ])
    return results
```

**3. Connection Pooling**
```python
# Redis connection pool
redis_pool = redis.ConnectionPool(
    host='redis-cluster',
    port=6379,
    max_connections=1000,
    decode_responses=True
)

# PostgreSQL connection pool
db_pool = asyncpg.create_pool(
    host='postgres-cluster',
    min_size=10,
    max_size=100
)
```

**4. Streaming Responses**
```python
# For long-running operations
@app.post("/api/v1/command")
async def process_command(request: CommandRequest):
    async def generate():
        yield {"status": "processing"}
        result = await orchestrator.process_command(request.command)
        yield {"status": "complete", "result": result}
    
    return StreamingResponse(generate())
```

### 8. Monitoring & Observability

#### Metrics to Track

**Application Metrics:**
- Request rate (RPS)
- Response time (p50, p95, p99)
- Error rate (4xx, 5xx)
- Queue depth
- Active sessions

**Infrastructure Metrics:**
- CPU usage per pod
- Memory usage per pod
- Database connections
- Redis memory usage
- Network throughput

**Business Metrics:**
- Active users (DAU, MAU)
- Commands per user
- Popular intents
- API usage by service

**Tools:**
- **Metrics**: Prometheus + Grafana
- **Logging**: ELK Stack (Elasticsearch, Logstash, Kibana)
- **Tracing**: Jaeger or Zipkin
- **APM**: New Relic or Datadog

### 9. Security & Authentication

#### Multi-User Authentication

**Current**: Single OAuth token
**New**: Per-user OAuth with token management

```python
# User authentication service
class AuthService:
    async def authenticate_user(self, user_id: str) -> Credentials:
        # Check Redis cache
        token = await redis.get(f"oauth_token:{user_id}")
        if token:
            return Credentials.from_token(token)
        
        # Refresh from database
        user = await db.get_user(user_id)
        credentials = await refresh_oauth_token(user)
        
        # Cache for 1 hour
        await redis.setex(
            f"oauth_token:{user_id}",
            3600,
            credentials.to_json()
        )
        return credentials
```

**Token Storage:**
- **Redis**: Active tokens (encrypted)
- **PostgreSQL**: Token metadata (user_id, expires_at)
- **Encryption**: AES-256 at rest

**Rate Limiting:**
```python
# Per-user rate limits
@rate_limit(requests=100, period=60)  # 100 req/min
@rate_limit(requests=1000, period=3600)  # 1000 req/hour
async def process_command(user_id: str, command: str):
    pass
```

### 10. Database Migration Plan

#### Phase 1: Add PostgreSQL (No downtime)
```python
# Dual-write pattern
async def save_session(session_data):
    # Write to both in-memory (current) and PostgreSQL
    in_memory_session = SessionContext(**session_data)
    await db.save_session(session_data)  # Async, non-blocking
    return in_memory_session
```

#### Phase 2: Migrate to Redis (Gradual)
```python
# Feature flag
if FEATURE_FLAG_REDIS_SESSIONS:
    session = await redis.get_session(user_id)
else:
    session = in_memory_session
```

#### Phase 3: Remove In-Memory (Cutover)
```python
# Remove old code, use Redis only
session = await redis.get_session(user_id)
```

### 11. Cost Estimation (AWS Example)

**Compute (Kubernetes):**
- API pods: 50 instances × $0.10/hour = $5/hour = $3,600/month
- Workers: 100 instances × $0.10/hour = $10/hour = $7,200/month

**Database:**
- PostgreSQL: 10 shards × $500/month = $5,000/month
- Read replicas: 20 × $250/month = $5,000/month

**Cache:**
- Redis Cluster: 6 nodes × $300/month = $1,800/month

**Storage:**
- PostgreSQL storage: 3TB × $0.10/GB = $300/month
- S3 archive: 10TB × $0.023/GB = $230/month

**Network:**
- Data transfer: ~$500/month

**Total: ~$24,000/month** (~$0.024 per user/month)

### 12. Implementation Roadmap

#### Phase 1: Foundation (Months 1-2)
- [ ] Add PostgreSQL database
- [ ] Implement user authentication
- [ ] Migrate session storage to Redis
- [ ] Add API layer (FastAPI)
- [ ] Implement connection pooling

#### Phase 2: Scaling (Months 3-4)
- [ ] Add message queue (RabbitMQ/Kafka)
- [ ] Implement async processing
- [ ] Add database sharding
- [ ] Set up load balancing
- [ ] Implement caching layers

#### Phase 3: Optimization (Months 5-6)
- [ ] Add monitoring (Prometheus/Grafana)
- [ ] Optimize API responses
- [ ] Implement CDN
- [ ] Add auto-scaling
- [ ] Performance tuning

#### Phase 4: Production (Month 7+)
- [ ] Load testing
- [ ] Security audit
- [ ] Disaster recovery setup
- [ ] Documentation
- [ ] Gradual rollout

### 13. Key Code Changes

#### New Service Structure
```
services/
├── api/
│   ├── intent_api.py      # Intent parsing endpoint
│   ├── gmail_api.py        # Gmail operations
│   ├── calendar_api.py     # Calendar operations
│   └── session_api.py      # Session management
├── workers/
│   ├── intent_worker.py    # Background intent processing
│   ├── gmail_worker.py     # Gmail operation worker
│   └── workflow_worker.py  # Workflow orchestration
├── storage/
│   ├── redis_client.py     # Redis connection
│   ├── postgres_client.py  # PostgreSQL connection
│   └── session_store.py    # Session storage abstraction
└── utils/
    ├── rate_limiter.py     # Rate limiting
    ├── cache.py            # Caching utilities
    └── metrics.py         # Metrics collection
```

#### Example: FastAPI Service
```python
# services/api/intent_api.py
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.rate_limit import RateLimitMiddleware
import redis
import asyncpg

app = FastAPI()

# Dependencies
redis_client = redis.RedisCluster(...)
db_pool = await asyncpg.create_pool(...)

@app.post("/api/v1/command")
async def process_command(
    request: CommandRequest,
    user_id: str = Depends(get_current_user)
):
    # Rate limiting
    await check_rate_limit(user_id)
    
    # Get session from Redis
    session = await get_session(user_id)
    
    # Queue for processing
    task_id = await queue.enqueue(
        "process_intent",
        user_id=user_id,
        command=request.command,
        session_id=session.id
    )
    
    return {"task_id": task_id, "status": "queued"}

@app.get("/api/v1/tasks/{task_id}")
async def get_task_status(task_id: str):
    result = await redis_client.get(f"task:{task_id}")
    return json.loads(result)
```

### 14. Testing Strategy

#### Load Testing
```bash
# Target: 10,000 RPS
k6 run --vus 10000 --duration 5m load_test.js

# Test scenarios:
# - Intent parsing: 5,000 RPS
# - Gmail operations: 3,000 RPS
# - Calendar operations: 1,500 RPS
# - Drive operations: 500 RPS
```

#### Stress Testing
- Test with 2x expected load (20,000 RPS)
- Test database failover
- Test Redis failover
- Test cache invalidation

### 15. Disaster Recovery

#### Backup Strategy
- **PostgreSQL**: Daily backups, point-in-time recovery
- **Redis**: AOF (Append-Only File) + RDB snapshots
- **S3**: Versioned backups

#### Failover Plan
- **Database**: Multi-AZ with automatic failover
- **Redis**: Cluster mode with automatic failover
- **API**: Multi-region deployment

## Summary

**Key Changes Required:**
1. ✅ Microservices architecture (7 services)
2. ✅ PostgreSQL + Redis for storage
3. ✅ Message queue for async processing
4. ✅ Database sharding (100 shards)
5. ✅ Kubernetes for orchestration
6. ✅ Load balancing + auto-scaling
7. ✅ Multi-level caching
8. ✅ Monitoring & observability
9. ✅ User authentication system
10. ✅ Rate limiting & security

**Estimated Effort:** 6-7 months
**Estimated Cost:** $24,000/month (~$0.024/user/month)
**Team Size:** 5-7 engineers

**Priority Actions:**
1. Add PostgreSQL database
2. Implement Redis caching
3. Build API layer (FastAPI)
4. Add user authentication
5. Implement message queue
6. Set up monitoring

