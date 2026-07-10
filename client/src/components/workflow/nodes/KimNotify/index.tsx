import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';

const KIM_NOTIFY_FIELDS: NodeField[] = [
  {
    key: 'username',
    label: '用户名（二选一）',
    type: 'text',
    placeholder: '如 chenzhixu（与 groupId 二选一）',
    linkedPortKey: 'username',
  },
  {
    key: 'groupId',
    label: 'GroupId（二选一）',
    type: 'text',
    placeholder: '如 5106961315438619（与 username 二选一）',
    linkedPortKey: 'groupId',
  },
  {
    key: 'message',
    label: '消息内容',
    type: 'textarea',
    rows: 3,
    required: true,
    placeholder: '发送的消息内容',
    linkedPortKey: 'message',
  },
];

function KimNotifyNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="💬"
      label="Kim 通知"
      nodeType="kimnotify"
      fields={KIM_NOTIFY_FIELDS}
    />
  );
}

export default memo(KimNotifyNode);
