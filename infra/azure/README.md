# Azure setup (one-time)

Target: **Azure for Students** subscription ($100 credit, no card). Expected cost ≈ $5–10/month
(Container Registry Basic is the main fixed cost; Container Apps scale to zero; Static Web Apps Free tier).
**Set a budget alert at $10** and delete the resource group after grading.

```
GitHub Actions ──OIDC──► Azure
   deploy-api.yml ──► ACR (solar-api image) ──► Container App  "solar-api"   (FastAPI, scale 0–1)
   deploy-web.yml ──────────────────────────► Static Web App  "solar-web"   (Next.js static export)
   (later, ML repo) ─► ACR (solar-ml image)  ──► Container Apps JOB "solar-forecast-daily" (cron)
                                                     └─ writes forecast JSON → Azure Files/Blob → read by API (FORECAST_PROVIDER=file)
```

## 1. Variables

```bash
# Git Bash / Cloud Shell
RG=rg-solar-forecast
LOC=southeastasia                # Singapore — closest region to Thailand
ACR=acrsolar$RANDOM              # must be globally unique, lowercase letters/digits
ENV=cae-solar
API=solar-api
SWA=solar-web
GH_REPO=pcismyname/solar-forecast-app
```

## 2. Create resources

```bash
az login
az group create -n $RG -l $LOC
az acr create -g $RG -n $ACR --sku Basic
az containerapp env create -g $RG -n $ENV -l $LOC

# First deploy with a public placeholder image; CI replaces it with ours.
az containerapp create -g $RG -n $API --environment $ENV \
  --image mcr.microsoft.com/k8se/quickstart:latest \
  --ingress external --target-port 8000 \
  --min-replicas 0 --max-replicas 1 \
  --registry-server $ACR.azurecr.io --registry-identity system \
  --env-vars APP_ENV=production FORECAST_PROVIDER=demo ALLOWED_ORIGINS=https://<your-swa-host>

az staticwebapp create -g $RG -n $SWA -l eastasia --sku Free
```

> If `--registry-identity system` fails on first create, create without the registry flags, then run
> `az containerapp registry set -g $RG -n $API --server $ACR.azurecr.io --identity system`.

## 3. Let GitHub Actions log in with OIDC (no secrets stored)

```bash
SUB=$(az account show --query id -o tsv)
TENANT=$(az account show --query tenantId -o tsv)
APP_ID=$(az ad app create --display-name gh-solar-forecast-app --query appId -o tsv)
az ad sp create --id $APP_ID
az ad app federated-credential create --id $APP_ID --parameters '{
  "name": "gh-main",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:'$GH_REPO':environment:production",
  "audiences": ["api://AzureADTokenExchange"]
}'
az role assignment create --assignee $APP_ID --role Contributor --scope /subscriptions/$SUB/resourceGroups/$RG
az role assignment create --assignee $APP_ID --role AcrPush \
  --scope $(az acr show -n $ACR --query id -o tsv)
```

> Azure for Students accounts sometimes cannot create app registrations (directory policy). Fallback: create a
> service principal secret with `az ad sp create-for-rbac --sdk-auth`, store it as secret `AZURE_CREDENTIALS`
> and use `azure/login@v2` with `creds:` instead of OIDC.

## 4. GitHub repository settings

Create environment **production** (Settings → Environments). Then:

| Type | Name | Value |
|---|---|---|
| Variable | `DEPLOY_API` | `true` |
| Variable | `DEPLOY_WEB` | `true` |
| Variable | `AZURE_CLIENT_ID` | `$APP_ID` |
| Variable | `AZURE_TENANT_ID` | `$TENANT` |
| Variable | `AZURE_SUBSCRIPTION_ID` | `$SUB` |
| Variable | `AZURE_RESOURCE_GROUP` | `$RG` |
| Variable | `ACR_NAME` | `$ACR` |
| Variable | `CONTAINER_APP_NAME` | `$API` |
| Variable | `API_BASE_URL` | `https://$(az containerapp show -g $RG -n $API --query properties.configuration.ingress.fqdn -o tsv)` |
| Secret | `AZURE_STATIC_WEB_APPS_API_TOKEN` | `az staticwebapp secrets list -g $RG -n $SWA --query properties.apiKey -o tsv` |

```bash
gh variable set DEPLOY_API --body true -R $GH_REPO      # etc.
gh secret set AZURE_STATIC_WEB_APPS_API_TOKEN -R $GH_REPO
```

Then update the API's `ALLOWED_ORIGINS` to the Static Web App URL and push to `main` (or run the workflows manually).

## 5. Later: daily forecast job (from the ML repo)

```bash
# 04:00 UTC = 11:00 ICT, before the 12:00 D-1 deadline
az containerapp job create -g $RG -n solar-forecast-daily --environment $ENV \
  --trigger-type Schedule --cron-expression "0 4 * * *" \
  --image $ACR.azurecr.io/solar-ml:latest --registry-server $ACR.azurecr.io --registry-identity system \
  --cpu 1 --memory 2Gi --replica-timeout 1800
```

The job writes `forecasts/{plant_id}/{YYYY-MM-DD}.json` (schema in `apps/api/README.md`) to an Azure Files share
mounted into both the job and the API; set the API to `FORECAST_PROVIDER=file`.

## 6. Clean up

```bash
az group delete -n $RG --yes --no-wait
```
