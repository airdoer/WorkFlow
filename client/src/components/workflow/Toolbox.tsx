import React from 'react';
import { nodeRegistryList } from './NodeRegistry';

const Toolbox: React.FC = () => {
  const onDragStart = (e: React.DragEvent, nodeType: string) => {
    e.dataTransfer.setData('workflow-node-type', nodeType);
  };

  return (
    <div
      style={{
        width: 180,
        borderRight: '1px solid #e8e8e8',
        padding: 12,
        background: '#fafafa',
        overflowY: 'auto',
      }}
    >
      <div style={{ fontWeight: 600, marginBottom: 12, fontSize: 14 }}>节点工具箱</div>
      {nodeRegistryList.map((entry) => (
        <div
          key={entry.type}
          draggable
          onDragStart={(e) => onDragStart(e, entry.type)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '8px 12px',
            marginBottom: 6,
            background: '#fff',
            border: '1px solid #d9d9d9',
            borderRadius: 6,
            cursor: 'grab',
            fontSize: 13,
          }}
        >
          {entry.icon}
          <span>{entry.label}</span>
        </div>
      ))}
    </div>
  );
};

export default Toolbox;
