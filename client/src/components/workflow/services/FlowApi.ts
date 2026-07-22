/**
 * API 基础路径策略：
 * - 开发模式：走 UMI 代理（proxy.ts 配置 /api/workflow/ 和 /socket.io/ → localhost:16666），API_BASE 为空
 * - 生产模式（Docker）：通过 deploy/dist/env-config.js 注入 window.FLASK_BACKEND_URL
 */
import { io, Socket } from 'socket.io-client';

const API_BASE =
  (typeof window !== 'undefined' && (window as any).FLASK_BACKEND_URL) || '';

// ── Socket.IO Singleton ───────────────────────────────────────────────────────
let _socket: Socket | null = null;

function getSocket(): Socket {
  // If socket exists (connected or reconnecting), reuse it.
  // Socket.IO with reconnection:true will auto-reconnect when disconnected.
  if (_socket) return _socket;

  // In dev mode, connect to same origin (proxied via UMI /socket.io/),
  // In Docker / prod, connect to explicit FLASK_BACKEND_URL
  const socketUrl = API_BASE || window.location.origin;
  const token = localStorage.getItem('access-token') || '';
  _socket = io(socketUrl, {
    transports: ['websocket', 'polling'],
    path: '/socket.io/',
    reconnection: true,
    reconnectionAttempts: Infinity,  // Keep trying to reconnect indefinitely
    reconnectionDelay: 500,          // Faster initial reconnection (default 1000)
    reconnectionDelayMax: 5000,      // Max delay between reconnection attempts
    timeout: 10000,                  // Connection timeout
    extraHeaders: {
      'Access-Token': token,
    },
  });

  _socket.on('connect', () => {
    console.log('[FlowApi] Socket.IO connected, sid:', _socket?.id);
  });
  _socket.on('disconnect', (reason) => {
    console.log('[FlowApi] Socket.IO disconnected:', reason);
  });
  _socket.on('connect_error', (err) => {
    console.error('[FlowApi] Socket.IO connection error:', err.message);
  });

  return _socket;
}

/**
 * Emit a Socket.IO event, waiting for the connection to be ready first.
 * If already connected, emits immediately. If reconnecting, waits up to
 * `timeoutMs` for the connection to be established before emitting.
 * Returns a boolean indicating whether the emit was sent while connected.
 */
function emitWhenReady(event: string, data: any, timeoutMs = 5000): Promise<boolean> {
  const socket = getSocket();
  if (socket.connected) {
    socket.emit(event, data);
    return Promise.resolve(true);
  }
  return new Promise((resolve) => {
    const timer = setTimeout(() => {
      // Timeout — emit anyway (Socket.IO will queue it internally)
      socket.emit(event, data);
      cleanup();
      resolve(false);
    }, timeoutMs);

    const onConnect = () => {
      clearTimeout(timer);
      socket.emit(event, data);
      cleanup();
      resolve(true);
    };

    function cleanup() {
      socket.off('connect', onConnect);
    }

    socket.on('connect', onConnect);
  });
}

// ── HTTP helpers ──────────────────────────────────────────────────────────────
async function handleResponse<T = any>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`请求失败 (${res.status}): ${text.slice(0, 200)}`);
  }
  const contentType = res.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) {
    const text = await res.text();
    throw new Error(
      `后端返回非 JSON 响应 (content-type: ${contentType})。响应: ${text.slice(0, 200)}`,
    );
  }
  return res.json();
}

// ── Public API ────────────────────────────────────────────────────────────────
export const FlowApi = {
  // CRUD
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

  async list(author?: string) {
    const params = new URLSearchParams();
    if (author) params.set('author', author);
    const qs = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${API_BASE}/api/workflow/list${qs}`);
    return handleResponse(res);
  },

  async delete(id: string) {
    const res = await fetch(`${API_BASE}/api/workflow/${id}`, { method: 'DELETE' });
    return handleResponse(res);
  },

  // Duplicate workflow
  async duplicateWorkflow(sourceId: string, newName: string) {
    const res = await fetch(`${API_BASE}/api/workflow/${sourceId}/duplicate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: newName }),
    });
    return handleResponse(res);
  },

  // Check if a name is already taken (server-side authoritative check)
  async checkName(name: string, excludeId?: string): Promise<boolean> {
    const params = new URLSearchParams({ name });
    if (excludeId) params.set('exclude', excludeId);
    const res = await fetch(`${API_BASE}/api/workflow/check_name?${params}`);
    const data = await handleResponse<{ exists: boolean }>(res);
    return data.exists;
  },

  // Trash operations
  async listTrash(): Promise<any[]> {
    const res = await fetch(`${API_BASE}/api/workflow/trash/list`);
    const data = await handleResponse<{ list: any[] }>(res);
    return data.list || [];
  },

  async restoreFromTrash(id: string) {
    const res = await fetch(`${API_BASE}/api/workflow/trash/${id}/restore`, { method: 'POST' });
    return handleResponse(res);
  },

  async purgeFromTrash(id: string) {
    const res = await fetch(`${API_BASE}/api/workflow/trash/${id}/purge`, { method: 'DELETE' });
    return handleResponse(res);
  },

  // C7 server list for dropdown
  async getC7ServerOptions(): Promise<{ label: string; value: string; type: string; namespace?: string; server_id?: number | string }[]> {
    const res = await fetch(`${API_BASE}/api/workflow/c7server/list`);
    const data = await handleResponse<{ options: { label: string; value: string; type: string; namespace?: string; server_id?: number | string }[] }>(res);
    return data.options || [];
  },

  // ExcelSearch file list for dropdown
  async getExcelSearchOptions(): Promise<{ label: string; value: string; localPath: string; p4Path: string; description: string }[]> {
    const res = await fetch(`${API_BASE}/api/workflow/excelsearch/list`);
    const data = await handleResponse<{ options: { label: string; value: string; localPath: string; p4Path: string; description: string }[] }>(res);
    return data.options || [];
  },

  // Seal operation list for dropdown
  async getSealOperationOptions(): Promise<{ label: string; value: string; template_id?: number; description: string; args_def: any[] }[]> {
    const res = await fetch(`${API_BASE}/api/workflow/seal/list`);
    const data = await handleResponse<{ options: { label: string; value: string; template_id?: number; description: string; args_def: any[] }[] }>(res);
    return data.options || [];
  },

  // Single-node run (REST, for node-level ▶ button)
  async runNode(type: string, config: any, input: any) {
    const res = await fetch(`${API_BASE}/api/workflow/node/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, config, input }),
    });
    return handleResponse(res);
  },

  // REST fallback: query task status
  async getTaskStatus(taskId: string) {
    const res = await fetch(`${API_BASE}/api/workflow/run/${taskId}/status`);
    return handleResponse(res);
  },

  // ── Execution History ──────────────────────────────────────────────────────

  async getHistory(workflowId: string) {
    const res = await fetch(`${API_BASE}/api/workflow/${workflowId}/history`);
    return handleResponse(res);
  },

  async getRecentHistory(author?: string, limit = 50) {
    const params = new URLSearchParams();
    if (author) params.set('author', author);
    params.set('limit', String(limit));
    const res = await fetch(`${API_BASE}/api/workflow/history/recent?${params}`);
    return handleResponse(res);
  },

  // ── Permission ──────────────────────────────────────────────────────────────

  async getPermissionGroups() {
    const token = localStorage.getItem('access-token') || '';
    const res = await fetch(`${API_BASE}/api/permission/groups`, {
      headers: { 'Access-Token': token },
    });
    return handleResponse(res);
  },

  async savePermissionGroup(group: any, action: 'save' | 'delete' = 'save') {
    const token = localStorage.getItem('access-token') || '';
    const res = await fetch(`${API_BASE}/api/permission/group/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Access-Token': token },
      body: JSON.stringify({ group, action }),
    });
    return handleResponse(res);
  },

  async getPermissionNodes() {
    const token = localStorage.getItem('access-token') || '';
    const res = await fetch(`${API_BASE}/api/permission/nodes`, {
      headers: { 'Access-Token': token },
    });
    return handleResponse(res);
  },

  async getPendingUsers() {
    const token = localStorage.getItem('access-token') || '';
    const res = await fetch(`${API_BASE}/api/permission/pending/list`, {
      headers: { 'Access-Token': token },
    });
    return handleResponse(res);
  },

  async assignPendingUser(username: string, groupIds: string[]) {
    const token = localStorage.getItem('access-token') || '';
    const res = await fetch(`${API_BASE}/api/permission/pending/assign`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Access-Token': token },
      body: JSON.stringify({ username, groupIds }),
    });
    return handleResponse(res);
  },

  async deletePendingUser(username: string) {
    const token = localStorage.getItem('access-token') || '';
    const res = await fetch(`${API_BASE}/api/permission/pending/${username}`, {
      method: 'DELETE',
      headers: { 'Access-Token': token },
    });
    return handleResponse(res);
  },

  // ── Admin Management ────────────────────────────────────────────────────────

  async getAdmins() {
    const token = localStorage.getItem('access-token') || '';
    const res = await fetch(`${API_BASE}/api/permission/admins`, {
      headers: { 'Access-Token': token },
    });
    return handleResponse(res);
  },

  async addAdmin(username: string, level: 'super' | 'admin' = 'admin') {
    const token = localStorage.getItem('access-token') || '';
    const res = await fetch(`${API_BASE}/api/permission/admins/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Access-Token': token },
      body: JSON.stringify({ action: 'add', username, level }),
    });
    return handleResponse(res);
  },

  async removeAdmin(username: string) {
    const token = localStorage.getItem('access-token') || '';
    const res = await fetch(`${API_BASE}/api/permission/admins/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Access-Token': token },
      body: JSON.stringify({ action: 'remove', username }),
    });
    return handleResponse(res);
  },

  /**
   * Run an entire workflow via Socket.IO WebSocket.
   *
   * Flow:
   *   client → emit('workflow:run', { workflowId })
   *   server → emit('workflow:started',     { taskId })
   *   server → emit('workflow:node_update', { taskId, nodeId, status, output })  (multiple times)
   *   server → emit('workflow:done',        { taskId, status, error })
   *
   * @param workflowId  Saved workflow ID
   * @param onNodeUpdate  Called on each node status change
   * @param onDone        Called when the workflow finishes
   * @returns             Cleanup function that removes listeners and cancels the run
   */
  runWorkflowWS(
    workflowId: string,
    onNodeUpdate: (nodeId: string, status: string, output: any) => void,
    onDone: (status: string, error: string | null) => void,
  ): () => void {
    const socket = getSocket();

    let taskId: string | null = null;

    const onStarted = (data: { taskId: string }) => {
      taskId = data.taskId;
      console.log('[FlowApi] Workflow started, taskId:', taskId);
    };

    const onNodeUpd = (data: { taskId: string; nodeId: string; status: string; output: any }) => {
      onNodeUpdate(data.nodeId, data.status, data.output);
    };

    const onDoneEvt = (data: { taskId: string; status: string; error: string | null }) => {
      console.log('[FlowApi] Workflow done:', data);
      onDone(data.status, data.error);
      cleanup();
    };

    const onError = (data: { error: string }) => {
      console.error('[FlowApi] Workflow error:', data.error);
      onDone('error', data.error);
      cleanup();
    };

    function cleanup() {
      socket.off('workflow:started', onStarted);
      socket.off('workflow:node_update', onNodeUpd);
      socket.off('workflow:done', onDoneEvt);
      socket.off('workflow:error', onError);
    }

    socket.on('workflow:started', onStarted);
    socket.on('workflow:node_update', onNodeUpd);
    socket.on('workflow:done', onDoneEvt);
    socket.on('workflow:error', onError);

    // Emit run request — wait for connection if reconnecting
    emitWhenReady('workflow:run', { workflowId });

    // Return a cancel function
    return () => {
      if (taskId) {
        socket.emit('workflow:cancel', { taskId });
      }
      cleanup();
    };
  },

  /**
   * Run a subgraph starting from a specific node via Socket.IO WebSocket.
   *
   * The server will execute startNodeId + all its downstream nodes in topo order.
   * Upstream nodes are NOT re-executed; their last outputs are passed via nodeDataOverrides
   * so the server can do port-mapping correctly.
   *
   * Flow:
   *   client → emit('workflow:run_from_node', { workflowId, startNodeId, nodeDataOverrides })
   *   server → emit('workflow:started',     { taskId })
   *   server → emit('workflow:node_update', { taskId, nodeId, status, output })  (multiple times)
   *   server → emit('workflow:done',        { taskId, status, error })
   *
   * @param workflowId        Saved workflow ID
   * @param startNodeId       ID of the node to start execution from
   * @param nodeDataOverrides { nodeId: fieldData | runOutput } — field overrides for the start
   *                          node and cached outputs for upstream nodes (for port mapping)
   * @param onNodeUpdate      Called on each node status change
   * @param onDone            Called when the subgraph finishes
   * @returns                 Cleanup / cancel function
   */
  runNodeWS(
    workflowId: string,
    startNodeId: string,
    nodeDataOverrides: Record<string, any>,
    onNodeUpdate: (nodeId: string, status: string, output: any) => void,
    onDone: (status: string, error: string | null) => void,
  ): () => void {
    const socket = getSocket();
    let taskId: string | null = null;

    const onStarted = (data: { taskId: string }) => {
      taskId = data.taskId;
      console.log('[FlowApi] NodeRun started, taskId:', taskId, 'startNode:', startNodeId);
    };

    const onNodeUpd = (data: { taskId: string; nodeId: string; status: string; output: any }) => {
      onNodeUpdate(data.nodeId, data.status, data.output);
    };

    const onDoneEvt = (data: { taskId: string; status: string; error: string | null }) => {
      console.log('[FlowApi] NodeRun done:', data);
      onDone(data.status, data.error);
      cleanup();
    };

    const onError = (data: { error: string }) => {
      console.error('[FlowApi] NodeRun error:', data.error);
      onDone('error', data.error);
      cleanup();
    };

    function cleanup() {
      socket.off('workflow:started', onStarted);
      socket.off('workflow:node_update', onNodeUpd);
      socket.off('workflow:done', onDoneEvt);
      socket.off('workflow:error', onError);
    }

    socket.on('workflow:started', onStarted);
    socket.on('workflow:node_update', onNodeUpd);
    socket.on('workflow:done', onDoneEvt);
    socket.on('workflow:error', onError);

    // Emit run request — wait for connection if reconnecting
    emitWhenReady('workflow:run_from_node', {
      workflowId,
      startNodeId,
      nodeDataOverrides,
    });

    return () => {
      if (taskId) socket.emit('workflow:cancel', { taskId });
      cleanup();
    };
  },

  /**
   * Run only a SINGLE node — execute it, propagate output, but do NOT
   * automatically execute downstream nodes. Used when the user clicks
   * the ▶ button on a single node.
   */
  runSingleNodeWS(
    workflowId: string,
    nodeId: string,
    nodeDataOverrides: Record<string, any>,
    onNodeUpdate: (nodeId: string, status: string, output: any) => void,
    onDone: (status: string, error: string | null) => void,
  ): () => void {
    const socket = getSocket();
    let taskId: string | null = null;

    const onStarted = (data: { taskId: string }) => {
      taskId = data.taskId;
      console.log('[FlowApi] SingleNodeRun started, taskId:', taskId, 'node:', nodeId);
    };

    const onNodeUpd = (data: { taskId: string; nodeId: string; status: string; output: any }) => {
      onNodeUpdate(data.nodeId, data.status, data.output);
    };

    const onDoneEvt = (data: { taskId: string; status: string; error: string | null }) => {
      console.log('[FlowApi] SingleNodeRun done:', data);
      onDone(data.status, data.error);
      cleanup();
    };

    const onError = (data: { error: string }) => {
      console.error('[FlowApi] SingleNodeRun error:', data.error);
      onDone('error', data.error);
      cleanup();
    };

    function cleanup() {
      socket.off('workflow:started', onStarted);
      socket.off('workflow:node_update', onNodeUpd);
      socket.off('workflow:done', onDoneEvt);
      socket.off('workflow:error', onError);
    }

    socket.on('workflow:started', onStarted);
    socket.on('workflow:node_update', onNodeUpd);
    socket.on('workflow:done', onDoneEvt);
    socket.on('workflow:error', onError);

    // Emit run request — wait for connection if reconnecting
    emitWhenReady('workflow:run_single_node', {
      workflowId,
      nodeId,
      nodeDataOverrides,
    });

    return () => {
      if (taskId) socket.emit('workflow:cancel', { taskId });
      cleanup();
    };
  },
};
