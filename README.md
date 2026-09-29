# Real-Time Voting Platform

A Django voting prototype that accepts votes submitted through Google Forms, forwards them from the linked Google Sheet with Google Apps Script, stores accepted votes in Django, and broadcasts updated totals to a live dashboard with Django Channels.

> **Integration status:** The Django webhook, vote model, WebSocket consumers, and dashboard are in this repository. The Google Form, response Sheet, and Apps Script project are external setup steps; no Apps Script source is currently included here. The example below is a starting point that must be configured with the real form field names and a publicly reachable Django URL.

## How the vote flows

1. A voter submits a Google Form containing an email address and candidate choice.
2. Google Forms records the response in its linked Google Sheet.
3. An installable Apps Script form-submit trigger reads the submitted row and sends JSON to Django's `POST /google/` endpoint.
4. Django validates the payload and stores the vote in the `Vote` table in SQLite. A database uniqueness constraint rejects an email address that has already voted.
5. Django recalculates totals and broadcasts them to the Channels group named `vote_results`.
6. The dashboard at `/` is connected to `/ws/votes/` and updates its chart when it receives a vote broadcast.

Google Sheets is the raw form-response store in this design. Django does not currently read vote totals from Sheets or write votes back to Sheets; its dashboard totals come from the Django database.

## Technology

- Python 3.13 and Django
- Django's built-in user authentication for dashboard accounts
- Django Channels and Daphne for ASGI/WebSocket support
- SQLite for vote storage
- Google Forms and a linked Google Sheet as the voting form and response log
- Google Apps Script as the HTTP bridge between the response Sheet and Django
- Docker Compose for local containerized development
- Chart.js for the browser dashboard chart

## Project layout

```text
.
|-- Dockerfile
|-- compose.yaml
|-- manage.py
|-- mainP/                 # Django project settings, URLs, ASGI routing
|-- firstPage/             # Vote model, webhook view, and Channels consumers
|-- template/main/account.html # Combined login and registration page
|-- template/main/home.html    # Authenticated real-time dashboard
|-- static/                # Source static assets
|-- staticfiles/            # collectstatic output (generated, not committed)
|-- media/                  # User-uploaded media (not committed)
|-- requirements.txt
`-- README.md
```

## Run locally with Docker

Start Docker Desktop, then from this directory run:

```powershell
docker compose up --build
```

Open <http://localhost:8000>. Register an account, then use Django Admin to approve it before signing in. Compose starts Redis for Channels, waits for it to become healthy, runs database migrations, and starts Django's development server. Stop the service with `Ctrl+C`; run `docker compose down` to remove the Compose containers and network. The source folder is mounted into the container for development.

Compose uses a development-only fallback Django secret key. To override it, create a local `.env` file (it is ignored by Git):

```dotenv
DJANGO_SECRET_KEY=replace-this-with-a-long-random-secret
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
```

For a public test tunnel, add its hostname to `DJANGO_ALLOWED_HOSTS`, without a scheme or port. Google Apps Script runs on Google's servers, so it cannot call a Django server that is only available on your computer's `localhost`; use a publicly reachable HTTPS deployment or tunnel for testing.

For a hosted deployment, configure `REDIS_URL` with the connection URL for the platform's Redis service so Channels can broadcast across web workers.

## Run locally with Python

Python 3.13 is recommended to match the Docker image. From the project root:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open <http://127.0.0.1:8000>. To run the Django system checks:

```powershell
python manage.py check
```

The development server is for local development, not production. Start a local Redis-compatible service on `127.0.0.1:6379` before running Django, or set `REDIS_URL` to its connection URL. `static/` is the source folder, `staticfiles/` is the `collectstatic` destination, and `media/` holds uploaded files. During `DEBUG=True`, Django serves static and media URLs using the project URL configuration. Run `python manage.py collectstatic` to gather static assets for deployment; serve the collected files and persistent user media through your production host or storage service.

## User accounts

The dashboard requires an administrator-approved account. Opening `/` while signed out redirects to `/account/`, where the **Log in** and **Create account** tabs share one page. Registration asks for a username, email address, and password, then creates an inactive account; registration does not sign the user in. An administrator reviews the account in **Admin > Users**, selects the account, and applies **Approve selected accounts**. Only after approval can the user log in with their username and password. The dashboard profile menu displays the signed-in username and provides a CSRF-protected logout action. The account page and dashboard share a light/dark theme preference saved in the browser.

The dashboard WebSocket at `/ws/votes/` also rejects unauthenticated connections. The Google Apps Script webhook at `/google/` remains separate from user sessions so the Google trigger can submit votes; secure that endpoint before public production use.

## Configure Google Forms, Sheets, and Apps Script

1. Create a Google Form with a required email field and a required candidate-choice field. The candidate field should be a short answer or multiple-choice question; candidate values are stored as strings and should be no longer than 20 characters.
2. In the Form's **Responses** tab, link the form to a Google Sheet. Google Forms will append each response to the Sheet.
3. Open the response Sheet, then choose **Extensions > Apps Script**.
4. Add the script below. Change `DJANGO_WEBHOOK_URL`, `EMAIL_FIELD`, and `CANDIDATE_FIELD` to match your public endpoint and the exact response column headings in the Sheet.
5. In Apps Script, create an installable trigger for `forwardVote`: select the clock icon (**Triggers**), add a trigger, choose `forwardVote`, select **From spreadsheet** and **On form submit**, then authorize the script.
6. Submit a test form response and confirm that the Script execution log shows an HTTP 200 response. Check the Django service logs if it does not.

```javascript
const DJANGO_WEBHOOK_URL = 'https://YOUR_PUBLIC_HOST/google/';
const EMAIL_FIELD = 'Email Address';
const CANDIDATE_FIELD = 'Candidate';

function forwardVote(event) {
  const response = event.namedValues;
  const email = (response[EMAIL_FIELD] || [''])[0].trim();
  const candidate = (response[CANDIDATE_FIELD] || [''])[0].trim();

  if (!email || !candidate) {
    throw new Error('The submitted response is missing email or candidate.');
  }

  const result = UrlFetchApp.fetch(DJANGO_WEBHOOK_URL, {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify({ email: email, candidate: candidate }),
    muteHttpExceptions: true,
  });

  const status = result.getResponseCode();
  console.log('Django response: ' + status + ' ' + result.getContentText());

  if (status < 200 || status >= 300) {
    throw new Error('Django rejected the vote with HTTP ' + status);
  }
}
```

The event's `namedValues` keys are the response Sheet's question/column headings. If the form uses a different label or collects email through Google's built-in email collection, update the constants to match the actual Sheet headings.

## HTTP and WebSocket interfaces

### Vote webhook

- **URL:** `POST /google/`
- **Content type:** `application/json`
- **Body:**

```json
{
  "email": "voter@example.com",
  "candidate": "Candidate A"
}
```

- **Success:** HTTP 200 with a confirmation, vote ID, and current totals.
- **Invalid/missing JSON fields:** HTTP 400.
- **Email already recorded:** HTTP 409.
- **Any method other than POST:** HTTP 405.

### Live dashboard socket

- **URL:** `ws://localhost:8000/ws/votes/` during local development.
- **Message:** JSON containing a `type` of `vote_update` and a `votes` object, for example `{"type":"vote_update","votes":{"Candidate A":1}}`.

The dashboard loads aggregate totals and the latest saved votes from SQLite when the page opens. The history table is paginated at 50 votes per page; each new vote is broadcast over Channels, updates the live totals, and appears at the top of page one. Voter email addresses are not sent to dashboard users.

## Data and administration

The `Vote` model stores an email, candidate string, and creation timestamp. Its unique constraint allows only one row per email. Django Admin is available at <http://localhost:8000/admin/> after creating an initial administrator with:

```powershell
python manage.py createsuperuser
```

Registered users appear in **Admin > Users**. Select pending users and run **Approve selected accounts** to activate them so they can log in. The admin can review submitted account details there; voter email addresses remain admin-only.

The database is SQLite at `db.sqlite3`. That local database is excluded from Git and from the Docker build context; Compose's source bind mount keeps it on the host during development.

## Important limitations and deployment notes

- **Prototype security:** The webhook is CSRF-exempt and currently has no authentication or shared-secret verification. Anyone who can reach it could submit fabricated votes. Add request authentication/signature verification, rate limiting, and server-side candidate validation before using this for a real election.
- **Email identity:** The unique constraint prevents duplicate submissions for the same exact email string in Django. It does not verify email ownership or normalize case/whitespace. Google Forms email collection can help identify respondents, but the webhook itself does not verify that identity.
- **Development configuration:** `DEBUG` is enabled, the fallback secret is not suitable for production, and `runserver` is a development server. Use a production ASGI server, HTTPS/WSS, protected secrets, and `DEBUG=False` for deployment.
- **Channels scaling:** Channels uses Redis, configured by `REDIS_URL` or `REDIS_HOST` and `REDIS_PORT`. Use one shared Redis service for all web workers; Compose starts a local Redis service named `redis`.
- **Database persistence:** SQLite is suitable for this prototype. Choose a production database and persistent storage/backups before running a real vote.
- **Dashboard analytics:** Candidate totals are live counts, not time-series data. Time-range buttons and several trend/participation labels in the current page are presentation placeholders and do not calculate historical metrics.
- **Static and uploaded files:** Django's URL-based static/media serving is only enabled for development. Configure the deployment platform or object storage for collected static assets and durable uploaded media.
- **Browser WebSocket URL:** The dashboard chooses `ws://` locally and `wss://` for HTTPS deployments.
- **Apps Script deployment:** Apps Script must reach Django over the public internet. Do not expose a local-only server or place secrets in a publicly shared script; secure the endpoint before production use.

## License

No license is specified in this repository. Add a license file before granting reuse or distribution permissions.
