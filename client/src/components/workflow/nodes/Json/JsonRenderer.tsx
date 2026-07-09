import React, { useRef, useCallback, useEffect } from 'react';
import { JsonEditor as JsonEditorCore } from 'jsoneditor-react';
import 'jsoneditor/dist/jsoneditor.css';

/**
 * JSON result renderer using jsoneditor-react.
 * Provides a professional JSON editor/viewer with tree, code, and table modes.
 * Read-only mode by default — used for displaying node execution output.
 */
interface JsonRendererProps {
  data: any;
  jsonPath?: string;
  onChange?: (data: any) => void;
  readOnly?: boolean;
}

const JsonRenderer: React.FC<JsonRendererProps> = ({ data, jsonPath, onChange, readOnly = true }) => {
  const editorRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const onEditorUpdate = useCallback(
    (json: any) => {
      if (onChange && !readOnly) {
        onChange(json);
      }
    },
    [onChange, readOnly],
  );

  // After editor is created, set it to view mode if readOnly
  useEffect(() => {
    if (editorRef.current?.jsonEditor && readOnly) {
      try {
        editorRef.current.jsonEditor.setMode('view');
      } catch {
        // fallback: some versions may not support setMode
      }
    }
  }, [readOnly]);

  if (data === null || data === undefined) {
    return <div style={{ color: '#999', fontSize: 12, padding: 8 }}>null</div>;
  }

  return (
    <div ref={containerRef} style={{ width: '100%', minHeight: 80, maxHeight: 400, overflow: 'auto' }}>
      {jsonPath && (
        <div
          style={{
            marginBottom: 4,
            padding: '2px 8px',
            background: '#e6f7ff',
            borderRadius: 3,
            fontSize: 11,
            color: '#1890ff',
            borderBottom: '1px solid #91d5ff',
          }}
        >
          Path: {jsonPath}
        </div>
      )}
      <div className="jsoneditor-react-container" style={{ width: '100%' }}>
        <JsonEditorCore
          ref={editorRef}
          value={data}
          onChange={onEditorUpdate}
          mode={readOnly ? 'view' : 'tree'}
          allowedModes={readOnly ? ['view'] : ['tree', 'code', 'form', 'text', 'view']}
          history={!readOnly}
          search={true}
          mainMenuBar={true}
          navigationBar={true}
          statusBar={true}
        />
      </div>
    </div>
  );
};

export default JsonRenderer;
