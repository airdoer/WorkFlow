import React, { memo, useEffect, useMemo, useState } from 'react';
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

/* ─── Operation option type (now with args_def) ───────────────────────── */
interface ArgDef {
  key: string;
  label: string;
  type: 'text' | 'select';
  required?: boolean;
  placeholder?: string;
  options?: { label: string; value: string }[];
}

interface OperationOption {
  label: string;
  value: string;
  template_id?: number;
  description: string;
  args_def: ArgDef[];
}

/* ─── SealNode ─────────────────────────────────────────────────────────── */
function SealNode({ data, id, selected }: NodeProps) {
  const [serverOptions, setServerOptions] = useState<ServerOption[]>([]);
  const [operationOptions, setOperationOptions] = useState<OperationOption[]>([]);

  const nodeData = data as Record<string, any>;
  const currentOperation = nodeData.operation || '';

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

  /* Find the args_def for the currently selected operation */
  const currentArgsDef = useMemo<ArgDef[]>(() => {
    const op = operationOptions.find((o) => o.value === currentOperation);
    return op?.args_def || [];
  }, [currentOperation, operationOptions]);

  /* Build the dynamic extra-arg fields based on args_def.
     Keys are flat in nodeData, e.g. "source_file", "mode" — 
     the backend executor collects them into extraArgs. */
  const dynamicArgFields = useMemo<NodeField[]>(() => {
    if (!currentArgsDef.length) return [];

    return currentArgsDef.map((def): NodeField => {
      if (def.type === 'select' && def.options?.length) {
        return {
          key: def.key,
          label: def.label,
          required: !!def.required,
          renderCustomField: (val, onChange, locked) => (
            <StyledSelect
              value={val || ''}
              options={def.options!.map((o) => ({ label: o.label, value: o.value, type: '' as const }))}
              onChange={(v: string) => onChange(v)}
              locked={locked}
              required={!!def.required}
              placeholder={def.placeholder || `请选择${def.label}`}
            />
          ),
        };
      }
      // text type
      return {
        key: def.key,
        label: def.label,
        type: 'text',
        required: !!def.required,
        placeholder: def.placeholder || '',
      };
    });
  }, [currentArgsDef]);

  const SEAL_FIELDS: NodeField[] = useMemo(() => {
    const base: NodeField[] = [
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
    ];

    // Insert dynamic args after operation, before executor
    base.push(...dynamicArgFields);

    base.push({
      key: 'executor',
      label: '执行人',
      type: 'text',
      placeholder: 'chenzhixu',
    });

    return base;
  }, [serverOptions, operationOptions, dynamicArgFields]);

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
