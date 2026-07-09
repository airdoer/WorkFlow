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
  if (_socket && _socket.connected) return _socket;

  // In dev mode, connect to same origin (proxied via UMI /socket.io/),
  // In Docker / prod, connect to explicit FLASK_BACKEND_URL
  const socketUrl = API_BASE || window.location.origin;
  _socket = io(socketUrl, {
    transports: ['websocket', 'polling'],
    path: '/socket.io/',
    reconnection: true,
    reconnectionAttempts: 5,
    reconnectionDelay: 1000,
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

  async list() {
    const res = await fetch(`${API_BASE}/api/workflow/list`);
    return handleResponse(res);
  },

  async delete(id: string) {
    const res = await fetch(`${API_BASE}/api/workflow/${id}`, { method: 'DELETE' });
    return handleResponse(res);
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

    // Emit run request
    socket.emit('workflow:run', { workflowId });

    // Return a cancel function
    return () => {
      if (taskId) {
        socket.emit('workflow:cancel', { taskId });
      }
      cleanup();
    };
  },
};
