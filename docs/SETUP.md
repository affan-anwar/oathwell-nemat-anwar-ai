# Setup (Windows PowerShell)
```
cd apps\api
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
$env:APP_SECRET_KEY = python -c "import secrets;print(secrets.token_urlsafe(48))"
alembic upgrade head
pytest
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000/docs. This uses a local SQLite file (`dev.db`) for development.
Keep the same PowerShell window: `APP_SECRET_KEY` only lives in that window, and tokens stop working if it changes.

## PostgreSQL
```
pip install -r requirements-postgres.txt
$env:DATABASE_URL = "postgresql://user:password@localhost:5432/nematanwar"
alembic upgrade head
```
Run tests on PostgreSQL: set `TEST_DATABASE_URL` to a throwaway database (the tests drop and recreate its tables).

## Real AI
```
$env:LLM_PROVIDER = "anthropic"
$env:ANTHROPIC_API_KEY = "your key"
```
## Real WordPress
In WordPress create an Application Password for a user who can publish posts. Then call `POST /api/v1/workspaces/{ws}/integrations/wordpress`, then `.../integrations/{id}/test`.
Production sites must use https. Private and internal addresses are blocked.

# Web app (second terminal)
```
cd apps\web
npm install
npm run dev
```
Open http://localhost:5173, register, create a workspace. The API must be running on port 8000.
Needs Node 20.19 or newer (check with `node --version`).

# Scheduler worker (third terminal) - needed for scheduled posts
Use the SAME `APP_SECRET_KEY` and `DATABASE_URL` as the API. A different key cannot decrypt saved WordPress passwords and invalidates sign-ins.
Generate the key once, then paste the same value in every terminal:
```
python -c "import secrets;print(secrets.token_urlsafe(48))"
$env:APP_SECRET_KEY = "PASTE_THE_SAME_VALUE"
```
Then in each of the API and worker terminals:
```
cd apps\api
.venv\Scripts\Activate.ps1
python -m app.workers.scheduler        # keeps running, checks every 15 seconds
python -m app.workers.scheduler --once # one pass, then exits
```
Upgrading an existing database from v3: run `alembic upgrade head` (keeps all data; tested on SQLite and PostgreSQL).


## AI provider keys (PowerShell, terminal 1 and the worker terminal, before starting)
```
$env:OPENAI_API_KEY = "<your new key>"      # or GEMINI_API_KEY / ANTHROPIC_API_KEY
```
Then sign in as the Owner, open **Owner Console > AI Providers**, press **Test connection**, choose a model from the list your account can use, and save. Never paste a key into chat, code or Git. If a key was ever shared, revoke it and create a new one.

## Owner Console and roles
The first account to create a workspace is its Owner. Add people on **Team**. Role limits are in `docs/RBAC.md`.

## Browser tests with a fake camera
Start Chromium with `--use-fake-device-for-media-stream --use-fake-ui-for-media-stream` and set `E2E_FAKE_CAMERA=1` to include the camera test.
