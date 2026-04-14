# Enterprise Agentic AI Architecture — 실습 가이드

> **PPT 연동**: 이 저장소는 `2026_Enterprise_Agentic_AI_Architecture.pptx` 실습 부록(Slide 69-95)의
> 참조 구현입니다. P01~P05 각 Plane을 단계별로 커밋하여 PPT 발표 순서와 동일하게 따라할 수 있습니다.

---

## 목차

- [A. 아키텍처 개요](#a-아키텍처-개요)
- [B. 사전 준비 및 환경 설정](#b-사전-준비-및-환경-설정)
- [C. P01 — Edge & Trust Boundary](#c-p01--edge--trust-boundary)
- [D. P02 — Control Plane](#d-p02--control-plane)
- [E. P03 — Domain Agent Runtime](#e-p03--domain-agent-runtime)
- [F. P04 — Shared Integration (MCP Server)](#f-p04--shared-integration-mcp-server)
- [G. P05 — Shared Knowledge / Memory / Model](#g-p05--shared-knowledge--memory--model)
- [H. 전체 스택 실행](#h-전체-스택-실행)
- [I. 관측성 (Observability)](#i-관측성-observability)
- [J. 배포 (Kubernetes / Helm)](#j-배포-kubernetes--helm)

---

## A. 아키텍처 개요

### 5-Plane 구조 (PPT Slide 12)

```
┌─────────────────────────────────────────────────────────┐
│  P01 Edge & Trust Boundary    (services/edge_api)        │
│  ─ JWT AuthN · Policy Guard · Risk Classifier            │
│  ─ ContextEnvelope 생성 (trace_id, tenant, risk_tier)   │
├─────────────────────────────────────────────────────────┤
│  P02 Control Plane            (services/control_plane)   │
│  ─ LangGraph 워크플로우 · Redis 체크포인트               │
│  ─ HITL Approval Gate (조건부, risk_score >= 0.8)       │
│  ─ Dispatcher → P03 에이전트 실행                        │
├──────────────────┬──────────────────────────────────────┤
│  P03 Domain      │  P04 Shared Integration               │
│  Agent Runtime   │  (services/mcp_server)                │
│  (agent_worker)  │  ─ Read / Write / Action 커넥터       │
│  ─ Research      │  ─ FastMCP Tool Gateway               │
│  ─ Operations    ├──────────────────────────────────────┤
│  ─ Customer      │  P05 Shared Knowledge                 │
│  ─ Finance       │  (services/knowledge_api)             │
│                  │  ─ RAG (pgvector)                     │
│                  │  ─ 3계층 메모리 (Redis)                │
│                  │  ─ LiteLLM Model Gateway              │
└──────────────────┴──────────────────────────────────────┘
```

### Runtime Tier 매핑 (PPT Slide 8)

| Tier | 역할 | Plane |
|------|------|-------|
| T1 Admission | 진입 검증, 인증/인가 | P01 |
| T2 Orchestration | 워크플로우 계획·조율 | P02 |
| T3 Domain Execution | 도메인별 태스크 실행 | P03 |

### Flow Semantics 5단계 (PPT Slide 9)

| Flow | 설명 | 구현 위치 |
|------|------|-----------|
| Flow 1: Admission | 모든 요청은 T1(P01) 진입 | `edge_api/routers/gateway.py` |
| Flow 2: Handoff | P02 → P03 에이전트 위임 | `control_plane/graph/nodes.py` dispatcher |
| Flow 3: Control loop | HITL 승인 (고위험 조건부) | `control_plane/graph/nodes.py` approval_gate |
| Flow 4: Shared usage | P03 → P04 도구 · P03 → P05 지식 독립 접근 | `agent_worker/agents/base.py` |
| Flow 5: Write path | 실행 후 P05 메모리 기록 | `knowledge_api/routers/memory.py` |

### ContextEnvelope (PPT Slide 기준)

모든 Plane 간 호출에 포함되는 단일 구조체 (`schemas/context_envelope.py`):

```python
ContextEnvelope(
    trace_id       = "uuid",         # 분산 추적
    tenant_id      = "acme",         # 멀티테넌트 격리
    user_id        = "analyst",      # 요청 주체
    session_id     = "uuid",         # 워크플로우 세션
    risk_tier      = "low",          # P01 분류: low / medium / high
    data_class     = "internal",     # public / internal / confidential / restricted
    scope          = ["read"],       # read / write / action
    delegation_chain = ["agent-1"],  # 에이전트 위임 체인 (감사 추적)
)
```

---

## B. 사전 준비 및 환경 설정

### 필요 도구

- Python 3.12+
- Docker Desktop (or Docker Engine + Compose plugin)
- Git

### 설치 및 설정

```bash
# 1. 저장소 클론
git clone https://github.com/choijoonbin/agentic-ai-lab.git
cd agentic-ai-lab

# 2. 환경 변수 설정
cp .env.example .env
# .env 열어서 ANTHROPIC_API_KEY 설정 (필수)
```

### `.env` 주요 항목

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `ANTHROPIC_API_KEY` | (필수 설정) | Anthropic API 키 |
| `JWT_SECRET_KEY` | `dev-secret-...` | JWT 서명 키 (운영 시 변경 필수) |
| `HIGH_RISK_THRESHOLD` | `0.7` | 이 점수 이상 → high risk |
| `REQUIRE_HITL_ABOVE` | `0.8` | 이 점수 이상 → HITL 승인 필요 |
| `LITELLM_MODEL` | `anthropic/claude-sonnet-4-6` | 기본 LLM 모델 |

---

## C. P01 — Edge & Trust Boundary

**PPT 연동**: Slide 13-17 (P01 상세)

### 역할

모든 에이전트 요청의 단일 진입점. 세 가지 핵심 기능:

1. **JWT 인증 (AuthN)** — 누가 요청하는가?
2. **Policy Guard (AuthZ)** — 무엇을 할 수 있는가?
3. **Risk Classifier** — 요청이 얼마나 위험한가?

### 주요 파일

```
services/edge_api/
├── auth/jwt_handler.py       # JWT 생성 / 검증 (python-jose)
├── policy/policy_guard.py    # RBAC 정책 평가
├── classifier/risk_classifier.py  # 키워드 + 스코프 기반 위험도 분류
├── routers/
│   ├── auth.py       # POST /auth/login
│   └── gateway.py    # POST /gateway/request
└── main.py
```

### API 사용 예시

```bash
# 1. 로그인 (JWT 토큰 획득)
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"analyst","password":"demo123","tenant_id":"acme"}'

# 응답: {"access_token": "eyJ...", "token_type": "bearer"}

# 2. 에이전트 요청 (토큰 포함)
curl -X POST http://localhost:8000/gateway/request \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "What are the latest AI trends?",
    "domain": "research",
    "requested_scope": ["read"]
  }'
```

### 데모 계정

| username | password | role | tenant |
|----------|----------|------|--------|
| `analyst` | `demo123` | analyst | acme |
| `admin` | `admin123` | admin | acme |

### Risk Classifier 로직

```
score = 0.0
+ 0.4  : 위험 키워드 포함 (delete, send email, transfer...)
+ 0.2  : 수정 키워드 포함 (update, modify, create...)
+ 0.3  : action scope 요청
+ 0.15 : write scope 요청
+ 0.1  : 고위험 도메인 (finance, operations)
× 0.8  : admin 역할 (위험도 감소)

tier: score >= 0.7 → high | >= 0.4 → medium | else → low
```

### Policy Guard 규칙

| Role | read | write | action | finance 도메인 |
|------|------|-------|--------|----------------|
| viewer | ✅ | ❌ | ❌ | ❌ |
| analyst | ✅ | ✅ | ❌ | ❌ |
| admin | ✅ | ✅ | ✅ | ✅ |

### 단위 테스트 실행

```bash
cd services/edge_api
pip install -r requirements.txt
pytest ../../tests/test_p01_edge.py ../../tests/test_p01_classifier.py ../../tests/test_p01_policy.py -v
```

---

## D. P02 — Control Plane

**PPT 연동**: Slide 18-23 (P02 상세)

### 역할

LangGraph 기반 워크플로우 오케스트레이터:
- 태스크를 서브태스크로 **분해** (Planner)
- 고위험 태스크에 대한 **HITL 승인 게이트** (조건부)
- P03 에이전트에 **위임** (Dispatcher)
- 결과 **집계** (Aggregator)

### LangGraph 노드 구조

```
planner → approval_gate ──(risk < 0.8)──→ dispatcher → aggregator → END
                  │
              (risk >= 0.8)
                  ↓
           [HITL 대기: Redis에 저장]
                  ↓
           POST /approval/decide
                  ↓
           dispatcher (체크포인트에서 재개)
```

> **주요 포인트 (PPT Slide 9 Flow 3)**:
> 승인은 **조건부**입니다. risk_score < 0.8이면 approval_gate를 통과하여 dispatcher로 바로 진행합니다.
> 승인 후 재개는 Planner 재실행이 아닌 **Dispatcher 체크포인트에서 재개**합니다.

### 주요 파일

```
services/control_plane/
├── graph/
│   ├── nodes.py     # planner, approval_gate, dispatcher, aggregator 노드
│   └── workflow.py  # LangGraph StateGraph 조립
├── state/
│   ├── schema.py           # WorkflowState, SubTask, WorkflowInput
│   └── redis_checkpoint.py # 체크포인트 저장/로드, 승인 대기 관리
├── routers/
│   ├── workflow.py  # POST /workflow/run
│   └── approval.py  # GET /approval/pending/{id}, POST /approval/decide
└── main.py
```

### HITL 승인 플로우 실습

```bash
# 1. 고위험 태스크 제출 (직접 Control Plane 호출)
curl -X POST http://localhost:8001/workflow/run \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Delete all expired user accounts from production",
    "domain": "operations",
    "context": {
      "tenant_id": "acme",
      "user_id": "admin",
      "session_id": "sess-001",
      "metadata": {"risk_score": 0.9}
    }
  }'
# 응답: {"requires_approval": true, "approval_granted": null, ...}

# 2. 대기 중인 승인 확인
curl http://localhost:8001/approval/pending/sess-001

# 3. 승인 결정
curl -X POST http://localhost:8001/approval/decide \
  -H "Content-Type: application/json" \
  -d '{"session_id":"sess-001","approved":true,"reviewer_id":"manager-1"}'
```

---

## E. P03 — Domain Agent Runtime

**PPT 연동**: Slide 24-28 (P03 상세)

### 역할

도메인별 전문 에이전트를 호스팅합니다. 모든 에이전트는 `BaseDomainAgent`를 상속하며:
1. P05 지식 검색 (자동)
2. P04 도구 호출 (도메인별)
3. LiteLLM을 통한 LLM 추론

### 에이전트 목록

| Agent | 도메인 | P04 도구 | 특징 |
|-------|--------|----------|------|
| ResearchAgent | research | web_search | 정보 수집·합성 |
| OperationsAgent | operations | get_metrics | 시스템 모니터링·인시던트 |
| CustomerAgent | customer | crm_lookup | CRM 조회·고객 지원 |
| FinanceAgent | finance | finance_query | 재무 분석 (admin 전용) |

### 주요 파일

```
services/agent_worker/
├── agents/
│   ├── base.py              # BaseDomainAgent (P04/P05 통합)
│   ├── research_agent.py
│   ├── operations_agent.py
│   ├── customer_agent.py
│   ├── finance_agent.py
│   └── registry.py          # 도메인 → 에이전트 매핑
├── routers/agent.py          # POST /agent/run
└── main.py
```

### 에이전트 직접 호출 실습

```bash
# Research Agent 직접 호출
curl -X POST http://localhost:8004/agent/run \
  -H "Content-Type: application/json" \
  -d '{
    "task": "What are key risks in enterprise AI deployments?",
    "domain": "research",
    "context": {"tenant_id": "acme", "trace_id": "t-001", "risk_tier": "low"}
  }'
```

### 새 에이전트 추가 방법

```python
# services/agent_worker/agents/hr_agent.py
from .base import BaseDomainAgent

class HRAgent(BaseDomainAgent):
    domain = "hr"
    system_prompt = "You are an HR specialist..."

    async def _call_tools(self, task, context):
        # P04 MCP 서버의 hr_lookup 도구 호출
        ...
```

그런 다음 `registry.py`에 등록:

```python
from .hr_agent import HRAgent
_registry["hr"] = HRAgent()
```

---

## F. P04 — Shared Integration (MCP Server)

**PPT 연동**: Slide 29-34 (P04 상세)

### 역할

FastMCP 기반 도구 게이트웨이. 모든 P03 에이전트가 외부 시스템에 접근하는 단일 창구.

### 커넥터 모델 (3가지 타입)

| 타입 | 승인 방식 | 도구 | 위험도 |
|------|----------|------|--------|
| **Read** | 자동 (auto-approved) | web_search, get_metrics, crm_lookup, finance_query | 낮음 |
| **Write** | RBAC (analyst+) | db_write, create_ticket | 중간 |
| **Action** | HITL 게이트 | send_email | 높음 |

### 주요 파일

```
services/mcp_server/
├── tools/
│   ├── read_connectors.py    # 읽기 전용 커넥터
│   ├── write_connectors.py   # RBAC 검사 커넥터
│   ├── action_connectors.py  # HITL 게이트 커넥터
│   └── registry.py           # 도구 이름 → 함수 매핑
├── routers/
│   ├── tools.py       # POST /tools/call, GET /tools/list
│   └── connectors.py  # GET /connectors/list
└── main.py
```

### 도구 호출 실습

```bash
# Read 커넥터 (자동 승인)
curl -X POST http://localhost:8002/tools/call \
  -H "Content-Type: application/json" \
  -d '{"tool":"web_search","arguments":{"query":"AI trends"},"context":{}}'

# Write 커넥터 (analyst 역할 필요)
curl -X POST http://localhost:8002/tools/call \
  -H "Content-Type: application/json" \
  -d '{"tool":"db_write","arguments":{"table":"logs"},"context":{"role":"analyst"}}'

# Action 커넥터 (HITL 승인 필요)
curl -X POST http://localhost:8002/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "send_email",
    "arguments": {"to":"mgr@acme.com","subject":"Q1 Report"},
    "context": {"approval_granted": true, "trace_id": "t-001"}
  }'

# 사용 가능한 도구 목록
curl http://localhost:8002/tools/list
```

### 단위 테스트 실행

```bash
cd services/mcp_server
pip install -r requirements.txt
pytest ../../tests/test_p04_tools.py -v
```

---

## G. P05 — Shared Knowledge / Memory / Model

**PPT 연동**: Slide 35-39 (P05 상세)

### 역할

세 가지 공유 자원을 제공:
1. **RAG (Retrieval Augmented Generation)** — pgvector 기반 의미 검색
2. **3계층 메모리** — 에피소딕/시맨틱/절차적
3. **LiteLLM 모델 게이트웨이** — 단일 API로 모든 LLM 접근

### RAG 파이프라인

```
[Ingest]  문서 → sentence-transformers → 384차원 벡터 → pgvector 저장
[Search]  쿼리 → sentence-transformers → IVFFlat ANN → cosine 유사도 → top-k
```

### 3계층 메모리 (PPT Slide 9 Flow 5: Write Path)

| 계층 | TTL | 용도 | 예시 |
|------|-----|------|------|
| episodic | 1시간 | 세션 상호작용 로그 | "사용자가 X를 요청했고 Y로 응답" |
| semantic | 7일 | 크로스세션 학습 사실 | "acme 테넌트는 finance 도메인을 자주 사용" |
| procedural | 영구 | 검증된 태스크 패턴 | "리포트 생성 워크플로우: 수집→분석→작성" |

### 주요 파일

```
services/knowledge_api/
├── rag/pipeline.py      # pgvector ingest / search
├── memory/store.py      # Redis 3계층 메모리
├── routers/
│   ├── knowledge.py     # POST /knowledge/search, /knowledge/ingest
│   ├── memory.py        # POST /memory/write, /memory/query
│   └── models.py        # POST /models/complete, GET /models/list
└── main.py
```

### 지식 시딩 및 검색 실습

```bash
# 1. 데모 지식 시딩
python scripts/seed_knowledge.py

# 2. 의미 검색
curl -X POST http://localhost:8003/knowledge/search \
  -H "Content-Type: application/json" \
  -d '{"query":"HITL approval flow","top_k":3,"tenant_id":"acme"}'

# 3. 메모리 쓰기 (Flow 5: Write Path)
curl -X POST http://localhost:8003/memory/write \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess-001",
    "agent_id": "research_agent",
    "content": "Q1 AI trends research completed successfully",
    "memory_type": "episodic",
    "metadata": {"task": "ai_trends", "result": "success"}
  }'

# 4. LLM 완성 (모델 게이트웨이)
curl -X POST http://localhost:8003/models/complete \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role":"user","content":"Explain Agentic AI in 2 sentences"}
    ],
    "max_tokens": 200
  }'
```

---

## H. 전체 스택 실행

### 빠른 시작

```bash
# 1. 환경 변수 설정
cp .env.example .env
# ANTHROPIC_API_KEY 반드시 설정

# 2. 전체 스택 빌드 및 실행
docker compose up --build -d

# 3. 실행 확인 (모든 서비스 healthy 상태 대기)
docker compose ps

# 4. 지식 시딩
python scripts/seed_knowledge.py

# 5. 엔드투엔드 데모
python scripts/demo_flow.py
```

### 서비스 포트

| 서비스 | 포트 | Swagger UI |
|--------|------|------------|
| P01 Edge API | 8000 | http://localhost:8000/docs |
| P02 Control Plane | 8001 | http://localhost:8001/docs |
| P04 MCP Server | 8002 | http://localhost:8002/docs |
| P05 Knowledge API | 8003 | http://localhost:8003/docs |
| P03 Agent Worker | 8004 | http://localhost:8004/docs |
| PostgreSQL | 5432 | — |
| Redis | 6379 | — |

### 전체 헬스 체크

```bash
for port in 8000 8001 8002 8003 8004; do
  echo -n "Port $port: "
  curl -s http://localhost:$port/health | python3 -c "import sys,json; print(json.load(sys.stdin))"
done
```

### 로그 확인

```bash
# 특정 서비스 로그
docker compose logs -f edge_api
docker compose logs -f control_plane

# 전체 로그
docker compose logs -f
```

### 서비스 중지

```bash
docker compose down        # 컨테이너 중지 (볼륨 유지)
docker compose down -v     # 컨테이너 + 볼륨 삭제 (DB 초기화)
```

---

## I. 관측성 (Observability)

### 관측성 스택 실행

```bash
# 전체 스택 + 관측성 동시 실행
docker compose -f docker-compose.yml -f docker-compose.observability.yml up -d
```

### 접속 URL

| 도구 | URL | 계정 |
|------|-----|------|
| Grafana | http://localhost:3000 | admin / admin |
| Prometheus | http://localhost:9090 | — |
| Jaeger (분산 추적) | http://localhost:16686 | — |

### 핵심 메트릭

- **P01**: 요청 건수, 위험 등급 분포, JWT 검증 실패율
- **P02**: 워크플로우 완료율, HITL 승인 대기 시간, 체크포인트 수
- **P03**: 에이전트별 실행 시간, LLM 토큰 사용량
- **P04**: 도구 호출 건수, 커넥터 타입별 분포
- **P05**: 벡터 검색 지연 시간, 메모리 계층별 히트율

---

## J. 배포 (Kubernetes / Helm)

> 이 섹션은 PPT Slide 40-46 (배포 뷰)의 실습 확장 내용입니다.

### 기본 Kubernetes 매니페스트 구조

```
k8s/
├── namespace.yaml
├── configmap.yaml        # 환경 설정
├── secret.yaml           # API 키 (실제 값 설정 필요)
├── deployments/
│   ├── edge-api.yaml
│   ├── control-plane.yaml
│   ├── agent-worker.yaml
│   ├── mcp-server.yaml
│   └── knowledge-api.yaml
└── services/
    ├── edge-api-svc.yaml
    └── ...
```

### Helm 차트 구조

```
helm/
└── agentic-ai/
    ├── Chart.yaml
    ├── values.yaml         # 기본값 (이미지, 리소스, 환경변수)
    ├── values-prod.yaml    # 운영 오버라이드
    └── templates/
        ├── deployment.yaml
        ├── service.yaml
        └── hpa.yaml        # Horizontal Pod Autoscaler
```

### 배포 명령 (참고)

```bash
# Helm으로 배포
helm install agentic-ai ./helm/agentic-ai \
  --namespace agentic-ai \
  --create-namespace \
  --set global.anthropicApiKey="sk-ant-..." \
  -f helm/agentic-ai/values-prod.yaml

# 상태 확인
kubectl get pods -n agentic-ai

# 업그레이드
helm upgrade agentic-ai ./helm/agentic-ai -n agentic-ai
```

---

## 문제 해결 (Troubleshooting)

### pgvector 연결 오류

```bash
# PostgreSQL 헬스 확인
docker compose exec postgres pg_isready -U postgres

# 수동 스키마 초기화
docker compose exec postgres psql -U postgres -d agentic_ai \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Redis 연결 오류

```bash
docker compose exec redis redis-cli ping
# PONG 응답 확인
```

### 에이전트 LLM 오류

```bash
# .env에 ANTHROPIC_API_KEY가 설정되어 있는지 확인
cat .env | grep ANTHROPIC
# agent_worker 로그 확인
docker compose logs agent_worker --tail=50
```

### 단위 테스트 (외부 서비스 불필요)

```bash
# 의존성 설치
pip install pytest pytest-asyncio

# P01 테스트 (FastAPI TestClient 사용)
cd services/edge_api && pip install -r requirements.txt
pytest ../../tests/test_p01_edge.py -v

# P04 도구 테스트
cd services/mcp_server && pip install -r requirements.txt
pytest ../../tests/test_p04_tools.py -v
```

---

## 커밋 히스토리 (단계별 학습)

이 저장소의 커밋은 PPT P01~P05 순서와 동일하게 구성되어 있습니다.
`git log --oneline`으로 각 단계를 확인하고, `git checkout <commit>` 으로
특정 단계의 코드 상태로 이동하여 학습할 수 있습니다.

```bash
git log --oneline
# docs: 실습 가이드 README
# test: P01/P04 단위 테스트 + 시드/데모 스크립트
# chore(infra): Docker Compose 전체 스택 + 관측성
# feat(P05): Knowledge/Memory/Model — pgvector RAG + 3계층 메모리 + LiteLLM
# feat(P04): Shared Integration — FastMCP Tool Gateway + 커넥터
# feat(P03): Domain Agent Runtime — BaseDomainAgent + 4개 에이전트
# feat(P02): Control Plane — LangGraph + Redis 체크포인트 + HITL 승인
# feat(P01): Edge & Trust Boundary — FastAPI + JWT + Policy + Classifier
# chore: 프로젝트 기반 구조 설정 — ContextEnvelope 스키마
```

---

*이 저장소는 `2026_Enterprise_Agentic_AI_Architecture.pptx` PPT의 실습 참조 구현입니다.*
