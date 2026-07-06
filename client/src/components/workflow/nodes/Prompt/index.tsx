import React, { memo } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';

function PromptNode({ data, selected }: NodeProps) {
  return (
    <div
      style={{
        background: '#fff',
        border: selected ? '2px solid #1890ff' : '1px solid #d9d9d9',
        borderRadius: 8,
        padding: 12,
        minWidth: 180,
      }}
    >
      <Handle type="target" position={Position.Left} />
      <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>
        🤖 Prompt
      </div>
      {(data?.model as string) && (
        <div style={{ fontSize: 11, color: '#999', marginBottom: 2 }}>
          {data.model as string}
        </div>
      )}
      {(data?.prompt as string) && (
        <div
          style={{
            fontSize: 11,
            color: '#666',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            maxWidth: 160,
          }}
        >
          {(data.prompt as string).slice(0, 50)}...
        </div>
      )}
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

export default memo(PromptNode);
