<!-- This project was developed with assistance from AI tools. -->

# Summit Cap Financial

**Multi-Agent Loan Origination -- Red Hat AI Quickstart**

Summit Cap Financial is a reference application demonstrating how to build multi-agent AI systems on Red Hat AI / OpenShift AI using a realistic, regulated-industry business use case. This Quickstart showcases advanced AI patterns applied to the mortgage lending lifecycle, from prospect inquiry through pre-qualification, application, underwriting, and approval.

!!! warning "Demonstration Purposes Only"
    All regulatory and compliance content in this application is simulated for demonstration purposes. This is not a production-ready system and does not constitute legal or financial advice.

## What is Summit Cap Financial?

Summit Cap Financial is a fictional mortgage lender headquartered in Denver, Colorado. The application models the end-to-end mortgage lending process, covering:

- Prospect inquiry and pre-qualification
- Borrower application and document submission
- Loan officer pipeline management and workflow
- Underwriter review, compliance checks, and decisioning
- Executive analytics and performance monitoring

The mortgage domain was chosen because regulated financial services demand the most challenging AI patterns: role-scoped agents, compliance knowledge bases, fair lending guardrails, demographic data isolation, and comprehensive audit trails. The architecture is MVP-maturity with production structure -- component boundaries, data models, and integration patterns are designed so adopters can harden toward production without rearchitecting.

## Key Personas

The application provides five distinct persona experiences, each with its own interface and AI agent:

| Persona | Role | Key Capabilities |
|---------|------|------------------|
| **Prospect** | Anonymous visitor | Product discovery, affordability calculator, mortgage Q&A chat |
| **Borrower** | Authenticated applicant | Application submission, document upload, status tracking, condition responses |
| **Loan Officer** | Employee originator | Pipeline management, document review, borrower communication, underwriting preparation |
| **Underwriter** | Employee decision-maker | Application review, compliance verification, risk assessment, approval/denial decisions |
| **CEO** | Executive | Pipeline analytics, denial trends, loan officer performance, audit trail review |

Each persona has a dedicated chat interface powered by a role-scoped AI agent with persona-specific tools and guardrails.

## AI Patterns Demonstrated

This Quickstart demonstrates production-ready AI patterns for regulated industries:

- **Multi-Agent Orchestration**: Five role-scoped agents with distinct tool sets and system prompts, coordinated via LangGraph
- **Compliance Knowledge Base**: RAG-powered retrieval from federal regulations (TRID, ECOA, ATR/QM, HMDA), agency guidelines (Fannie Mae, FHA), and internal policies
- **Fair Lending Guardrails**: ECOA compliance checks, adverse action validation, and prohibited basis detection
- **HMDA Data Isolation**: Demographic information stored in a dedicated schema with restricted access, isolated from general application data
- **Audit Trails**: Immutable append-only audit logs with cryptographic hash chains for all agent actions and decisions
- **Model Routing**: Rule-based routing between fast/capable models based on query complexity and tool requirements
- **Safety Shields**: Optional integration with Llama Guard for input/output content moderation
- **Observability**: Comprehensive tracing via LangFuse for agent conversations, tool calls, and model usage

## Technology Stack

| Layer | Technology |
|-------|-----------|
| **Agent Framework** | LangGraph for multi-agent orchestration |
| **Observability** | LangFuse (self-hosted) for tracing and monitoring |
| **Model Serving** | LlamaStack abstraction layer (supports OpenAI, local LLMs, OpenShift AI) |
| **Backend** | FastAPI with async SQLAlchemy 2.0, Pydantic 2.x validation |
| **Database** | PostgreSQL 16 with pgvector for embeddings |
| **Frontend** | React 19 with TanStack Router and Query, Tailwind CSS, shadcn/ui components |
| **Identity** | Keycloak (OIDC) with role-based access control |
| **Storage** | MinIO (S3-compatible) for document storage |
| **Fairness Metrics** | TrustyAI Python library for bias detection |
| **Build System** | Turborepo monorepo with pnpm (Node.js) and uv (Python) |
| **Deployment** | Helm charts for OpenShift / Kubernetes |

## What's Next

- **[Architecture](architecture.md)** -- System design, component boundaries, and data flow
- **[Personas](personas.md)** -- Detailed persona workflows and capabilities
- **[API Reference](api-reference.md)** -- REST and WebSocket API documentation

## Project Goals

This Quickstart is designed to:

1. Showcase Red Hat AI / OpenShift AI capabilities through a credible, domain-rich business use case
2. Demonstrate advanced AI patterns for regulated industries (compliance, audit, fairness, data isolation)
3. Enable single-command local setup for rapid exploration
4. Serve as a reusable template that developers can clone, deploy, and adapt to their own domain

## Non-Goals

This is a reference application, not a production system. It does not include:

- Real external system integrations (credit bureaus, MLS, AUS, government databases)
- Real payment processing or financial transactions
- BSA/AML/KYC identity verification workflows
- Production security hardening (see maturity expectations)
- Mobile-native applications (web only)
- Multi-tenant / multi-institution support
- Automated underwriting decisions (all decisions require human confirmation)

## Source Code

The source code is available at [github.com/rh-ai-quickstart/mortgage-ai](https://github.com/rh-ai-quickstart/mortgage-ai).
