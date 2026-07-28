# Deploying Sajilo Loan (free cloud, shareable URL)

This guide puts the app online so anyone with the link can use it:

- **Database** → MongoDB Atlas (free M0 cluster)
- **Backend** (FastAPI + Tesseract OCR) → Render (free Docker web service)
- **Frontend** (Next.js) → Vercel (free hobby project)

The frontend talks to the backend **server-side** (Next.js API routes proxy to
`SAJILO_API_BASE_URL`), so your friends' browsers only ever hit the Vercel URL.

**Deploy order matters:** Database → Backend → Frontend → wire CORS back to the
frontend. Each step needs a value produced by the previous one.

---

## 0. Prerequisites

1. Push this project to a **GitHub repository** (both `backend/` and `frontend/`
   in one repo is fine — the configs here assume that layout).
2. Free accounts on: [MongoDB Atlas](https://www.mongodb.com/atlas),
   [Render](https://render.com), and [Vercel](https://vercel.com). Signing in
   to Render and Vercel with GitHub is easiest.

```bash
# From the project root, if you haven't pushed yet:
git init
git add .
git commit -m "Sajilo Loan with EMI module"
git branch -M main
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

`.gitignore` already excludes `.env`, `node_modules/`, `.next/`, and `uploads/`,
so no secrets or build junk get committed.

---

## 1. MongoDB Atlas (database)

1. Create a project, then **Build a Database → M0 (Free)**. Pick a region close
   to your Render region.
2. **Database Access →** add a database user (username + password). Save these.
3. **Network Access →** Add IP Address → **Allow access from anywhere**
   (`0.0.0.0/0`). Render's free plan has no fixed IP, so this is required.
4. **Database → Connect → Drivers →** copy the connection string. It looks like:

   ```
   mongodb+srv://<user>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
   ```

   Replace `<user>` / `<password>` with the credentials from step 2. Keep this —
   it becomes `MONGODB_URI`. (The app uses database name `sajilo_loan`.)

---

## 2. Backend on Render

The repo includes `render.yaml` (a Blueprint) and `backend/Dockerfile`, so
Render builds the OCR-ready image automatically.

1. In Render: **New + → Blueprint**, then select your GitHub repo. Render reads
   `render.yaml` and creates a web service named **sajilo-loan-api**.
2. It will ask for the two secret env vars marked `sync: false`:
   - `MONGODB_URI` → the Atlas string from step 1.
   - `CORS_ALLOWED_ORIGINS` → leave blank for now (you don't have the Vercel URL
     yet). You'll set it in step 4.
   `JWT_SECRET_KEY` is **auto-generated** by Render, and `APP_ENV=production`,
   `TESSERACT_CMD`, and `UPLOAD_DIR` are set for you.
3. Click **Apply / Create**. The first Docker build takes a few minutes.
4. When it's live you'll get a URL like `https://sajilo-loan-api.onrender.com`.
   Verify it:
   - `https://sajilo-loan-api.onrender.com/` → `{"message": "Sajilo Loan API starter"}`
   - `https://sajilo-loan-api.onrender.com/docs` → interactive API docs.

Copy the backend URL — it becomes `SAJILO_API_BASE_URL` for the frontend.

> **Prefer clicking over the Blueprint?** Create a **Web Service**, choose
> **Docker**, set **Root Directory** to `backend`, and add the env vars from
> `render.yaml` manually (generate a 32+ character `JWT_SECRET_KEY` yourself with
> `openssl rand -hex 32`).

---

## 3. Frontend on Vercel

1. In Vercel: **Add New → Project**, import the same GitHub repo.
2. Set **Root Directory** to `frontend` (click *Edit* next to the repo name).
   Vercel auto-detects Next.js — leave build/output settings default.
3. Add an **Environment Variable**:
   - Name: `SAJILO_API_BASE_URL`
   - Value: your Render backend URL, e.g. `https://sajilo-loan-api.onrender.com`
     (no trailing slash)
4. **Deploy.** You'll get a URL like `https://sajilo-loan.vercel.app`. That's the
   link you share with friends.

---

## 4. Wire CORS back to the frontend

1. In Render → **sajilo-loan-api → Environment**, set:
   ```
   CORS_ALLOWED_ORIGINS = https://sajilo-loan.vercel.app
   ```
   (your actual Vercel URL, no trailing slash). Add multiple origins
   comma-separated if you also use a custom domain.
2. Save — Render redeploys automatically.

Open the Vercel URL, register an account, and submit a test loan application to
confirm end-to-end flow (including the new EMI calculator).

---

## 5. Create an officer/admin account

Registration always creates a **customer**. To review applications you need at
least one **officer** (and optionally an **admin**). Bootstrap the first one by
promoting a registered user directly in the database:

1. Register the user normally through the app (remember their email).
2. In Atlas → **Browse Collections → `sajilo_loan` → `users`**, find that user
   and edit the `role` field from `customer` to `officer` (or `admin`).

   Or via `mongosh`:
   ```js
   use sajilo_loan
   db.users.updateOne(
     { email: "you@example.com" },
     { $set: { role: "officer" } }   // or "admin"
   )
   ```
3. Log out and back in. An **admin** can promote further officers from the Admin
   dashboard, so you only need to do this DB edit once.

---

## Environment variable reference

**Backend (Render)**

| Variable | Value | Notes |
|---|---|---|
| `APP_ENV` | `production` | Enforces a strong JWT secret |
| `MONGODB_URI` | Atlas SRV string | Secret — set in dashboard |
| `MONGODB_DB` | `sajilo_loan` | Database name |
| `JWT_SECRET_KEY` | 32+ char random | Auto-generated by the Blueprint |
| `CORS_ALLOWED_ORIGINS` | Vercel URL(s) | Comma-separated, no trailing slash |
| `TESSERACT_CMD` | `/usr/bin/tesseract` | OCR binary path in the image |
| `UPLOAD_DIR` | `/app/uploads` | Where documents are written |

**Frontend (Vercel)**

| Variable | Value | Notes |
|---|---|---|
| `SAJILO_API_BASE_URL` | Render backend URL | No trailing slash |

---

## Free-tier limitations (worth knowing)

- **Cold starts:** Render's free service sleeps after ~15 min idle; the first
  request then takes ~30–60 s to wake. Fine for a demo friends check now and
  then. Upgrade to a paid instance to keep it always-on.
- **Uploaded documents are ephemeral:** the free plan has no persistent disk, so
  files in `/app/uploads` are lost on redeploy/restart. Application data,
  EMI values, and risk scores live in MongoDB and persist. To keep uploaded
  files, attach a Render **Disk** (paid) mounted at `/app/uploads`, or switch
  document storage to a bucket (e.g. S3/Cloudflare R2).
- **Atlas M0** is capped at 512 MB — plenty for a demo.

---

## Updating after changes

Every `git push` to `main` triggers an automatic redeploy on both Render and
Vercel. No manual steps needed.
