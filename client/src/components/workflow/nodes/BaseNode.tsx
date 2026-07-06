import React, { useCallback, useState } from 'react';
import { Handle, Position, NodeProps, useReactFlow } from 'reactflow';
import { PlayCircleOutlined, LoadingOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import { FlowApi } from '../services/FlowApi';

export type RunStatus = 'idle' | 'running' | 'success' | 'error';

export interface NodeField {
  key: string;
  label: string;
  placeholder?: string;
  type?: 'text' | 'textarea' | 'number';
  rows?: number; // for textarea
  step?: number; // for number
}

interface BaseNodeProps {
  data: Record<string, unknown>;
  id: string;
  selected: boolean;
  icon: string;
  label: string;
  fields: NodeField[];
  summaryFields?: string[]; // fields to show in collapsed summary
}

export function useNodeRun(nodeId: string, nodeType: string, data: Record<string, unknown>) {
  const { setNodes } = useReactFlow();
  const [running, setRunning] = useState(false);

  const run = useCallback(async () => {
    setRunning(true);
    setNodes((nds) =>
      nds.map((n) =>
        n.id === nodeId ? { ...n, data: { ...n.data, _runStatus: 'running' } } : n,
      ),
    );

    try {
      const result = await FlowApi.runNode(nodeType, data, {});
      const output = result.output ?? result;
      const status = output?.error ? 'error' : 'success';
      setNodes((nds) =>
        nds.map((n) =>
          n.id === nodeId
            ? { ...n, data: { ...n.data, _runStatus: status, _runOutput: output } }
            : n,
        ),
      );
      setRunning(false);
      return output;
    } catch (err: any) {
      setNodes((nds) =>
        nds.map((n) =>
          n.id === nodeId
            ? { ...n, data: { ...n.data, _runStatus: 'error', _runOutput: { error: err.message } } }
            : n,
        ),
      );
      setRunning(false);
      return null;
    }
  }, [nodeId, nodeType, data, setNodes]);

  return { running, run };
}

const STATUS_CONFIG = {
  idle: { color: '#8c8c8c', bg: '#f5f5f5', icon: PlayCircleOutlined, title: '运行节点' },
  running: { color: '#1890ff', bg: '#e6f7ff', icon: LoadingOutlined, title: '运行中...' },
  success: { color: '#52c41a', bg: '#f6ffed', icon: CheckCircleOutlined, title: '运行成功' },
  error: { color: '#ff4d4f', bg: '#fff2f0', icon: CloseCircleOutlined, title: '运行失败' },
};

const BaseNode: React.FC<BaseNodeProps> = ({
  data,
  id,
  selected,
  icon,
  label,
  fields,
}) => {
  const { setNodes } = useReactFlow();
  const [editing, setEditing] = useState(false);
  const [running, setRunning] = useState(false);

  const runStatus = (data._runStatus as RunStatus) || 'idle';
  const runOutput = data._runOutput as any;
  const statusCfg = STATUS_CONFIG[runStatus];

  const handleFieldChange = useCallback(
    (key: string, value: any) => {
      setNodes((nds) =>
        nds.map((n) =>
          n.id === id ? { ...n, data: { ...n.data, [key]: value } } : n,
        ),
      );
    },
    [id, setNodes],
  );

  const handleRun = useCallback(
    async (e: React.MouseEvent) => {
      e.stopPropagation();
      setRunning(true);
      setNodes((nds) =>
        nds.map((n) =>
          n.id === id ? { ...n, data: { ...n.data, _runStatus: 'running' } } : n,
        ),
      );

      try {
        const nodeType = (data as any).__nodeType || label.toLowerCase();
        const result = await FlowApi.runNode(nodeType, data, {});
        const output = result.output ?? result;
        const newStatus = output?.error ? 'error' : 'success';
        setNodes((nds) =>
          nds.map((n) =>
            n.id === id
              ? { ...n, data: { ...n.data, _runStatus: newStatus, _runOutput: output } }
              : n,
          ),
        );
      } catch (err: any) {
        setNodes((nds) =>
          nds.map((n) =>
            n.id === id
              ? {
                  ...n,
                  data: {
                    ...n.data,
                    _runStatus: 'error',
                    _runOutput: { error: err.message },
                  },
                }
              : n,
          ),
        );
      }
      setRunning(false);
    },
    [id, label, data, setNodes],
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

  return (
    <div
      style={{
        background: '#fff',
        border: `2px solid ${borderColor}`,
        borderRadius: 8,
        padding: 10,
        minWidth: 200,
        fontSize: 12,
      }}
      onDoubleClick={(e) => {
        e.stopPropagation();
        setEditing(!editing);
      }}
    >
      <Handle type="target" position={Position.Left} />

      {/* Header row: icon + label + run button */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
        <div style={{ fontWeight: 600, fontSize: 13 }}>
          {icon} {label}
        </div>
        <button
          onClick={handleRun}
          disabled={running}
          title={statusCfg.title}
          style={{
            width: 24,
            height: 24,
            borderRadius: 4,
            border: 'none',
            background: statusCfg.bg,
            color: statusCfg.color,
            cursor: running ? 'wait' : 'pointer',
            fontSize: 14,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 0,
            flexShrink: 0,
            transition: 'all 0.2s',
          }}
        >
          {React.createElement(statusCfg.icon, { spin: runStatus === 'running' })}
        </button>
      </div>

      {/* Collapsed: summary view */}
      {!editing && (
        <div style={{ color: '#666', fontSize: 11 }}>
          {fields.map((f) => {
            const val = data[f.key];
            if (!val) return null;
            const display = f.type === 'textarea'
              ? String(val).slice(0, 40) + (String(val).length > 40 ? '...' : '')
              : String(val);
            return (
              <div key={f.key} style={{ marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                <span style={{ color: '#999', marginRight: 4 }}>{f.label}:</span>
                {display}
              </div>
            );
          })}
          <div style={{ color: '#bbb', fontSize: 10, marginTop: 4 }}>双击编辑</div>
        </div>
      )}

      {/* Expanded: editable form */}
      {editing && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {fields.map((f) => {
            const val = (data[f.key] as any) ?? '';
            if (f.type === 'textarea') {
              return (
                <div key={f.key}>
                  <label style={{ display: 'block', fontSize: 10, color: '#888', marginBottom: 2 }}>{f.label}</label>
                  <textarea
                    value={val}
                    onChange={(e) => handleFieldChange(f.key, e.target.value)}
                    placeholder={f.placeholder}
                    rows={f.rows || 3}
                    onClick={(e) => e.stopPropagation()}
                    style={{
                      width: '100%',
                      fontSize: 11,
                      padding: '3px 6px',
                      border: '1px solid #d9d9d9',
                      borderRadius: 3,
                      resize: 'vertical',
                      boxSizing: 'border-box',
                    }}
                  />
                </div>
              );
            }
            if (f.type === 'number') {
              return (
                <div key={f.key}>
                  <label style={{ display: 'block', fontSize: 10, color: '#888', marginBottom: 2 }}>{f.label}</label>
                  <input
                    type="number"
                    value={val}
                    onChange={(e) => handleFieldChange(f.key, parseFloat(e.target.value) || 0)}
                    placeholder={f.placeholder}
                    step={f.step}
                    onClick={(e) => e.stopPropagation()}
                    style={{
                      width: '100%',
                      fontSize: 11,
                      padding: '3px 6px',
                      border: '1px solid #d9d9d9',
                      borderRadius: 3,
                      boxSizing: 'border-box',
                    }}
                  />
                </div>
              );
            }
            return (
              <div key={f.key}>
                <label style={{ display: 'block', fontSize: 10, color: '#888', marginBottom: 2 }}>{f.label}</label>
                <input
                  type="text"
                  value={val}
                  onChange={(e) => handleFieldChange(f.key, e.target.value)}
                  placeholder={f.placeholder}
                  onClick={(e) => e.stopPropagation()}
                  style={{
                    width: '100%',
                    fontSize: 11,
                    padding: '3px 6px',
                    border: '1px solid #d9d9d9',
                    borderRadius: 3,
                    boxSizing: 'border-box',
                  }}
                />
              </div>
            );
          })}
          <div
            onClick={(e) => { e.stopPropagation(); setEditing(false); }}
            style={{ color: '#1890ff', fontSize: 10, cursor: 'pointer', textAlign: 'center', marginTop: 2 }}
          >
            收起
          </div>
        </div>
      )}

      {/* Run output hint (error only, on node) */}
      {runStatus === 'error' && runOutput?.error && (
        <div
          style={{
            marginTop: 4,
            padding: '3px 6px',
            background: '#fff2f0',
            borderRadius: 3,
            fontSize: 10,
            color: '#cf1322',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {String(runOutput.error).slice(0, 50)}
        </div>
      )}

      <Handle type="source" position={Position.Right} />
    </div>
  );
};

export default BaseNode;
