# Web Push & Multi-Channel Alert Setup Guide

This guide describes how to configure, test, and deploy the standards-based **Web Push** and **SMS-ready** alerting system for the **Chungthang–Teesta Early Warning System (FFEWS)**.

---

## 1. Overview & Architecture

The alerting system uses a multi-channel dispatcher architecture (`backend/app/alerts/dispatcher.py`) adhering to strict open standards and data protection principles:

```
                               ┌──────────────────────────────────────────────┐
                               │     Hydro / Rainfall Risk Evaluator          │
                               │  (Hysteresis, Stale Checks, Simulation Flag) │
                               └──────────────────────┬───────────────────────┘
                                                      │
                                                      ▼
                               ┌──────────────────────────────────────────────┐
                               │        LiveAlertEvent (SQLite / Postgres)    │
                               │   Unique ID, Zone, Q, Threshold, Freshness   │
                               └──────────────────────┬───────────────────────┘
                                                      │
                                                      ▼
                               ┌──────────────────────────────────────────────┐
                               │         MultiChannelAlertDispatcher          │
                               └──┬───────────────────┬───────────────────┬───┘
                                  │                   │                   │
                                  ▼                   ▼                   ▼
                     ┌───────────────────────┐ ┌───────────────┐ ┌───────────────────┐
                     │  Web Push Channel     │ │  SMS Channel  │ │  CAP v1.2 XML     │
                     │  (VAPID RFC 8292)     │ │  (TRAI DLT)   │ │  (OASIS Compliant)│
                     │  Browser PWA Devices  │ │  Status:      │ │  Downloadable     │
                     │  Status: READY        │ │  NOT CONFIGURED││  Export           │
                     └───────────────────────┘ └───────────────┘ └───────────────────┘
```

### Critical Security & Reliability Policies:
1. **Zero Private Key Exposure:** The VAPID private key and alert administration keys reside **strictly** in backend environment variables. They are never exported through `VITE_*` variables or included in frontend client bundles.
2. **Real Subscriptions Only:** Push notifications are delivered only to active, validated browser push subscriptions registered in the `push_subscriptions` database table.
3. **Expired Endpoint Pruning:** If a browser revokes permission or the push service returns HTTP 404 / 410 Gone, the backend automatically flags the subscription as `is_active = False` to prevent future wasted requests.
4. **Honest Readiness States:** When credentials or physical gateways are not configured, the system reports `NOT CONFIGURED` rather than fabricating delivery receipts or simulating fake SMS.
5. **Clear Demarcation:** Every alert and notification is strictly classified as `LIVE`, `SIMULATION`, or `TEST`. Test notifications can never be mistaken for real-world flash-flood warnings.

---

## 2. Standards-based Web Push (VAPID RFC 8292)

Web Push is the W3C and IETF open standard for delivering notifications to web browsers across desktop (Chrome, Edge, Firefox, Brave, Safari on macOS) and mobile devices (Chrome on Android, Safari on iOS 16.4+ when added to Home Screen).

### Step 1: Generate VAPID Keypair

You can generate a compliant P-256 VAPID keypair using Node.js:
```bash
npx web-push generate-vapid-keys
```

Or using the installed Python virtual environment:
```bash
.\venv\Scripts\python.exe -c "from py_vapid import Vapid; v = Vapid(); v.generate_keys(); from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat; import base64; print('PUBLIC KEY:', base64.urlsafe_b64encode(v.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)).decode().rstrip('=')); print('PRIVATE KEY:\n' + v.private_pem().decode())"
```

*Note: If no VAPID keys are provided in the environment during local development, the backend automatically generates a secure ephemeral keypair in memory so that development and testing function seamlessly.*

### Step 2: Configure Environment Variables

Add the keys to your backend `.env` file:
```bash
WEB_PUSH_ENABLED=true
VAPID_PUBLIC_KEY=BDn9G6vcXgZFpukkpHWv0F9ivcMI2z04IinpdHKuDYKp3U1JLvFtfFYeKdWN_vo7olNTTKm2sb838fR24qOW7y4...
VAPID_PRIVATE_KEY="-----BEGIN EC PRIVATE KEY-----\n...\n-----END EC PRIVATE KEY-----"
VAPID_CLAIM_EMAIL=mailto:alerts@chungthang-flood-warning.org
ALERT_ADMIN_KEY=your_secure_admin_passphrase
```

---

## 3. Browser PWA Push Notification Workflow

### How it Works:
1. **User Subscription:**
   - The user opens the **Active Alerts** page on the dashboard (`/alerts`).
   - Under the **Multi-Channel Notification Channels** section, the user clicks **Enable Push Notifications**.
   - The frontend queries `GET /api/v1/alerts/push/vapid-public-key` to receive the public key.
   - The browser prompts the user for notification permissions.
   - Upon grant, the Service Worker calls `registration.pushManager.subscribe()` using the VAPID public key.
   - The subscription object (`endpoint`, `p256dh`, `auth`) is sent to `POST /api/v1/alerts/push/subscribe`.
2. **Notification Reception (`frontend/public/custom-push-sw.js`):**
   - The Service Worker listens to the `push` event.
   - It parses the incoming JSON payload containing `title`, `body`, `zone`, `severity`, and `url`.
   - The device displays a native system notification with a siren icon and high-priority vibration pattern (`[300, 100, 300, 100, 300]`).
3. **Notification Click:**
   - Clicking the notification activates the `notificationclick` handler, safely opening or focusing the early warning dashboard (`/alerts`).
4. **Unsubscribe:**
   - The user can click **Unsubscribe** at any time. The browser deactivates the push subscription and notifies `POST /api/v1/alerts/push/unsubscribe`.

---

## 4. Operator Testing & Acknowledgement Workflow

### Sending a Test Push Notification:
1. Navigate to the **Active Alerts** page (`/alerts`).
2. In the **Test Notification Simulation** panel, click **Send Test Notification**.
3. The backend:
   - Emits a verified `alert_type = "TEST"` record.
   - Dispatches a push notification with title `[TEST] Emergency Alert Test - Chungthang`.
   - Persists a non-active audit entry (`is_active = False`) in the database.
   - The test notification is clearly labelled and cannot trigger false evacuations.

### Operator Alert Acknowledgement:
1. When an active `WARNING` or `CRITICAL` alert is active, it appears in the Active Alerts table.
2. An authorized operator clicks **Acknowledge Alert**.
3. In the modal dialog, the operator inputs their name (e.g. `Duty Officer - SSDMA Gangtok`) and deployment actions taken.
4. The system updates the alert state to `ACKNOWLEDGED` via `POST /api/v1/alerts/{alert_id}/acknowledge`, logging timestamp and operator metadata for post-event audit.

---

## 5. Render Deployment Configuration & Production Persistence

The repository is configured with `render.yaml` for deployment on Render.

### Critical Database Persistence Note:
> [!IMPORTANT]
> **Ephemeral Filesystem vs Persistent Storage:**
> Render Web Services use ephemeral container filesystems by default. Without dedicated persistent storage, SQLite databases are destroyed on every service restart, sleep cycle, or Git deployment.

#### Option A: Persistent Disk with SQLite (Render Starter Plan or above)
Render persistent disks are supported on paid instance types (Starter plan or higher).
- **Disk Configuration:** In `render.yaml`, a 1 GB persistent disk is configured and mounted at `/data`:
  ```yaml
  disk:
    name: flashflood-data
    mountPath: /data
    sizeGB: 1
  ```
- **Database Path:** Set `SQLITE_DB_PATH=/data/flashflood.db`. The application automatically resolves this path and runs idempotent migrations at startup via `migrate_db.py`.
- **Preservation:** Existing data in `/data/flashflood.db` is preserved across redeployments and restarts.

#### Option B: Render Managed PostgreSQL (Free or Multi-Instance Production)
If a persistent disk is not available (e.g. running on Render's Free tier or requiring multi-worker scaling):
- Provision a **Render Managed PostgreSQL** database instance from the Render dashboard.
- Set `DATABASE_URL` in the Web Service environment to the provided Internal Connection String:
  ```
  DATABASE_URL=postgresql://flashflood_user:password@dpg-xxx-a:5432/flashflood_db
  ```
- Set `USE_SQLITE=false`. The application will automatically connect to PostgreSQL and run startup migrations cleanly.

---

### Production VAPID Key Stability:
> [!CAUTION]
> **Never Rely on Auto-Generated Keys in Production:**
> In development mode, the backend generates an in-memory keypair for rapid testing.
> In production mode (`ENV=production`), auto-generation is strictly disabled. If `VAPID_PUBLIC_KEY` or `VAPID_PRIVATE_KEY` is missing or mismatched, the Web Push channel enters `CONFIG_ERROR` status and safely skips dispatch without crashing.
> **Key Stability:** Existing browser push subscriptions are cryptographically bound to the public key used during subscription. Changing the VAPID keypair in production invalidates all existing browser subscriptions and requires every user to re-subscribe. Generate **one** stable keypair once and store it in Render's Private Environment Settings.

#### Generate a Stable Production Keypair:
Run the following once on your workstation:
```bash
.\venv\Scripts\python.exe -c "from py_vapid import Vapid; v = Vapid(); v.generate_keys(); from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat; import base64; print('=== VAPID_PUBLIC_KEY ==='); print(base64.urlsafe_b64encode(v.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)).decode().rstrip('=')); print('\n=== VAPID_PRIVATE_KEY ==='); print(v.private_pem().decode())"
```

### Backend Web Service Environment Variables:
| Environment Variable | Recommended Value | Description |
|----------------------|-------------------|-------------|
| `ENV` | `production` | Enables strict production security checks |
| `CORS_ORIGINS` | `https://flashflood-frontend.onrender.com` | Allowed CORS origins (exact deployed frontend URL, never `*`) |
| `USE_SQLITE` | `true` | Persistent SQLite storage (when persistent disk attached) |
| `SQLITE_DB_PATH` | `/data/flashflood.db` | Mount path on Render persistent disk |
| `ALERT_NOTIFICATIONS_ENABLED` | `true` | Master toggle for alerts |
| `WEB_PUSH_ENABLED` | `true` | Enables Web Push delivery |
| `VAPID_PUBLIC_KEY` | *(Set in Render Dashboard)* | Base64url P-256 public key (stable) |
| `VAPID_PRIVATE_KEY` | *(Set in Render Dashboard)* | PEM EC private key (stable, keep private) |
| `VAPID_CLAIM_EMAIL` | `mailto:admin@chungthang-ffews.gov.in` | RFC 8292 contact email for push services |
| `SMS_ENABLED` | `false` | Kept false until DLT registration |
| `ALERT_ADMIN_KEY` | *(Set in Render Dashboard)* | Secret passphrase for admin endpoints (`X-Admin-Key`) |
| `INGESTION_CRON_SECRET` | *(Set in Render Dashboard)* | Secret for scheduled ingestion webhooks |

### Frontend Static Site Settings:
The static frontend is built using:
```bash
cd frontend && npm install && npm run build
```
Publish path: `frontend/dist`

The frontend communicates with the backend via `VITE_API_URL` pointing to the deployed backend service URL (e.g., `https://flashflood-backend.onrender.com`).
Operators can authenticate by clicking **Operator Auth** on `/alerts` to enter the `ALERT_ADMIN_KEY`, which is stored strictly in browser session memory (`sessionStorage`) and never logged or exposed in URLs.
