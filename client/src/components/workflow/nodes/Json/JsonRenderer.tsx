import React, { useMemo, useState } from 'react';

/**
 * JSON result renderer with collapsible tree view.
 * Uses a simple recursive component for JSON visualization.
 */
interface JsonRendererProps {
  data: any;
  jsonPath?: string;
}

const JsonRenderer: React.FC<JsonRendererProps> = ({ data, jsonPath }) => {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const toggle = (path: string) => {
    setCollapsed((prev) => ({ ...prev, [path]: !prev[path] }));
  };

  if (data === null || data === undefined) {
    return <div style={{ color: '#999', fontSize: 12, padding: 8 }}>null</div>;
  }

  if (typeof data !== 'object') {
    return (
      <div style={{ padding: 8, fontFamily: 'monospace', fontSize: 12, color: '#333' }}>
        {String(data)}
      </div>
    );
  }

  return (
    <div style={{ fontFamily: "'SF Mono', 'Consolas', monospace", fontSize: 12, padding: 4 }}>
      {jsonPath && (
        <div style={{ marginBottom: 6, padding: '2px 6px', background: '#e6f7ff', borderRadius: 3, fontSize: 10, color: '#1890ff' }}>
          Path: {jsonPath}
        </div>
      )}
      <JsonTreeNode data={data} path="$" collapsed={collapsed} onToggle={toggle} />
    </div>
  );
};

interface JsonTreeNodeProps {
  data: any;
  path: string;
  collapsed: Record<string, boolean>;
  onToggle: (path: string) => void;
  depth?: number;
}

const JsonTreeNode: React.FC<JsonTreeNodeProps> = ({ data, path, collapsed, onToggle, depth = 0 }) => {
  const isCollapsed = collapsed[path] ?? (depth > 2);

  if (data === null) {
    return <span style={{ color: '#a5d6a7' }}>null</span>;
  }

  if (typeof data === 'boolean') {
    return <span style={{ color: '#ff9800' }}>{String(data)}</span>;
  }

  if (typeof data === 'number') {
    return <span style={{ color: '#2196f3' }}>{data}</span>;
  }

  if (typeof data === 'string') {
    const display = data.length > 80 ? data.slice(0, 80) + '...' : data;
    return <span style={{ color: '#4caf50' }}>"{display}"</span>;
  }

  const isArray = Array.isArray(data);
  const entries = isArray
    ? data.map((item, idx) => [String(idx), item] as [string, any])
    : Object.entries(data);
  const count = entries.length;

  const indent = depth * 16;

  if (count === 0) {
    return (
      <span style={{ paddingLeft: indent }}>
        {isArray ? '[]' : '{}'}
      </span>
    );
  }

  return (
    <div>
      <span
        style={{ paddingLeft: indent, cursor: 'pointer', userSelect: 'none' }}
        onClick={() => onToggle(path)}
      >
        <span style={{ color: '#666', fontSize: 10, marginRight: 4 }}>
          {isCollapsed ? '▶' : '▼'}
        </span>
        {isArray ? (
          <span style={{ color: '#722ed1' }}>{"Array[" + count + "]"}</span>
        ) : (
          <span style={{ color: '#1890ff' }}>{"Object{" + count + "}"}</span>
        )}
      </span>
      {!isCollapsed && (
        <div>
          {entries.map(([key, value]) => (
            <div key={key} style={{ paddingLeft: indent + 16 }}>
              <span style={{ color: isArray ? '#722ed1' : '#fa8c16' }}>
                {isArray ? `[${key}]` : key}
              </span>
              <span style={{ color: '#999', margin: '0 4px' }}>:</span>
              <JsonTreeNode
                data={value}
                path={`${path}.${key}`}
                collapsed={collapsed}
                onToggle={onToggle}
                depth={depth + 1}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default JsonRenderer;
