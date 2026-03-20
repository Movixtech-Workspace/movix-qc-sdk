# Movix QC API — Node.js Example

This example demonstrates the simplified `/run/` workflow using plain Node.js (no external dependencies).

## What It Does

1. Creates a case
2. Uploads upper and lower STL files via presigned links
3. Calls `POST /run/` — validates files and launches all analyses in one request
4. Polls task status until all tasks complete
5. Generates a summary and viewer link

## Prerequisites

- Node.js 18+ (uses built-in `fetch`)
- Movix QC API credentials
- Upper and lower STL files

## Setup

### 1. Configure Credentials

Edit `index.mjs` and replace the placeholder values:

```javascript
const API_URL = "https://api-staging.movixtech.com";
const EMAIL = "";
const PASSWORD = "";
```

### 2. Add STL Files

Place your test files in this directory:
- `upper.stl` — Upper jaw
- `lower.stl` — Lower jaw

## Running

```bash
npm start
```

## Production Notes

- **Webhooks**: The example uses polling for simplicity. In production, use webhooks for task completion notifications. See the [webhooks documentation](https://docs.movixtech.com) for setup.
- **Token refresh**: The example obtains a single access token. For long-running processes, implement token refresh using the `refresh` token from the login response.
