# SDK Overview (Detailed)

This SDK provides a focused Python wrapper around the Movix QC API. The
sections below list the public surface, models, data formats, limits, and
all SDK-generated error messages.

## Client

`Client(...)` creates a client using username/password (default) or a custom
token provider.

**Constructor Arguments** (all optional, fallback to environment variables):
- `api_url`: Base API URL (required via arg or env)
- `username`: Email address for authentication (required for password auth)
- `password`: Login password (required for password auth)
- `timeout`: Per-request timeout in seconds (default: 45)
- `retries`: Retry count for transient errors (default: 10)
- `user_agent`: Custom user agent string (default: `movix-qc-sdk/0.2.0`)
- `occlusion_threshold_mm`: Default occlusion threshold in mm (default: 0.0)
- `holes_threshold_area_mm`: Default holes threshold in mm² (default: 0.0)
- `token_provider`: Custom token provider (advanced usage)

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

`wait_for_completion(case_id, task_id, timeout_s=600, poll_interval_s=5)`
Alias for `wait()` method. Poll a task until it completes or times out.

Arguments:
- `case_id`: required case UUID as a string.
- `task_id`: task integer ID.
- `timeout_s`: overall wait deadline in seconds.
- `poll_interval_s`: delay between polls in seconds; default 5s balances load
  and responsiveness.

`create_data_validation(case_id)`
Create a data validation task (synchronous - completes immediately).

Arguments:
- `case_id`: required case UUID as a string.

Returns a `Task` object with `task_id`, `status`, and `result` fields.

`create_occlusion(case_id, threshold_mm=None, visualization=True, generate_drc=False)`
Create an occlusal evaluation task (asynchronous).

Arguments:
- `case_id`: required case UUID as a string.
- `threshold_mm`: occlusion threshold in millimeters (defaults to config value: 0.0mm).
  Set higher to ignore minor occlusions. Method parameter overrides Client initialization
  value, which overrides environment variable.
- `visualization`: generate visualization assets (default: True). Set to False to skip
  heatmap images and contact meshes.
- `generate_drc`: generate DRC files alongside meshes (default: False). Only applies
  when `visualization=True`.

Returns a `Task` object. Use `wait_for_completion()` to poll until done.

`create_holes(case_id, threshold_area_mm=None, visualization=True, generate_drc=False)`
Create a holes detection task (asynchronous).

Arguments:
- `case_id`: required case UUID as a string.
- `threshold_area_mm`: minimum hole area in mm² (defaults to config value: 0.0mm²).
  Set higher to filter out smaller holes. Method parameter overrides Client initialization
  value, which overrides environment variable.
- `visualization`: generate visualization assets (default: True). Set to False to skip
  annotated screenshots and colored meshes.
- `generate_drc`: generate DRC files alongside meshes (default: False). Only applies
  when `visualization=True`.

Returns a `Task` object. Use `wait_for_completion()` to poll until done.

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

## Task Result Interpretation

After a task completes (`status == TaskStatus.SUCCEEDED`), the `result` field contains
service-specific output. This section explains how to interpret each service's results.

### Data Validation Results

Data Validation runs synchronously and returns immediately. The result contains:

```python
{
    "validations": {
        "upper_not_empty": {"valid": bool, "message": str},
        "lower_not_empty": {"valid": bool, "message": str},
        "files_not_equal": {"valid": bool, "message": str},
        "upper_stl_format": {"valid": bool, "message": str},
        "lower_stl_format": {"valid": bool, "message": str}
    },
    "overall_valid": bool,
    "errors": []
}
```

**Interpretation**:
- Check `overall_valid` first - if `False`, examine individual validations
- Each validation has a `valid` boolean and descriptive `message`
- `upper_not_empty`/`lower_not_empty`: Files must not be empty (>0 bytes)
- `files_not_equal`: Upper and lower files must be different (different hashes)
- `upper_stl_format`/`lower_stl_format`: Files must be valid STL/DRC format
- `errors` array contains unexpected issues that prevented validation

**Common Issues**:
- Identical files (same hash) → `files_not_equal.valid = False`
- Empty files → `upper_not_empty.valid = False` or `lower_not_empty.valid = False`
- Corrupt STL → `upper_stl_format.valid = False` or `lower_stl_format.valid = False`

### Occlusal Evaluation Results

Occlusal evaluation runs asynchronously. The result contains:

```python
{
    "status": "success",
    "min_gap": float,           # millimeters
    "overlap": float,           # millimeters
    "penetration": float,       # millimeters
    "hyperocclusion": bool,
    "threshold_mm": float       # threshold used
}
```

**Interpretation**:
- `hyperocclusion`: Boolean flag - `True` when `penetration > threshold_mm`
- `penetration`: Maximum penetration depth in mm (when arches overlap)
- `min_gap`: Minimum distance between arches in mm (when no overlap)
- `overlap`: Surface area of overlap in mm²
- `threshold_mm`: The threshold value that was used (echoed from request)

**Understanding the Results**:

When `hyperocclusion = True`:
- Arches are penetrating each other
- `penetration` shows the maximum depth of penetration
- Higher values indicate more severe occlusion issues
- Example: `penetration = 0.466mm` means arches overlap by 0.466mm at deepest point

When `hyperocclusion = False`:
- No problematic occlusion detected
- `min_gap` shows the smallest clearance between arches
- Example: `min_gap = 0.118mm` means arches are 0.118mm apart at closest point

**Typical Thresholds**:
- `0.0mm`: Detect any penetration (most sensitive)
- `0.1-0.2mm`: Moderate sensitivity (common for production)
- `0.3mm+`: Less sensitive (allows minor overlaps)

### Holes Detection Results

Holes detection runs asynchronously. The result contains:

```python
{
    "status": "success",
    "lower_arch_holes_count": int,
    "upper_arch_holes_count": int
}
```

**Interpretation**:
- Counts only include holes with area >= `threshold_area_mm`
- Zero counts indicate no holes detected above threshold
- Non-zero counts indicate quality issues requiring attention

**Understanding Hole Counts**:
- Each count represents discrete holes in the mesh
- Holes indicate incomplete scan data or mesh defects
- Higher counts suggest more extensive scanning issues
- Visualization assets show exact locations and sizes

**Typical Thresholds**:
- `0.0mm²`: Include all detected holes (most comprehensive)
- `5-10mm²`: Filter out very small holes (noise reduction)
- `20mm²+`: Only significant holes (less sensitive)

**Example Workflows**:

```python
# Data Validation
validation = client.tasks.create_data_validation(case_id)
if not validation.result.get("overall_valid"):
    print("Validation failed:", validation.result["validations"])

# Occlusion Analysis
occlusion = client.tasks.create_occlusion(case_id, threshold_mm=0.2)
result = client.tasks.wait_for_completion(case_id, occlusion.task_id)
if result.result["hyperocclusion"]:
    print(f"Hyperocclusion detected: {result.result['penetration']}mm penetration")
else:
    print(f"No hyperocclusion. Min gap: {result.result['min_gap']}mm")

# Holes Detection
holes = client.tasks.create_holes(case_id, threshold_area_mm=10.0)
result = client.tasks.wait_for_completion(case_id, holes.task_id)
total_holes = result.result["upper_arch_holes_count"] + result.result["lower_arch_holes_count"]
if total_holes > 0:
    print(f"Found {total_holes} holes (>10mm² each)")
```

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
- Occlusion threshold must be a number.
- Occlusion threshold must be zero or greater.
- Holes threshold must be a number.
- Holes threshold must be zero or greater.
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
- Unexpected response when creating data validation task.
- Unexpected response when creating occlusion task.
- Unexpected response when creating holes task.

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
Email address for authentication.

`MOVIX_QC_PASSWORD` (required for password auth)  
Login password.

`MOVIX_QC_TIMEOUT` (optional, default: 45)  
Per-request timeout in seconds. Recommended range: 30-90 depending on network
conditions and file sizes.

`MOVIX_QC_RETRIES` (optional, default: 10)  
Retry count for transient errors (network errors, 429, 5xx). Recommended range:
5-10 for production integrations.

`MOVIX_QC_USER_AGENT` (optional, default: `movix-qc-sdk/0.2.0`)
Custom user agent for traceability. Recommended format:
`Company/AppVersion (+contact)`.

`MOVIX_QC_OCCLUSION_THRESHOLD_MM` (optional, default: 0.0)
Occlusion threshold in millimeters. The `hyperocclusion` boolean flag in task results
becomes `true` when measured penetration exceeds this threshold. Set to `0.0` to detect
all occlusions. Can be overridden via Client initialization or method parameters.

`MOVIX_QC_HOLES_THRESHOLD_AREA_MM` (optional, default: 0.0)
Holes threshold in mm². Filters visualization and counts to only include holes with
area >= threshold. Set to `0.0` to include all detected holes. Can be overridden via
Client initialization or method parameters.

**Threshold Precedence** (highest to lowest):
1. Method parameter: `create_occlusion(case_id, threshold_mm=0.3)`
2. Client initialization: `Client(..., occlusion_threshold_mm=0.2)`
3. Environment variable: `MOVIX_QC_OCCLUSION_THRESHOLD_MM=0.2`
