# Free test deployment: Render + Neon

This runs the same two containers as the Cloud Run setup (the API from the
root [`Dockerfile`](../Dockerfile), the web app from
[`apps/web/Dockerfile`](../apps/web/Dockerfile)). It uses free tiers only, so
no billing account is needed:

- **Render** (free web services) runs both containers from the GitHub repo.
  The [`render.yaml`](../render.yaml) Blueprint sets them up together.
- **Neon** (free PostgreSQL) holds the database and the library files.

Good for a trial, not for production. See [Limits](#limits) before sharing it.

## 1. Create the database (Neon)

1. Sign up at <https://neon.tech> and create a project. Pick the region
   **AWS US West 2 (Oregon)**, which sits next to Render's Oregon region.
2. On the project dashboard click **Connect**. Turn **Connection pooling off**
   and copy the connection string. It looks like
   `postgresql://user:password@ep-….us-west-2.aws.neon.tech/neondb?sslmode=require`
3. Change the start from `postgresql://` to **`postgresql+psycopg://`**. The
   rest stays the same. This is your `ARCHSCOPE_DATABASE_URL`.

## 2. Make an encryption key

From the repository folder:

```powershell
uv run python -m archscope_api.cli secret-key
```

Save the output somewhere safe (a password manager). This is your
`ARCHSCOPE_SECRET_KEY`. If it ever changes, saved HubSpot and AI keys can't
be read anymore.

## 3. Push the code to GitHub

Render deploys from GitHub. Push the branch you want to test, for example
`rebuild/web-platform`, to `github.com/AlosedAG/archgen`.

## 4. Create both services (Render)

1. Sign up at <https://render.com> with your GitHub account and let Render
   access the `archgen` repository.
2. **New → Blueprint**, choose the repository and **the branch from step 3**.
   Render reads `render.yaml` and lists `archscope-api` and `archscope-web`.
3. Fill in the values it asks for:
   - `ARCHSCOPE_DATABASE_URL`: from step 1.
   - `ARCHSCOPE_SECRET_KEY`: from step 2.
   - `API_URL`: **`https://archscope-api.onrender.com`**. If Render gave the
     API a different address (shown on the service page once it's created),
     change it there later. See step 5.
4. Click **Apply**. The first build takes about 5–10 minutes per service.

## 5. Check the address and test

1. Open the **archscope-api** service. Its address is at the top. Visit
   `<that address>/healthz`; it should show `"status":"ok"`.
2. If the address is **not** `https://archscope-api.onrender.com`: open
   **archscope-web → Environment**, set `API_URL` to the real address (no
   slash at the end), and choose **Save, rebuild, and deploy**. The address
   is built into the web app, so it always needs a rebuild after a change.
3. Open the **archscope-web** address. This is the link you share.

## 6. Create the accounts

Render's free tier blocks outgoing email (SMTP), so sign-up codes can't be
sent and self sign-up stays off. Instead, create each tester's account from
your laptop, directly in the Neon database. The API creates the tables on its
first start, so do this after step 5.

```powershell
$env:ARCHSCOPE_DATABASE_URL = "postgresql+psycopg://…"   # from step 1
uv run python -m archscope_api.cli create-user --email you@sonamation.com --name "You" --workspace SonaMation --role owner
uv run python -m archscope_api.cli create-user --email tester@sonamation.com --name "Tester" --workspace SonaMation
Remove-Item Env:ARCHSCOPE_DATABASE_URL
```

Each command asks for that person's password. Send it to them privately.
`set-password --email …` resets one later.

## 7. AI drafting

Once signed in, add a Gemini key (free tier, from
<https://aistudio.google.com/apikey>) or an Anthropic key on the
**Settings** page. You can instead add `GEMINI_API_KEY` or
`ANTHROPIC_API_KEY` under **archscope-api → Environment**.

## Updating

Every push to the branch rebuilds and redeploys both services. To deploy only
by hand, turn off **Auto-Deploy** in each service's settings and use
**Manual Deploy**.

## Limits

- **Sleeps when idle.** After about 15 minutes with no visits, each service
  shuts down. The next visit wakes it in about a minute. Warn testers that
  the first page can be slow.
- **No email.** No sign-up codes, password-reset emails or Feedback-button
  emails (see step 6). Paid Render instances allow ports 465/587, and so does
  the Cloud Run setup.
- **Free hours.** Render's free plan includes a monthly allowance of
  instance hours shared by all free services. Both services sleeping when
  idle keeps light testing well inside it.
- **Neon free storage** is a fraction of a GB. Library files are stored in
  the database, so large uploads use it up faster.

Moving to Cloud Run later doesn't lose data: point its
`archscope-database-url` secret at the same Neon database and reuse the same
secret key.
