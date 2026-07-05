// 备份当前的 Toolbox 实现（点击创建）
import React from 'react';
import { nodeRegistryList } from './NodeRegistry';

interface ToolboxProps {
  editorRef: React.RefObject<any>;
}

const Toolbox: React.FC<ToolboxProps> = ({ editorRef }) => {
  const handleNodeClick = (nodeType: string) => {
    if (!editorRef.current) {
      console.error('Editor not initialized');
      return;
    }

    const editor = editorRef.current;
    
    // 使用 operation.addNode 创建节点
    try {
      if (editor.operation && typeof editor.operation.addNode === 'function') {
        // 从注册表中获取节点配置
        const registry = nodeRegistryList.find(r => r.type === nodeType);
        if (!registry) {
          console.error('Node registry not found for type:', nodeType);
          return;
        }

        const nodeConfig = {
          id: `${nodeType}_${Date.now()}`,
          type: nodeType,
          meta: { 
            position: { x: 300, y: 200 },
            ...(registry.registry.meta || {})
          },
          data: {},
          blocks: [],
          edges: [],
        };
        
        console.log('Creating node with registry:', registry);
        console.log('Node config:', nodeConfig);
        editor.operation.addNode(nodeConfig);
        console.log('Node created successfully');
      } else {
        console.error('operation.addNode not available');
      }
    } catch (error) {
      console.error('Failed to create node:', error);
    }
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
          onClick={() => handleNodeClick(entry.type)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '8px 12px',
            marginBottom: 6,
            background: '#fff',
            border: '1px solid #d9d9d9',
            borderRadius: 6,
            cursor: 'pointer',
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
