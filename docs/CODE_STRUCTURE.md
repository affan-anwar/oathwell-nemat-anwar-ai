# Code Structure
```
nemat-anwar-ai/
├── apps/
│   ├── web/                  React + Vite (features: workspace, campaign-brief, content-studio, approvals, integrations, analytics)
│   │   └── design-preview/   Look reference (HTML)
│   └── api/                  FastAPI + Python
│       ├── app/api/v1/       Routes
│       ├── app/core/         Config, security
│       ├── app/domains/      Tenants, campaigns, content, leads
│       ├── app/agent/        state_machine, policy_engine, executor (done); planner, tool_registry, memory, model_gateway (planned)
│       ├── app/integrations/ One adapter per provider
│       ├── app/workers/      Background jobs
│       ├── app/db/           Models and migrations
│       └── tests/
├── infra/
├── docs/ (architecture, runbooks)
└── .github/workflows/
```
