import React, { memo } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from './BaseNode';

const KDIP_FIELDS: NodeField[] = [
  {
    key: 'serverName',
    label: '服务器名',
    type: 'text',
    required: true,
    placeholder: '由连线从 C7Server 节点提供',
    linkedPortKey: 'serverName',
  },
  {
    key: 'cmdKey',
    label: '任务名',
    type: 'select',
    required: true,
    options: [
      { label: 'kdip_game_get_config_for_qa', value: 'kdip_game_get_config_for_qa' },
      { label: 'kdip_game_get_service_switch_state', value: 'kdip_game_get_service_switch_state' },
      { label: 'kdip_game_get_hotfix_info', value: 'kdip_game_get_hotfix_info' },
      { label: 'kdip_game_get_server_run_info', value: 'kdip_game_get_server_run_info' },
      { label: 'kdip_game_get_stall_metric_info', value: 'kdip_game_get_stall_metric_info' },
    ],
  },
  {
    key: 'username',
    label: '用户名',
    type: 'text',
    required: true,
    placeholder: '如 chenzhixu（可由连线提供）',
    linkedPortKey: 'username',
  },
  {
    key: 'cmdParam',
    label: '附加参数 (JSON)',
    type: 'textarea',
    rows: 2,
    placeholder: '{"key": "value"}（可选）',
  },
];

function KdipNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="⚙️"
      label="KDIP"
      nodeType="kdip"
      fields={KDIP_FIELDS}
    />
  );
}

export default memo(KdipNode);
