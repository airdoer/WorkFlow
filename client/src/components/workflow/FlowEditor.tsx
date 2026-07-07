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
   */
  const handleNodeSuccess = useCallback(
    (succeededNodeId: string, output: any) => {
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

      for (const edge of downstreamEdges) {
        const targetNode = getNode(edge.target);
        if (!targetNode) continue;

        // Gather input from the succeeded node's output
        const input: Record<string, any> = {};
        if (edge.sourceHandle && output[edge.sourceHandle] !== undefined) {
          input[edge.targetHandle || edge.sourceHandle] = output[edge.sourceHandle];
        } else {
          Object.assign(input, output);
        }

        // Set downstream node to running
        setNodes((nds) =>
          nds.map((n) =>
            n.id === edge.target
              ? { ...n, data: { ...n.data, _runStatus: 'running', _runOutput: null } }
              : n,
          ),
        );

        // Run the downstream node
        FlowApi.runNode(targetNode.type || '', targetNode.data || {}, input)
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
    (json: WorkflowJSON) => {
      console.log('Run workflow:', json);
    },
    [],
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
        <PropertyPanel selectedNode={selectedNode} setNodes={setNodes} edges={edges} />
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
