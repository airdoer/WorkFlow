import React, { useCallback } from 'react';
import type { Node } from 'reactflow';
import { nodeRegistryList } from './NodeRegistry';

interface ToolboxProps {
  nodes: Node[];
  setNodes: React.Dispatch<React.SetStateAction<Node[]>>;
}

const Toolbox: React.FC<ToolboxProps> = ({ nodes, setNodes }) => {
  const handleNodeClick = useCallback(
    (nodeType: string) => {
      const id = `${nodeType}_${Date.now()}`;
      const newNode: Node = {
        id,
        type: nodeType,
        position: {
          x: Math.random() * 300 + 100,
          y: Math.random() * 200 + 100,
        },
        data: {},
      };
      setNodes((nds) => [...nds, newNode]);
    },
    [setNodes],
  );

  // Group by category
  const grouped = nodeRegistryList.reduce<Record<string, typeof nodeRegistryList>>((acc, entry) => {
    const cat = entry.category || '其他';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(entry);
    return acc;
  }, {});

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
      {Object.entries(grouped).map(([category, entries]) => (
        <div key={category} style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 10, color: '#999', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 1 }}>
            {category}
          </div>
          {entries.map((entry) => (
            <div
              key={entry.type}
              onClick={() => handleNodeClick(entry.type)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '8px 12px',
                marginBottom: 4,
                background: '#fff',
                border: '1px solid #d9d9d9',
                borderRadius: 6,
                cursor: 'pointer',
                fontSize: 13,
                transition: 'border-color 0.2s',
              }}
              title={entry.description}
            >
              {entry.icon}
              <span>{entry.label}</span>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
};

export default Toolbox;
