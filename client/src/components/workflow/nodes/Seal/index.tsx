import React, { memo, useEffect, useState } from 'react';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';
import { FlowApi } from '../../services/FlowApi';
import { StyledSelect, TypedOption } from '../SharedStyledSelect';

/* ─── Server option type ──────────────────────────────────────────────── */
interface ServerOption {
  label: string;
  value: string;
  type: 'server' | 'group';
  namespace?: string;
  server_id?: number | string;
}

/* ─── Operation option type ────────────────────────────────────────────── */
interface OperationOption {
  label: string;
  value: string;
  template_id?: number;
  description: string;
}

/* ─── SealNode ─────────────────────────────────────────────────────────── */
function SealNode({ data, id, selected }: NodeProps) {
  const [serverOptions, setServerOptions] = useState<ServerOption[]>([]);
  const [operationOptions, setOperationOptions] = useState<OperationOption[]>([]);

  useEffect(() => {
    FlowApi.getC7ServerOptions()
      .then((opts) => setServerOptions(opts as ServerOption[]))
      .catch((err) => console.warn('[SealNode] Failed to load server options:', err));
  }, []);

  useEffect(() => {
    FlowApi.getSealOperationOptions()
      .then((opts) => setOperationOptions(opts as OperationOption[]))
      .catch((err) => console.warn('[SealNode] Failed to load operation options:', err));
  }, []);

  const SEAL_FIELDS: NodeField[] = [
    {
      key: 'serverName',
      label: '目标服务器',
      required: true,
      linkedPortKey: 'serverName',
      renderCustomField: (val, onChange, locked) => (
        <StyledSelect
          value={val || ''}
          options={serverOptions as TypedOption[]}
          onChange={onChange}
          locked={locked}
          required
          placeholder="请选择服务器或分组"
          showTypeBadge
        />
      ),
    },
    {
      key: 'operation',
      label: '流程',
      required: true,
      renderCustomField: (val, onChange, locked) => (
        <StyledSelect
          value={val || ''}
          options={operationOptions as TypedOption[]}
          onChange={onChange}
          locked={locked}
          required
          placeholder="请选择流程"
          showDescription
        />
      ),
    },
    {
      key: 'executor',
      label: '执行人',
      type: 'text',
      placeholder: 'chenzhixu',
    },
  ];

  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="🐾"
      label="Seal 海豹"
      nodeType="seal"
      fields={SEAL_FIELDS}
    />
  );
}

export default memo(SealNode);
