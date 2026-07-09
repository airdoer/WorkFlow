import React, { useCallback, useMemo, useState } from 'react';
import ReactFlow, {
  Node,
  Edge,
  OnNodesChange,
  OnEdgesChange,
  OnConnect,
  addEdge,
  Background,
  Controls,
  MiniMap,
  ReactFlowProvider,
  useNodesState,
  useEdgesState,
  useReactFlow,
  NodeMouseHandler,
  Connection,
} from 'reactflow';
import 'reactflow/dist/style.css';
import Toolbox from './Toolbox';
import PropertyPanel from './PropertyPanel';
import Toolbar from './Toolbar';
import { nodeTypes } from './NodeRegistry';
import FlowingEdge from './nodes/FlowingEdge';
import { isPortTypeCompatible, getNodePorts } from './PortTypes';
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
}: FlowEditorProps) {
  const initialNodes = initialData?.nodes || [];

  // Re-compute matchStatus for all edges on load, in case saved data is stale
  // (e.g., port type compatibility rules changed since the workflow was last saved)
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
        const tgtPort = getNodePorts(tgtNode.type || '').find(
          (p: any) => p.key === e.targetHandle && p.direction === 'input',
        );
        if (srcPort && tgtPort) {
          const compatible = isPortTypeCompatible(srcPort.type, tgtPort.type);
          return {
            ...e,
            type: 'flowing',
            data: {
              ...e.data,
              sourcePortType: srcPort.type,
              targetPortType: tgtPort.type,
              matchStatus: compatible ? 'matched' : 'mismatched',
            },
          };
        }
      }
      return { ...e, type: 'flowing' };
    });
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps — only run once on mount

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  // cancelFn returned by FlowApi.runWorkflowWS — non-null while a workflow run is in progress
  const [runCancelFn, setRunCancelFn] = useState<(() => void) | null>(null);

  const { getNode } = useReactFlow();

  const selectedNode = useMemo(
    () => (selectedNodeId ? nodes.find((n) => n.id === selectedNodeId) ?? null : null),
    [selectedNodeId, nodes],
  );

  // ── Status map: backend → frontend ──────────────────────────────────────
  const statusMap: Record<string, string> = {
    idle: 'idle',
    processing: 'running',
    success: 'success',
    error: 'error',
  };

  /**
   * Shared node update handler — used by BOTH the full-graph run (Toolbar) and
   * single-node ▶ run (BaseNode). Applies status/output to the target node and
   * activates outgoing edges on success.
   */
  const handleNodeUpdate = useCallback(
    (nodeId: string, nodeStatus: string, output: any) => {
      const frontendStatus = statusMap[nodeStatus] ?? nodeStatus;
      setNodes((nds) =>
        nds.map((n) =>
          n.id === nodeId
            ? { ...n, data: { ...n.data, _runStatus: frontendStatus, _runOutput: output } }
            : n,
        ),
      );
      if (nodeStatus === 'success') {
        setEdges((eds) =>
          eds.map((e) =>
            e.source === nodeId && e.data?.matchStatus === 'matched'
              ? { ...e, data: { ...e.data, activated: true } }
              : e,
          ),
        );
      }
    },
    [setNodes, setEdges],
  );

  const onConnect: OnConnect = useCallback(
    (params: Connection) => {
      const sourceNode = getNode(params.source!);
      const targetNode = getNode(params.target!);

      if (sourceNode && targetNode && params.sourceHandle && params.targetHandle) {
        const sourcePort = getNodePorts(sourceNode.type || '').find(
          (p) => p.key === params.sourceHandle && p.direction === 'output',
        );
        const targetPort = getNodePorts(targetNode.type || '').find(
          (p) => p.key === params.targetHandle && p.direction === 'input',
        );

        if (sourcePort && targetPort) {
          const compatible = isPortTypeCompatible(sourcePort.type, targetPort.type);
          const edgeData = {
            sourcePortType: sourcePort.type,
            targetPortType: targetPort.type,
            matchStatus: compatible ? 'matched' : 'mismatched',
            activated: false,
          };

          const newEdge = addEdge(
            {
              ...params,
              type: 'flowing',
              data: edgeData,
            },
            edges,
          );
          setEdges(newEdge);
          return;
        }
      }

      setEdges((eds) =>
        addEdge({ ...params, type: 'flowing', data: { matchStatus: 'unknown', activated: false } }, eds),
      );
    },
    [edges, setEdges, getNode],
  );

  const onNodeClick: NodeMouseHandler = useCallback((_, node) => {
    setSelectedNodeId(node.id);
  }, []);

  const onPaneClick = useCallback(() => {
    setSelectedNodeId(null);
  }, []);

  const onNodesDelete = useCallback(
    (deleted: Node[]) => {
      if (deleted.some((n) => n.id === selectedNodeId)) {
        setSelectedNodeId(null);
      }
    },
    [selectedNodeId],
  );

  /**
   * When a node succeeds, mark its outgoing matched edges as activated.
   * (Legacy frontend cascade is removed — cascade is now handled by the backend subgraph run.)
   */

  const handleRun = useCallback(
    async (json: WorkflowJSON, currentWorkflowId?: string) => {
      const wfId = currentWorkflowId || workflowId;
      if (!wfId) {
        return;
      }

      // Reset all node statuses to 'idle' and deactivate all edges
      setNodes((nds) =>
        nds.map((n) => ({ ...n, data: { ...n.data, _runStatus: 'idle', _runOutput: null } })),
      );
      setEdges((eds) =>
        eds.map((e) => ({ ...e, data: { ...e.data, activated: false } })),
      );

      // Start WebSocket-based workflow run
      const cancelFn = FlowApi.runWorkflowWS(
        wfId,
        handleNodeUpdate,
        // onDone: workflow finished
        (_status, error) => {
          setRunCancelFn(null);
          if (error) {
            console.error('[FlowEditor] Workflow run finished with error:', error);
          }
        },
      );

      // Store cancel function so Toolbar stop button can cancel
      setRunCancelFn(() => cancelFn);
    },
    [workflowId, setNodes, setEdges, handleNodeUpdate],
  );

  return (
    <WorkflowContext.Provider value={{ workflowId, onNodeUpdate: handleNodeUpdate }}>
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
        isFullscreen={isFullscreen}
        onFullscreenToggle={onFullscreenToggle}
        onSave={onSave}
        onRun={handleRun}
        runCancelFn={runCancelFn}
      />
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        <Toolbox nodes={nodes} setNodes={setNodes} />
        <div style={{ flex: 1, minHeight: 0, position: 'relative', width: '100%', height: '100%' }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            onNodesDelete={onNodesDelete}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            fitView
            deleteKeyCode={['Delete', 'Backspace']}
          >
            <Background />
            <Controls />
            <MiniMap />
          </ReactFlow>
        </div>
        <PropertyPanel selectedNode={selectedNode} setNodes={setNodes} edges={edges} nodes={nodes} />
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
