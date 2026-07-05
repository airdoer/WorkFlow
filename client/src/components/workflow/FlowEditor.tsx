import React, { useRef, useEffect, useCallback, useState } from 'react';
import {
  FreeLayoutEditorProvider,
  EditorRenderer,
  FreeLayoutPluginContext,
  WorkflowNodeRenderer,
} from '@flowgram.ai/free-layout-editor';
import { NodeRender } from '@flowgram.ai/form-core';
import { createBackgroundPlugin } from '@flowgram.ai/background-plugin';
import { createMinimapPlugin } from '@flowgram.ai/minimap-plugin';
import { createFreeSnapPlugin } from '@flowgram.ai/free-snap-plugin';
import Toolbox from './Toolbox';
import PropertyPanel from './PropertyPanel';
import Toolbar from './Toolbar';
import { nodeRegistries } from './NodeRegistry';
import type { WorkflowJSON } from './types';

interface FlowEditorProps {
  initialData?: WorkflowJSON;
  workflowId?: string;
  workflowName?: string;
  onSave?: (id: string, name: string) => void;
}

const FlowEditor: React.FC<FlowEditorProps> = ({
  initialData,
  workflowId,
  workflowName,
  onSave,
}) => {
  const editorRef = useRef<FreeLayoutPluginContext | null>(null);
  const [selectedNode, setSelectedNode] = useState<any>(null);

  const handleRun = useCallback((json: WorkflowJSON) => {
    console.log('Run workflow:', json);
  }, []);

  // 监听节点选择变化
  useEffect(() => {
    if (!editorRef.current) return;

    const editor = editorRef.current;
    
    // 监听选择变化事件
    const handleSelectionChange = () => {
      const selected = editor.document?.getSelectedWorkflowNodes?.() || [];
      setSelectedNode(selected[0] || null);
    };

    // 订阅文档变化事件
    const unsubscribe = editor.document?.addEventListener?.('selectionChange', handleSelectionChange);

    return () => {
      if (typeof unsubscribe === 'function') {
        unsubscribe();
      }
    };
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
      <Toolbar
        editorRef={editorRef}
        workflowId={workflowId}
        workflowName={workflowName}
        onSave={onSave}
        onRun={handleRun}
      />
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        <Toolbox editorRef={editorRef} />
        <div style={{ flex: 1, position: 'relative', minHeight: 0, overflow: 'hidden' }}>
          <FreeLayoutEditorProvider
            ref={editorRef}
            initialData={initialData}
            nodeRegistries={nodeRegistries}
            nodeEngine={{ enable: true }}
            variableEngine={{ enable: true }}
            materials={{
              renderDefaultNode: ({ node }) => (
                <WorkflowNodeRenderer
                  node={node}
                  style={{
                    background: '#fff',
                    border: '1px solid #d9d9d9',
                    borderRadius: 8,
                    padding: 12,
                    minWidth: 180,
                  }}
                >
                  <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8 }}>
                    {node.getNodeMeta?.()?.title || node.type}
                  </div>
                  <NodeRender node={node} />
                </WorkflowNodeRenderer>
              ),
            }}
            plugins={() => [
              createBackgroundPlugin(),
              createMinimapPlugin(),
              createFreeSnapPlugin(),
            ]}
          >
            <EditorRenderer style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }} />
          </FreeLayoutEditorProvider>
          <PropertyPanel editorRef={editorRef} selectedNode={selectedNode} />
        </div>
      </div>
    </div>
  );
};

export default FlowEditor;
