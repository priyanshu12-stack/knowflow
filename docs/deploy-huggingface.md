# Deploying KnowFlow to a free Hugging Face Space

This puts KnowFlow online for free, with **no credit card**, on a Hugging Face Docker Space
("CPU basic": 2 vCPU, 16 GB RAM at the time of writing; check huggingface.co/pricing).

Everything runs in one container: PostgreSQL 16 + pgvector, Ollama with both models, the API, the
ingestion worker, the Next.js web app and Caddy (the public port and an optional password). The
models still run locally inside the container, so ADR-007 (no paid inference) holds.

Files: [`deploy/huggingface/`](../deploy/huggingface/)

| File | Goes where | What it does |
|---|---|---|
| `Dockerfile` | **uploaded to the Space** | Builds the image and clones this GitHub repo into it |
| `README.md` | **uploaded to the Space** | Space settings (`sdk: docker`, `app_port: 7860`) and the Space's front page |
| `start.sh` | stays in GitHub (cloned during the build) | Starts all services at boot and reloads the demo data |

The Space only holds those two files. The code is cloned from GitHub during the build because the
Hugging Face git server rejects plain binary files (the screenshots and `.docx` specs).

## Limitations

- **Temporary data.** The free disk is wiped on every restart. At boot the start script recreates the
  database and reloads the sample documents, the gold set and the SQL demo. Anything uploaded is lost
  on restart.
- **Sleeps after ~48 h without visitors.** The next visit wakes it (a few minutes).
- **Slow.** 2 shared CPU cores: about 1–3 minutes per answer.
- **No user accounts.** KnowFlow has no login. Set `APP_PASSWORD` (step 3) or make the Space private.

## Step by step

### 1. Push your latest code to GitHub

The build clones `main` from `https://github.com/priyanshu12-stack/knowflow`, which must be
**public**. Only committed and pushed changes reach the Space.

```powershell
git push origin main
```

### 2. Create the Space

1. Sign up at https://huggingface.co (email only).
2. Click **New → Space**.
3. Name: `knowflow` · License: your choice · **SDK: Docker → Blank** · Hardware: **CPU basic (Free)**.
4. Visibility: **Public** (anyone can open it; protect it with step 3) or **Private** (only your
   Hugging Face account can open it).
5. Click **Create Space**.

### 3. Add a password (recommended for a public Space)

In the Space: **Settings → Variables and secrets → New secret**

| Name | Value |
|---|---|
| `APP_PASSWORD` | a password visitors must enter (username is `admin`) |
| `APP_USERNAME` | *(optional)* a different username |

Don't add database passwords or `SECRET_KEY`. They're generated fresh at every boot because the data
is temporary anyway.

### 4. Upload the two files

In the Space: **Files → Add file → Upload files**. Upload **`deploy/huggingface/Dockerfile`** and
**`deploy/huggingface/README.md`** from this repo, replacing the Space's own `README.md`, and commit.

Or use git (sign in with a Hugging Face **write** access token as the password):

```powershell
git clone https://huggingface.co/spaces/<your-hf-username>/knowflow hf-space
Copy-Item deploy\huggingface\Dockerfile, deploy\huggingface\README.md hf-space\
cd hf-space; git add .; git commit -m "Deploy KnowFlow"; git push
```

### 5. Wait for the build

The Space starts building on its own. Follow it in the **Logs** tab. The first build takes
**about 15–25 minutes**: it downloads ~3.5 GB of model weights and builds the Next.js app.
After the build, the startup log ends with:

```
[knowflow] PostgreSQL is up
[knowflow] Ollama is up
[knowflow] API is up
[knowflow] web is up
[knowflow] sample documents queued for indexing
[knowflow] password gate ON (user: admin)
[knowflow] KnowFlow is ready on port 7860
```

### 6. Open it

`https://<your-hf-username>-knowflow.hf.space`. Use this direct link rather than the Space page
on huggingface.co: the Space page shows the app inside an embedded frame, and browsers may not
show the password prompt there. Open **Overview**: every
readiness check should be green. The sample documents take a few minutes to index. Watch them
in **Knowledge Library**.

## Updating the live app

1. Push to `main` on GitHub.
2. In the Space: **Settings → Factory rebuild**. The build notices the new commit and re-clones the
   code. The model-weights layer is reused, so rebuilds are much faster.

To deploy a different branch or fork, change `KNOWFLOW_REF` / `KNOWFLOW_GITHUB` at the top of the
Space's `Dockerfile`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Build fails at `git clone` | The GitHub repo is private, or `KNOWFLOW_REF` names a branch that doesn't exist. |
| Build fails at `ADD https://api.github.com/...` | GitHub API rate limit (60 requests/hour per IP). Retry the build later. |
| Space shows "Runtime error" | Open **Logs**. The script prints the last 40 lines of the service that stopped. |
| Answers time out | The first answer after a wake-up also loads the model. Ask again. |
| Overview shows a model as missing | The model pull failed during the build. Run **Factory rebuild**. |
| Browser keeps asking for the password | Use the `APP_USERNAME` (default `admin`) and `APP_PASSWORD` you set in step 3. |
