/**
 * JsonNode
 * - 接受上游文件内容（fileContent 端口）
 * - jsonPath 参数支持两种模式（互斥）：
 *   1. 直接在节点上手动输入 JSON Path 字符串
 *   2. 通过连线从上游节点（如 String 节点）获取
 * - 两者同时存在时，连线优先，并在节点上显示警告提示
 */

import React, { memo, useCallback, useState, useEffect } from 'react';
import { NodeProps, useReactFlow, useStore } from 'reactflow';
import { InfoCircleOutlined } from '@ant-design/icons';
import BaseNode, { NodeField, FieldTextInput } from '../BaseNode';
import { useWorkflowContext } from '../../WorkflowContext';

function JsonNode({ data, id, selected }: NodeProps) {
  const { setNodes, getNodes } = useReactFlow();
  const { getRunOutput } = useWorkflowContext();
  const nodeData = data as Record<string, any>;

  // 检测 jsonPath 端口是否有连线
  const hasJsonPathEdge = useStore(
    useCallback((s) => s.edges.some((e) => e.target === id && e.targetHandle === 'jsonPath'), [id]),
  );

  // 检测 fileContent 端口是否有连线
  const hasFileContentEdge = useStore(
    useCallback((s) => s.edges.some((e) => e.target === id && e.targetHandle === 'fileContent'), [id]),
  );

  const manualJsonPath = nodeData.jsonPath as string | undefined;
  const [overrideWarning, setOverrideWarning] = useState(false);

  // 当连线接入 jsonPath 且手动有值时，展示覆盖警告
  useEffect(() => {
    if (hasJsonPathEdge && manualJsonPath && manualJsonPath.trim() !== '') {
      setOverrideWarning(true);
      const timer = setTimeout(() => setOverrideWarning(false), 4000);
      return () => clearTimeout(timer);
    }
  }, [hasJsonPathEdge]);

  // Display the upstream jsonPath value (from external run output store)
  const upstreamJsonPath = useStore(
    useCallback(
      (s) => {
        if (!hasJsonPathEdge) return undefined;
        const edge = s.edges.find((e) => e.target === id && e.targetHandle === 'jsonPath');
        if (!edge) return undefined;
        const srcOutput = getRunOutput(edge.source);
        if (!srcOutput) return undefined;
        if (edge.sourceHandle && srcOutput[edge.sourceHandle] !== undefined) {
          return String(srcOutput[edge.sourceHandle]);
        }
        return srcOutput.value !== undefined ? String(srcOutput.value) : undefined;
      },
      [id, hasJsonPathEdge, getRunOutput],
    ),
  );

  const fields: NodeField[] = [
    {
      key: 'jsonPath',
      label: 'JSON Path',
      placeholder: '$.data.items（可选）',
      linkedPortKey: 'jsonPath',
      renderCustomField: (val, onChange, locked) => {
        if (locked && hasJsonPathEdge) {
          return (
            <input
              className="nodrag"
              type="text"
              value={upstreamJsonPath ?? '...等待上游运行'}
              readOnly
              placeholder="由连线提供"
              style={{
                width: '100%', fontSize: 11, padding: '3px 6px',
                border: '1px solid #d9d9d9', borderRadius: 3, boxSizing: 'border-box',
                background: '#f5f5f5', color: '#aaa', cursor: 'not-allowed',
              }}
            />
          );
        }
        return (
          <FieldTextInput
            value={String(val ?? '')}
            placeholder="$.data.items（可选）"
            onChange={onChange}
            style={{
              width: '100%', fontSize: 11, padding: '3px 6px',
              border: '1px solid #d9d9d9', borderRadius: 3, boxSizing: 'border-box',
              background: '#fff', color: '#333', cursor: 'text',
            }}
          />
        );
      },
    },
  ];

  // Override warning as extraContentBeforeFields
  const extraContentBeforeFields = overrideWarning ? (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 4,
      padding: '4px 6px', marginBottom: 6,
      background: '#fffbe6', border: '1px solid #ffe58f', borderRadius: 4,
      fontSize: 10, color: '#d48806',
    }}>
      <InfoCircleOutlined />
      <span>连线输入已覆盖手动填写的 JSON Path</span>
    </div>
  ) : undefined;

  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="📋"
      label="JSON"
      nodeType="json"
      fields={fields}
      extraContentBeforeFields={extraContentBeforeFields}
    />
  );
}

export default memo(JsonNode);
