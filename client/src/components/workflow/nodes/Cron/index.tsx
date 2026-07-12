import React, { memo, useCallback, useState, useMemo } from 'react';
import { NodeProps, Handle, Position, useReactFlow } from 'reactflow';
import { message, Tag, Button } from 'antd';
import { PlayCircleOutlined, LoadingOutlined, CheckCircleOutlined, CloseCircleOutlined, StopOutlined, ClockCircleOutlined, ExpandOutlined } from '@ant-design/icons';
import { NodeField } from '../BaseNode';
import { FieldTextInput } from '../BaseNode';
import { getNodePorts } from '../../PortTypes';
import { useWorkflowContext } from '../../WorkflowContext';
import { FlowApi } from '../../services/FlowApi';
import { startCron, stopCron } from './executor';
import NodeDetailModal from '../NodeDetailModal';

type RunStatus = 'idle' | 'running' | 'success' | 'error';

const STATUS_CONFIG = {
  idle:    { color: '#8c8c8c', bg: '#f5f5f5', icon: PlayCircleOutlined,  title: '启动定时任务' },
  running: { color: '#1890ff', bg: '#e6f7ff', icon: LoadingOutlined,      title: '运行中...' },
  success: { color: '#52c41a', bg: '#f6ffed', icon: CheckCircleOutlined,  title: '运行成功' },
  error:   { color: '#ff4d4f', bg: '#fff2f0', icon: CloseCircleOutlined,  title: '运行失败' },
};

const PORT_COLORS: Record<string, string> = {
  'any': '#8c8c8c',
  'string': '#fa8c16',
};

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

// Cron field labels for reference
const CRON_REF = '分 时 日 月 周';

function CronNode({ data, id, selected }: NodeProps) {
  const nodeData = data as Record<string, unknown>;
  const { workflowId } = useWorkflowContext();
  const { setNodes, getEdges } = useReactFlow();

  const runStatus: RunStatus = (nodeData._runStatus as RunStatus) || 'idle';
  const runOutput = nodeData._runOutput as any;
  const statusCfg = STATUS_CONFIG[runStatus];

  // Is this cron currently running?
  const isCronRunning = !!(runOutput?.success && runOutput?.cronId);

  // ── Run handler: start cron ──
  const handleRun = useCallback(async () => {
    const cronExpr = (nodeData.cronExpr as string || '').trim();
    if (!cronExpr) {
      message.warning('请先输入 Cron 表达式');
      return;
    }

    // Set running status
    setNodes((nds) =>
      nds.map((n) => (n.id === id ? { ...n, data: { ...n.data, _runStatus: 'running' } } : n))
    );

    try {
      const result = await startCron(cronExpr, workflowId, id);
      if (result.error) {
        setNodes((nds) =>
          nds.map((n) => (n.id === id ? { ...n, data: { ...n.data, _runStatus: 'error', _runOutput: { error: result.error } } } : n))
        );
        message.error(result.error);
      } else {
        setNodes((nds) =>
          nds.map((n) => (n.id === id ? { ...n, data: { ...n.data, _runStatus: 'success', _runOutput: result } } : n))
        );
        message.success(result.message || `Cron 已启动: ${cronExpr}`);
      }
    } catch (e: any) {
      setNodes((nds) =>
        nds.map((n) => (n.id === id ? { ...n, data: { ...n.data, _runStatus: 'error', _runOutput: { error: e.message } } } : n))
      );
      message.error('启动失败: ' + e.message);
    }
  }, [nodeData.cronExpr, workflowId, id, setNodes]);

  // ── Stop handler ──
  const handleStop = useCallback(async () => {
    const cronId = runOutput?.cronId;
    if (!cronId) return;

    try {
      const result = await stopCron(cronId);
      if (result.success) {
        setNodes((nds) =>
          nds.map((n) => (n.id === id ? { ...n, data: { ...n.data, _runStatus: 'idle', _runOutput: null } } : n))
        );
        message.success('Cron 已停止');
      } else {
        message.error(result.error || '停止失败');
      }
    } catch (e: any) {
      message.error('停止失败: ' + e.message);
    }
  }, [runOutput?.cronId, id, setNodes]);

  // ── Detail modal ──
  const [detailOpen, setDetailOpen] = useState(false);

  // ── Port info ──
  const ports = getNodePorts('cron');
  const inputPorts = ports.filter((p) => p.direction === 'input');
  const outputPorts = ports.filter((p) => p.direction === 'output');

  // Check if valueIn port is connected
  const allEdges = useReactFlow().getEdges();
  const hasIncomingEdge = allEdges.some((e) => e.target === id && e.targetHandle === 'valueIn');

  return (
    <div
      style={{
        background: '#fff',
        borderRadius: 8,
        border: `1.5px solid ${selected ? '#1677ff' : '#e8e8e8'}`,
        boxShadow: selected ? '0 0 0 2px rgba(22,119,255,.15)' : '0 1px 4px rgba(0,0,0,.06)',
        minWidth: 180,
        fontSize: 11,
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex', alignItems: 'center', gap: 4,
          padding: '6px 10px', borderBottom: '1px solid #f0f0f0',
          background: statusCfg.bg,
        }}
      >
        <span style={{ fontSize: 13 }}>⏰</span>
        <strong style={{ flex: 1, fontSize: 11, color: '#333' }}>Cron</strong>
        {isCronRunning && (
          <Tag color="blue" style={{ fontSize: 9, margin: 0, lineHeight: '16px', padding: '0 4px' }}>运行中</Tag>
        )}
        <span
          onClick={isCronRunning ? handleStop : handleRun}
          style={{ cursor: 'pointer', fontSize: 13, color: isCronRunning ? '#ff4d4f' : statusCfg.color }}
          title={isCronRunning ? '停止定时任务' : statusCfg.title}
        >
          {isCronRunning ? <StopOutlined /> : React.createElement(statusCfg.icon)}
        </span>
        <span
          onClick={() => setDetailOpen(true)}
          style={{ cursor: 'pointer', fontSize: 12, color: '#8c8c8c' }}
          title="详细信息"
        >
          <ExpandOutlined />
        </span>
      </div>

      {/* Body: Cron expression field */}
      <div style={{ padding: '8px 10px' }}>
        <div style={{ fontSize: 10, color: '#999', marginBottom: 4 }}>Cron 表达式（{CRON_REF}）</div>
        <FieldTextInput
          value={(nodeData.cronExpr as string) || ''}
          onChange={(v) => {
            setNodes((nds) =>
              nds.map((n) => (n.id === id ? { ...n, data: { ...n.data, cronExpr: v } } : n))
            );
          }}
          locked={hasIncomingEdge}
          placeholder="0 2 * * 0"
        />
        {isCronRunning && runOutput?.cronExpr && (
          <div style={{ marginTop: 6, fontSize: 10, color: '#52c41a' }}>
            <ClockCircleOutlined /> 运行中: {runOutput.cronExpr}
            {runOutput.cronId && <span style={{ color: '#999', marginLeft: 4 }}>ID: {runOutput.cronId}</span>}
          </div>
        )}
      </div>

      {/* Input port handle */}
      {inputPorts.map((p) => (
        <Handle
          key={p.key}
          type="target"
          position={Position.Left}
          id={p.key}
          style={{ background: PORT_COLORS[p.type] || '#8c8c8c', width: 8, height: 8 }}
        />
      ))}

      {/* Output port handle */}
      {outputPorts.map((p) => (
        <Handle
          key={p.key}
          type="source"
          position={Position.Right}
          id={p.key}
          style={{ background: PORT_COLORS[p.type] || '#8c8c8c', width: 8, height: 8 }}
        >
          <span style={{
            position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)',
            fontSize: 9, color: '#999', whiteSpace: 'nowrap',
          }}>
            {p.label}
          </span>
        </Handle>
      ))}

      {/* Detail Modal */}
      <NodeDetailModal
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        nodeId={id}
        nodeType="cron"
        icon="⏰"
        label="Cron"
        fields={CRON_FIELDS}
      />
    </div>
  );
}

export default memo(CronNode);
