# SDK Overview (Detailed)

This SDK provides a focused Python wrapper around the Movix QC API. The
sections below list the public surface, models, data formats, limits, and
all SDK-generated error messages.

## Client

`Client(...)` creates a client using username/password (default) or a custom
token provider.

**Properties**

- `config`: resolved configuration as a Config object.

**Methods**

- `health()`: returns True when an authenticated request succeeds.
- `close()`: closes HTTP resources (and token provider if applicable).

## Cases (`client.cases`)

**Methods**

`create(note=None, client=None)`  
Create a new case.

Arguments:
- `note`: optional string note for the case.
- `client`: optional string client identifier (external ID).

`get(case_id)`  
Fetch a case by ID (from the case list).

Arguments:
- `case_id`: required case UUID as a string.

`upload_files(case_id, paths, extension=None, timeout_s=None)`  
Validate two local files (upper/lower) and upload via presigned URLs.

Arguments:
- `case_id`: required case UUID as a string.
- `paths`: iterable with exactly two file paths. If names include "upper"/"lower",
  those are used; otherwise order is preserved.
- `extension`: optional `"stl"` or `"drc"`. Use to force the file type when
  filenames are ambiguous. Must match file extensions if provided. `"drc"` also
  signals the server to expect Draco input.
- `timeout_s`: optional per-request timeout (seconds) for upload calls.

`upload_urls(case_id, urls, extension=None, timeout_s=None)`  
Download two public URLs into a temporary directory, validate, then upload via
presigned URLs.

Arguments:
- `case_id`: required case UUID as a string.
- `urls`: iterable with exactly two public HTTP(S) URLs. Naming works the same
  as paths (upper/lower or order).
- `extension`: optional `"stl"` or `"drc"` with the same semantics as above.
- `timeout_s`: optional per-request timeout (seconds) for download and upload.

`submit(paths, metadata=None, extension=None)`  
Create a case, upload local files, and start the default validation task.

Arguments:
- `paths`: same as `upload_files`.
- `metadata`: optional dict with `note` and `client` keys.
- `extension`: same as `upload_files`.

`submit_urls(urls, metadata=None, extension=None)`
Create a case, upload from URLs, and start the default validation task.

Arguments:
- `urls`: same as `upload_urls`.
- `metadata`: optional dict with `note` and `client` keys.
- `extension`: same as `upload_urls`.

`generate_summary(case_id, language_code=None)`
Generate a result summary for a case after all validation tasks are complete.

Arguments:
- `case_id`: required case UUID as a string.
- `language_code`: optional language code (e.g., "en", "es", "de", "fr"). If not
  provided, uses the user's language or default language.

Returns `SummaryResult` with a `message` field (str if issues found, None otherwise).

Typical usage: call after Data Validation, Occlusion, and Holes tasks complete to get
a narrative summary ready to share with stakeholders.

`generate_viewer_link(case_id)`
Generate a secure viewer link for a case to share visualization results.

Arguments:
- `case_id`: required case UUID as a string.

Returns `ViewerLink` with `url`, `public_id`, and `expires_at` fields.

Raises `TasksNotCompletedError` if required tasks (Occlusal Evaluation and IQC Holes
Detection) are not complete. The endpoint is idempotent—if a valid link exists, it
returns that link (200 OK); creating a new link returns 201 Created. Links expire
after 24 hours by default.

## Tasks (`client.tasks`)

**Methods**

`get(task_id, case_id)`  
Fetch a task by ID for a case.

Arguments:
- `task_id`: task integer ID.
- `case_id`: required case UUID as a string.

`list(case_id, status=None)`  
List tasks for a case, optionally filtered by normalized status.

Arguments:
- `case_id`: required case UUID as a string.
- `status`: optional `TaskStatus` or string value (`queued`, `running`,
  `succeeded`, `failed`).

`wait(task_id, case_id, timeout_s=600, poll_interval_s=5)`  
Poll a task until it completes or times out.

Arguments:
- `task_id`: task integer ID.
- `case_id`: required case UUID as a string.
- `timeout_s`: overall wait deadline in seconds.
- `poll_interval_s`: delay between polls in seconds; default 5s balances load
  and responsiveness.

## Models and Public Fields

### Case

- `case_id`: str (UUID string from the API)
- `created_at`: datetime | None (parsed from ISO 8601 string)
- `updated_at`: datetime | None (parsed from ISO 8601 string)
- `note`: str | None
- `client`: str | None

### Task

- `task_id`: int (API task identifier)
- `title`: str | None
- `description`: str | None
- `service_name`: str | None
- `status`: TaskStatus | None
- `started`: datetime | None (parsed from ISO 8601 string)
- `completed`: datetime | None (parsed from ISO 8601 string)
- `created`: datetime | None (parsed from ISO 8601 string)
- `result`: Any | None (JSON payload from the API, see format below)

### UploadResult

- `case_id`: str
- `upper_file_id`: str
- `lower_file_id`: str

### SummaryResult

- `message`: str | None (summary text if issues found, None otherwise)

### ViewerLink

- `url`: str (full viewer URL with embedded access token)
- `public_id`: str (UUID identifying this link)
- `expires_at`: datetime (link expiration timestamp)

### TaskStatus (normalized)

- `queued`
- `running`
- `succeeded`
- `failed`

Status mapping from API strings (case-insensitive):

- Created -> queued
- Run -> running
- Done -> succeeded
- Failed -> failed
- Error -> failed

## Data Formats

- Datetime fields: ISO 8601 strings from the API are exposed as datetime
  objects.
- Task.status: normalized to the TaskStatus enum above.
- Task.result: arbitrary JSON (dict/list/primitive) passed through from the API.

## Limits

- URL downloads are capped at 256 MB per file (`MAX_URL_DOWNLOAD_BYTES`) to
  prevent untrusted links from exhausting disk space.

## Runtime and temp files

- Supported OS: Linux, macOS, Windows (Python 3.11+).
- URL downloads use `tempfile.TemporaryDirectory()`. The OS chooses the temp
  location (Linux: `/tmp`, macOS: `/var/folders/...`, Windows: `%TEMP%`) and the
  directory is removed automatically after each call.

## Errors (Messages Raised by the SDK)

### ValidationError

- api_url is required.
- api_url must be a valid http(s) URL.
- Timeout must be a number of seconds.
- Timeout must be greater than zero.
- Retries must be an integer.
- Retries must be zero or greater.
- username and password are required.
- note must be a string.
- client must be a string.
- Presigned link response is missing file data.
- Presigned link response is invalid.
- Presigned URL domain not allowed: {domain}. Expected domain ending with one of: {allowed_suffixes}
- Exactly two file paths are required.
- Exactly two file URLs are required.
- Upload files must exist on disk.
- File URLs must be valid http(s) URLs.
- File extension does not match expected format.
- File is empty.
- Files are identical.
- File does not have .stl extension.
- Invalid STL format.
- STL validation requires numpy and trimesh to be installed.
- File does not have .drc extension.
- Invalid DRC format.
- DRC validation requires DracoPy to be installed.
- DRC validation requires numpy to be installed.
- extension must be 'stl' or 'drc'.
- Both files must share the same extension.
- Unsupported file extension.
- File download failed.
- File exceeds maximum size limit.
- File upload failed.
- case_id is required to fetch a task.
- Unexpected response when fetching task.
- Unexpected response when listing tasks.
- Unknown task status filter.
- timeout_s must be greater than zero.
- poll_interval_s must be greater than zero.
- language_code must be a string.
- Unexpected response when generating summary.
- Unexpected response when generating viewer link.

### AuthenticationError

- Login failed.
- Login did not return an access token.
- Token refresh failed.
- Refresh did not return an access token.

### ApiError

- Unexpected response from authentication endpoint.
- Unexpected response from API.
- Request failed due to a network error.
- Request failed with no response.
- Request failed with status {status_code}.
- If the API returns a JSON payload with an "error" or "message" field, that
  value is used as the error text.

### MovixQCError

- Timed out waiting for task completion.

### TasksNotCompletedError

- Required tasks (Occlusal Evaluation and IQC Holes Detection) are not complete.

### AuthorizationError, NotFoundError, RateLimitError

- These use the same safe message logic as ApiError (see above).

## Configuration (Environment Variables)

`MOVIX_QC_API_URL` (required)  
Base API URL. Use one of:
- Staging (integration/testing): `https://api-staging.movixtech.com`
- Production: `https://api.movixtech.com`

`MOVIX_QC_USERNAME` (required for password auth)  
Login username, typically an email.

`MOVIX_QC_PASSWORD` (required for password auth)  
Login password.

`MOVIX_QC_TIMEOUT` (optional, default: 45)  
Per-request timeout in seconds. Recommended range: 30-90 depending on network
conditions and file sizes.

`MOVIX_QC_RETRIES` (optional, default: 10)  
Retry count for transient errors (network errors, 429, 5xx). Recommended range:
5-10 for production integrations.

`MOVIX_QC_USER_AGENT` (optional, default: `movix-qc-sdk/0.1.0`)  
Custom user agent for traceability. Recommended format:
`Company/AppVersion (+contact)`.
