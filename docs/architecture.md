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
| Forecast generation | **Container Apps Job** on a daily cron (`apps/forecast-job`, with the ML repo's feature and model code copied in) | Day-ahead forecasting is a **batch** problem, so nothing needs to predict live on each request | The API only reads precomputed forecasts |
| Dashboard | **Next.js static export** on an **Azure Storage static website** | The tech stack is already agreed; Static Web Apps is not available in the regions Azure for Students allows here, and a static export needs only file hosting | No server-side rendering, no Next.js API routes, no auth. Two client-side pages (station overview, station detail) that fetch from the API. See [frontend-requirements.md](frontend-requirements.md) |
| CI/CD | **GitHub Actions**: CI on every PR, deploy on merge to `main` (OIDC login) | It is the simplest pipeline the professor will accept | 3 workflow files |

**When it *would* be over-engineering:** running Next.js as a server, adding a database, user accounts, Kubernetes,
or microservices per plant. None of that adds marks.

**Simpler fallback if the team runs short of time:** drop Next.js and serve one HTML page from FastAPI, or use
Streamlit. The API, job and CI/CD stay exactly the same, so this choice is low-risk to change later.

## Request flow

```
            daily 11:00 ICT
apps/forecast-job ──► Container Apps Job ──► forecasts/S01/2026-10-17.json  (Azure Files)
                                         │
Browser ──► Storage static website (Next.js) ──► Container App (FastAPI)  GET /api/v1/forecast?plant_id=S01&date=…
```

## Repository split

- **solar-forecast-app** (this repo): API, web, forecast job, infrastructure, deployment. The job's feature and model
  code is copied unchanged from the ML repo and checked for drift (`apps/forecast-job/README.md`).
- **Solar_Power_Prediction** (ML repo): data, experiments, training. The forecast job writes JSON in the schema
  described in `apps/api/README.md`.

That JSON file is the contract between the two repos. Change it only via PRs that update both.
