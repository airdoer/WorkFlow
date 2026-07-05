const API_BASE = process.env.FLASK_BACKEND_URL || '';

export const FlowApi = {
  async save(name: string, json: any, id?: string) {
    const res = await fetch(`${API_BASE}/api/workflow/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, json, id }),
    });
    return res.json();
  },

  async get(id: string) {
    const res = await fetch(`${API_BASE}/api/workflow/${id}`);
    return res.json();
  },

  async list() {
    const res = await fetch(`${API_BASE}/api/workflow/list`);
    return res.json();
  },

  async delete(id: string) {
    const res = await fetch(`${API_BASE}/api/workflow/${id}`, { method: 'DELETE' });
    return res.json();
  },

  async runNode(type: string, config: any, input: any) {
    const res = await fetch(`${API_BASE}/api/workflow/node/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, config, input }),
    });
    return res.json();
  },

  async runWorkflow(workflowId: string) {
    const res = await fetch(`${API_BASE}/api/workflow/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workflowId }),
    });
    return res.json();
  },
};
