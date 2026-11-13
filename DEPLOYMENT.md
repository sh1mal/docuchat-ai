# Deploy DocuChat AI to the existing Render services

Use Qdrant first for the deployed library. Keep the existing React static site and FastAPI Web Service; no paid Render disk is needed. Secrets belong only in backend environment settings. Never use `VITE_` for a secret: Vite includes those values in public JavaScript.

## 1. Create the free Qdrant cluster

1. Open https://cloud.qdrant.io/ and sign in or create your account yourself. Review account terms before accepting them.
2. Create one **Free** cluster (1 GB RAM / 4 GB disk). Do not choose a paid cluster, upgrade or add a payment method for this demo.
3. Wait until the cluster is running. Copy its HTTPS endpoint from the cluster overview.
4. Create/copy a cluster database API key in the Qdrant console. You must complete any credential-creation steps yourself. Give it collection and point read/write permissions for this application's dedicated collection, including collection/index creation if the collection does not exist yet. Keep the key private.
5. Use `docuchat_gemini_768` as a new dedicated collection. The app creates its 768-dimensional Cosine vector collection and keyword payload indexes (`type`, `document_id`) on first access. Do not reuse an unrelated collection.

The application stores **extracted text**, page/chunk metadata and embeddings in Qdrant, not original PDF files. Qdrant is independent of Render restarts, but its free tier has suspension/deletion rules; it is not a backup guarantee.

## 2. Set the backend environment in Render

Existing service: `docuchat-ai-backend`.

Set the following in that service's **Environment** page. Retain your existing private keys if still valid; rotate any previously exposed API key yourself. Do not share screenshots with values visible.

| Variable | Value |
| --- | --- |
| `PYTHON_VERSION` | `3.14.5` (matches local verification) |
| `GEMINI_API_KEY` | Your private Google AI Studio key, with embedding + generation access |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` (existing project model; configurable) |
| `FRONTEND_ORIGIN` | `https://docuchat-ai-frontend.onrender.com` (no `/chat`) |
| `VECTOR_STORE` | `qdrant` |
| `QDRANT_URL` | The cluster HTTPS endpoint from Qdrant |
| `QDRANT_API_KEY` | Your private cluster database key |
| `QDRANT_COLLECTION` | `docuchat_gemini_768` |

`GEMINI_API_KEY` and `QDRANT_API_KEY` must **not** be in the frontend environment, repository, chat, build command or start command. Existing `CHROMA_DB_PATH` is unused and can be removed.

Backend **Settings**:

| Setting | Value |
| --- | --- |
| Repository | `https://github.com/sh1mal/docuchat-ai` |
| Branch | The reviewed fix branch, or `main` after merging |
| Root Directory | `backend` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1` |
| Health Check Path | `/health` |
| Instance | Free |

Use **Manual Deploy → Clear build cache & deploy** for the first migration so the old ML packages are not reused. Keep the existing service URL. Confirm logs report it is live, and check memory metrics during an upload. Local startup measurement was approximately 56 MB on macOS; it is not a guarantee of peak memory on Render.

If `VECTOR_STORE` is omitted on Render, the app defaults to Qdrant and fails safely until its settings are supplied. To deliberately use a temporary demo instead, set `VECTOR_STORE=sqlite`; the UI then warns users to reupload after Render restarts. This is not the chosen Qdrant deployment.

## 3. Connect/rebuild the existing React static site

| Setting | Value |
| --- | --- |
| Root Directory | `my-react-app` |
| Build Command | `npm ci && npm run build` |
| Publish Directory | `dist` |
| Environment | `VITE_API_URL=https://docuchat-ai-backend.onrender.com` |
| Rewrite | `/*` → `/index.html`, action **Rewrite** (200) |

Verify the backend URL against the actual Web Service URL before saving. `VITE_API_URL` is read at build time: changing it requires a frontend rebuild. The rewrite lets opening `/chat` directly work.

The frontend loads the shared document library automatically. No demo key or sign-in is required. All visitors can upload, read, and delete documents. Remove the unused `DOCUCHAT_DEMO_KEY` environment variable from the backend if present. Deploy both backend and frontend changes together. An older backend still requires a key and will reject requests from the updated frontend.

## 4. Verify the live deployment

1. Open the backend `/health`: expect `{"status":"ok"}`. This checks the process only.
2. Open `/documents` without any credentials: expect 200 with the document list and storage notice.
3. Open https://docuchat-ai-frontend.onrender.com/chat, verify the library loads automatically with a Qdrant storage notice and no key prompt.
4. Upload two small public/sample text PDFs with different facts. Ask one question about each, switch documents and expand page/chunk sources. Confirm sources belong to the selected PDF.
5. Delete one test PDF; verify the other remains and still answers questions.
6. Redeploy/restart only FastAPI. Reload and confirm the remaining test PDF still appears from Qdrant. Then delete your test document through the UI if desired.
7. In Render metrics, verify the process stays below the free instance's 512 MB limit during upload and chat. Test an idle/cold start as well.

Do not call the deployment complete based only on `/health` or offline tests. The Qdrant library load, real Gemini embedding/answer calls and restart check are separate acceptance steps.

## Troubleshooting

- **401:** the backend is still running the older key-protected version. Deploy the updated backend as well as the frontend.
- **503 / storage unavailable:** verify `VECTOR_STORE=qdrant`, the cluster is active, endpoint/key, permissions and the dedicated collection's 768/Cosine schema. Qdrant free strict mode requires the payload indexes the app creates.
- **Gemini rejected request:** check the Google project key and access to `gemini-embedding-001` and the configured generation model. A model available in one project need not be available in another.
- **429:** API quota was reached or the single operation slot is busy. Retry later; smaller PDFs use fewer embedding tokens. Check AI Studio for your actual quotas.
- **Browser network/CORS error:** ensure `FRONTEND_ORIGIN` exactly matches the frontend origin, `VITE_API_URL` is the backend HTTPS URL, and rebuild/redeploy both after changes. An idle backend may need about a minute to wake.
- **413:** reduce the PDF size/page count/text volume or remove documents from the demo library.
- **No extractable text:** use a text PDF or run OCR separately.

## Cost and retention limits

The selected Render and Qdrant plans are free. Render Free has 512 MB RAM, 750 free instance hours per workspace/month and sleep after 15 minutes idle; filesystem changes can disappear on restart, redeploy and spin-down. Qdrant's free cluster has 4 GB disk, can suspend after one week unused and can be deleted after four weeks of inactivity unless reactivated.

Gemini embedding and Flash-Lite free tiers have project/model quotas and data-use terms. Free-tier input/output may be used to improve Google products. If Google billing is enabled, current standard prices are $0.15 per million input tokens for `gemini-embedding-001`, and $0.30 input / $2.50 output per million tokens for `gemini-3.5-flash-lite`. These are provider prices, not an enforced spending cap in this app. Do not enable billing to bypass quotas without deciding your budget. Render bandwidth/build allowances may also apply.

Official references: [Render Free](https://render.com/docs/free), [Render Python versions](https://render.com/docs/python-version), [Qdrant Cloud free cluster](https://qdrant.tech/documentation/cloud/create-cluster/), [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing), [Gemini rate limits](https://ai.google.dev/gemini-api/docs/rate-limits), [Gemini embedding API](https://ai.google.dev/api/embeddings).
