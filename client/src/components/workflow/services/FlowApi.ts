/**
 * API 基础路径策略：
 * - 开发模式：走 UMI 代理（proxy.ts 配置 /api/workflow/ → localhost:16666），API_BASE 为空
 * - 生产模式（Docker）：通过 deploy/dist/env-config.js 注入 window.FLASK_BACKEND_URL
 *
 * 注意：process.env.FLASK_BACKEND_URL 在 UMI 中不会被注入，
 * 除非在 config.ts 的 define 中显式声明，否则运行时始终为 undefined。
 */
const API_BASE =
  (typeof window !== 'undefined' && (window as any).FLASK_BACKEND_URL) || '';

async function handleResponse<T = any>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`请求失败 (${res.status}): ${text.slice(0, 200)}`);
  }
  const contentType = res.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) {
    const text = await res.text();
    throw new Error(
      `后端返回非 JSON 响应 (content-type: ${contentType})，请确认后端服务是否正常运行。响应前 200 字符: ${text.slice(0, 200)}`,
    );
  }
  return res.json();
}

export const FlowApi = {
  async save(name: string, json: any, id?: string, meta?: { author?: string; description?: string }) {
    const res = await fetch(`${API_BASE}/api/workflow/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, json, id, author: meta?.author || '', description: meta?.description || '' }),
    });
    return handleResponse(res);
  },

  async get(id: string) {
    const res = await fetch(`${API_BASE}/api/workflow/${id}`);
    return handleResponse(res);
  },

  async list() {
    const res = await fetch(`${API_BASE}/api/workflow/list`);
    return handleResponse(res);
  },

  async delete(id: string) {
    const res = await fetch(`${API_BASE}/api/workflow/${id}`, { method: 'DELETE' });
    return handleResponse(res);
  },

  async runNode(type: string, config: any, input: any) {
    const res = await fetch(`${API_BASE}/api/workflow/node/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, config, input }),
    });
    return handleResponse(res);
  },

  async runWorkflow(workflowId: string) {
    const res = await fetch(`${API_BASE}/api/workflow/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workflowId }),
    });
    return handleResponse(res);
  },
};
