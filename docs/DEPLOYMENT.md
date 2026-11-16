# Deployment

EquipTrack runs on three managed services, all on free tiers:

```
 Browser ──HTTPS──▶ Vercel (Next.js)          the UI + a small server-side proxy that holds the login cookie
                        │  server-to-server
                        ▼
                    Azure Container Apps      the FastAPI image, 0.5 vCPU / 1 GiB, scales to zero
                        │  TLS
                        ▼
                    Neon Postgres + pgvector  data, documents, embeddings
```

| Piece | Service | Why this one |
|---|---|---|
| API | Azure Container Apps (Consumption plan) | Runs the same Docker image as local dev. Memory is configurable (the local embedding model needs ~500 MiB, more than the 512 MB free tiers elsewhere). Scales to zero, and the monthly free grant (180k vCPU-seconds, 360k GiB-seconds, 2M requests) does not expire. |
| Image registry | GitHub Container Registry (public package) | Free. Azure Container Registry would cost ~$5/month. |
| Database | Neon | Free Postgres with pgvector that never expires (1 GB storage per project). Azure's free Postgres lasts only 12 months. Keeping the database off Azure also means the API can move host without moving data. |
| Frontend | Vercel (Hobby) | Built for Next.js. |
| Migrations + delivery | GitHub Actions (`.github/workflows/deploy.yml`) | After CI passes on `main`: build and push the image, run Liquibase against Neon, roll Azure onto the new image, smoke-test `/health`. |

## How a change reaches production

1. Push to `main` → **CI** runs lint, tests (≥95% coverage), the Docker end-to-end check and the frontend build.
2. Only if CI passes, **Deploy** starts. It checks out the exact commit CI tested.
3. `image`: builds once and pushes `ghcr.io/vedpawar1410/equiptrack:<commit-sha>` (and `:latest`).
4. `migrate`: `liquibase update` against Neon. This runs **before** the new code, and that is safe because every changeset is additive (expand/contract): the running version keeps working on the new schema.
5. `deploy`: `az containerapp update --image …:<commit-sha>`. Container Apps starts the new revision and switches traffic once it is up. Then the workflow polls `/health` until the API answers from the database.

Vercel deploys the frontend on its own from every push to `main`.

**Rollback:** re-point the app at an earlier commit's image (every image is kept in GHCR):

```bash
az containerapp update -n equiptrack-api -g equiptrack-rg --image ghcr.io/vedpawar1410/equiptrack:<older-sha>
```

Rolling back the code never needs a database rollback, because migrations only add.

## Cost guardrails

The free grant covers about 100 *awake* hours a month at 0.5 vCPU / 1 GiB. The app is awake only while it serves requests, plus a few minutes before scaling back to zero. A recruiter clicking through the demo uses a small fraction of that.

| Guardrail | Setting |
|---|---|
| Can never scale out | `--max-replicas 1` |
| Costs nothing when idle | `--min-replicas 0` |
| No log-ingestion charges | Container Apps environment created with `--logs-destination none` |
| No registry charges | Image pulled from public GHCR, not Azure Container Registry |
| No database charges | Neon free plan; writes fail at 1 GB, they are never billed |
| LLM quotas protected | 30 AI questions per user per hour (`AI_REQUESTS_PER_HOUR`) |
| Early warning | Azure budget with email alerts at $1 and $5 (an Azure budget alerts, it does **not** stop spending) |

Worst case, if something kept the replica awake 24/7 for a month, the bill would be roughly $30-35. You would see the budget alert first.

**Kill switch.** Turn off ingress. With no way in, nothing can wake the app, so it stays at zero replicas
and uses no compute (`--max-replicas` can't be set to 0; this is the off switch):

```bash
az containerapp ingress disable -n equiptrack-api -g equiptrack-rg
```

Turn it back on with `az containerapp ingress enable -n equiptrack-api -g equiptrack-rg --type external --target-port 8000`.

**Tear down everything on Azure:**

```bash
az group delete -n equiptrack-rg
```

**Moving off Azure** is one deploy step and one Vercel variable. The database is on Neon and the API is a standard Docker image, so the same image runs on Google Cloud Run, Render or any container host.

## First-time setup

You do this once. Every secret is typed by you into the provider's own dashboard or CLI, never committed. Use the same region family throughout so the three services sit close together (the examples use Singapore).

### 1. Neon (database)

1. Create a project at neon.tech. Postgres 16, region **AWS Asia Pacific (Singapore)**.
2. Open **Connect** and turn **Connection pooling off**. Use the *direct* connection string, because PgBouncer in transaction mode breaks asyncpg's prepared statements.
3. Keep two forms of it handy:
   - For the API (`DATABASE_URL`): the string exactly as Neon shows it, `postgresql://USER:PASSWORD@HOST/DB?sslmode=require&channel_binding=require`. The app converts it for asyncpg at startup.
   - For Liquibase: `jdbc:postgresql://HOST/DB?sslmode=require` (no user or password in it), plus the user and password separately.

### 2. Make the image public

Push to `main` once after this workflow is merged. The `image` job publishes `ghcr.io/vedpawar1410/equiptrack`, and the `migrate`/`deploy` jobs show as *skipped*, which is expected. Then on GitHub, open **your profile → Packages → equiptrack → Package settings → Change visibility → Public**. Azure can now pull it without credentials.

### 3. Azure resources

Install the Azure CLI (`brew install azure-cli`), then:

```bash
az login
az extension add --name containerapp --upgrade
az provider register --namespace Microsoft.App --wait
az group create --name equiptrack-rg --location southeastasia
az containerapp env create --name equiptrack-env --resource-group equiptrack-rg \
  --location southeastasia --logs-destination none
```

Read the secrets into your shell without echoing them or saving them in shell history:

```bash
read -s "DATABASE_URL?Neon URL: "; echo
read -s "GROQ_API_KEY?Groq key: "; echo
read -s "GEMINI_API_KEY?Gemini key: "; echo
JWT_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")
```

Create the app. Secrets are stored encrypted in Container Apps and referenced with `secretref:`:

```bash
az containerapp create --name equiptrack-api --resource-group equiptrack-rg \
  --environment equiptrack-env --image ghcr.io/vedpawar1410/equiptrack:latest \
  --ingress external --target-port 8000 \
  --cpu 0.5 --memory 1.0Gi --min-replicas 0 --max-replicas 1 \
  --secrets database-url="$DATABASE_URL" jwt-secret="$JWT_SECRET_KEY" \
            groq-key="$GROQ_API_KEY" gemini-key="$GEMINI_API_KEY" \
  --env-vars DATABASE_URL=secretref:database-url JWT_SECRET_KEY=secretref:jwt-secret \
             GROQ_API_KEY=secretref:groq-key GEMINI_API_KEY=secretref:gemini-key \
  --query properties.configuration.ingress.fqdn --output tsv
```

The last line prints the API's address (`equiptrack-api.<random>.southeastasia.azurecontainerapps.io`). Keep it for Vercel.

**Budget:** in the Azure portal, open **Cost Management → Budgets → Add**. Use a monthly budget of $5 with email alerts at 20% ($1) and 100% ($5).

### 4. Let GitHub deploy to Azure (OIDC, no stored password)

GitHub Actions gets a short-lived token, and Azure trusts it only for this repository's `production` environment. The deploy identity can manage only the `equiptrack-rg` resource group.

```bash
SUB=$(az account show --query id -o tsv)
TENANT=$(az account show --query tenantId -o tsv)
APP_ID=$(az ad app create --display-name equiptrack-github-deploy --query appId -o tsv)
az ad sp create --id "$APP_ID" --output none
az ad app federated-credential create --id "$APP_ID" --parameters '{
  "name": "github-production",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:VedPawar1410/EquipTrack:environment:production",
  "audiences": ["api://AzureADTokenExchange"]
}'
az role assignment create --assignee "$APP_ID" --role Contributor \
  --scope "/subscriptions/$SUB/resourceGroups/equiptrack-rg"
echo "AZURE_CLIENT_ID=$APP_ID  AZURE_TENANT_ID=$TENANT  AZURE_SUBSCRIPTION_ID=$SUB"
```

**The subject must match exactly what GitHub sends.** GitHub may use its newer format with the owner's
and repository's numeric IDs, e.g. `repo:VedPawar1410@178157570/EquipTrack@1306498421:environment:production`
(IDs, unlike names, can never be renamed or re-registered by someone else). If the first deploy fails
with `AADSTS700213: No matching federated identity record`, copy the `subject claim` that the
`azure/login` step printed and update the credential:

```bash
az ad app federated-credential update --id "$APP_ID" --federated-credential-id github-production \
  --parameters '{"name":"github-production","issuer":"https://token.actions.githubusercontent.com","subject":"<subject claim from the log>","audiences":["api://AzureADTokenExchange"]}'
```

These three IDs are identifiers, not secrets. They are useless without the trust set up above, but storing them as secrets keeps them out of logs.

### 5. GitHub settings

In the repo, open **Settings → Environments → New environment → `production`**, then add:

| Kind | Name | Value |
|---|---|---|
| Secret | `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` | from step 4 |
| Secret | `NEON_JDBC_URL` | `jdbc:postgresql://HOST/DB?sslmode=require` |
| Secret | `NEON_DB_USER`, `NEON_DB_PASSWORD` | from Neon |

Then open **Settings → Secrets and variables → Actions → Variables** and add the repository variables `AZURE_CONTAINERAPP_NAME` = `equiptrack-api` and `AZURE_RESOURCE_GROUP` = `equiptrack-rg`. Setting `AZURE_CONTAINERAPP_NAME` is what switches the `migrate` and `deploy` jobs on.

Run **Actions → Deploy → Run workflow**. It migrates Neon, rolls the app onto the commit's image and checks `/health`.

### 6. Load the demo data

Run the seed once from your machine against Neon, from the repo root, using the local docker compose image.
It contains the embedding model, so the manuals are embedded on your machine and stored in Neon.
(The GHCR image is built for amd64; on an Apple Silicon Mac the locally built image runs natively.)

```bash
read -s "DATABASE_URL?Neon URL: "; echo
read -s "DEMO_ADMIN_PASSWORD?Private admin password: "; echo
docker compose run --rm --no-deps \
  -e DATABASE_URL="$DATABASE_URL" -e DEMO_ADMIN_PASSWORD="$DEMO_ADMIN_PASSWORD" \
  app python -m app.seed_demo
```

`--no-deps` skips the local Postgres and Liquibase containers: the seed talks to Neon only.

With `DEMO_ADMIN_PASSWORD` set, the admin account (`priya`) gets your private password. The supervisor (`maria`) and technician (`ravi`, `jlee`) accounts keep the published demo passwords from `app/seed_demo.py`. The seed is idempotent, so re-running it restores any demo machine a visitor deleted.

### 7. Vercel (frontend)

1. Open **Add New → Project** and import the GitHub repo.
2. Set **Root Directory** to `frontend`. The framework (Next.js) is detected automatically.
3. Under **Environment Variables**, add `API_URL` = `https://<the fqdn from step 3>`, with no trailing slash.
4. Deploy. Then, in **Settings → Functions → Function Region**, choose **Singapore (sin1)**. Every API call goes browser → Vercel function → Azure, so keeping the function next to the API avoids an extra round trip across the world.

The browser only ever talks to Vercel. The API address and the login token stay server-side, so the API needs no CORS setup.

## Operating notes

- **Cold start:** after a few idle minutes the API scales to zero. The next request waits while Azure pulls the image (~1 GB) and starts it. Neon's compute also sleeps after 5 idle minutes and wakes in well under a second.
- **Logs:** with `--logs-destination none`, nothing is stored. To watch a live problem, stream the console with `az containerapp logs show -n equiptrack-api -g equiptrack-rg --follow`.
- **Rotating a secret:** `az containerapp secret set -n equiptrack-api -g equiptrack-rg --secrets groq-key=<new>`, then restart the revision. Rotating `jwt-secret` signs everyone out.
- **The rate limit is per process.** That is correct here because there is at most one replica. With several replicas the counter would have to move to Redis or an API gateway.
