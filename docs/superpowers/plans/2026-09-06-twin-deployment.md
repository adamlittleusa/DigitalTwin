# Twin Deployment Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the twin API at `https://api.adambuilds.ai` on one always-on Fly.io machine, with secrets in Fly, a Fly-managed certificate, tests on every pull request, and a deploy on every merge to `main`.

**Architecture:** A hand-written `fly.toml` at the repo root builds the existing `apps/twin/Dockerfile` on Fly's remote builder. One GitHub Actions workflow runs ruff and the unit tests on pull requests and, on `main`, deploys with a deploy-scoped token and smokes the public health route. A small code change lets the client key prefer a proxy-set header. Two inherited safeguards land as a CI test and a one-off history scan.

**Tech Stack:** Fly.io (Machines, `flyctl`), GitHub Actions, GoDaddy DNS, the existing Python 3.13 package (uv, ruff, pytest).

**Spec:** `docs/superpowers/specs/2026-09-06-twin-deployment-design.md`.

**Skills to apply:** @superpowers:test-driven-development for the code tasks.

## Review-driven deviations, recorded during execution

- **Task 3.** `fly config validate` needs a login, so it ran at the start of Task 6 (valid). The `fly` alias was not created (admin symlink); commands use `%USERPROFILE%\.fly\bin\flyctl.exe`.
- **Task 5.** Scan found Deloitte, T-Mobile, and Becton Dickinson in two early revisions of `evals/twin_qa.yaml` (an eval must-not-say list later replaced by decoys); nothing else. Reported to Adam.
- **Task 6.** Region `bos` is deprecated on Fly; the app runs in `ewr`. Fly required the CNAME to point at the app-specific name `6kz5qlj.adambuilds-twin.fly.dev` before it would issue the certificate; Adam updated the GoDaddy record. Machine `8d2d30beee5778`, image 76 MB compressed.

---

## Conventions

- `uv`, `pytest`, `ruff` run from `apps/twin/`; `fly`, `git`, and `gh` from the repo root. Branch `feat/twin-deploy`.
- Commit messages: conventional-commit prefix; trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Never open, print, or copy `.env`. Task 6 pipes selected lines of it into `fly secrets import`; that is the only allowed use. Never paste a token, key, or salt into a report, a commit, or a log.
- Steps marked **Adam** need him at the keyboard (browser login, account settings, the deploy token). Stop and report at those steps.
- A bare `uv run pytest` never calls the model. Task 6's acceptance is the only paid model use.

## File structure

| Path | Responsibility |
|---|---|
| `apps/twin/twin/config.py` | `Settings.client_ip_header` from `TWIN_CLIENT_IP_HEADER`. |
| `apps/twin/twin/api/security.py` | `client_key` prefers the configured header when the proxy is trusted. |
| `apps/twin/tests/test_knowledge_reviewed.py` | Every committed knowledge file has a `reviewed` date. |
| `fly.toml` (repo root) | The Fly app: build, env, service, health check, machine size. |
| `.github/workflows/twin.yml` | Tests on PRs; deploy and smoke on `main`. |
| `.env.example`, `README.md` | Document the new setting and the deploy path. |

---

### Task 1: Client key from a proxy-set header

**Files:**
- Modify: `apps/twin/twin/config.py`, `apps/twin/twin/api/security.py`, `.env.example`
- Test: `apps/twin/tests/test_config.py`, `apps/twin/tests/test_api_routes.py`

- [ ] **Step 1: Failing tests**

Append to `apps/twin/tests/test_config.py`:

```python
def test_client_ip_header_defaults_blank_and_is_stripped() -> None:
    assert Settings.from_env({"OPENAI_API_KEY": "sk-test"}).client_ip_header == ""
    settings = Settings.from_env({"OPENAI_API_KEY": "sk-test", "TWIN_CLIENT_IP_HEADER": " Fly-Client-IP "})
    assert settings.client_ip_header == "Fly-Client-IP"
```

Append to `apps/twin/tests/test_api_routes.py` (it already has `req(...)`, `FakeRequest`, `client_key`, and the `make_runtime` fixture; `req` builds headers from a dict, so extend it or build a `FakeRequest` directly as shown):

```python
def test_client_key_prefers_the_configured_header_behind_a_trusted_proxy(
    make_runtime: Callable[..., Runtime],
) -> None:
    trusted = make_runtime(TWIN_TRUST_PROXY="true", TWIN_LOG_SALT="s", TWIN_CLIENT_IP_HEADER="Fly-Client-IP").settings
    with_header = FakeRequest({"fly-client-ip": "198.51.100.7", "x-forwarded-for": "1.2.3.4"}, Address("10.0.0.1", 1))
    assert client_key(with_header, trusted) == "198.51.100.7"
    without_header = FakeRequest({"x-forwarded-for": "1.2.3.4, 203.0.113.9"}, Address("10.0.0.1", 1))
    assert client_key(without_header, trusted) == "203.0.113.9"
    blank_header = FakeRequest({"fly-client-ip": "  "}, Address("10.0.0.1", 1))
    assert client_key(blank_header, trusted) == "10.0.0.1"


def test_client_ip_header_is_ignored_when_not_configured(make_runtime: Callable[..., Runtime]) -> None:
    trusted = make_runtime(TWIN_TRUST_PROXY="true", TWIN_LOG_SALT="s").settings
    request = FakeRequest({"fly-client-ip": "198.51.100.7"}, Address("10.0.0.1", 1))
    assert client_key(request, trusted) == "10.0.0.1"
    untrusted = make_runtime(TWIN_CLIENT_IP_HEADER="Fly-Client-IP").settings
    assert client_key(request, untrusted) == "10.0.0.1"
```

Check how `FakeRequest` is declared (a frozen dataclass with `headers` and `client`); if its `headers` is a `Mapping[str, str]`, the dict works as is. Header lookups are case-insensitive in Starlette; the fake is a plain dict, so keys are lower-case in the tests and the code lower-cases the configured name.

Run: `uv run pytest tests/test_config.py tests/test_api_routes.py -q`. Expected: the three new tests fail (`AttributeError: client_ip_header`, then wrong keys).

- [ ] **Step 2: Code**

In `apps/twin/twin/config.py`, add the field after `host`:

```python
    client_ip_header: str = ""
```

and in `from_env`, after `host=...`:

```python
            client_ip_header=_read(source, "TWIN_CLIENT_IP_HEADER"),
```

In `apps/twin/twin/api/security.py`, replace `client_key` with:

```python
def client_key(request: RequestLike, settings: Settings) -> str:
    """The visitor's address behind a trusted proxy, else the peer.

    Behind a trusted proxy the configured client-IP header (Fly sets Fly-Client-IP) wins when present.
    Otherwise the last non-empty X-Forwarded-For hop is used: a proxy appends the address it saw to the
    end, so anything earlier came from the client and can say whatever it likes. Without either, the
    peer address is used.
    """
    if settings.trust_proxy:
        header = settings.client_ip_header.lower()
        named = request.headers.get(header, "").strip() if header else ""
        if named:
            return named
        hops = [hop.strip() for hop in request.headers.get("x-forwarded-for", "").split(",")]
        appended = next((hop for hop in reversed(hops) if hop), None)
        if appended:
            return appended
    host = getattr(request.client, "host", None)
    if not host:
        log.warning("No client address on the request; such visitors share one rate-limit bucket.")
        return "unknown"
    return host
```

In `.env.example`, after the `TWIN_LOG_SALT=` line:

```
# Header a trusted proxy sets with the real client address; Fly sets Fly-Client-IP. Blank means use X-Forwarded-For.
TWIN_CLIENT_IP_HEADER=
```

- [ ] **Step 3: Verify and commit**

Run: `uv run pytest -q` (all pass) and `uv run ruff check .` (clean). From the repo root:

```bash
git add apps/twin/twin/config.py apps/twin/twin/api/security.py apps/twin/tests/test_config.py apps/twin/tests/test_api_routes.py .env.example
git commit -m "feat(api): client key prefers a proxy-set header such as Fly-Client-IP

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Every committed knowledge file has a reviewed date

**Files:**
- Create: `apps/twin/tests/test_knowledge_reviewed.py`

- [ ] **Step 1: The test**

```python
"""Every knowledge file that ships must carry a reviewed date; this gate runs in CI."""

from twin.config import DEFAULT_KNOWLEDGE_DIR
from twin.knowledge import load_knowledge


def test_every_committed_knowledge_file_is_reviewed() -> None:
    knowledge = load_knowledge(DEFAULT_KNOWLEDGE_DIR)
    unreviewed = sorted(str(file.path) for file in knowledge.files if not file.reviewed)
    assert not unreviewed, f"Set a reviewed date on: {unreviewed}"
```

Run: `uv run pytest tests/test_knowledge_reviewed.py -q`. Expected: it passes; `projects/digital-twin.md` already carries a reviewed date (Adam set `06-09-2026`). Normalise that value to the ISO form the other files use, `reviewed: 2026-09-06`, and confirm the test still passes. (If any file were unreviewed, the test would name it and **Adam** would set the date.)

- [ ] **Step 2: Commit**

```bash
git add apps/twin/tests/test_knowledge_reviewed.py knowledge/projects/digital-twin.md
git commit -m "test(knowledge): every committed knowledge file carries a reviewed date

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: `fly.toml` and `flyctl`

**Files:**
- Create: `fly.toml` (repo root)

- [ ] **Step 1: Install flyctl**

In PowerShell: `pwsh -Command "iwr https://fly.io/install.ps1 -useb | iex"` (or `powershell` if `pwsh` is absent). Open a new shell so `fly` is on the path; `fly version` prints a version. No login is needed for this task.

- [ ] **Step 2: Write `fly.toml`**

```toml
# Fly.io configuration for the twin API. The build context is this directory, the repo root.
app = "adambuilds-twin"
primary_region = "bos"

[build]
  dockerfile = "apps/twin/Dockerfile"

[env]
  TWIN_TRUST_PROXY = "true"
  TWIN_CLIENT_IP_HEADER = "Fly-Client-IP"
  TWIN_ALLOWED_ORIGINS = "https://adambuilds.ai,https://www.adambuilds.ai"
  TWIN_SITE_URL = "https://adambuilds.ai"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = "off"
  auto_start_machines = true
  min_machines_running = 1

  [http_service.concurrency]
    type = "requests"
    soft_limit = 25
    hard_limit = 50

  [[http_service.checks]]
    grace_period = "15s"
    interval = "15s"
    timeout = "5s"
    method = "GET"
    path = "/v1/health"

[[vm]]
  size = "shared-cpu-1x"
  memory = "512mb"
```

- [ ] **Step 3: Validate and commit**

Run from the repo root: `fly config validate`. Expected: the config is valid. If it rejects a key, fix the key to what the installed `flyctl` accepts and record the change in the plan's deviations section.

```bash
git add fly.toml
git commit -m "chore(deploy): Fly.io app configuration for the twin API

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: The GitHub Actions workflow

**Files:**
- Create: `.github/workflows/twin.yml`
- Modify: `README.md`

- [ ] **Step 1: Write the workflow**

Check the current major of `astral-sh/setup-uv` on GitHub and pin it (the spec assumed v10).

```yaml
name: twin

on:
  pull_request:
  push:
    branches: [main]
    paths:
      - "apps/twin/**"
      - "knowledge/**"
      - "evals/**"
      - "fly.toml"
      - ".dockerignore"
      - ".github/workflows/twin.yml"
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: apps/twin
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v10.0.1
        with:
          python-version: "3.13"
      - run: uv sync --frozen
      - run: uv run ruff check .
      - run: uv run pytest --cov=twin

  deploy:
    needs: test
    if: github.event_name != 'pull_request'
    runs-on: ubuntu-latest
    concurrency:
      group: twin-deploy
      cancel-in-progress: false
    steps:
      - uses: actions/checkout@v4
      - uses: superfly/flyctl-actions/setup-flyctl@master
      - run: flyctl deploy --remote-only --ha=false
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
      - name: Smoke the public URL
        run: |
          # The same four locations the Dockerfile copies; a new top-level knowledge directory must be added to both.
          expected=$(ls knowledge/*.md knowledge/roles/*.md knowledge/topics/*.md knowledge/projects/*.md | grep -v -i readme | wc -l)
          body=$(curl -fsS --retry 6 --retry-delay 10 --retry-all-errors https://api.adambuilds.ai/v1/health)
          echo "$body"
          echo "$body" | grep -q '"status":"ok"'
          echo "$body" | grep -q "\"knowledge_files\":$expected"
```

- [ ] **Step 2: Check it parses and the count matches**

From the repo root: `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/twin.yml'))"` (use `uv run --directory apps/twin python ...` if `python` lacks PyYAML). Then run the `expected=` line in Git Bash and confirm it prints the same number `/v1/health` reports locally (17 today). If `actionlint` is installed, run it too.

- [ ] **Step 3: README**

In `README.md`, add after "The API" (before "Test"):

```markdown
## Deploy

The API runs on Fly.io as `adambuilds-twin` at `https://api.adambuilds.ai`,
one always-on machine. `.github/workflows/twin.yml` runs ruff and the unit
tests on every pull request; a merge to `main` that touches the app, the
knowledge, or the deploy files deploys with `fly deploy --remote-only --ha=false`
and checks the public health route. Secrets live in Fly (`fly secrets`); the
deploy token lives in the repository secret `FLY_API_TOKEN`. Never run
`fly scale count` above 1: the rate limits live in process memory. See
`docs/superpowers/specs/2026-09-06-twin-deployment-design.md`.
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/twin.yml README.md
git commit -m "ci: tests on pull requests, Fly deploy and health smoke on main

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

The `test` job will run on the pull request for this branch once pushed; the `deploy` job only runs on `main`.

---

### Task 5: History scan (read-only)

- [ ] **Step 1: Build the term list locally**

Read `private/review-notes-2026-09-04.md` and `private/review-notes-2026-09-05.md` (local, gitignored) and list the names and details Adam struck or held back (client names other than Verizon, the family detail, the wording he softened). Keep the list in the scratchpad only.

- [ ] **Step 2: Scan**

From the repo root, for each term: `git log -p --all -i -S"<term>" -- knowledge evals | grep -i -c "<term>"` (or `git grep -i "<term>" $(git rev-list --all) -- knowledge evals`). A term that appears only in the current tree, where Adam allowed it, is not a finding; a term that appears in an old revision and not in the current tree is.

- [ ] **Step 3: Report**

Report to Adam: "found nothing" or the list of terms and the commits they appear in, without repeating the content in the plan or the repo. Rewriting history, if he wants it, is a separate decision and not part of this plan.

---

### Task 6: First deploy

Run with Adam present. Git Bash from the repo root unless stated. Already done by Adam on 2026-09-06: payment method on the Fly account, the GoDaddy CNAME, and the OpenAI monthly usage limit.

- [ ] **Step 1: Login** — **Adam**: `fly auth login` (browser). Then `fly auth whoami` shows his email.
- [ ] **Step 2: Create the app** — `fly apps create adambuilds-twin --org personal`. If the name is taken, use `adambuilds-twin-api`, change `app` in `fly.toml`, commit, and tell Adam the CNAME value changes to `adambuilds-twin-api.fly.dev`.
- [ ] **Step 3: Secrets, without printing** —

```bash
grep -E '^(OPENAI_API_KEY|PUSHOVER_USER|PUSHOVER_TOKEN)=' .env | fly secrets import --stage -a adambuilds-twin
fly secrets set --stage -a adambuilds-twin TWIN_LOG_SALT="$(uv run --directory apps/twin python -c 'import secrets; print(secrets.token_hex(32))')"
fly secrets list -a adambuilds-twin
```

Expected: four names listed with digests, no values.

- [ ] **Step 4: Deploy** — `fly deploy --remote-only --ha=false`. Expected: the remote build succeeds and one machine starts in `bos`. Then `fly scale show -a adambuilds-twin` reports 1 machine, `fly status` shows it healthy, and `curl -s https://adambuilds-twin.fly.dev/v1/health` returns `"status":"ok"` with `"knowledge_files":17`.
- [ ] **Step 5: Certificate** — Adam added the CNAME `api` → `adambuilds-twin.fly.dev` at GoDaddy on 2026-09-06; confirm it resolves first with `nslookup api.adambuilds.ai` (expect the `fly.dev` name in the answer; if not, wait for propagation before continuing). Then `fly certs add api.adambuilds.ai -a adambuilds-twin`, then `fly certs check api.adambuilds.ai -a adambuilds-twin` until it reports the certificate is issued (DNS propagation plus issuance, usually minutes).
- [ ] **Step 6: Acceptance from the public URL** —

```bash
curl -s https://api.adambuilds.ai/v1/health
curl -s -N -H "Content-Type: application/json" -d '{"messages":[{"role":"user","content":"Where are you based?"}]}' https://api.adambuilds.ai/v1/chat
curl -s -N -H "Content-Type: application/json" -d '{"messages":[{"role":"user","content":"Why did you leave Corelight?"}]}' https://api.adambuilds.ai/v1/chat
fly logs -a adambuilds-twin --no-tail | tail -20
```

Expected: health over TLS; a streamed Boston reply; the Corelight turn shows the `tool` frame labelled "Passing this along to Adam" and a reply that the role wrapped up in August 2026 with no reason (this sends one real push); the logs show JSON turn lines with hashed clients and no message text.

- [ ] **Step 7: Record** — add the app name, region, and machine id to the plan's deviations section if anything differed from the spec.

---

### Task 7: Deploy token, merge, and verify the pipeline

- [ ] **Step 1: Token** — **Adam** runs, from the repo root: `fly tokens create deploy -x 8760h -a adambuilds-twin | gh secret set FLY_API_TOKEN`. Then `gh secret list` shows `FLY_API_TOKEN`. The token is never displayed.
- [ ] **Step 2: Pull request** — push the branch and open a PR titled "Deploy the twin API to Fly.io" with a summary and the acceptance results from Task 6 (no hostnames beyond the public one, no ids that identify secrets); the `test` job must be green on the PR.
- [ ] **Step 3: Merge and watch** — **Adam** merges (or approves the merge). The `deploy` job runs on `main`; confirm in the Actions tab that both jobs are green and the smoke step printed the health body. Then `fly releases -a adambuilds-twin` shows the new release and `fly scale show` still reports one machine.
- [ ] **Step 4: Wrap-up** — record deviations in this plan and in section 19-style notes in the deployment spec if anything changed; update the roadmap memory; report the public URL, the cost, and the two rules (one machine; rotate the token yearly).
