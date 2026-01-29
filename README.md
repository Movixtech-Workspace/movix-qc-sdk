# movix-qc-sdk

Production-ready Python SDK for the Movix QC API. It keeps the surface small,
handles authentication safely, and focuses on the core QC workflow.

For a full API surface description, see `overview.md`.

## Requirements

- Python 3.11+
- Validation requires `numpy`, `trimesh`, and `DracoPy` (installed automatically).

## Base URLs

The API is available in two environments. Use staging during integration and
testing, and switch to production for go-live.

- Staging: `https://api-staging.movixtech.com`
- Production: `https://api.movixtech.com`

## Installation

```bash
python -m pip install -e .
```

## Quick start

You can initialize the client in two ways.

Environment variables + `Client()`:

```bash
export MOVIX_QC_API_URL="https://api-staging.movixtech.com"
export MOVIX_QC_USERNAME="user@example.com"
export MOVIX_QC_PASSWORD="..."
```

Explicit arguments:

```python
from movix_qc_sdk import Client

client = Client(
    api_url="https://api-staging.movixtech.com",
    username="user@example.com",
    password="...",
    timeout=45,
    retries=10,
    user_agent="Movix/1.2 (+example@movixtech.com)",
)
```

If you use `Client()` or `with Client() as client:` without arguments, make
sure the environment variables are set first.

Full example (submit, then poll for completion). `submit()` creates the default
validation task for the case:

```python
from movix_qc_sdk import Client

with Client() as client:
    case = client.cases.submit(
        paths=["/path/to/upper.stl", "/path/to/lower.stl"],
        metadata={"note": "Demo", "client": "ACME-001"},
    )

    tasks = client.tasks.list(case_id=case.case_id)
    if tasks:
        task = client.tasks.wait(task_id=tasks[0].task_id, case_id=case.case_id)
        print(task.status)
```

Upload from public URLs (two files):

```python
from movix_qc_sdk import Client

with Client() as client:
    case = client.cases.submit_urls(
        urls=[
            "https://files.example.com/upper.stl",
            "https://files.example.com/lower.stl",
        ],
        metadata={"note": "Demo", "client": "ACME-001"},
    )
```

### Generate result summary

After all validation tasks complete, generate a narrative summary ready to share with stakeholders:

```python
from movix_qc_sdk import Client, TasksNotCompletedError

with Client() as client:
    # Wait for tasks to complete first
    tasks = client.tasks.list(case_id=case.case_id)
    for task in tasks:
        client.tasks.wait(task_id=task.task_id, case_id=case.case_id)

    # Generate summary (uses user's language by default)
    summary = client.cases.generate_summary(case_id=case.case_id)
    if summary.message:
        print("Issues found:")
        print(summary.message)
    else:
        print("No issues detected")

    # Or generate summary in a specific language
    summary_es = client.cases.generate_summary(
        case_id=case.case_id,
        language_code="es"
    )
```

### Generate viewer link

After Occlusal Evaluation and IQC Holes Detection tasks complete, generate a secure link to share visualization results:

```python
from movix_qc_sdk import Client, TasksNotCompletedError

with Client() as client:
    try:
        link = client.cases.generate_viewer_link(case_id=case.case_id)
        print(f"Viewer URL: {link.url}")
        print(f"Expires at: {link.expires_at}")

        # Share link.url with stakeholders
        # The link is valid for 24 hours by default
    except TasksNotCompletedError:
        print("Required tasks (Occlusal Evaluation and IQC Holes Detection) not complete yet")
```

The viewer link endpoint is idempotent—if a valid link already exists, it returns that link. Only one link per case can be active at a time.

## Configuration

All settings can be passed to `Client(...)` or set via environment variables.

### Environment variables

| Variable | Client arg | Required | Default | Description | Example |
| --- | --- | --- | --- | --- | --- |
| `MOVIX_QC_API_URL` | `api_url` | Yes | None | Base URL of the Movix QC API. Use `https://api-staging.movixtech.com` for staging or `https://api.movixtech.com` for production. The SDK strips a trailing slash. | `https://api-staging.movixtech.com` |
| `MOVIX_QC_USERNAME` | `username` | Yes | None | Email address for password-based authentication. | `user@example.com` |
| `MOVIX_QC_PASSWORD` | `password` | Yes | None | Login password for password-based auth. | `s3cr3t` |
| `MOVIX_QC_TIMEOUT` | `timeout` | No | `45` | Per-request timeout in seconds. Must be greater than zero. | `30` |
| `MOVIX_QC_RETRIES` | `retries` | No | `10` | Number of retries for transient errors (network errors, 429, 5xx). Must be zero or greater. | `2` |
| `MOVIX_QC_USER_AGENT` | `user_agent` | No | `movix-qc-sdk/0.2.0` | Custom user-agent string. Recommended format: `<Company>/<AppVersion> (+contact)` for traceability. | `Movix/1.2 (+example@movixtech.com)` |
| `MOVIX_QC_OCCLUSION_THRESHOLD_MM` | `occlusion_threshold_mm` | No | `0.0` | Occlusion threshold in millimeters. Set based on quality requirements. | `0.2` |
| `MOVIX_QC_HOLES_THRESHOLD_AREA_MM` | `holes_threshold_area_mm` | No | `0.0` | Holes threshold in mm². Set based on quality requirements. | `10.0` |

## Complete Examples

See the `examples/` directory for a full workflow demonstration:

- **[examples/main.py](examples/main.py)** - Complete QC workflow showing:
  - Case creation with STL file upload
  - Data validation (synchronous)
  - Parallel occlusion and holes detection (asynchronous)
  - Summary and viewer link generation
  - Proper error handling and result interpretation

- **[examples/README.md](examples/README.md)** - Setup instructions and configuration guide

The example demonstrates enterprise-ready code with proper threshold configuration,
error handling, and result interpretation.

## Authentication

The SDK authenticates using email and password (passed as `username` and `password` parameters) and refreshes tokens automatically. The `username` parameter accepts your email address.

## Error handling

Exceptions raised by the SDK:

- `ValidationError` for invalid input or unexpected payload shapes
- `AuthenticationError`, `AuthorizationError`, `NotFoundError`, `RateLimitError`
- `TasksNotCompletedError` when required tasks are not complete for an operation
- `ApiError` for other HTTP failures (includes `status_code` when available)
- `MovixQCError` as the base class

## Security notes

- The SDK never logs tokens or passwords.
- Authorization headers and cookies are redacted if logging is enabled.
- Tokens are stored in memory by default and refreshed automatically.
- **Credentials (username, password) and tokens are stored in plaintext in memory during the session. In high-security environments, ensure proper process isolation and avoid core dumps.**
- URL uploads are capped at 256 MB per file; clients must validate/approve URLs.
- Presigned URLs are validated against an allowed list of storage domains to prevent unauthorized upload destinations.

### SSRF Protection

When using `submit_urls()` or `upload_urls()` on a server that accepts URLs from untrusted users, you are responsible for validating those URLs to prevent SSRF (Server-Side Request Forgery) attacks.

**Example of safe usage:**

```python
from urllib.parse import urlparse

ALLOWED_DOMAINS = {"your-storage.com", "trusted-cdn.com"}

def validate_user_urls(urls: list[str]) -> None:
    """Validate URLs from untrusted users before passing to SDK."""
    for url in urls:
        parsed = urlparse(url)
        if parsed.netloc not in ALLOWED_DOMAINS:
            raise ValueError(f"Domain not allowed: {parsed.netloc}")

# In your API endpoint:
@app.post("/upload")
def upload(urls: list[str]):
    validate_user_urls(urls)  # Validate BEFORE passing to SDK
    client.cases.submit_urls(urls=urls)
```

**Risk:** If you pass untrusted URLs directly to the SDK without validation, attackers may access your internal services (localhost, private networks, cloud metadata endpoints).

## Async task results

Tasks are typically polled until they complete. The SDK provides a `wait()`
helper to do this safely. Confirm with the Movix team before choosing the
long-term approach. Options to consider:

- Polling (simple, current default)
- Webhooks/callbacks (preferred if available)
- Long-polling or server-sent events (only if supported)
