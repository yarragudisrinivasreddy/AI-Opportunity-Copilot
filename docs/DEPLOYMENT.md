# Deployment (commands are a starting point: verify flags against current gcloud/firebase docs)

Placeholders: `PROJECT`, `REGION` (a region that serves your Gemini model), `BUCKET`, `MODEL_ID`.

```bash
gcloud config set project PROJECT
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  aiplatform.googleapis.com firestore.googleapis.com storage.googleapis.com vision.googleapis.com \
  dlp.googleapis.com secretmanager.googleapis.com firebase.googleapis.com identitytoolkit.googleapis.com

gcloud firestore databases create --location=REGION          # Native mode
gcloud storage buckets create gs://BUCKET --location=REGION --uniform-bucket-level-access --public-access-prevention

gcloud iam service-accounts create copilot-api
# Grant the runtime service account (least privilege): Vertex AI User, Firestore (Datastore) User,
# Storage Object Admin on the bucket only, DLP User. Verify role names in IAM docs.

gcloud run deploy opportunity-copilot-api --source . --region REGION \
  --service-account copilot-api@PROJECT.iam.gserviceaccount.com --allow-unauthenticated \
  --timeout=300 --min-instances=1 --cpu=1 --memory=1Gi \
  --set-env-vars ENV=production,AUTH_MODE=firebase,LLM_MODE=vertex,STORE_MODE=firestore,MEDIA_MODE=gcs,PRIVACY_MODE=gcp,GCP_PROJECT=PROJECT,GCP_LOCATION=REGION,GEMINI_MODEL=MODEL_ID,MEDIA_BUCKET=BUCKET,FIRESTORE_DATABASE=copilot,UPLOADS_ENABLED=false,ALLOWED_ORIGINS=https://PROJECT.web.app,https://PROJECT.firebaseapp.com
```
`--allow-unauthenticated` is required for the Hosting rewrite; the API itself requires a valid Firebase ID token on every `/api` route except `/api/sample` and `/api/config`.

Use a **Native** Firestore database co-located with Cloud Run (this project: `copilot` in `us-central1`; the legacy `(default)` DB may be Datastore-mode). Keep `UPLOADS_ENABLED=false` until Cloud Vision + DLP are verified on real frames (text-only kill switch).

Runtime SA roles (least privilege): `roles/aiplatform.user`, `roles/datastore.user`, `roles/storage.objectAdmin` on the media bucket, `roles/dlp.user`. On Vision/DLP **403**, grant only the missing role — do not widen to Editor.

Frontend and rules:
```bash
cd frontend && cp .env.example .env.local   # fill VITE_FIREBASE_* from the Firebase console; enable Anonymous sign-in
npm run build
cd .. && firebase deploy --only hosting,firestore
```
Before deploying, replace `REPLACE_WITH_CLOUD_RUN_REGION` in `firebase.json`.

Checklist:
- **budget alert** set (`copilot-alert` INR 2000) — emails only; does **not** stop spend.
- **Vertex AI quota** capped in IAM Quotas (**first item tomorrow morning** — this is the real spend brake).
- `GLOBAL_DAILY_CASE_CAP` / `DAILY_CASE_CAP` set; size global cap from `python -m eval.run --suite e8 --llm vertex` cost/case vs INR 2000. Sample must never count against caps.
- **App Check:** register provider → run in **monitor** mode → test Incognito + phone → only then `ENFORCE_APP_CHECK=true`. Keep a one-command rollback (`false` + redeploy). Do not flip on late 17 Oct.
- Incognito / second browser / mobile / Safari private: sample loads; live path fails with a clear sign-in/storage message (not a blank screen).
- Fresh-clone verify (single branch, small size, `pip install -r requirements-dev.txt` + `pytest`, `npm ci` + `npm run build`).

Uptime / gate health URL: `https://HOST/api/health` (not `/healthz`).
