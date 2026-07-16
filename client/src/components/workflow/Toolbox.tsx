import React, { useCallback, useRef, useState, type DragEvent } from 'react';
import type { Node } from 'reactflow';
import { nodeRegistryList } from './NodeRegistry';
import { getFormatInitialData } from './nodes/Format';

interface ToolboxProps {
  nodes: Node[];
  setNodes: React.Dispatch<React.SetStateAction<Node[]>>;
  onAddNode?: () => void;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

const Toolbox: React.FC<ToolboxProps> = ({ nodes, setNodes, onAddNode, collapsed, onToggleCollapse }) => {
  const dragRef = useRef<{ nodeType: string; offsetX: number; offsetY: number } | null>(null);
  const [search, setSearch] = useState('');

  const handleNodeClick = useCallback(
    (nodeType: string) => {
      const id = `${nodeType}_${Date.now()}`;
      const initialData = nodeType === 'format' ? getFormatInitialData() : {};
      const newNode: Node = {
        id,
        type: nodeType,
        position: {
          x: Math.random() * 300 + 100,
          y: Math.random() * 200 + 100,
        },
        data: initialData,
      };
      setNodes((nds) => [...nds, newNode]);
      onAddNode?.();
    },
    [setNodes, onAddNode],
  );

  const handleDragStart = useCallback(
    (e: DragEvent<HTMLDivElement>, nodeType: string) => {
      e.dataTransfer.setData('application/reactflow', nodeType);
      e.dataTransfer.effectAllowed = 'move';
      const rect = e.currentTarget.getBoundingClientRect();
      e.dataTransfer.setDragImage(e.currentTarget, rect.width / 2, rect.height / 2);
    },
    [],
  );

  // Filter by search keyword
  const filtered = search.trim()
    ? nodeRegistryList.filter((e) =>
        e.label.toLowerCase().includes(search.toLowerCase()) ||
        (e.category || '').toLowerCase().includes(search.toLowerCase()) ||
        (e.description || '').toLowerCase().includes(search.toLowerCase()),
      )
    : nodeRegistryList;

  // Group by category (preserving original order)
  const grouped = filtered.reduce<Record<string, typeof nodeRegistryList>>((acc, entry) => {
    const cat = entry.category || '其他';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(entry);
    return acc;
  }, {});

  // Collapsed state — show a narrow sidebar strip with expand button
  if (collapsed) {
    return (
      <div
        style={{
          width: 36,
          borderRight: '1px solid #e8e8e8',
          background: '#fafafa',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          paddingTop: 8,
          gap: 6,
          flexShrink: 0,
        }}
      >
        <button
          onClick={onToggleCollapse}
          title="展开工具箱"
          style={{
            width: 28,
            height: 28,
            borderRadius: 4,
            border: '1px solid #d9d9d9',
            background: '#fff',
            cursor: 'pointer',
            fontSize: 14,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#595959',
          }}
        >
          ▶
        </button>
        <div style={{ writingMode: 'vertical-rl', fontSize: 11, color: '#999', letterSpacing: 2, marginTop: 8 }}>
          工具箱
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        width: 180,
        borderRight: '1px solid #e8e8e8',
        background: '#fafafa',
        display: 'flex',
        flexDirection: 'column',
        position: 'relative',
        flexShrink: 0,
        height: '100%',
      }}
    >
      {/* Fixed header — always visible */}
      <div style={{ padding: '10px 10px 0', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
          <div style={{ fontWeight: 600, fontSize: 14 }}>节点工具箱</div>
          <button
            onClick={onToggleCollapse}
            title="折叠工具箱"
            style={{
              width: 20, height: 20, borderRadius: 3,
              border: 'none', background: 'transparent',
              cursor: 'pointer', fontSize: 12, color: '#999',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            ◀
          </button>
        </div>

        {/* Search input */}
        <div style={{ position: 'relative', marginBottom: 6 }}>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索节点..."
            style={{
              width: '100%',
              fontSize: 12,
              padding: '4px 24px 4px 8px',
              border: '1px solid #d9d9d9',
              borderRadius: 4,
              outline: 'none',
              boxSizing: 'border-box',
              background: '#fff',
              color: '#262626',
            }}
          />
          {search && (
            <span
              onClick={() => setSearch('')}
              style={{
                position: 'absolute', right: 6, top: '50%', transform: 'translateY(-50%)',
                cursor: 'pointer', color: '#bfbfbf', fontSize: 12, lineHeight: 1,
              }}
            >
              ✕
            </span>
          )}
        </div>
        <div style={{ fontSize: 10, color: '#999', marginBottom: 6 }}>点击添加 / 拖拽到画布</div>
      </div>

      {/* Scrollable body */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '0 10px 12px' }}>
      {Object.keys(grouped).length === 0 ? (
        <div style={{ fontSize: 12, color: '#bfbfbf', textAlign: 'center', marginTop: 20 }}>
          无匹配节点
        </div>
      ) : (
        Object.entries(grouped).map(([category, entries]) => (
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
        ))
      )}
      </div>
    </div>
  );
};

export default Toolbox;
