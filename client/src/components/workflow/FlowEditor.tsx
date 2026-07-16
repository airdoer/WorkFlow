import React, { useCallback, useEffect, useMemo, useState, useRef } from 'react';
import ReactFlow, {
  Node,
  Edge,
  OnNodesChange,
  OnEdgesChange,
  OnConnect,
  addEdge,
  updateEdge,
  Background,
  Controls,
  MiniMap,
  ReactFlowProvider,
  useNodesState,
  useEdgesState,
  useReactFlow,
  NodeMouseHandler,
  Connection,
  OnSelectionChangeFunc,
  ConnectionMode,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { message, Modal } from 'antd';
import Toolbox from './Toolbox';
import PropertyPanel from './PropertyPanel';
import Toolbar from './Toolbar';
import { nodeTypes } from './NodeRegistry';
import { getFormatInitialData } from './nodes/Format';
import FlowingEdge from './nodes/FlowingEdge';
import { isPortTypeCompatible, getNodePorts } from './PortTypes';
import QuickAddMenu from './QuickAddMenu';
import { FlowApi } from './services/FlowApi';
import { WorkflowContext } from './WorkflowContext';
import type { WorkflowJSON } from './types';

const edgeTypes = { flowing: FlowingEdge };

interface FlowEditorProps {
  initialData?: WorkflowJSON;
  workflowId?: string;
  workflowName?: string;
  workflowAuthor?: string;
  workflowDescription?: string;
  workflowCreatedAt?: string;
  workflowUpdatedAt?: string;
  isFullscreen?: boolean;
  onFullscreenToggle?: () => void;
  onSave?: (id: string, name: string) => void;
  onSwitchWorkflow?: (id: string) => void;
  onDeleteWorkflow?: () => void;
  initialLibraryOpen?: boolean;
}

function FlowEditorInner({
  initialData,
  workflowId,
  workflowName,
  workflowAuthor,
  workflowDescription,
  workflowCreatedAt,
  workflowUpdatedAt,
  isFullscreen,
  onFullscreenToggle,
  onSave,
  onSwitchWorkflow,
  onDeleteWorkflow,
  initialLibraryOpen,
}: FlowEditorProps) {
  const initialNodes = initialData?.nodes || [];

  // ── Fast lookup cache for run status/output ──────────────────────────────
  // This mirrors _runStatus/_runOutput from node.data for quick access
  // without iterating over all nodes. Updated in sync with setNodes calls.
  const runStateCacheRef = useRef<Record<string, { status: string; output: any }>>({});

  // Re-compute matchStatus for all edges on load
  const initialEdges = useMemo(() => {
    const nodeMap: Record<string, any> = {};
    for (const n of initialNodes) nodeMap[n.id] = n;

    return (initialData?.edges || []).map((e: any) => {
      const srcNode = nodeMap[e.source];
      const tgtNode = nodeMap[e.target];
      if (srcNode && tgtNode && e.sourceHandle && e.targetHandle) {
        const srcPort = getNodePorts(srcNode.type || '').find(
          (p: any) => p.key === e.sourceHandle && p.direction === 'output',
        );
        let tgtPort = getNodePorts(tgtNode.type || '').find(
          (p: any) => p.key === e.targetHandle && p.direction === 'input',
        );
        // Fallback: for nodes with dynamic ports (like Format), check node.data.variables
        if (!tgtPort && tgtNode.type === 'format') {
          const vars = tgtNode.data?.variables || [];
          const targetVar = vars.find((v: any) => v.name === e.targetHandle);
          if (targetVar) {
            tgtPort = { key: targetVar.name, type: 'string', direction: 'input' as const };
          }
        }
        if (srcPort && tgtPort) {
          const compatible = isPortTypeCompatible(srcPort.type, tgtPort.type);
          // Restore activated state from saved data: if source node was successful, edge was activated
          const srcSuccess = srcNode.data?._runStatus === 'success';
          return {
            ...e,
            type: 'flowing',
            data: {
              ...e.data,
              sourcePortType: srcPort.type,
              targetPortType: tgtPort.type,
              matchStatus: compatible ? 'matched' : 'mismatched',
              activated: srcSuccess ? true : (e.data?.activated || false),
            },
          };
        }
      }
      return { ...e, type: 'flowing' };
    });
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  // Ensure _runStatusHint is present on initial load (for nodes with saved _runStatus)
  const initialNodesCleaned = useMemo(() => {
    return initialNodes.map((n: any) => {
      const data = n.data || {};
      // Pre-populate the fast lookup cache from saved data
      if (data._runStatus && data._runOutput) {
        runStateCacheRef.current[n.id] = {
          status: data._runStatus,
          output: data._runOutput,
        };
      }
      // If _runStatusHint is missing but _runStatus exists, derive it
      return {
        ...n,
        data: {
          ...data,
          _runStatusHint: data._runStatusHint || data._runStatus || undefined,
        },
      };
    });
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodesCleaned);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // ── Node sequence numbering (topological sort) ───────────────────────
  const renumberNodes = useCallback((currentNodes: Node[], currentEdges: Edge[]): Node[] => {
    const inDegree: Record<string, number> = {};
    const adj: Record<string, string[]> = {};
    const nodeIds = new Set(currentNodes.map((n) => n.id));
    for (const nid of nodeIds) { inDegree[nid] = 0; adj[nid] = []; }
    for (const e of currentEdges) {
      if (nodeIds.has(e.source) && nodeIds.has(e.target)) {
        adj[e.source].push(e.target);
        inDegree[e.target] = (inDegree[e.target] || 0) + 1;
      }
    }
    const queue: string[] = [];
    for (const nid of nodeIds) { if (inDegree[nid] === 0) queue.push(nid); }
    queue.sort((a, b) => {
      const sA = (currentNodes.find(n => n.id === a)?.data as any)?._seq ?? 9999;
      const sB = (currentNodes.find(n => n.id === b)?.data as any)?._seq ?? 9999;
      return sA - sB;
    });
    const sorted: string[] = [];
    while (queue.length) {
      const nid = queue.shift()!;
      sorted.push(nid);
      const targets = adj[nid].slice().sort((a, b) => {
        const sA = (currentNodes.find(n => n.id === a)?.data as any)?._seq ?? 9999;
        const sB = (currentNodes.find(n => n.id === b)?.data as any)?._seq ?? 9999;
        return sA - sB;
      });
      for (const t of targets) { inDegree[t]--; if (inDegree[t] === 0) queue.push(t); }
    }
    for (const nid of nodeIds) { if (!sorted.includes(nid)) sorted.push(nid); }
    const seqMap: Record<string, number> = {};
    sorted.forEach((nid, idx) => { seqMap[nid] = idx + 1; });
    return currentNodes.map((n) => {
      const newSeq = seqMap[n.id];
      if ((n.data as any)._seq === newSeq) return n;
      return { ...n, data: { ...n.data, _seq: newSeq } };
    });
  }, []);

  // Re-number nodes whenever the graph structure changes (add/delete/reconnect)
  const prevStructRef = useRef<string>('');
  useEffect(() => {
    const structKey = nodes.map(n => n.id).join(',') + '|' + edges.map(e => `${e.source}->${e.target}`).join(',');
    if (structKey !== prevStructRef.current) {
      prevStructRef.current = structKey;
      const renumbered = renumberNodes(nodes, edges);
      // Only update if any seq actually changed
      const changed = renumbered.some((n, i) => n !== nodes[i]);
      if (changed) setNodes(renumbered);
    }
  }, [nodes, edges, renumberNodes, setNodes]);

  const [selectedNodeId, setSelectedNodeIdRaw] = useState<string | null>(() => {
    const sp = new URLSearchParams(window.location.search);
    return sp.get('node') || null;
  });
  const [runCancelFn, setRunCancelFn] = useState<(() => void) | null>(null);
  const [detailNodeId, setDetailNodeIdRaw] = useState<string | null>(() => {
    const sp = new URLSearchParams(window.location.search);
    return sp.get('detail') || null;
  });

  // Panel collapse state (driven by URL)
  const [toolboxCollapsed, setToolboxCollapsedRaw] = useState(() => {
    const sp = new URLSearchParams(window.location.search);
    return sp.get('toolbox') === '1';
  });
  const [propPanelCollapsed, setPropPanelCollapsedRaw] = useState(() => {
    const sp = new URLSearchParams(window.location.search);
    return sp.get('panel') === '1';
  });
  const [compactMode, setCompactModeRaw] = useState(() => {
    const sp = new URLSearchParams(window.location.search);
    return sp.get('compact') === '1';
  });

  // ── URL sync helper ──────────────────────────────────────────
  const updateUrlParam = useCallback((key: string, value: string | null) => {
    const sp = new URLSearchParams(window.location.search);
    if (value) {
      sp.set(key, value);
    } else {
      sp.delete(key);
    }
    const newSearch = sp.toString();
    const currentSearch = window.location.search.replace(/^\?/, '');
    if (newSearch !== currentSearch) {
      window.history.replaceState(null, '', `${window.location.pathname}${newSearch ? '?' + newSearch : ''}`);
    }
  }, []);

  // Wrappers that sync state to URL
  const setSelectedNodeId = useCallback((id: string | null) => {
    setSelectedNodeIdRaw(id);
    updateUrlParam('node', id);
  }, [updateUrlParam]);

  const setDetailNodeId = useCallback((id: string | null) => {
    setDetailNodeIdRaw(id);
    updateUrlParam('detail', id);
  }, [updateUrlParam]);

  const setToolboxCollapsed = useCallback((v: boolean | ((prev: boolean) => boolean)) => {
    setToolboxCollapsedRaw(prev => {
      const next = typeof v === 'function' ? v(prev) : v;
      updateUrlParam('toolbox', next ? '1' : null);
      return next;
    });
  }, [updateUrlParam]);

  const setPropPanelCollapsed = useCallback((v: boolean | ((prev: boolean) => boolean)) => {
    setPropPanelCollapsedRaw(prev => {
      const next = typeof v === 'function' ? v(prev) : v;
      updateUrlParam('panel', next ? '1' : null);
      return next;
    });
  }, [updateUrlParam]);

  const setCompactMode = useCallback((v: boolean | ((prev: boolean) => boolean)) => {
    setCompactModeRaw(prev => {
      const next = typeof v === 'function' ? v(prev) : v;
      updateUrlParam('compact', next ? '1' : null);
      return next;
    });
  }, [updateUrlParam]);

  // Track unsaved state
  const [isDirty, setIsDirty] = useState(false);
  const lastSavedJsonRef = useRef<string>('');

  // Auto-save on mount when a new workflow already has a name (created via naming modal)
  // This turns the pre-saved empty record into a proper record with the correct json
  useEffect(() => {
    if (!workflowId && workflowName && workflowName !== '未命名工作流') {
      // Slight delay to let ReactFlow initialize
      const t = setTimeout(async () => {
        try {
          const json = toObject();
          const result = await FlowApi.save(workflowName, json, undefined, {
            author: workflowAuthor || '',
            description: workflowDescription || '',
          });
          onSave?.(result.id, workflowName);
        } catch (_) {}
      }, 300);
      return () => clearTimeout(t);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Track multi-selection for special styling
  const [multiSelectedIds, setMultiSelectedIds] = useState<Set<string>>(new Set());

  const { getNode, getNodes, getEdges, toObject, screenToFlowPosition } = useReactFlow();

  const selectedNode = useMemo(
    () => (selectedNodeId ? nodes.find((n) => n.id === selectedNodeId) ?? null : null),
    [selectedNodeId, nodes],
  );

  // ── Undo history ─────────────────────────────────────────────────────────
  // Stack of { nodes, edges } snapshots. We push a snapshot before every
  // meaningful structural change so Ctrl+Z can roll back.
  const undoStack = useRef<Array<{ nodes: Node[]; edges: Edge[] }>>([]);
  const isUndoing = useRef(false);

  /** Push current state onto undo stack (call BEFORE applying the change). */
  const pushUndo = useCallback(() => {
    if (isUndoing.current) return;
    undoStack.current.push({ nodes: getNodes(), edges: getEdges() });
    // Keep at most 50 steps
    if (undoStack.current.length > 50) undoStack.current.shift();
  }, [getNodes, getEdges]);

  // ── Status map: backend → frontend ──────────────────────────────────────
  const statusMap: Record<string, string> = {
    idle: 'idle',
    processing: 'running',
    success: 'success',
    error: 'error',
  };

  /** Read a node's run status (fast lookup from cache, falls back to node.data) */
  const getRunStatus = useCallback((nodeId: string): RunStatus => {
    const cached = runStateCacheRef.current[nodeId];
    if (cached) return cached.status as RunStatus;
    return 'idle';
  }, []);

  /** Read a node's run output (fast lookup from cache) */
  const getRunOutput = useCallback((nodeId: string): any => {
    return runStateCacheRef.current[nodeId]?.output;
  }, []);

  /**
   * Shared node update handler — updates _runStatus, _runOutput,
   * and _runStatusHint in node.data so that:
   * - toObject() includes full run data for save persistence
   * - _runStatusHint triggers the lightweight re-render for the specific node
   */
  const handleNodeUpdate = useCallback(
    (nodeId: string, nodeStatus: string, output: any) => {
      const frontendStatus = statusMap[nodeStatus] ?? nodeStatus;
      // Update fast lookup cache
      runStateCacheRef.current[nodeId] = { status: frontendStatus, output };
      // Update node.data (persists through toObject/save)
      setNodes((nds) =>
        nds.map((n) =>
          n.id === nodeId
            ? { ...n, data: { ...n.data, _runStatus: frontendStatus, _runOutput: output, _runStatusHint: frontendStatus } }
            : n,
        ),
      );

      if (nodeStatus === 'success') {
        setEdges((eds) => {
          return eds.map((e) => {
            // Activate edge if source node succeeded AND edge is compatible (matched or unknown)
            // 'unknown' happens when dynamic ports (like Format variables) aren't in static definitions
            if (e.source === nodeId && (e.data?.matchStatus === 'matched' || e.data?.matchStatus === 'unknown')) {
              return { ...e, data: { ...e.data, activated: true } };
            }
            return e;
          });
        });
      }
    },
    [setNodes, setEdges, statusMap],
  );

  /**
   * Perform an actual save regardless of dirty state.
   * Returns the saved workflow ID, or undefined on failure.
   */
  const doSave = useCallback(async (): Promise<string | undefined> => {
    if (!workflowId) return undefined;
    try {
      const json = toObject();
      const result = await FlowApi.save(workflowName || '未命名工作流', json, workflowId, {
        author: workflowAuthor || '',
        description: workflowDescription || '',
      });
      lastSavedJsonRef.current = JSON.stringify(json);
      setIsDirty(false);
      onSave?.(result.id, workflowName || '未命名工作流');
      return result.id;
    } catch (err: any) {
      console.warn('[FlowEditor] Auto-save failed:', err.message);
      return undefined;
    }
  }, [workflowId, workflowName, workflowAuthor, workflowDescription, toObject, onSave]);

  /**
   * Ensure the workflow is saved before running.
   * If dirty, saves first; otherwise returns the current workflowId.
   */
  const ensureSaved = useCallback(async (): Promise<string | undefined> => {
    if (!workflowId) {
      message.warning('请先保存工作流后再运行节点');
      return undefined;
    }
    if (isDirty) {
      const savedId = await doSave();
      if (!savedId) {
        message.error('自动保存失败，请手动保存后重试');
      }
      return savedId;
    }
    return workflowId;
  }, [workflowId, isDirty, doSave]);

  // ── Quick Add Menu (drag connection to empty space) ───────────────────
  const [quickAdd, setQuickAdd] = useState<{
    canvasX: number;
    canvasY: number;
    screenX: number;
    screenY: number;
    sourceId: string;
    sourceHandle: string;
    sourcePortType: string;
  } | null>(null);
  const connectStartRef = useRef<{ nodeId: string; handleId: string; type: 'source' | 'target'; portType: string } | null>(null);
  const connectSucceededRef = useRef(false);
  const connectMouseStartRef = useRef<{ x: number; y: number } | null>(null);
  const quickAddJustOpenedRef = useRef(false); // prevent onPaneClick from closing immediately

  const onConnectStart = useCallback((_: any, { nodeId, handleId, type }: Connection) => {
    // Determine the port type for compatibility filtering
    let portType = 'any';
    if (nodeId) {
      const node = nodes.find((n) => n.id === nodeId);
      if (node) {
        const port = getNodePorts(node.type || '').find(
          (p) => p.key === handleId && (type === 'source' ? p.direction === 'output' : p.direction === 'input'),
        );
        if (port) portType = port.type;
      }
    }
    connectStartRef.current = { nodeId: nodeId || '', handleId: handleId || '', type: type || 'source', portType };
    connectSucceededRef.current = false;
    // Record mouse start position for drag distance check
    const evt = _ as MouseEvent;
    if (evt?.clientX !== undefined) {
      connectMouseStartRef.current = { x: evt.clientX, y: evt.clientY };
    }
  }, [nodes]);

  const onConnectEnd = useCallback((event: MouseEvent | TouchEvent) => {
    const start = connectStartRef.current;
    if (!start || start.type !== 'source') {
      connectStartRef.current = null;
      return;
    }
    connectStartRef.current = null;
    // Check if the connection actually landed on a Handle element.
    // ReactFlow Handles have the class 'react-flow__handle'.
    // If released over a handle, the connection succeeded — don't show menu.
    const target = (event as MouseEvent).target as HTMLElement;
    const landedOnHandle = target?.closest?.('.react-flow__handle');
    if (connectSucceededRef.current || landedOnHandle) {
      connectSucceededRef.current = false;
      return;
    }
    // Check minimum drag distance — if user barely moved, don't show menu
    // (prevents accidental clicks on Handles from triggering quick-add)
    const MIN_DRAG_DISTANCE = 10;
    const clientX = 'clientX' in event ? event.clientX : 0;
    const clientY = 'clientY' in event ? event.clientY : 0;
    const mouseStart = connectMouseStartRef.current;
    if (mouseStart) {
      const dx = clientX - mouseStart.x;
      const dy = clientY - mouseStart.y;
      if (Math.sqrt(dx * dx + dy * dy) < MIN_DRAG_DISTANCE) {
        return; // Barely moved — just a click, don't show menu
      }
    }
    // Connection did NOT land on a target handle → show quick-add menu
    // Set flag to prevent onPaneClick from closing the menu immediately
    // (ReactFlow fires onPaneClick in the same mouseup event)
    quickAddJustOpenedRef.current = true;
    const canvasPos = screenToFlowPosition({ x: clientX, y: clientY });
    setQuickAdd({
      canvasX: canvasPos.x,
      canvasY: canvasPos.y,
      screenX: clientX,
      screenY: clientY,
      sourceId: start.nodeId,
      sourceHandle: start.handleId,
      sourcePortType: start.portType,
    });
    // Clear the flag after the current event loop tick,
    // so the next onPaneClick won't be blocked
    setTimeout(() => { quickAddJustOpenedRef.current = false; }, 0);
  }, [screenToFlowPosition]);

  const handleQuickAddSelect = useCallback((nodeType: string, targetHandle: string) => {
    if (!quickAdd) return;
    const id = `${nodeType}_${Date.now()}`;
    // Provide initial data for nodes that need it (e.g. Format with default str1)
    const initialData = nodeType === 'format' ? getFormatInitialData() : {};
    const newNode: Node = {
      id,
      type: nodeType,
      position: { x: quickAdd.canvasX, y: quickAdd.canvasY },
      data: initialData,
    };
    setNodes((nds) => [...nds, newNode]);

    // Build edge data with type compatibility
    const sourcePort = getNodePorts(nodes.find((n) => n.id === quickAdd.sourceId)?.type || '').find(
      (p) => p.key === quickAdd.sourceHandle && p.direction === 'output',
    );
    let targetPort = getNodePorts(nodeType).find((p) => p.key === targetHandle && p.direction === 'input');
    // Fallback for dynamic ports: check Format variables
    if (!targetPort && nodeType === 'format') {
      targetPort = { key: targetHandle, type: 'string', direction: 'input' as const };
    }
    const compatible = sourcePort && targetPort ? isPortTypeCompatible(sourcePort?.type || 'any', targetPort.type) : true;
    const edgeData: any = {
      sourcePortType: sourcePort?.type || 'any',
      targetPortType: targetPort?.type || 'any',
      matchStatus: compatible ? 'matched' : 'mismatched',
      activated: false,
    };
    if (!compatible) {
      message.warning(`端口类型不兼容: ${sourcePort?.type || '?'} → ${targetPort?.type || '?'}，请检查连线`);
    }
    const newEdge: Edge = {
      id: `e_${Date.now()}`,
      source: quickAdd.sourceId,
      sourceHandle: quickAdd.sourceHandle,
      target: id,
      targetHandle,
      type: 'flowing',
      data: edgeData,
    };
    setEdges((eds) => [...eds, newEdge]);
    setQuickAdd(null);
    setIsDirty(true);
    pushUndo();
    setTimeout(() => doSave(), 150);
  }, [quickAdd, nodes, setNodes, setEdges, pushUndo, doSave]);

  const onConnect: OnConnect = useCallback(
    (params: Connection) => {
      // Mark as succeeded so onConnectEnd doesn't show the quick-add menu
      connectSucceededRef.current = true;
      if (!params.target || !params.targetHandle) {
        // No target handle info — fall through to default
        pushUndo();
        setEdges((eds) =>
          addEdge({ ...params, type: 'flowing', data: { matchStatus: 'unknown', activated: false } }, eds),
        );
        setIsDirty(true);
        setTimeout(() => doSave(), 100);
        return;
      }

      // Check if there's already an edge going to the same target handle (input port)
      const existingEdge = edges.find(
        (e) => e.target === params.target && e.targetHandle === params.targetHandle,
      );

      /** Clear run state for a node and all its downstream nodes (BFS). */
      const clearDownstreamRunState = (startNodeId: string, currentEdges: Edge[]) => {
        const visited = new Set<string>();
        const queue = [startNodeId];
        while (queue.length) {
          const nid = queue.shift()!;
          if (visited.has(nid)) continue;
          visited.add(nid);
          currentEdges.forEach((e) => {
            if (e.source === nid && !visited.has(e.target)) queue.push(e.target);
          });
        }
        // Clear run state from node.data and cache
        for (const nid of visited) {
          delete runStateCacheRef.current[nid];
        }
        setNodes((nds) =>
          nds.map((n) =>
            visited.has(n.id)
              ? { ...n, data: { ...n.data, _runStatus: 'idle', _runOutput: null, _runStatusHint: 'idle' } }
              : n,
          ),
        );
        // Also clear activated state on edges from cleared nodes
        setEdges((eds) =>
          eds.map((e) =>
            visited.has(e.source) ? { ...e, data: { ...e.data, activated: false } } : e,
          ),
        );
      };

      const doConnect = (removeOldEdge: boolean, currentEdges: Edge[]) => {
        pushUndo();
        const sourceNode = getNode(params.source!);
        const targetNode = getNode(params.target!);
        let edgesAfterRemoval = currentEdges;

        if (removeOldEdge && existingEdge) {
          edgesAfterRemoval = currentEdges.filter((e) => e.id !== existingEdge.id);
          // Clear run state for the target node and all downstream
          clearDownstreamRunState(params.target!, edgesAfterRemoval);
        }

        if (sourceNode && targetNode && params.sourceHandle && params.targetHandle) {
          const sourcePort = getNodePorts(sourceNode.type || '').find(
            (p) => p.key === params.sourceHandle && p.direction === 'output',
          );
          let targetPort = getNodePorts(targetNode.type || '').find(
            (p) => p.key === params.targetHandle && p.direction === 'input',
          );

          // Fallback: for nodes with dynamic ports (like Format), check node.data.variables
          // This handles cases where the targetHandle is a user-defined variable name (e.g. 'str2', 'ip')
          // that doesn't exist in the static PortTypes definition.
          if (!targetPort && targetNode.type === 'format') {
            const vars = (targetNode.data as Record<string, any>)?.variables || [];
            const targetVar = vars.find((v: any) => v.name === params.targetHandle);
            if (targetVar) {
              targetPort = { key: targetVar.name, type: 'string', direction: 'input' as const };
            }
          }

          if (sourcePort && targetPort) {
            const compatible = isPortTypeCompatible(sourcePort.type, targetPort.type);
            const edgeData = {
              sourcePortType: sourcePort.type,
              targetPortType: targetPort.type,
              matchStatus: compatible ? 'matched' : 'mismatched',
              activated: false,
            };

            if (!compatible) {
              message.warning(`端口类型不兼容: ${sourcePort.type} → ${targetPort.type}，请检查连线`);
            }

            setEdges(addEdge({ ...params, type: 'flowing', data: edgeData }, edgesAfterRemoval));
            setIsDirty(true);
            setTimeout(() => doSave(), 100);
            return;
          }
        }

        setEdges(
          addEdge(
            { ...params, type: 'flowing', data: { matchStatus: 'unknown', activated: false } },
            edgesAfterRemoval,
          ),
        );
        setIsDirty(true);
        setTimeout(() => doSave(), 100);
      };

      if (existingEdge) {
        // Ask user whether to replace the existing connection
        Modal.confirm({
          title: '端口已有连线',
          content: `输入端口「${params.targetHandle}」已被其他节点连接。是否替换原有连线？`,
          okText: '替换',
          cancelText: '保留原连线（取消）',
          onOk: () => doConnect(true, edges),
          onCancel: () => { /* do nothing — keep existing edge */ },
        });
      } else {
        doConnect(false, edges);
      }
    },
    [edges, setEdges, setNodes, getNode, pushUndo, doSave],
  );

  // ── Edge reconnect (drag from connected target Handle) ────────────────
  const edgeUpdateStartRef = useRef<Edge | null>(null);
  const edgeUpdateSucceededRef = useRef(false);
  const edgeUpdateMouseStartRef = useRef<{ x: number; y: number } | null>(null);

  const onEdgeUpdateStart = useCallback((_: any, edge: Edge) => {
    edgeUpdateStartRef.current = edge;
    edgeUpdateSucceededRef.current = false;
    // Record mouse position to detect if user actually dragged
    const evt = _ as MouseEvent;
    if (evt?.clientX !== undefined) {
      edgeUpdateMouseStartRef.current = { x: evt.clientX, y: evt.clientY };
    }
  }, []);

  const onEdgeUpdate = useCallback(
    (oldEdge: Edge, newConnection: Connection) => {
      edgeUpdateSucceededRef.current = true;
      // Also mark connectSucceeded so onConnectEnd won't show quick-add menu
      connectSucceededRef.current = true;
      if (!newConnection.target || !newConnection.targetHandle) {
        // Dropped on empty or invalid target → delete the edge
        pushUndo();
        setEdges((eds) => eds.filter((e) => e.id !== oldEdge.id));
        setIsDirty(true);
        setTimeout(() => doSave(), 100);
        return;
      }

      // Check port type compatibility
      const sourceNode = getNode(newConnection.source!);
      const targetNode = getNode(newConnection.target!);
      if (sourceNode && targetNode && newConnection.sourceHandle && newConnection.targetHandle) {
        const sourcePort = getNodePorts(sourceNode.type || '').find(
          (p) => p.key === newConnection.sourceHandle && p.direction === 'output',
        );
        const targetPort = getNodePorts(targetNode.type || '').find(
          (p) => p.key === newConnection.targetHandle && p.direction === 'input',
        );
        if (sourcePort && targetPort) {
          const compatible = isPortTypeCompatible(sourcePort.type, targetPort.type);
          const updatedEdge = updateEdge(oldEdge, newConnection, edges);
          // Apply matchStatus to the updated edge
          const finalEdge = updatedEdge.map((e) =>
            e.id === oldEdge.id
              ? {
                  ...e,
                  source: newConnection.source!,
                  sourceHandle: newConnection.sourceHandle,
                  target: newConnection.target!,
                  targetHandle: newConnection.targetHandle,
                  data: {
                    ...e.data,
                    sourcePortType: sourcePort.type,
                    targetPortType: targetPort.type,
                    matchStatus: compatible ? 'matched' : 'mismatched',
                    activated: false,
                  },
                }
              : e,
          );
          if (!compatible) {
            message.warning(`端口类型不兼容: ${sourcePort.type} → ${targetPort.type}，请检查连线`);
          }
          pushUndo();
          setEdges(finalEdge);
          setIsDirty(true);
          setTimeout(() => doSave(), 100);
          return;
        }
      }
      // Fallback: just update edge without port type check
      pushUndo();
      setEdges(updateEdge(oldEdge, newConnection, edges));
      setIsDirty(true);
      setTimeout(() => doSave(), 100);
    },
    [edges, setEdges, getNode, pushUndo, doSave],
  );

  const onEdgeUpdateEnd = useCallback(
    (_: any, edge: Edge) => {
      // Mark connect as succeeded so onConnectEnd doesn't show quick-add menu
      connectSucceededRef.current = true;

      // Check if user actually dragged (minimum distance threshold)
      // If they just clicked or barely moved, don't delete the edge
      const MIN_DRAG_DISTANCE = 10; // pixels
      const evt = _ as MouseEvent;
      const startMouse = edgeUpdateMouseStartRef.current;
      let actuallyDragged = true;
      if (startMouse && evt?.clientX !== undefined) {
        const dx = evt.clientX - startMouse.x;
        const dy = evt.clientY - startMouse.y;
        actuallyDragged = Math.sqrt(dx * dx + dy * dy) >= MIN_DRAG_DISTANCE;
      }

      // If the edge update didn't succeed AND the user actually dragged,
      // delete the edge (they deliberately dropped on empty space).
      // If they barely moved, keep the edge intact (accidental click).
      if (!edgeUpdateSucceededRef.current && edgeUpdateStartRef.current && actuallyDragged) {
        const oldEdge = edgeUpdateStartRef.current;
        pushUndo();
        setEdges((eds) => eds.filter((e) => e.id !== oldEdge.id));
        setIsDirty(true);
        setTimeout(() => doSave(), 100);
      }
      edgeUpdateStartRef.current = null;
      edgeUpdateSucceededRef.current = false;
      edgeUpdateMouseStartRef.current = null;
    },
    [setEdges, pushUndo, doSave],
  );

  const onNodeClick: NodeMouseHandler = useCallback((_, node) => {
    setSelectedNodeId(node.id);
  }, []);

  const onNodeDragStart: NodeMouseHandler = useCallback((_, node) => {
    setSelectedNodeId(node.id);
  }, []);

  // When a node finishes dragging, reset its zIndex back to default (0).
  // This prevents pasted nodes from staying permanently on top after being moved.
  const onNodeDragStop: NodeMouseHandler = useCallback((_, node) => {
    if (node.zIndex) {
      setNodes((nds) =>
        nds.map((n) => (n.id === node.id ? { ...n, zIndex: 0 } : n)),
      );
    }
  }, [setNodes]);

  const onPaneClick = useCallback(() => {
    // If QuickAdd menu just opened (from onConnectEnd), don't close it immediately.
    // ReactFlow fires onPaneClick in the same mouseup event as onConnectEnd.
    if (quickAddJustOpenedRef.current) {
      quickAddJustOpenedRef.current = false;
      return;
    }
    setSelectedNodeId(null);
    setMultiSelectedIds(new Set());
    setQuickAdd(null);  // Close quick-add menu when clicking on canvas
  }, []);

  const onNodesDelete = useCallback(
    (deleted: Node[]) => {
      if (deleted.some((n) => n.id === selectedNodeId)) {
        setSelectedNodeId(null);
      }
      setIsDirty(true);
    },
    [selectedNodeId],
  );

  const onEdgesDelete = useCallback(() => {
    setIsDirty(true);
  }, []);

  // Track selection changes for special styling
  const onSelectionChange: OnSelectionChangeFunc = useCallback(
    ({ nodes: selectedNodes }) => {
      if (selectedNodes.length >= 1) {
        setSelectedNodeId(selectedNodes[0].id);
        setMultiSelectedIds(new Set(selectedNodes.map((n) => n.id)));
      } else {
        setSelectedNodeId(null);
        setMultiSelectedIds(new Set());
      }
    },
    [],
  );

  // Track node/edge changes as dirty
  const wrappedOnNodesChange: OnNodesChange = useCallback(
    (changes) => {
      const meaningful = changes.some(
        (c) => c.type === 'add' || c.type === 'remove' || c.type === 'position',
      );
      if (meaningful) {
        pushUndo();
        setIsDirty(true);
      }
      onNodesChange(changes);
    },
    [onNodesChange, pushUndo],
  );

  const wrappedOnEdgesChange: OnEdgesChange = useCallback(
    (changes) => {
      const meaningful = changes.some(
        (c) => c.type === 'add' || c.type === 'remove',
      );
      if (meaningful) {
        pushUndo();
        setIsDirty(true);
      }
      onEdgesChange(changes);
    },
    [onEdgesChange, pushUndo],
  );

  /**
   * Duplicate a node — create a copy with fresh id, offset position, no run status
   */
  const handleDuplicateNode = useCallback(
    (nodeId: string) => {
      const node = getNode(nodeId);
      if (!node) return;

      const newNodeId = `${node.type}_${Date.now()}`;
      const { _runStatusHint, _runStatus, _runOutput, _seq, ...cleanData } = node.data as any;

      const newNode: Node = {
        id: newNodeId,
        type: node.type,
        position: { x: node.position.x + 50, y: node.position.y + 50 },
        data: { ...cleanData },
      };

      setNodes((nds) => [...nds, newNode]);
      setIsDirty(true);
    },
    [getNode, setNodes],
  );

  // ── Clipboard: Ctrl+C / Ctrl+X / Ctrl+V (cross-tab via localStorage) ──────
  // Payload format: { nodes: [...], edges: [...] }
  // - nodes include position + clean data (no run state)
  // - edges are filtered to only those connecting nodes within the selection
  // localStorage makes it accessible from any tab/window on the same origin.
  const CLIPBOARD_KEY = 'wf_clipboard';

  const handleRun = useCallback(
    async (json: WorkflowJSON, currentWorkflowId?: string) => {
      // Auto-save before running to ensure backend has latest state
      const wfId = await ensureSaved() || currentWorkflowId || workflowId;
      if (!wfId) {
        message.warning('请先保存工作流');
        return;
      }

      // Clear run status and output from all nodes + cache
      runStateCacheRef.current = {};
      setNodes((nds) =>
        nds.map((n) => ({ ...n, data: { ...n.data, _runStatus: 'idle', _runOutput: null, _runStatusHint: 'idle' } })),
      );
      setEdges((eds) =>
        eds.map((e) => ({ ...e, data: { ...e.data, activated: false } })),
      );

      const cancelFn = FlowApi.runWorkflowWS(
        wfId,
        handleNodeUpdate,
        (_status, error) => {
          setRunCancelFn(null);
          if (error) {
            console.error('[FlowEditor] Workflow run finished with error:', error);
            message.error(`运行出错: ${error}`);
          }
        },
      );

      setRunCancelFn(() => cancelFn);
    },
    [workflowId, ensureSaved, setNodes, setEdges, handleNodeUpdate],
  );

  // Handle drag-over from Toolbox
  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  }, []);

  // Handle drop from Toolbox — create a new node at the exact drop position
  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const nodeType = e.dataTransfer.getData('application/reactflow');
      if (!nodeType) return;

      // Use screenToFlowPosition to convert screen coords to flow coords
      const position = screenToFlowPosition({
        x: e.clientX,
        y: e.clientY,
      });

      const id = `${nodeType}_${Date.now()}`;
      const initialData = nodeType === 'format' ? getFormatInitialData() : {};
      const newNode: Node = {
        id,
        type: nodeType,
        position,
        data: initialData,
      };

      setNodes((nds) => [...nds, newNode]);
      setIsDirty(true);
      // Auto-save after React has committed the new node to ReactFlow state
      setTimeout(() => doSave(), 100);
    },
    [setNodes, screenToFlowPosition, doSave],
  );

  // Keyboard shortcuts — must be on the ReactFlow pane, not on a random div
  const onKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      const ctrl = e.ctrlKey || e.metaKey;
      const tag = (e.target as HTMLElement).tagName;
      const inInput = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';

      // ── Ctrl+Z: undo ──────────────────────────────────────────────────
      if (ctrl && e.key === 'z' && !inInput) {
        e.preventDefault();
        const snapshot = undoStack.current.pop();
        if (snapshot) {
          isUndoing.current = true;
          setNodes(snapshot.nodes);
          setEdges(snapshot.edges);
          setIsDirty(true);
          isUndoing.current = false;
          message.info('已撤销');
        } else {
          message.info('没有更多可撤销的操作');
        }
        return;
      }

      if (inInput) return;

      const selectedNodes = nodes.filter((n) => n.selected);

      // Helper: build clipboard payload including intra-selection edges
      const buildPayload = (sNodes: Node[]) => {
        const ids = new Set(sNodes.map((n) => n.id));
        // Include edges where BOTH source and target are in selection
        const sEdges = edges.filter((e) => ids.has(e.source) && ids.has(e.target));
        return {
          nodes: sNodes.map((n) => {
            const { _runStatusHint, _runStatus, _runOutput, _seq, ...cleanData } = n.data as any;
            return { id: n.id, type: n.type || '', data: cleanData, position: n.position };
          }),
          edges: sEdges.map((e) => ({
            source: e.source, target: e.target,
            sourceHandle: e.sourceHandle, targetHandle: e.targetHandle,
            type: e.type, data: e.data,
          })),
        };
      };

      // ── Ctrl+C: copy selected node(s) to localStorage clipboard ───────
      if (ctrl && e.key === 'c') {
        // If user has text selected in a modal/panel, let browser handle copy
        const sel = window.getSelection();
        if (sel && sel.toString().length > 0) return;
        if (selectedNodes.length > 0) {
          try { localStorage.setItem(CLIPBOARD_KEY, JSON.stringify(buildPayload(selectedNodes))); } catch (_) {}
          e.preventDefault();
          message.success(`已复制 ${selectedNodes.length} 个节点`);
        }
      }

      // ── Ctrl+X: cut selected node(s) ─────────────────────────────────
      if (ctrl && e.key === 'x') {
        // If user has text selected, let browser handle cut
        const sel = window.getSelection();
        if (sel && sel.toString().length > 0) return;
        if (selectedNodes.length > 0) {
          try { localStorage.setItem(CLIPBOARD_KEY, JSON.stringify(buildPayload(selectedNodes))); } catch (_) {}
          const ids = new Set(selectedNodes.map((n) => n.id));
          pushUndo();
          setNodes((nds) => nds.filter((n) => !ids.has(n.id)));
          setEdges((eds) => eds.filter((e) => !ids.has(e.source) && !ids.has(e.target)));
          setIsDirty(true);
          e.preventDefault();
          message.success(`已剪切 ${selectedNodes.length} 个节点`);
        }
      }

      // ── Ctrl+V: paste from localStorage clipboard ─────────────────────
      if (ctrl && e.key === 'v') {
        try {
          const raw = localStorage.getItem(CLIPBOARD_KEY);
          if (!raw) return;
          const payload: { nodes: any[]; edges: any[] } = JSON.parse(raw);
          if (!payload?.nodes?.length) return;

          pushUndo();
          const OFFSET = 50;
          // Build id remap: original id → new id
          const idMap: Record<string, string> = {};
          payload.nodes.forEach((n) => { idMap[n.id] = `${n.type}_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`; });

          const newNodes: Node[] = payload.nodes.map((n) => ({
            id: idMap[n.id],
            type: n.type,
            data: { ...n.data },  // no run state (already stripped on copy)
            position: { x: n.position.x + OFFSET, y: n.position.y + OFFSET },
            zIndex: 1000,         // bring to front so they appear on top of existing nodes
            selected: true,       // auto-select pasted nodes
          }));

          // Strip edge activated state — pasted edges should be unactivated
          const newEdges: Edge[] = (payload.edges || []).map((e) => ({
            id: `e_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
            source: idMap[e.source] || e.source,
            target: idMap[e.target] || e.target,
            sourceHandle: e.sourceHandle,
            targetHandle: e.targetHandle,
            type: e.type || 'flowing',
            data: { ...e.data, activated: false },  // clear activation status
          }));

          // Deselect existing nodes, then add pasted ones on top
          setNodes((nds) => [
            ...nds.map((n) => ({ ...n, selected: false })),
            ...newNodes,
          ]);
          setEdges((eds) => [...eds, ...newEdges]);
          setIsDirty(true);
          e.preventDefault();
          message.success(`已粘贴 ${newNodes.length} 个节点（无运行状态）`);
          setTimeout(() => doSave(), 100);
        } catch (_) {
          message.error('粘贴失败');
        }
      }

      // ── Ctrl+D: duplicate selected node ──────────────────────────────
      if (ctrl && e.key === 'd' && selectedNodeId) {
        e.preventDefault();
        handleDuplicateNode(selectedNodeId);
      }
    },
    [nodes, edges, selectedNodeId, handleDuplicateNode, setNodes, setEdges, getNode, pushUndo, doSave],
  );

  // ── Memoized context value: prevents unnecessary re-renders of all BaseNode ──
  // components when only node positions change (e.g. during dragging).
  const contextValue = useMemo(() => ({
    workflowId,
    workflowName: workflowName || '',
    onNodeUpdate: handleNodeUpdate,
    ensureSaved,
    multiSelectedIds,
    compactMode,
    setCompactMode,
    selectedNodeId,
    setSelectedNodeId,
    detailNodeId,
    setDetailNodeId,
    getRunStatus,
    getRunOutput,
  }), [workflowId, workflowName, handleNodeUpdate, ensureSaved, multiSelectedIds, compactMode, setCompactMode, selectedNodeId, setSelectedNodeId, detailNodeId, setDetailNodeId, getRunStatus, getRunOutput]);

  return (
    <WorkflowContext.Provider value={contextValue}>
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <Toolbar
        nodes={nodes}
        edges={edges}
        setNodes={setNodes}
        setEdges={setEdges}
        workflowId={workflowId}
        workflowName={workflowName}
        workflowAuthor={workflowAuthor}
        workflowDescription={workflowDescription}
        workflowCreatedAt={workflowCreatedAt}
        workflowUpdatedAt={workflowUpdatedAt}
        isDirty={isDirty}
        isFullscreen={isFullscreen}
        onFullscreenToggle={onFullscreenToggle}
        onSave={(id, name) => {
          setIsDirty(false);
          onSave?.(id, name);
        }}
        onRun={handleRun}
        runCancelFn={runCancelFn}
        compactMode={compactMode}
        onToggleCompactMode={() => setCompactMode(c => !c)}
        onSwitchWorkflow={onSwitchWorkflow}
        onDeleteWorkflow={onDeleteWorkflow}
        initialLibraryOpen={initialLibraryOpen}
      />
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        <Toolbox nodes={nodes} setNodes={setNodes} onAddNode={() => {
          setIsDirty(true);
          // Auto-save after React has committed the new node to ReactFlow state
          setTimeout(() => doSave(), 100);
        }} collapsed={toolboxCollapsed} onToggleCollapse={() => setToolboxCollapsed(c => !c)} />
        <div style={{ flex: 1, minHeight: 0, position: 'relative', width: '100%', height: '100%' }} onKeyDown={onKeyDown} tabIndex={-1}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={wrappedOnNodesChange}
            onEdgesChange={wrappedOnEdgesChange}
            onConnect={onConnect}
            onConnectStart={onConnectStart}
            onConnectEnd={onConnectEnd as any}
            onEdgeUpdate={onEdgeUpdate as any}
            onEdgeUpdateStart={onEdgeUpdateStart as any}
            onEdgeUpdateEnd={onEdgeUpdateEnd as any}
            edgesUpdatable="target"
            connectionMode={ConnectionMode.Loose}
            onNodeClick={onNodeClick}
            onNodeDragStart={onNodeDragStart}
            onNodeDragStop={onNodeDragStop}
            onPaneClick={onPaneClick}
            onNodesDelete={onNodesDelete}
            onEdgesDelete={onEdgesDelete}
            onDragOver={onDragOver}
            onDrop={onDrop}
            onSelectionChange={onSelectionChange}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            fitView
            deleteKeyCode={['Delete', 'Backspace']}
            multiSelectionKeyCode="Control"
            selectNodesOnDrag={true}
          >
            <Background />
            <Controls />
            <MiniMap />
          </ReactFlow>
          {/* Quick Add Menu — shows when connection dragged to empty space */}
          {quickAdd && (
            <QuickAddMenu
              canvasPosition={{ x: quickAdd.canvasX, y: quickAdd.canvasY }}
              sourceId={quickAdd.sourceId}
              sourceHandle={quickAdd.sourceHandle}
              sourcePortType={quickAdd.sourcePortType}
              onSelect={handleQuickAddSelect}
              onClose={() => setQuickAdd(null)}
              // Position the menu near the mouse release point
              style={{ left: quickAdd.screenX, top: quickAdd.screenY }}
            />
          )}
        </div>
        <PropertyPanel
          selectedNode={selectedNode}
          setNodes={setNodes}
          edges={edges}
          nodes={nodes}
          onDuplicate={handleDuplicateNode}
          collapsed={propPanelCollapsed}
          onToggleCollapse={() => setPropPanelCollapsed(c => !c)}
        />
      </div>
    </div>
    </WorkflowContext.Provider>
  );
}

const FlowEditor: React.FC<FlowEditorProps> = (props) => {
  return (
    <ReactFlowProvider>
      <FlowEditorInner {...props} />
    </ReactFlowProvider>
  );
};

export default FlowEditor;
