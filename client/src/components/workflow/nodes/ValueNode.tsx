/**
 * ValueNode — 通用基础类型节点基础组件
 *
 * 支持两种输入模式（互斥）：
 * 1. 直接在节点上手动输入值
 * 2. 通过连线从上游节点获取输入值
 *
 * 当有连线输入时，手动输入框被禁用并显示提示；
 * 当手动有值且连线尝试覆盖时，通过连接事件检测并展示提示。
 */

import React, { useCallback, useMemo, useState, useEffect } from 'react';
import { Handle, Position, useReactFlow, useStore } from 'reactflow';
import {
  PlayCircleOutlined,
  LoadingOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  InfoCircleOutlined,
  ExpandOutlined,
} from '@ant-design/icons';
import { FlowApi } from '../services/FlowApi';
import { useWorkflowContext } from '../WorkflowContext';
import NodeDetailModal from './NodeDetailModal';
import { NodeField, FieldTextInput, SeqBadge } from './BaseNode';

export type RunStatus = 'idle' | 'running' | 'success' | 'error';

export interface ValueNodeProps {
  id: string;
  data: Record<string, unknown>;
  selected: boolean;
  /** 节点图标 emoji */
  icon: string;
  /** 节点显示名 */
  label: string;
  /** 注册的 nodeType 字符串 */
  nodeType: string;
  /** 存放节点值的 data key */
  valueKey: string;
  /** 节点输出端口颜色 */
  portColor: string;
  /** 输入控件类型 */
  inputType: 'text' | 'number' | 'boolean';
  /** 输出端口 key（与 PortTypes 对应） */
  outputPortKey?: string;
  /** 输出端口标签 */
  outputPortLabel?: string;
  /** 输入端口 key（与 PortTypes 对应，用于检测连线） */
  inputPortKey?: string;
  /** 输入端口标签 */
  inputPortLabel?: string;
}

const STATUS_CONFIG = {
  idle: { color: '#8c8c8c', bg: '#f5f5f5', icon: PlayCircleOutlined, title: '运行节点' },
  running: { color: '#1890ff', bg: '#e6f7ff', icon: LoadingOutlined, title: '运行中...' },
  success: { color: '#52c41a', bg: '#f6ffed', icon: CheckCircleOutlined, title: '运行成功' },
  error: { color: '#ff4d4f', bg: '#fff2f0', icon: CloseCircleOutlined, title: '运行失败' },
};

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
  const { setNodes, getEdges, getNode, getNodes } = useReactFlow();
  const { workflowId, onNodeUpdate, ensureSaved, multiSelectedIds, compactMode, detailNodeId, setDetailNodeId, getRunStatus, getRunOutput } = useWorkflowContext();
  const detailOpen = detailNodeId === id;
  const [overrideWarning, setOverrideWarning] = useState(false);

  const runStatus = (getRunStatus(id) as RunStatus) || (data._runStatusHint as RunStatus) || 'idle';
  const runOutput = getRunOutput(id);
  const statusCfg = STATUS_CONFIG[runStatus];

  // Whether this node is part of a multi-selection
  const isMultiSelected = selected && multiSelectedIds.size > 0 && multiSelectedIds.has(id);

  // 检测是否有连线连接到输入端口
  const hasIncomingEdge = useStore(
    useCallback(
      (s) => s.edges.some((e) => e.target === id && e.targetHandle === inputPortKey),
      [id, inputPortKey],
    ),
  );

  // 从连线获取上游值（用于显示）— 从外部 store 读取
  const upstreamValue = useMemo(() => {
    const edges = getEdges();
    const inEdge = edges.find((e) => e.target === id && e.targetHandle === inputPortKey);
    if (!inEdge) return undefined;
    const srcOutput = getRunOutput(inEdge.source);
    if (!srcOutput) return undefined;
    if (inEdge.sourceHandle && srcOutput[inEdge.sourceHandle] !== undefined) {
      return srcOutput[inEdge.sourceHandle];
    }
    return srcOutput[outputPortKey] ?? Object.values(srcOutput)[0];
  }, [getEdges, getRunOutput, id, inputPortKey, outputPortKey]);

  const manualValue = data[valueKey];

  // 当有连线且有手动值时，短暂显示覆盖警告
  useEffect(() => {
    if (hasIncomingEdge && manualValue !== undefined && manualValue !== null && manualValue !== '') {
      setOverrideWarning(true);
      const timer = setTimeout(() => setOverrideWarning(false), 4000);
      return () => clearTimeout(timer);
    }
  }, [hasIncomingEdge]);

  const handleValueChange = useCallback(
    (val: any) => {
      if (hasIncomingEdge) return; // 有连线时禁止手动修改
      setNodes((nds) =>
        nds.map((n) => (n.id === id ? { ...n, data: { ...n.data, [valueKey]: val } } : n)),
      );
    },
    [id, setNodes, valueKey, hasIncomingEdge],
  );

  // 计算实际使用的值（连线优先）
  const effectiveValue = hasIncomingEdge ? upstreamValue : manualValue;
  const canRun = runStatus !== 'running' && (hasIncomingEdge ? upstreamValue !== undefined : manualValue !== undefined && manualValue !== null && String(manualValue).trim() !== '');

  const handleRun = useCallback(
    async (e: React.MouseEvent) => {
      e.stopPropagation();
      if (!canRun) return;

      // Ensure workflow is saved before running
      const savedId = await ensureSaved();
      if (!savedId) return;

      // Use lightweight _runStatusHint instead of full _runStatus + _runOutput
      setNodes((nds) =>
        nds.map((n) =>
          n.id === id ? { ...n, data: { ...n.data, _runStatusHint: 'running' } } : n,
        ),
      );

      // Build node data overrides: current node config + other nodes' cached outputs
      const allNodes = getNodes();
      const nodeDataOverrides: Record<string, any> = {};

      // Override current node's config with latest field values
      nodeDataOverrides[id] = { [valueKey]: effectiveValue };

      // Pass cached outputs of other nodes from the external store
      for (const n of allNodes) {
        if (n.id !== id) {
          const nodeOutput = getRunOutput(n.id);
          if (nodeOutput && !nodeOutput.error) {
            nodeDataOverrides[n.id] = nodeOutput;
          }
        }
      }

      FlowApi.runNodeWS(
        savedId,
        id,
        nodeDataOverrides,
        onNodeUpdate,
        (_status, error) => {
          if (error) console.error('[ValueNode] NodeRun error:', error);
        },
      );
    },
    [id, nodeType, effectiveValue, valueKey, setNodes, canRun, ensureSaved, onNodeUpdate, getNodes, getRunOutput],
  );

  const borderColor =
    runStatus === 'success'
      ? '#52c41a'
      : runStatus === 'error'
        ? '#ff4d4f'
        : runStatus === 'running'
          ? '#1890ff'
          : selected
            ? '#1890ff'
            : '#d9d9d9';

  // 为 NodeDetailModal 提供一个 fields 列表
  const fields: NodeField[] = [
    { key: valueKey, label: label, type: inputType === 'boolean' ? 'text' : inputType, required: true, linkedPortKey: inputPortKey },
  ];

  const renderInput = () => {
    const inputStyle: React.CSSProperties = {
      width: '100%',
      fontSize: 11,
      padding: '3px 6px',
      border: `1px solid ${hasIncomingEdge ? '#d9d9d9' : (!manualValue && !hasIncomingEdge ? '#ffccc7' : '#d9d9d9')}`,
      borderRadius: 3,
      boxSizing: 'border-box',
      background: hasIncomingEdge ? '#f5f5f5' : '#fff',
      color: hasIncomingEdge ? '#aaa' : '#333',
      cursor: hasIncomingEdge ? 'not-allowed' : 'text',
    };

    if (inputType === 'boolean') {
      const boolVal = hasIncomingEdge
        ? upstreamValue
        : (data[valueKey] as boolean | undefined);

      return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <label style={{ fontSize: 11, color: hasIncomingEdge ? '#aaa' : '#333', cursor: hasIncomingEdge ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
            <input
              className="nodrag"
              type="checkbox"
              checked={!!boolVal}
              disabled={hasIncomingEdge}
              onChange={(e) => {
                e.stopPropagation();
                handleValueChange(e.target.checked);
              }}
              style={{ cursor: hasIncomingEdge ? 'not-allowed' : 'pointer' }}
            />
            <span>{boolVal ? 'true' : 'false'}</span>
          </label>
        </div>
      );
    }

    if (inputType === 'number') {
      return (
        <FieldTextInput
          value={hasIncomingEdge ? String(upstreamValue ?? '') : String((data[valueKey] as number) ?? '')}
          disabled={hasIncomingEdge}
          locked={hasIncomingEdge}
          onChange={(v) => handleValueChange(parseFloat(v) || 0)}
          style={inputStyle}
          placeholder={hasIncomingEdge ? '由连线提供' : '输入数值'}
        />
      );
    }

    return (
      <FieldTextInput
        value={hasIncomingEdge ? String(upstreamValue ?? '') : String((data[valueKey] as string) ?? '')}
        disabled={hasIncomingEdge}
        locked={hasIncomingEdge}
        onChange={handleValueChange}
        style={inputStyle}
        placeholder={hasIncomingEdge ? '由连线提供' : '输入字符串'}
      />
    );
  };

  return (
    <>
      <div
        className={isMultiSelected ? 'node-multi-selected' : undefined}
        data-multi-selected={isMultiSelected ? 'true' : undefined}
        style={{
          background: '#fff',
          border: `2px solid ${borderColor}`,
          borderRadius: 8,
          minWidth: 200,
          maxWidth: 260,
          fontSize: 12,
          position: 'relative',
        }}
      >
        {/* ===== Header ===== */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '8px 10px 6px',
            borderBottom: '1px solid #f0f0f0',
          }}
        >
          <div style={{ fontWeight: 600, fontSize: 13, display: 'flex', alignItems: 'center', gap: 4 }}>
            {(data as any)._seq != null && <SeqBadge seq={(data as any)._seq} />}
            <span style={{ fontSize: 16 }}>{icon}</span>
            <span>{label}</span>
          </div>
          <div style={{ display: 'flex', gap: 4 }}>
            <button
              onClick={(e) => { e.stopPropagation(); setDetailNodeId(id); }}
              title="查看详情"
              style={{
                width: 24, height: 24, borderRadius: 4, border: 'none',
                background: '#f0f5ff', color: '#1890ff', cursor: 'pointer',
                fontSize: 14, display: 'flex', alignItems: 'center', justifyContent: 'center',
                padding: 0, flexShrink: 0,
              }}
            >
              <ExpandOutlined />
            </button>
            <button
              onClick={handleRun}
              disabled={!canRun}
              title={!canRun ? '请先填入值或连接输入' : statusCfg.title}
              style={{
                width: 24, height: 24, borderRadius: 4, border: 'none',
                background: !canRun ? '#f5f5f5' : statusCfg.bg,
                color: !canRun ? '#d9d9d9' : statusCfg.color,
                cursor: !canRun ? 'not-allowed' : runStatus === 'running' ? 'wait' : 'pointer',
                fontSize: 14, display: 'flex', alignItems: 'center', justifyContent: 'center',
                padding: 0, flexShrink: 0,
                opacity: !canRun ? 0.5 : 1,
              }}
            >
              {React.createElement(canRun ? statusCfg.icon : PlayCircleOutlined, { spin: canRun && runStatus === 'running' })}
            </button>
          </div>
        </div>

        {/* ===== Port Row ===== */}
        <div
          style={{
            display: 'flex',
            borderBottom: '1px solid #f0f0f0',
            padding: '6px 0',
          }}
        >
          {/* Input port */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4, paddingLeft: 22, position: 'relative' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                fontSize: 10,
                color: portColor,
                position: 'relative',
                height: 20,
              }}
            >
              <Handle
                type="target"
                position={Position.Left}
                id={inputPortKey}
                style={{
                  position: 'absolute',
                  left: -15,
                  top: '50%',
                  transform: 'translateY(-50%)',
                  width: 10,
                  height: 10,
                  background: portColor,
                  border: '2px solid #fff',
                  boxShadow: '0 0 0 1px rgba(0,0,0,0.1)',
                }}
              />
              <span style={{ marginLeft: 0 }}>{inputPortLabel}</span>
            </div>
          </div>
          {/* Output port */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4, paddingRight: 22, textAlign: 'right', position: 'relative' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'flex-end',
                fontSize: 10,
                color: portColor,
                position: 'relative',
                height: 20,
              }}
            >
              <span style={{ marginRight: 0 }}>{outputPortLabel}</span>
              <Handle
                type="source"
                position={Position.Right}
                id={outputPortKey}
                style={{
                  position: 'absolute',
                  right: -15,
                  top: '50%',
                  transform: 'translateY(-50%)',
                  width: 10,
                  height: 10,
                  background: portColor,
                  border: '2px solid #fff',
                  boxShadow: '0 0 0 1px rgba(0,0,0,0.1)',
                }}
              />
            </div>
          </div>
        </div>

        {/* ===== Content ===== */}
        <div style={{ padding: '8px 10px' }}>
          {/* Override warning */}
          {overrideWarning && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 4,
              padding: '4px 6px', marginBottom: 6,
              background: '#fffbe6', border: '1px solid #ffe58f', borderRadius: 4,
              fontSize: 10, color: '#d48806',
            }}>
              <InfoCircleOutlined />
              <span>连线输入已覆盖手动输入值</span>
            </div>
          )}

          {/* Connected indicator */}
          {hasIncomingEdge && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 4,
              padding: '3px 6px', marginBottom: 6,
              background: '#f0f5ff', border: '1px solid #adc6ff', borderRadius: 4,
              fontSize: 10, color: '#2f54eb',
            }}>
              <span>🔗 已连线，使用上游输入</span>
            </div>
          )}

          {/* Input field */}
          <div style={{ marginBottom: 6 }}>
            <label style={{ display: 'block', fontSize: 10, color: '#888', marginBottom: 2 }}>
              {label} 值
              {!hasIncomingEdge && <span style={{ color: '#ff4d4f', marginLeft: 2 }}>*</span>}
              {hasIncomingEdge && <span style={{ color: '#2f54eb', marginLeft: 4 }}>(连线优先)</span>}
            </label>
            {renderInput()}
          </div>

          {/* Run output — compact mode shows only status badge */}
          {runOutput && runStatus !== 'idle' && runStatus !== 'running' && (
            compactMode ? (
              <div style={{ marginTop: 4, display: 'flex', alignItems: 'center', gap: 4, fontSize: 10 }}>
                {runStatus === 'error' ? (
                  <span style={{ color: '#cf1322' }}>❌ 错误</span>
                ) : (
                  <span style={{ color: '#389e0d' }}>✅ 已执行</span>
                )}
              </div>
            ) : (
            <div style={{ marginTop: 6 }}>
              {runStatus === 'error' ? (
                <div style={{ background: '#fff2f0', border: '1px solid #ffccc7', borderRadius: 4, overflow: 'hidden' }}>
                  <div style={{ padding: '3px 6px', fontWeight: 600, fontSize: 10, color: '#cf1322', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#ff4d4f', display: 'inline-block' }} />
                    错误
                  </div>
                  <div style={{ padding: '4px 6px', maxHeight: 60, overflowY: 'auto', borderTop: '1px solid #ffccc7', fontSize: 9 }}
                       className="nowheel nopan">
                    <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all', color: '#cf1322' }}>
                      {typeof runOutput === 'string' ? runOutput : runOutput.error || JSON.stringify(runOutput, null, 2)}
                    </pre>
                  </div>
                </div>
              ) : (
                <div style={{ background: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: 4, overflow: 'hidden' }}>
                  <div style={{ padding: '3px 6px', fontWeight: 600, fontSize: 10, color: '#389e0d', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: portColor, display: 'inline-block' }} />
                    {outputPortLabel} ✅
                  </div>
                  <div style={{ padding: '4px 6px', maxHeight: 80, overflowY: 'auto', fontSize: 9, borderTop: '1px solid #b7eb8f' }}
                       className="nowheel nopan">
                    <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                      {typeof runOutput[outputPortKey] !== 'undefined'
                        ? String(runOutput[outputPortKey])
                        : JSON.stringify(runOutput, null, 2)}
                    </pre>
                  </div>
                </div>
              )}
            </div>
            ) /* end compactMode ternary */
          )}
        </div>
      </div>

      <NodeDetailModal
        open={detailOpen}
        onClose={() => setDetailNodeId(null)}
        nodeId={id}
        nodeType={nodeType}
        icon={icon}
        label={label}
        fields={fields}
      />
    </>
  );
};

export default ValueNode;
