# Azure setup

What runs in Azure, how the pieces connect, and why. Everything is in one resource group on an **Azure for Students**
subscription. Expected cost is about $5 a month (Container Registry Basic is the main fixed cost); a budget emails at
$10. Delete the resource group after grading.

```
GitHub Actions ──OIDC──► managed identity id-gh-solar-deploy
   deploy-api.yml ──► ACR (solar-api) ─────────► Container App "solar-api"            (FastAPI, scale 0–1)
   deploy-web.yml ──────────────────────────────► Storage static website on stsolarkm  (Next.js static export)
   deploy-job.yml ──► ACR (solar-forecast-job) ─► Container Apps Job "solar-forecast-daily" (cron 23:00 ICT)

Storage account stsolarkm
   $web             the dashboard
   solar-models     model files     → job /models (read only)              API: not mounted
   solar-forecasts  forecast JSON   → job /forecasts (read and write)      API /forecasts (read only)
```

## Why it looks like this

- **Japan East.** Azure for Students allows only UAE North, Japan East, Central India, Indonesia Central and India
  South Central (Azure Policy → Assignments → allowed locations). Southeast Asia is not one of them.
- **Storage static website, not Static Web Apps.** Static Web Apps runs only in regions this subscription blocks. The
  dashboard is a static export, so plain file hosting is enough.
- **Two file shares.** The model files are made from confidential plant data, so only the job mounts them. The API
  mounts the forecast share read only: it can serve forecasts but never change them.
- **A job, not code in the API.** Day-ahead forecasting is a batch problem. The job runs once a night and exits; the
  API only reads files, needs no model code, and scales to zero.
- **No passwords.** Images are pulled by each app's own identity and pushed by the deploy identity; GitHub logs in
  with a federated credential. The only stored secret is the storage account key, which Container Apps needs for the
  file share mounts (they cannot use a managed identity) and keeps inside the environment.
- **No VNet.** Everything uses public HTTPS endpoints. Confidentiality comes from what is mounted where, and plant data
  never reaches Azure.

## Resources

All in resource group `rg-solar-forecast`, Japan East (the alert and action group are global).

| Resource | Name | Settings that matter |
|---|---|---|
| Container Registry | `acrsolarkm` | Basic (10 GB); admin user off. Image tags are git commits |
| Storage account | `stsolarkm` | StorageV2, Standard LRS, TLS 1.2, anonymous blob access off, **shared key access on** (the mounts need it) |
| Static website | on `stsolarkm` | Index `index.html`, error `404.html`, content in `$web` |
| File shares | `solar-models`, `solar-forecasts` | Classic file shares, SMB, transaction optimized, no backup |
| Log Analytics workspace | | 30-day retention; receives all container logs |
| Container Apps environment | `cae-solar` | **Workload profiles** mode (Consumption profile), public network, logs to the workspace |
| Container App | `solar-api` | Ingress external, HTTPS only, target port 8000; 0.5 CPU, 1 GiB; scale 0–1; single revision mode |
| Container Apps Job | `solar-forecast-daily` | Schedule `0 16 * * *` (UTC = 23:00 Bangkok); timeout 1800 s; 1 retry; 0.5 CPU, 1 GiB; env `ISSUE_SCENARIO=d1_2355` |
| Managed identity | `id-gh-solar-deploy` | User-assigned; the account GitHub Actions logs in as |
| Action group | `ag-solar-email` | Emails the deployment owner |
| Metric alert | `alert-forecast-job-failed` | Job metric `Executions`, `state` = `Failed`, total > 0; every 5 min over 15 min; severity 1; resolves by itself |
| Budget | on the subscription | $10 a month, emails at 50, 80 and 100 % |

## Identities and roles

| Identity | Role | Scope | Why |
|---|---|---|---|
| `id-gh-solar-deploy` | Contributor | Resource group | Update the API's and the job's image |
| | AcrPush | Registry | Push images |
| | Storage Blob Data Contributor | Storage account | Upload the dashboard to `$web` (a data role; Contributor alone cannot) |
| `solar-api` (system-assigned) | AcrPull | Registry | Pull its image |
| `solar-forecast-daily` (system-assigned) | AcrPull | Registry or resource group | Pull its image |

The deploy identity has one federated credential per repo that deploys: issuer `https://token.actions.githubusercontent.com`,
audience `api://AzureADTokenExchange`, subject = the repo's `production` environment. This org uses GitHub's ID-based
subject format (`repo:<owner>@<ownerId>/<repo>@<repoId>:environment:production`), so the portal's "GitHub Actions"
scenario, which builds the name-based form, does not match; use "Other issuer" with the subject from the command below.

## File shares and mounts

A share reaches a container in three links: the **file share**, an **environment storage** on `cae-solar` (share +
access mode + account key), and a **volume and mount** on the app or job.

| Environment storage | Share | Access | Mounted in | Path | Mount options |
|---|---|---|---|---|---|
| `models-ro` | `solar-models` | Read only | job | `/models` | `uid=10001,gid=10001,dir_mode=0550,file_mode=0440` |
| `forecasts-rw` | `solar-forecasts` | Read/write | job | `/forecasts` | `uid=10001,gid=10001,dir_mode=0750,file_mode=0640` |
| `forecasts-ro` | `solar-forecasts` | Read only | API | `/forecasts` | `uid=10001,gid=10001,dir_mode=0550,file_mode=0440` |

Both images run as user 10001, and Azure Files mounts belong to root unless `uid`/`gid` say otherwise. The API also
needs `FORECAST_PROVIDER=file` and `FORECAST_DIR=/forecasts`; its other settings are `APP_ENV=production` and
`ALLOWED_ORIGINS` = the website URL without a trailing slash.

The five model files (`pvlib_baseline_{S01,S02}.json`, `{S01,S02}_climatology.csv`, `climatology_meta.json`) are
uploaded to `solar-models` by hand. They are made from the plant data, so they are never committed or built into an
image.

## GitHub settings

Environment **production** holds these variables (no secrets are needed): `AZURE_CLIENT_ID` (the deploy identity),
`AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_RESOURCE_GROUP`, `ACR_NAME`, `CONTAINER_APP_NAME`,
`FORECAST_JOB_NAME`, `STORAGE_ACCOUNT`, `API_BASE_URL` (`https://` + the API's FQDN; baked into the dashboard build).

`DEPLOY_API`, `DEPLOY_WEB` and `DEPLOY_JOB` turn the three deploy workflows on. They must be **repository** variables:
GitHub evaluates a job's `if:` before it loads the environment, so a switch set on the environment reads as empty and
the deploy silently skips.

| Workflow | Runs on | Does |
|---|---|---|
| `deploy-api.yml` | push to `main` touching `apps/api/**` | build, push, `az containerapp update --image` (keeps env vars and mounts), `/health` check |
| `deploy-web.yml` | push to `main` touching `apps/web/**` | build with `API_BASE_URL`, upload `out/` to `$web` |
| `deploy-job.yml` | CI passing on `main` | build and deploy only if `apps/forecast-job/` changed since the running image's commit; check the mounts survived |

## Commands the portal cannot do

Find the OIDC subject for a repo:

```bash
gh api repos/<owner>/<repo>/actions/oidc/customization/sub --jq .sub_claim_prefix
```

Append `:environment:production`.

Mount the shares. The CLI has no volume flags, so export the app or job, add the volumes with
[`add_mounts.py`](add_mounts.py), and apply. Export right before applying: an older export undoes later changes,
including a system identity turned on after it.

```bash
az containerapp job show -g rg-solar-forecast -n solar-forecast-daily -o yaml > /tmp/job.yaml
uv run --no-project --with pyyaml python infra/azure/add_mounts.py job /tmp/job.yaml /tmp/job-mounts.yaml
az containerapp job update -g rg-solar-forecast -n solar-forecast-daily --yaml /tmp/job-mounts.yaml
```

For the API: `az containerapp show` / `add_mounts.py api` / `az containerapp update` the same way (it also sets
`FORECAST_PROVIDER` and `FORECAST_DIR`). In the portal the API's volumes are under Application → Volumes.

Let the job pull with its identity (the portal has no setting for this on jobs):

```bash
az containerapp job registry set -g rg-solar-forecast -n solar-forecast-daily --server acrsolarkm.azurecr.io --identity system
```

## Gotchas

- **Workload profiles mode is required.** Without `--environment-mode WorkloadProfiles` the CLI creates an Express
  environment, which refuses a system identity for registry pulls.
- **Overrides drop mounts.** `az containerapp job start` with `--image`/`--command`/`--env-vars` runs that execution
  without the job's mounts and env vars. To test a fallback, change the job's env var, start it plainly, then remove
  the variable. A run that only exits 1 (`--command false`) is how the failure alert was tested.
- **Finished runs' logs are only in Log Analytics** (`ContainerAppConsoleLogs_CL`, one JSON line per plant and day);
  `az containerapp job logs show` works only while a run is going.
- **Rotating the storage key** breaks the mounts until all three environment storages have the new key.
- **Owner cannot read file share contents with `--auth-mode login`**: that needs a file data role. Use the account key
  or the portal's storage browser.

## Clean up

```bash
az group delete -n rg-solar-forecast --yes --no-wait
```

The budget and the GitHub environment and variables are outside the resource group; remove them separately.
