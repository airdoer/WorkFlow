import { message } from 'antd';

const API_BASE = (window as any).FLASK_BACKEND_URL || '/api';

/**
 * Start a cron schedule on the server.
 */
export async function startCron(cronExpr: string, workflowId: string, nodeId: string) {
  const res = await fetch(`${API_BASE}/workflow/cron/start`, {
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
  const res = await fetch(`${API_BASE}/workflow/cron/list`);
  return res.json();
}

/**
 * Stop a running cron job.
 */
export async function stopCron(cronId: string) {
  const res = await fetch(`${API_BASE}/workflow/cron/${cronId}/stop`, { method: 'POST' });
  return res.json();
}
