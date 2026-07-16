import React, { memo, useCallback, useEffect, useMemo, useState } from 'react';
import { NodeProps, useReactFlow } from 'reactflow';
import { Select } from 'antd';
import BaseNode, { NodeField } from '../BaseNode';
import { PortDefinition } from '../PortTypes';
import { FlowApi } from '../../services/FlowApi';
import { StyledSelect, TypedOption } from '../SharedStyledSelect';

/* ─── Server option type ──────────────────────────────────────────────── */
interface ServerOption {
  label: string;
  value: string;
  type: 'server' | 'group';
  namespace?: string;
  server_id?: number | string;
  tree_id?: number | null;
  seal_env?: string; // 'prod' | 'test' | ''
}

/* ─── Operation option type ───────────────────────────────────────────── */
interface ArgDef {
  key: string;
  label: string;
  type: 'text' | 'select' | 'multiselect';
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
  seal_env?: string; // 'prod' | 'test' | ''
}

/* ─── SealNode ─────────────────────────────────────────────────────────── */
function SealNode({ data, id, selected }: NodeProps) {
  const { setNodes } = useReactFlow();
  const [allServerOptions, setAllServerOptions] = useState<ServerOption[]>([]);
  const [allOperationOptions, setAllOperationOptions] = useState<OperationOption[]>([]);

  const nodeData = data as Record<string, any>;
  const currentServer = nodeData.serverName || '';
  const currentOperation = nodeData.operation || '';

  useEffect(() => {
    FlowApi.getC7ServerOptions()
      .then((opts) => {
        // Seal 节点只展示 tree_id 有值的服务器/分组
        const sealOnly = (opts as ServerOption[]).filter((s) => s.tree_id);
        setAllServerOptions(sealOnly);
      })
      .catch((err) => console.warn('[SealNode] Failed to load server options:', err));
  }, []);

  useEffect(() => {
    FlowApi.getSealOperationOptions()
      .then((opts) => setAllOperationOptions(opts as OperationOption[]))
      .catch((err) => console.warn('[SealNode] Failed to load operation options:', err));
  }, []);

  /* ── Derive the current seal_env from whichever is selected ──────── */
  const activeSealEnv = useMemo<string>(() => {
    // If server is selected, use its seal_env
    const serverOpt = allServerOptions.find((s) => s.value === currentServer);
    if (serverOpt?.seal_env) return serverOpt.seal_env;
    // If operation is selected, use its seal_env
    const opOpt = allOperationOptions.find((o) => o.value === currentOperation);
    if (opOpt?.seal_env) return opOpt.seal_env;
    return ''; // no filter
  }, [currentServer, currentOperation, allServerOptions, allOperationOptions]);

  /* ── Filtered server options based on active seal_env ────────────── */
  const filteredServerOptions = useMemo<ServerOption[]>(() => {
    if (!activeSealEnv) return allServerOptions;
    return allServerOptions.filter((s) => s.seal_env === activeSealEnv);
  }, [allServerOptions, activeSealEnv]);

  /* ── Filtered operation options based on active seal_env ─────────── */
  const filteredOperationOptions = useMemo<OperationOption[]>(() => {
    if (!activeSealEnv) return allOperationOptions;
    return allOperationOptions.filter((o) => o.seal_env === activeSealEnv);
  }, [allOperationOptions, activeSealEnv]);

  /* Find the args_def for the currently selected operation */
  const currentArgsDef = useMemo<ArgDef[]>(() => {
    const op = allOperationOptions.find((o) => o.value === currentOperation);
    return op?.args_def || [];
  }, [currentOperation, allOperationOptions]);

  /* Dynamic input ports from args_def */
  const dynamicPorts = useMemo<PortDefinition[]>(() => {
    const ports: PortDefinition[] = [
      { key: 'serverName', label: '服务器名', type: 'string', direction: 'input', maxConnections: 1 },
    ];
    for (const def of currentArgsDef) {
      ports.push({
        key: def.key,
        label: def.label,
        type: 'string',
        direction: 'input',
        maxConnections: 1,
      });
    }
    ports.push(
      { key: 'success', label: '执行结果', type: 'boolean', direction: 'output' },
      { key: 'taskUrl', label: '任务链接', type: 'string', direction: 'output' },
      { key: 'taskId', label: '任务ID', type: 'string', direction: 'output' },
    );
    return ports;
  }, [currentArgsDef]);

  /* Build dynamic arg fields */
  const dynamicArgFields = useMemo<NodeField[]>(() => {
    if (!currentArgsDef.length) return [];

    return currentArgsDef.map((def): NodeField => {
      if (def.type === 'multiselect' && def.options?.length) {
        return {
          key: def.key,
          label: def.label,
          required: !!def.required,
          linkedPortKey: def.key,
          renderCustomField: (val, onChange, locked) => (
            <div className="nodrag nopan nowheel" onWheel={(e) => e.stopPropagation()}>
              <Select
                mode="multiple"
                size="small"
                disabled={locked}
                value={Array.isArray(val) ? val : (val ? [val] : [])}
                onChange={(v) => onChange(v)}
                options={def.options!.map((o) => ({ label: o.label, value: o.value }))}
                placeholder={def.placeholder || `请选择${def.label}`}
                style={{ width: '100%', fontSize: 11 }}
                maxTagCount={2}
                maxTagTextLength={8}
                allowClear
                getPopupContainer={(node) => node.parentElement || document.body}
                styles={{ popup: { root: { fontSize: 11 } } }}
              />
            </div>
          ),
        };
      }
      if (def.type === 'select' && def.options?.length) {
        return {
          key: def.key,
          label: def.label,
          required: !!def.required,
          linkedPortKey: def.key,
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
      return {
        key: def.key,
        label: def.label,
        type: 'text',
        required: !!def.required,
        placeholder: def.placeholder || '',
        linkedPortKey: def.key,
      };
    });
  }, [currentArgsDef]);

  /* Update node data helper */
  const updateNodeData = useCallback(
    (updater: (d: Record<string, any>) => Record<string, any>) => {
      setNodes((nds) =>
        nds.map((n) => (n.id === id ? { ...n, data: updater(n.data as Record<string, any>) } : n)),
      );
    },
    [id, setNodes],
  );

  /* Handle server selection — clear operation if it doesn't match new seal_env */
  const handleServerChange = useCallback(
    (val: string) => {
      const serverOpt = allServerOptions.find((s) => s.value === val);
      const newEnv = serverOpt?.seal_env || '';
      updateNodeData((d) => {
        const next: Record<string, any> = { ...d, serverName: val };
        // If current operation's seal_env doesn't match, clear it
        if (d.operation) {
          const currentOp = allOperationOptions.find((o) => o.value === d.operation);
          if (currentOp && currentOp.seal_env && newEnv && currentOp.seal_env !== newEnv) {
            next.operation = '';
            // Also clear dynamic arg values
            if (currentOp.args_def) {
              for (const def of currentOp.args_def) {
                if (next[def.key] !== undefined) delete next[def.key];
              }
            }
          }
        }
        return next;
      });
    },
    [allServerOptions, allOperationOptions, updateNodeData],
  );

  /* Handle operation selection — clear server if it doesn't match new seal_env */
  const handleOperationChange = useCallback(
    (val: string) => {
      const opOpt = allOperationOptions.find((o) => o.value === val);
      const newEnv = opOpt?.seal_env || '';
      updateNodeData((d) => {
        const next: Record<string, any> = { ...d, operation: val };
        // If current server's seal_env doesn't match, clear it
        if (d.serverName) {
          const currentSrv = allServerOptions.find((s) => s.value === d.serverName);
          if (currentSrv && currentSrv.seal_env && newEnv && currentSrv.seal_env !== newEnv) {
            next.serverName = '';
          }
        }
        // Clear old dynamic arg values from previous operation
        const oldOp = allOperationOptions.find((o) => o.value === d.operation);
        if (oldOp?.args_def) {
          for (const def of oldOp.args_def) {
            if (next[def.key] !== undefined) delete next[def.key];
          }
        }
        return next;
      });
    },
    [allServerOptions, allOperationOptions, updateNodeData],
  );

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
            options={filteredServerOptions as TypedOption[]}
            onChange={handleServerChange}
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
            options={filteredOperationOptions as TypedOption[]}
            onChange={handleOperationChange}
            locked={locked}
            required
            placeholder="请选择流程"
            showDescription
          />
        ),
      },
    ];

    base.push(...dynamicArgFields);

    base.push({
      key: 'executor',
      label: '执行人',
      type: 'text',
      placeholder: 'chenzhixu',
    });

    return base;
  }, [filteredServerOptions, filteredOperationOptions, dynamicArgFields, handleServerChange, handleOperationChange]);

  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="🐾"
      label="Seal 海豹"
      nodeType="seal"
      fields={SEAL_FIELDS}
      overridePorts={dynamicPorts}
    />
  );
}

export default memo(SealNode);
