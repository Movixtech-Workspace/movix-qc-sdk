/**
 * Movix QC API — Node.js Example
 *
 * Demonstrates the simplified /run/ workflow:
 *  1. Create a case
 *  2. Upload upper & lower STL files
 *  3. Call POST /run/ to validate and launch all analyses
 *  4. Poll tasks until all are done
 *  5. Generate summary and viewer link
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

// ---------------------------------------------------------------------------
// Configuration — replace with your credentials
// ---------------------------------------------------------------------------
const API_URL = "https://api-staging.movixtech.com";
const EMAIL = "";
const PASSWORD = "";

const POLL_INTERVAL_MS = 30_000; // 30 seconds

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const UPPER_STL = path.join(__dirname, "upper.stl");
const LOWER_STL = path.join(__dirname, "lower.stl");

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function api(method, endpoint, { body, token, headers: extra } = {}) {
  const url = `${API_URL}/api/v1${endpoint}`;
  const headers = { ...extra };

  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (body !== undefined && !(body instanceof Buffer)) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(body);
  }

  const res = await fetch(url, { method, headers, body });

  if (res.status === 204) return null;
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${method} ${endpoint} → ${res.status}: ${text}`);
  }
  return res.json();
}

async function login() {
  const data = await api("POST", "/auth/login/", {
    body: { email: EMAIL, password: PASSWORD },
  });
  return data.access;
}

// ---------------------------------------------------------------------------
// Workflow
// ---------------------------------------------------------------------------

async function main() {
  // Validate STL files exist
  for (const f of [UPPER_STL, LOWER_STL]) {
    if (!fs.existsSync(f)) {
      console.error(`STL file not found: ${f}`);
      console.error(
        "Place upper.stl and lower.stl in examples/nodejs/."
      );
      process.exit(1);
    }
  }

  // Authenticate
  console.log("Authenticating...");
  const token = await login();
  console.log("Authenticated.\n");

  // Step 1 — Create case
  console.log("1. Creating case...");
  const caseData = await api("POST", "/base/cases/", {
    token,
    body: { note: "Node.js example" },
  });
  const caseId = caseData.case_id;
  console.log(`   Case created: ${caseId}\n`);

  // Step 2 — Get presigned upload links and upload files
  console.log("2. Uploading STL files...");
  const links = await api("POST", `/base/cases/${caseId}/presigned-links/`, {
    token,
  });

  await Promise.all([
    uploadFile(links.upper_jaw.url, UPPER_STL),
    uploadFile(links.lower_jaw.url, LOWER_STL),
  ]);
  console.log("   Files uploaded.\n");

  // Step 3 — Run (validate + launch all analyses in one call)
  console.log("3. Running case (validate + launch analyses)...");
  const runResult = await api("POST", `/services/cases/${caseId}/run/`, {
    token,
    body: { visualization: true },
  });
  console.log(`   ${runResult.message}`);
  console.log(`   Tasks started: ${runResult.tasks.length}\n`);

  // Step 4 — Poll until all tasks are done
  // NOTE: Webhooks are the preferred mechanism for tracking task completion.
  //       Configure webhooks to receive `task_done` / `case_done` events
  //       and avoid the need for periodic polling entirely.
  console.log("4. Polling for task completion...");
  // The /run/ endpoint starts the pipeline and returns immediately.
  // All tasks (including Data Validation) complete asynchronously.
  // We poll the full task list to track progress.
  const completed = await pollAllTasks(token, caseId);

  for (const task of completed) {
    console.log(`   [${task.status}] ${task.service_name} (task ${task.id})`);
  }
  console.log();

  // Check if any task failed before proceeding
  const hasFailed = completed.some(
    (t) => t.status === "Failed" || t.status === "Error"
  );
  if (hasFailed) {
    console.error("Some tasks failed. Check the results above.");
    process.exit(1);
  }

  // Step 5 — Summary and viewer link
  console.log("5. Generating summary and viewer link...");
  const summary = await api("POST", `/services/cases/${caseId}/summary/`, {
    token,
    body: { code: "en" },
  });

  if (summary?.message) {
    console.log(`\n   Summary:\n   ${summary.message}\n`);
  }

  const viewer = await api("POST", "/viewer/links/", {
    token,
    body: { case_id: caseId },
  });

  if (viewer?.url) {
    console.log(`   Viewer: ${viewer.url}`);
    console.log(`   Expires: ${viewer.expires_at}\n`);
  } else {
    console.log(
      "   Viewer link not available (requires occlusion + holes tasks).\n"
    );
  }

  console.log("Done.");
}

// ---------------------------------------------------------------------------
// Upload helper
// ---------------------------------------------------------------------------

async function uploadFile(presignedUrl, filePath) {
  const fileBuffer = fs.readFileSync(filePath);
  const res = await fetch(presignedUrl, {
    method: "PUT",
    headers: { "Content-Type": "application/octet-stream" },
    body: fileBuffer,
  });
  if (!res.ok) {
    throw new Error(`Upload failed (${res.status}): ${filePath}`);
  }
}

// ---------------------------------------------------------------------------
// Polling helper
// ---------------------------------------------------------------------------

async function pollAllTasks(token, caseId) {
  const seen = new Set();

  // Poll until all tasks reach a terminal status, or any task fails.

  for (;;) {
    const { tasks } = await api(
      "GET",
      `/services/cases/${caseId}/tasks/`,
      { token }
    );

    for (const t of tasks) {
      if (isTerminal(t) && !seen.has(t.id)) {
        seen.add(t.id);
        console.log(`   Task ${t.id} → ${t.status} (${t.service_name})`);
      }
    }

    // Stop immediately if any task failed.
    const anyFailed = tasks.some(
      (t) => t.status === "Failed" || t.status === "Error"
    );
    if (anyFailed) {
      return tasks;
    }

    // Wait until analysis tasks appear (more than just Data Validation)
    // AND every task has reached a terminal status.
    const allTerminal = tasks.length >= 2 && tasks.every(isTerminal);
    if (allTerminal) {
      return tasks;
    }

    await sleep(POLL_INTERVAL_MS);
  }
}

function isTerminal(task) {
  return task.status === "Done" || task.status === "Failed" || task.status === "Error";
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ---------------------------------------------------------------------------

main().catch((err) => {
  console.error(`\nError: ${err.message}`);
  process.exit(1);
});
