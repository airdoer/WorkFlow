/**
 * ValueNode — 通用基础类型节点基础组件
 *
 * 支持两种输入模式（互斥）：
 * 1. 直接在节点上手动输入值
 * 2. 通过连线从上游节点获取输入值
 *
 * 当有连线输入时，手动输入框被禁用并显示提示；
 * 当手动有值且连线尝试覆盖时，通过连接事件检测并展示提示。
 *
 * 现在统一使用 BaseNode 渲染，通过 renderCustomField 实现连线锁定和类型渲染。
 */

import React, { useCallback, useState, useEffect } from 'react';
import { NodeProps, useReactFlow, useStore } from 'reactflow';
import BaseNode, { NodeField, FieldTextInput, RunStatus } from './BaseNode';
import { useWorkflowContext } from '../WorkflowContext';

export interface ValueNodeProps {
  id: string;
  data: Record<string, unknown>;
  selected: boolean;
  icon: string;
  label: string;
  nodeType: string;
  valueKey: string;
  portColor: string;
  inputType: 'text' | 'number' | 'boolean';
  outputPortKey?: string;
  outputPortLabel?: string;
  inputPortKey?: string;
  inputPortLabel?: string;
}

const ValueNode: React.FC<ValueNodeProps> = ({
  id,
  data,
  selected,
  icon,
  label,
  nodeType,
  valueKey,
  portColor,
  inputType,
  outputPortKey = 'value',
  outputPortLabel = '输出值',
  inputPortKey = 'valueIn',
  inputPortLabel = '输入值',
}) => {
  const { setNodes, getEdges, getNodes } = useReactFlow();
  const { getRunOutput } = useWorkflowContext();
  const [overrideWarning, setOverrideWarning] = useState(false);

  const runStatus = (data._runStatusHint as RunStatus) || 'idle';

  // 检测是否有连线连接到输入端口
  const hasIncomingEdge = useStore(
    useCallback(
      (s) => s.edges.some((e) => e.target === id && e.targetHandle === inputPortKey),
      [id, inputPortKey],
    ),
  );

  // 从连线获取上游值（用于显示）
  const upstreamValue = (() => {
    const edges = getEdges();
    const inEdge = edges.find((e) => e.target === id && e.targetHandle === inputPortKey);
    if (!inEdge) return undefined;
    const srcOutput = getRunOutput(inEdge.source);
    if (!srcOutput) return undefined;
    if (inEdge.sourceHandle && srcOutput[inEdge.sourceHandle] !== undefined) {
      return srcOutput[inEdge.sourceHandle];
    }
    return srcOutput[outputPortKey] ?? Object.values(srcOutput)[0];
  })();

  const manualValue = data[valueKey];

  // 当有连线且有手动值时，短暂显示覆盖警告
  useEffect(() => {
    if (hasIncomingEdge && manualValue !== undefined && manualValue !== null && manualValue !== '') {
      setOverrideWarning(true);
      const timer = setTimeout(() => setOverrideWarning(false), 4000);
      return () => clearTimeout(timer);
    }
  }, [hasIncomingEdge]);

  // Build field with renderCustomField
  const fields: NodeField[] = [
    {
      key: valueKey,
      label: label,
      type: inputType === 'boolean' ? 'text' : inputType,
      required: true,
      linkedPortKey: inputPortKey,
      renderCustomField: (val, onChange, locked) => {
        if (locked && hasIncomingEdge) {
          // Connected: show "🔗 已连线，使用上游输入" style
          if (inputType === 'boolean') {
            const boolVal = upstreamValue ?? (data[valueKey] as boolean | undefined);
            return (
              <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 4, padding: '3px 6px',
                background: '#f0f5ff', border: '1px solid #adc6ff', borderRadius: 3, fontSize: 10, color: '#2f54eb', minWidth: 0 }}>
                <span>🔗 已连线，使用上游输入</span>
                <span style={{ marginLeft: 'auto', fontSize: 9, color: '#999' }}>{boolVal ? 'true' : 'false'}</span>
              </div>
            );
          }
          return (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 4, padding: '3px 6px',
              background: '#f0f5ff', border: '1px solid #adc6ff', borderRadius: 3, fontSize: 10, color: '#2f54eb', minWidth: 0 }}>
              <span>🔗 已连线，使用上游输入</span>
            </div>
          );
        }

        // Not connected: render appropriate input
        if (inputType === 'boolean') {
          const boolVal = data[valueKey] as boolean | undefined;
          return (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <label style={{ fontSize: 11, color: '#333', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
                <input
                  className="nodrag"
                  type="checkbox"
                  checked={!!boolVal}
                  onChange={(e) => { e.stopPropagation(); onChange(e.target.checked); }}
                  style={{ cursor: 'pointer' }}
                />
                <span>{boolVal ? 'true' : 'false'}</span>
              </label>
            </div>
          );
        }

        if (inputType === 'number') {
          return (
            <FieldTextInput
              value={String((data[valueKey] as number) ?? '')}
              onChange={(v) => onChange(parseFloat(v) || 0)}
              placeholder="输入数值"
              style={{
                width: '100%', fontSize: 11, padding: '3px 6px',
                border: '1px solid #d9d9d9', borderRadius: 3, boxSizing: 'border-box',
              }}
            />
          );
        }

        return (
          <FieldTextInput
            value={String((data[valueKey] as string) ?? '')}
            onChange={onChange}
            placeholder="输入字符串"
            style={{
              width: '100%', fontSize: 11, padding: '3px 6px',
              border: '1px solid #d9d9d9', borderRadius: 3, boxSizing: 'border-box',
            }}
          />
        );
      },
    },
  ];

  return (
    <BaseNode
      data={data}
      id={id}
      selected={selected}
      icon={icon}
      label={label}
      nodeType={nodeType}
      fields={fields}
    />
  );
};

export default ValueNode;
