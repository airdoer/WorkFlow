import React, { useRef, useEffect, useCallback } from 'react';
import {
  FreeLayoutEditorProvider,
  EditorRenderer,
  FreeLayoutPluginContext,
  createShortcutsPlugin,
} from '@flowgram.ai/free-layout-editor';
import { createBackgroundPlugin } from '@flowgram.ai/background-plugin';
import { createMinimapPlugin } from '@flowgram.ai/minimap-plugin';
import { createFreeSnapPlugin } from '@flowgram.ai/free-snap-plugin';
import { createFreeAutoLayoutPlugin } from '@flowgram.ai/free-auto-layout-plugin';
import { createFreeHistoryPlugin } from '@flowgram.ai/free-history-plugin';
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

  const handleRun = useCallback((json: WorkflowJSON) => {
    console.log('Run workflow:', json);
  }, []);

  const handleCanvasDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const nodeType = e.dataTransfer.getData('workflow-node-type');
      if (!nodeType || !editorRef.current) return;

      const document = editorRef.current.document;
      const canvasRect = (e.currentTarget as HTMLElement).getBoundingClientRect();
      const x = e.clientX - canvasRect.left;
      const y = e.clientY - canvasRect.top;

      document.createWorkflowNode({
        id: `${nodeType}_${Date.now()}`,
        type: nodeType,
        meta: { position: { x, y } },
        data: {},
        blocks: [],
        edges: [],
      });
    },
    [],
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <Toolbar
        editorRef={editorRef}
        workflowId={workflowId}
        workflowName={workflowName}
        onSave={onSave}
        onRun={handleRun}
      />
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <Toolbox />
        <div
          style={{ flex: 1, position: 'relative' }}
          onDrop={handleCanvasDrop}
          onDragOver={(e) => e.preventDefault()}
        >
          <FreeLayoutEditorProvider
            ref={editorRef}
            initialData={initialData}
            nodeRegistries={nodeRegistries}
            nodeEngine={{ enable: true }}
            variableEngine={{ enable: true }}
            plugins={() => [
              createBackgroundPlugin(),
              createMinimapPlugin(),
              createFreeSnapPlugin(),
              createFreeAutoLayoutPlugin(),
              createFreeHistoryPlugin(),
              createShortcutsPlugin(),
            ]}
          >
            <EditorRenderer style={{ width: '100%', height: '100%' }} />
          </FreeLayoutEditorProvider>
        </div>
        <PropertyPanel />
      </div>
    </div>
  );
};

export default FlowEditor;
