# Architecture
These are designs. Capacity numbers are targets until load tests prove them.

## 1. System
```mermaid
flowchart TD
  U[Web, mobile, API clients] --> E[CDN, WAF, API gateway]
  E --> C[Core services FastAPI]
  C --> A[Agent platform]
  A --> P[Policy engine and execution guard]
  P --> CH[Channel adapters: CMS, email, social, ads]
  CH --> M[Metrics and analytics]
  M --> A
  C --- D[(Postgres, Redis, Vector DB, ClickHouse)]
```

## 2. Agent execution flow
```mermaid
flowchart TD
  B[Brief and rules] --> PL[Plan the day]
  PL --> G[Generate content]
  G --> V[Validate: links, brand words, consent]
  V --> S{Policy decision}
  S -- Automatic allowed --> Q[Schedule]
  S -- Ask me first --> R[Review inbox]
  R -- approve --> Q
  R -- reject or changes --> G
  Q --> X[Execution guard]
  X -- blocked --> Z[Log reason]
  X -- ok --> PR[Provider call with idempotency key]
  PR --> CF{Provider confirms?}
  CF -- yes --> OK[Published or sent]
  CF -- no or unclear --> RC[Reconciliation required]
  OK --> L[Learn from results]
```

## 3. Data flow
```mermaid
flowchart LR
  User --> API --> DB[(Postgres)]
  API --> Queue[Task queue]
  Queue --> Worker --> Gateway[Model gateway]
  Worker --> Guard --> Adapter --> Provider
  Provider --> Webhook --> Events[(Delivery events)] --> Metrics[(ClickHouse)]
  Worker --> Audit[(Audit events)]
```

## 4. Authentication and approval
```mermaid
sequenceDiagram
  participant U as User
  participant A as API
  participant G as Guard
  U->>A: Login
  A-->>U: Session with tenant and role
  U->>A: Approve content version
  A->>A: Check role, tenant, content hash
  A-->>U: Approval stored for exact version
  A->>G: Execute at scheduled time
  G->>G: Recheck approval, limits, pause, consent
```

## 5. Deployment
```mermaid
flowchart TD
  Git --> CI --> Reg[Image registry] --> K[Container platform]
  K --> API2[API pods]
  K --> W[Worker pods]
  API2 --> PG[(Managed Postgres)]
  W --> PG
  API2 --> RD[(Redis)]
  K --> Sec[Managed secrets]
```

## 6. Scale design for 10 million registered users (target, untested)
Assumptions to validate: 1 percent daily active (100,000 users), about 20 agent actions per tenant per day, peaks at 5 times average.
```mermaid
flowchart TD
  Users --> CDN --> GW[API gateway with tenant limits]
  GW --> Core[Stateless API, autoscaled]
  Core --> Bus[Event bus partitioned by tenant]
  Bus --> AW[Agent workers, autoscaled by queue depth]
  AW --> LLM[Model gateway with routing and caching]
  AW --> Guard2[Policy and guard] --> Ad[Adapters with per-provider rate limits]
  Core --> PGS[(Postgres sharded by tenant)]
  Core --> RC[(Redis)]
  Bus --> CH2[(ClickHouse metrics)]
  AW --> VDB[(Vector DB)]
  CP[Global control plane: tenant directory, billing, auth] --- GW
```
Needed before claiming capacity: load tests, shard rebalancing test, provider rate-limit test, cost model.
