# GraphRAG Platform — React + FastAPI + LangGraph + Neo4j + Vertex AI (GCP)

A production-oriented scaffold for an agentic GraphRAG application: a Planner agent
routes each question to a RAG agent (BigQuery vector search), a Graph agent (Neo4j
Cypher), and/or a SQL agent (Cloud SQL/Postgres), then a Report agent synthesizes the
final answer. Orchestration is implemented with LangGraph; the LLM is Gemini via
Vertex AI.

## Architecture

```
React (Vite+TS) → Cloud Run (FastAPI) → LangGraph orchestrator
                                             ├── Planner Agent (Gemini)
                                             ├── RAG Agent → BigQuery vector search
                                             ├── Graph Agent → Neo4j (Cypher)
                                             ├── SQL Agent → Cloud SQL (Postgres)
                                             └── Report Agent (Gemini) → final answer
```

Ingestion pipeline (PDF upload): text extraction → semantic chunking →
embeddings → BigQuery, in parallel with entity/relationship extraction → Neo4j.

## Repository layout

```
backend/           FastAPI app, LangGraph orchestrator, agents, tools
frontend/          React + Vite + TypeScript SPA (Firebase Auth, chat + upload UI)
terraform/         All GCP infrastructure as code
.github/workflows/ CI/CD pipeline (GitHub Actions, Workload Identity Federation)
scripts/           deploy.sh / deploy.ps1 — manual deploy for either shell
docker-compose.yml Local dev stack (backend, frontend, Postgres, Neo4j)
```

## Prerequisites

- GCP project with billing enabled
- `gcloud`, `terraform` (>=1.7), `docker`, `node` (20+), `python` (3.11+)
- A Neo4j instance — [AuraDB](https://neo4j.com/cloud/aura/) free tier works, or self-host
- Firebase project (for auth) linked to the same GCP project

### Creating a GCP Project with `gcloud`

If you don't already have a GCP project, you can create one using the Google Cloud CLI (`gcloud`):

1. **Authenticate with Google Cloud:**
   ```bash
   gcloud auth login
   ```

2. **Create a new project:**
   Replace `my-graphrag-project` with your desired project ID (must be globally unique, 6-30 lowercase letters, digits, or hyphens).
   ```bash
   gcloud projects create my-graphrag-project --name="GraphRAG Platform"
   ```

3. **Get the Project ID:**
   To list your projects and find your Project ID:
   ```bash
   gcloud projects list
   ```
   *Note the `PROJECT_ID` column for your newly created project.*

4. **Set the active project:**
   ```bash
   gcloud config set project <PROJECT_ID>
   ```

5. **Link a Billing Account:**
   GCP requires an active billing account to provision resources. List your billing accounts to get the `ACCOUNT_ID`:
   ```bash
   gcloud beta billing accounts list
   ```
   Link it to your project:
   ```bash
   gcloud beta billing projects link <PROJECT_ID> --billing-account=<ACCOUNT_ID>
   ```

### Firebase Auth (frontend sign-in)

The frontend bakes Firebase config into the Docker image at **build time** (`VITE_*` vars).

1. Open [Firebase Console](https://console.firebase.google.com/) → select project **`my-graphrag-project`** (same GCP project).
2. **Build → Authentication → Sign-in method** → enable **Google**.
3. **Project settings** (gear icon) → **General** → **Your apps** → add a **Web app** if you don't have one.
4. Copy the **Web API Key** from the Firebase config snippet.

**Local dev** — create `frontend/.env`:

```bash
VITE_API_URL=http://localhost:8080
VITE_FIREBASE_API_KEY=AIza...
VITE_FIREBASE_AUTH_DOMAIN=my-graphrag-project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=my-graphrag-project
```

**CI/CD** — add GitHub secrets (values from the Firebase config snippet):

| Secret | Example value |
|--------|----------------|
| `FIREBASE_API_KEY` | `AIzaSy...` |
| `FIREBASE_AUTH_DOMAIN` | `my-graphrag-project-d3260.firebaseapp.com` |
| `FIREBASE_PROJECT_ID` | `my-graphrag-project-d3260` |

Do **not** paste the Firebase snippet into `firebase.ts` — the app reads these via `VITE_*` build args. Also set `firebase_project_id` in `terraform.tfvars` so the backend verifies tokens against the same Firebase project.

6. **Enable Required APIs:**
   Although Terraform can enable some, it's a good idea to enable the core APIs required for setup:
   ```bash
   gcloud services enable \
     compute.googleapis.com \
     run.googleapis.com \
     sqladmin.googleapis.com \
     aiplatform.googleapis.com \
     cloudresourcemanager.googleapis.com \
     iam.googleapis.com \
     secretmanager.googleapis.com \
     artifactregistry.googleapis.com
   ```

### Database Hosting Strategy (Free Tiers)

To deploy this project completely for free (or close to it), you should combine two different Free Tiers:

1. **GCP Free Tier (For Compute & Architecture):** We use Google Cloud for our primary infrastructure. Services like Cloud Run scale down to zero when not in active use, meaning for personal projects, it typically remains within the GCP free quota boundaries.
2. **Neo4j AuraDB Free Tier (For the Database):** Instead of self-hosting the Neo4j graph database on GCP, we highly recommend signing up for a free AuraDB instance directly at [neo4j.com](https://neo4j.com/cloud/aura/).

**Why not just host Neo4j on the GCP Free Tier VM?**
The free Google Compute Engine (GCE) tier only provides an `e2-micro` virtual machine equipped with **1GB of RAM**. Neo4j is a heavy, Java-based database that requires an absolute minimum of 2GB (ideally 4GB+) of memory to start up comfortably. Attempting to self-host it on the free GCP machine will almost certainly result in Out-Of-Memory (OOM) crashes before the system even boots. 

By using the Neo4j AuraDB Free Tier specifically for your database, you get a properly sized machine for free that connects remotely to your extremely cost-efficient GCP architecture!

### Setting up Neo4j AuraDB

1. **Sign Up:** Go to [Neo4j Aura](https://neo4j.com/cloud/aura/) and create a free account.
2. **Create Instance:** Once in the console, create a new "AuraDB Free" instance.
3. **Save Credentials:** Upon creation, it will provide your Connection URI (`neo4j+s://[YOUR-ID].databases.neo4j.io`) and generate a password (often downloaded automatically as a `.txt` file). **Save this password securely.**
4. **Update Terraform Configuration:** Open your `terraform/terraform.tfvars` file and inject these credentials so Terraform can securely push them into Google Secret Manager during deployment:
   ```hcl
   neo4j_uri      = "neo4j+s://[YOUR-ID].databases.neo4j.io"
   neo4j_user     = "neo4j"
   neo4j_password = "[YOUR-GENERATED-PASSWORD]"
   ```
5. *(Optional)* **Update Local Development:** By default, local `docker compose up` spins up an ephemeral local Neo4j container. If you prefer to test your local frontend/backend against your live AuraDB instance, update the `NEO4J_*` variables inside `backend/.env` with these same credentials.

## Access model: users vs. admin

Both UIs share the same React app and the same Google sign-in (Firebase Auth) —
the app just renders differently depending on role:

- **Regular users**: chat only. They can ask questions; the orchestrator
  answers using whatever's already been ingested. They cannot see or manage files.
- **Admins**: get a "Chat / Admin" toggle in the header. The Admin tab lists
  every uploaded document (status, chunk/entity/relationship counts, upload
  date) and lets them upload new PDFs or delete existing ones (which cleans up
  the file in GCS, its embeddings in BigQuery, and its facts in Neo4j).

Role is decided **server-side**, not just hidden in the UI: every
`/api/v1/admin/*` route requires the `admin` custom claim on the caller's
Firebase ID token (checked in `app/core/auth.py::get_current_admin`). The
frontend calls `GET /api/v1/me` after sign-in to find out which view to show,
but a non-admin calling the admin endpoints directly still gets a 403.

**Granting admin access** — a user must sign in once first (so Firebase knows
about them), then:

```bash
python backend/scripts/set_admin_claim.py alice@example.com --grant
python backend/scripts/set_admin_claim.py alice@example.com --revoke
```

This requires Application Default Credentials with rights to manage the
Firebase project (`gcloud auth application-default login` as an Owner/Firebase
Admin, or a service account key with the "Firebase Authentication Admin" role).
The user needs to sign out/in (or the app force-refreshes their token on next
load) for the new claim to take effect.

For initial bootstrapping before you've set any custom claims, you can also
set `ADMIN_EMAILS=you@example.com` (comma-separated) as a fallback allowlist —
see `backend/.env.example` / `terraform/variables.tf` (`admin_emails`). Custom
claims should be the long-term source of truth; the email allowlist is just to
get your first admin in the door.

## What Data Should I Test With?

Because this platform features an automated ingestion pipeline, you **do not need** to manually load a pre-existing dataset into Neo4j or Postgres. 

When you log in with an Admin account and upload a PDF via the UI, the application automatically:
1. Chunks the text and stores vectors in **BigQuery** (for the RAG Agent).
2. Extracts `(:Entity)-[:RELATES]->(:Entity)` facts using Vertex AI and pushes them directly into **Neo4j** (for the Graph Agent).

**Suggested Documents to Upload:**
To really see the multi-agent orchestration shine, try uploading highly relational PDFs such as:
- **Legal Contracts:** (e.g., "Company A agrees to pay Company B") — This tests the Graph Agent's ability to map corporate entity networks. 
  *Where to find:* [SEC EDGAR Contract Search](https://www.sec.gov/edgar/search/) or public legal corpuses.
- **Medical or Scientific Papers:** (e.g., "Drug X inhibits Protein Y") — The Graph Agent will excel at tracing biological or chemical dependencies. 
  *Where to find:* Open-access PDF papers on [PubMed Central (PMC)](https://www.ncbi.nlm.nih.gov/pmc/) or [arXiv (q-bio)](https://arxiv.org/archive/q-bio).
- **Financial Earnings Call Transcripts:** Great for testing the orchestrator's ability to hit both the BigQuery RAG agent (for general sentiment/text questions) and the Neo4j Graph agent (for Executive/Company relationships) for the same user query. 
  *Where to find:* Export as PDFs from [The Motley Fool Earnings Transcripts](https://www.fool.com/earnings/call-transcripts/) or similar financial aggregator sites.

### ⚡ Bonus: Loading Pre-made Graph Data Directly
If you want to skip the PDF ingestion phase and immediately populate your Neo4j database with rich data to test the platform's Cypher-generating capabilities, you can use Neo4j's built-in sample datasets!

1. Open your Neo4j Aura Console and launch the **Workspace / Browser**.
2. In the query prompt at the top, run the command `:play movies`
3. Click to the second slide of the tutorial that pops up, and click the giant block of Cypher code. This will copy it to your editor.
4. Hit **Run** (the play button). 
5. This will instantly populate your database with roughly 170 nodes (Actors and Movies) and 250 relationships! 

You can now go to this project's chat interface and ask questions like *"Who acted in The Matrix?"* or *"Find movies directed by Christopher Nolan"*, and the LangGraph Graph Agent will dynamically write and execute Cypher queries against this dataset to answer you!

## Local development

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend: http://localhost:8080/api/v1/health
- Neo4j browser: http://localhost:7474

Google Cloud calls (Vertex AI, BigQuery, GCS) require Application Default
Credentials even locally:

```bash
gcloud auth application-default login
```

## Provisioning GCP infrastructure

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars   # fill in real values
terraform init -backend-config="bucket=<PROJECT_ID>-graphrag-platform-tfstate"
terraform plan
terraform apply
```

This creates: Cloud Run services (backend + frontend), Cloud SQL (Postgres),
BigQuery dataset/table for embeddings, GCS bucket for uploaded documents,
Artifact Registry repo, service accounts + IAM bindings, Secret Manager entries
for Neo4j/SQL credentials, and a Workload Identity Federation pool for GitHub
Actions (no long-lived JSON key needed in CI).

> The Terraform state bucket must exist **before** the first `terraform init`.
> Create it once, then grant your deployer SA access until Terraform manages it:
>
> ```bash
> ./scripts/bootstrap-tf-state.sh your-gcp-project
> # or on Windows: .\scripts\bootstrap-tf-state.ps1 -ProjectId your-gcp-project
> ```

## Manual deploy (build + push + apply in one step)

```bash
./scripts/deploy.sh <project_id> <region> <environment>      # bash/macOS/Linux
.\scripts\deploy.ps1 -ProjectId <project_id> -Region <region> -Environment <environment>  # Windows
```

## CI/CD

`.github/workflows/deploy.yml` runs on every push to `main`:
lint/compile check → frontend build → Docker build & push (backend + frontend)
→ `terraform plan`/`apply` → smoke test against `/api/v1/health`.

Required GitHub repo secrets: `GCP_PROJECT_ID`, `WIF_PROVIDER`, `DEPLOYER_SA_EMAIL`,
`TF_STATE_BUCKET`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `BACKEND_URL`,
`FIREBASE_API_KEY`, `ADMIN_EMAILS`.

| Secret | Source |
|--------|--------|
| `WIF_PROVIDER` | `terraform output workload_identity_provider` |
| `DEPLOYER_SA_EMAIL` | `terraform output deployer_service_account` |
| `TF_STATE_BUCKET` | `terraform output tf_state_bucket` — must be `…-tfstate`, **not** `…-documents-dev` |
| `BACKEND_URL` | `terraform output -raw backend_url` |
| `FIREBASE_API_KEY` | Firebase config → `apiKey` |
| `FIREBASE_AUTH_DOMAIN` | Firebase config → `authDomain` |
| `FIREBASE_PROJECT_ID` | Firebase config → `projectId` |

## Notes on production hardening

- Cloud SQL currently uses a public IP for simplicity — switch to private IP +
  VPC peering for production (`sql.tf`).
- The SQL Agent only ever executes single `SELECT` statements and rejects any
  DDL/DML keywords as a defense-in-depth measure, but a dedicated read-only
  Postgres role is recommended as well.
- The Graph Agent's LLM-generated Cypher fallback is restricted to read-only
  queries by keyword-blocklist; treat this as a first layer of defense, not a
  substitute for a properly scoped Neo4j role.
