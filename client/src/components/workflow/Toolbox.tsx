import React, { useCallback, useRef, type DragEvent } from 'react';
import type { Node } from 'reactflow';
import { nodeRegistryList } from './NodeRegistry';

interface ToolboxProps {
  nodes: Node[];
  setNodes: React.Dispatch<React.SetStateAction<Node[]>>;
  onAddNode?: () => void;
}

const Toolbox: React.FC<ToolboxProps> = ({ nodes, setNodes, onAddNode }) => {
  const dragRef = useRef<{ nodeType: string; offsetX: number; offsetY: number } | null>(null);

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
      onAddNode?.();
    },
    [setNodes, onAddNode],
  );

  const handleDragStart = useCallback(
    (e: DragEvent<HTMLDivElement>, nodeType: string) => {
      // Store the node type and offset in dataTransfer
      e.dataTransfer.setData('application/reactflow', nodeType);
      e.dataTransfer.effectAllowed = 'move';
      // Set drag image offset to center of the element
      const rect = e.currentTarget.getBoundingClientRect();
      e.dataTransfer.setDragImage(e.currentTarget, rect.width / 2, rect.height / 2);
    },
    [],
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
      <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 14 }}>节点工具箱</div>
      <div style={{ fontSize: 10, color: '#999', marginBottom: 12 }}>点击添加 / 拖拽到画布</div>
      {Object.entries(grouped).map(([category, entries]) => (
        <div key={category} style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 10, color: '#999', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 1 }}>
            {category}
          </div>
          {entries.map((entry) => (
            <div
              key={entry.type}
              draggable
              onDragStart={(e) => handleDragStart(e, entry.type)}
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
                cursor: 'grab',
                fontSize: 13,
                transition: 'border-color 0.2s, box-shadow 0.2s',
                userSelect: 'none',
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
