/**
 * Cron API — aligned with FlowApi.ts base URL convention.
 * API_BASE = window.FLASK_BACKEND_URL || ''
 * All paths start with /api/workflow/cron/...
 */

const API_BASE =
  (typeof window !== 'undefined' && (window as any).FLASK_BACKEND_URL) || '';

/**
 * Start a cron schedule on the server.
 */
export async function startCron(cronExpr: string, workflowId: string, nodeId: string) {
  const res = await fetch(`${API_BASE}/api/workflow/cron/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cronExpr, workflowId, nodeId }),
  });
  return res.json();
}

/**
 * List all running cron jobs.
 */
export async function listCrons() {
  const res = await fetch(`${API_BASE}/api/workflow/cron/list`);
  return res.json();
}

/**
 * Stop a running cron job.
 */
export async function stopCron(cronId: string) {
  const res = await fetch(`${API_BASE}/api/workflow/cron/${cronId}/stop`, { method: 'POST' });
  return res.json();
}
