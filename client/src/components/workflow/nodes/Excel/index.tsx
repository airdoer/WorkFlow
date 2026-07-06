import React, { memo } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';

function ExcelNode({ data, selected }: NodeProps) {
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
        📊 Excel
      </div>
      {(data?.p4Path as string) && (
        <div
          style={{
            fontSize: 11,
            color: '#999',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {data.p4Path as string}
        </div>
      )}
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

export default memo(ExcelNode);
