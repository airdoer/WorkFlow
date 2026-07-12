import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const CRON_FIELDS: NodeField[] = [
  {
    key: 'cronExpr',
    label: 'Cron 表达式',
    type: 'text',
    required: true,
    placeholder: '0 2 * * 0（分 时 日 月 周）',
    linkedPortKey: 'valueIn',
  },
];

function CronNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="⏰"
      label="Cron"
      nodeType="cron"
      fields={CRON_FIELDS}
    />
  );
}

export default memo(CronNode);
