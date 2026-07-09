import React, { useCallback, useEffect, useMemo, useState } from 'react';
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
import { NodeEventBus } from './NodeEventBus';
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
  const [nodes, setNodes, onNodesChange] = useNodesState(initialData?.nodes || []);
  const [edges, setEdges, onEdgesChange] = useEdgesState(
    (initialData?.edges || []).map((e: any) => ({
      ...e,
      type: 'flowing',
    })),
  );
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  // cancelFn returned by FlowApi.runWorkflowWS — non-null while a workflow run is in progress
  const [runCancelFn, setRunCancelFn] = useState<(() => void) | null>(null);

  const { getNode, getEdges } = useReactFlow();

  const selectedNode = useMemo(
    () => (selectedNodeId ? nodes.find((n) => n.id === selectedNodeId) ?? null : null),
    [selectedNodeId, nodes],
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
   * When a node succeeds, mark its outgoing matched edges as activated
   * and cascade-trigger connected downstream nodes.
   *
   * A downstream node is only triggered when ALL its matched incoming edges
   * have a successful upstream output — preventing partial-input runs.
   */
  const handleNodeSuccess = useCallback(
    (succeededNodeId: string, _output: any) => {
      // Mark outgoing matched edges as activated
      setEdges((eds) =>
        eds.map((e) => {
          if (e.source === succeededNodeId && e.data?.matchStatus === 'matched') {
            return { ...e, data: { ...e.data, activated: true } };
          }
          return e;
        }),
      );

      // Cascade: find downstream nodes connected via matched edges and trigger them
      const currentEdges = getEdges();
      const downstreamEdges = currentEdges.filter(
        (e) => e.source === succeededNodeId && e.data?.matchStatus === 'matched',
      );

      // Deduplicate downstream targets (a node may have multiple edges from this node)
      const triggeredTargets = new Set<string>();

      for (const edge of downstreamEdges) {
        if (triggeredTargets.has(edge.target)) continue;
        triggeredTargets.add(edge.target);

        const targetNode = getNode(edge.target);
        if (!targetNode) continue;

        // Collect ALL upstream inputs for this downstream node
        const allIncomingEdges = currentEdges.filter((e) => e.target === edge.target);

        // Check: ALL matched incoming edges must have a successful upstream output.
        // If any upstream hasn't completed yet, skip — it will trigger again when that upstream finishes.
        const allUpstreamsReady = allIncomingEdges
          .filter((e) => e.data?.matchStatus === 'matched')
          .every((inEdge) => {
            const srcNode = getNode(inEdge.source);
            if (!srcNode) return false;
            const srcOutput = (srcNode.data as any)?._runOutput;
            return srcOutput && !srcOutput.error;
          });

        if (!allUpstreamsReady) {
          // Not all upstreams done yet — this node will be triggered by the other upstream when it finishes
          continue;
        }

        const input: Record<string, any> = {};
        for (const inEdge of allIncomingEdges) {
          const srcNode = getNode(inEdge.source);
          if (!srcNode) continue;
          const srcOutput = (srcNode.data as any)?._runOutput;
          if (!srcOutput || srcOutput.error) continue;
          if (inEdge.sourceHandle && srcOutput[inEdge.sourceHandle] !== undefined) {
            input[inEdge.targetHandle || inEdge.sourceHandle] = srcOutput[inEdge.sourceHandle];
          } else if (inEdge.sourceHandle && srcOutput.value !== undefined) {
            // Basic type nodes output { value: ... } — map to target handle
            input[inEdge.targetHandle || inEdge.sourceHandle] = srcOutput.value;
          } else {
            Object.assign(input, srcOutput);
          }
        }

        // Set downstream node to running
        setNodes((nds) =>
          nds.map((n) =>
            n.id === edge.target
              ? { ...n, data: { ...n.data, _runStatus: 'running', _runOutput: null } }
              : n,
          ),
        );

        // Build clean config (strip internal keys)
        const cleanConfig: Record<string, any> = {};
        for (const [k, v] of Object.entries(targetNode.data as Record<string, any>)) {
          if (!k.startsWith('_') && v !== undefined && v !== null && String(v).trim() !== '') {
            cleanConfig[k] = v;
          }
        }

        // Run the downstream node
        FlowApi.runNode(targetNode.type || '', cleanConfig, input)
          .then((result) => {
            const out = result.output ?? result;
            const newStatus = out?.error ? 'error' : 'success';
            setNodes((nds) =>
              nds.map((n) =>
                n.id === edge.target
                  ? { ...n, data: { ...n.data, _runStatus: newStatus, _runOutput: out } }
                  : n,
              ),
            );
            // Continue cascade if downstream also succeeds
            if (newStatus === 'success') {
              NodeEventBus.emit(edge.target, out);
            }
          })
          .catch((err) => {
            setNodes((nds) =>
              nds.map((n) =>
                n.id === edge.target
                  ? { ...n, data: { ...n.data, _runStatus: 'error', _runOutput: { error: err.message } } }
                  : n,
              ),
            );
          });
      }
    },
    [setEdges, setNodes, getNode, getEdges],
  );

  // Subscribe to node success events
  useEffect(() => {
    const unsub = NodeEventBus.subscribe(handleNodeSuccess);
    return unsub;
  }, [handleNodeSuccess]);

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

      // Status map: backend → frontend
      const statusMap: Record<string, string> = {
        idle: 'idle',
        processing: 'running',
        success: 'success',
        error: 'error',
      };

      // Start WebSocket-based workflow run
      const cancelFn = FlowApi.runWorkflowWS(
        wfId,
        // onNodeUpdate: called for each node status push from backend
        (nodeId, nodeStatus, output) => {
          const frontendStatus = statusMap[nodeStatus] ?? nodeStatus;
          setNodes((nds) =>
            nds.map((n) =>
              n.id === nodeId
                ? { ...n, data: { ...n.data, _runStatus: frontendStatus, _runOutput: output } }
                : n,
            ),
          );
          // Activate outgoing edges when a node succeeds
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
    [workflowId, setNodes, setEdges],
  );

  return (
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
