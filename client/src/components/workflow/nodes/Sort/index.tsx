import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const SORT_FIELDS: NodeField[] = [
  { key: 'key', label: '排序字段', placeholder: 'age（对象列表时使用）' },
  { key: 'order', label: '排序方向', type: 'select', options: [{ label: '升序 (asc)', value: 'asc' }, { label: '降序 (desc)', value: 'desc' }], placeholder: 'asc' },
];

function SortNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="🔢"
      label="Sort 排序"
      nodeType="sort"
      fields={SORT_FIELDS}
    />
  );
}

export default memo(SortNode);
