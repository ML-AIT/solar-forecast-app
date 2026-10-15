# Architecture & stack decision

## What the course requires

- Phase 2 (due 2 Nov 2026): deployment preparation "using **Azure or AWS containers**", the app architecture, model serving
  and a **simple CI/CD pipeline**.
- Phase 3 (due 16 Nov 2026): deploy to production plus a presentation.
- Phase 0 brief: "learn to deploy your model using Azure or AWS and establish a **simple** CI/CD pipeline".

The grade is about the ML work plus a working, reproducible deployment. The frontend is not graded for its own sake.

## Decision: Next.js + FastAPI on Azure. Good enough, if we keep it small.

| Part | Choice | Why | Guardrail against over-engineering |
|---|---|---|---|
| Model serving | **FastAPI** in a **container** on **Azure Container Apps** | Satisfies "containers" directly. Python is the same language as the ML code. It scales to zero, so it is cheap | One service. No database, auth server or message queue. Forecasts are JSON files |
| Forecast generation | **Container Apps Job** on a daily cron (built from the ML repo) | Day-ahead forecasting is a **batch** problem, so nothing needs to predict live on each request | The API only reads precomputed forecasts |
| Dashboard | **Next.js static export** on **Azure Static Web Apps (Free)** | The tech stack is already agreed; Static Web Apps is free and has built-in CI/CD | No server-side rendering, no Next.js API routes, no auth. One page that fetches from the API |
| CI/CD | **GitHub Actions**: CI on every PR, deploy on merge to `main` (OIDC login) | It is the simplest pipeline the professor will accept | 3 workflow files |

**When it *would* be over-engineering:** running Next.js as a server, adding a database, user accounts, Kubernetes,
or microservices per plant. None of that adds marks.

**Simpler fallback if the team runs short of time:** drop Next.js and serve one HTML page from FastAPI, or use
Streamlit. The API, job and CI/CD stay exactly the same, so this choice is low-risk to change later.

## Request flow

```
            daily 11:00 ICT
ML repo ──► Container Apps Job ──► forecasts/S01/2026-10-17.json  (Azure Files)
                                         │
Browser ──► Static Web App (Next.js) ──► Container App (FastAPI)  GET /api/v1/forecast?plant_id=S01&date=…
```

## Repository split

- **solar-forecast-app** (this repo): API, web, infrastructure, deployment.
- **Solar_Power_Prediction** (ML repo): data, experiments, training. It also builds the `solar-ml` job image, which
  writes forecast JSON in the schema described in `apps/api/README.md`.

That JSON file is the contract between the two repos. Change it only via PRs that update both.
