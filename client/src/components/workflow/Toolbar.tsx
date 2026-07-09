import React, { useState } from 'react';
import type { Node, Edge } from 'reactflow';
import { useReactFlow } from 'reactflow';
import { Button, Space, Input, Popover, message } from 'antd';
import {
  SaveOutlined,
  PlayCircleOutlined,
  StopOutlined,
  ExportOutlined,
  ImportOutlined,
  FullscreenOutlined,
  FullscreenExitOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons';
import { FlowApi } from './services/FlowApi';
import type { WorkflowJSON } from './types';

interface ToolbarProps {
  nodes: Node[];
  edges: Edge[];
  setNodes: React.Dispatch<React.SetStateAction<Node[]>>;
  setEdges: React.Dispatch<React.SetStateAction<Edge[]>>;
  workflowId?: string;
  workflowName?: string;
  workflowAuthor?: string;
  workflowDescription?: string;
  workflowCreatedAt?: string;
  workflowUpdatedAt?: string;
  isFullscreen?: boolean;
  onFullscreenToggle?: () => void;
  onSave?: (id: string, name: string) => void;
  onRun?: (json: WorkflowJSON, workflowId?: string) => void;
  runCancelFn?: (() => void) | null;
}

const Toolbar: React.FC<ToolbarProps> = ({
  nodes,
  edges,
  setNodes,
  setEdges,
  workflowId,
  workflowName: initialName,
  workflowAuthor: initialAuthor,
  workflowDescription: initialDesc,
  workflowCreatedAt,
  workflowUpdatedAt,
  isFullscreen,
  onFullscreenToggle,
  onSave,
  onRun,
  runCancelFn,
}) => {
  const [saving, setSaving] = useState(false);
  const isRunning = !!runCancelFn;
  const [name, setName] = useState(initialName || '未命名工作流');
  const [author, setAuthor] = useState(initialAuthor || '');
  const [description, setDescription] = useState(initialDesc || '');
  const reactFlowInstance = useReactFlow();

  const handleSave = async () => {
    setSaving(true);
    try {
      const json = reactFlowInstance.toObject();
      const result = await FlowApi.save(name, json, workflowId, { author, description });
      onSave?.(result.id, name);
      message.success('保存成功');
    } catch (err: any) {
      message.error(`保存失败: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleRun = async () => {
    if (!workflowId) {
      message.warning('请先保存工作流');
      return;
    }
    const json = reactFlowInstance.toObject();
    onRun?.(json, workflowId);
  };

  const handleStop = async () => {
    if (runCancelFn) {
      runCancelFn();
      message.info('已请求停止运行');
    }
  };

  const handleExport = () => {
    const json = reactFlowInstance.toObject();
    const blob = new Blob([JSON.stringify(json, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${name}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleImport = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = (e: any) => {
      const file = e.target.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (ev) => {
        try {
          const json = JSON.parse(ev.target?.result as string);
          if (json.nodes) setNodes(json.nodes as Node[]);
          if (json.edges) setEdges(json.edges as Edge[]);
          if (json.viewport) {
            reactFlowInstance.setViewport(json.viewport);
          }
          message.success('导入成功');
        } catch {
          message.error('JSON 解析失败');
        }
      };
      reader.readAsText(file);
    };
    input.click();
  };

  const formatTime = (t?: string) =>
    t ? new Date(t).toLocaleString('zh-CN') : '-';

  const metaContent = (
    <div style={{ width: 280 }}>
      <div style={{ marginBottom: 8 }}>
        <label style={{ display: 'block', fontSize: 11, color: '#888', marginBottom: 2 }}>名称</label>
        <Input value={name} onChange={(e) => setName(e.target.value)} size="small" />
      </div>
      <div style={{ marginBottom: 8 }}>
        <label style={{ display: 'block', fontSize: 11, color: '#888', marginBottom: 2 }}>作者</label>
        <Input value={author} onChange={(e) => setAuthor(e.target.value)} size="small" placeholder="可选" />
      </div>
      <div style={{ marginBottom: 8 }}>
        <label style={{ display: 'block', fontSize: 11, color: '#888', marginBottom: 2 }}>描述</label>
        <Input.TextArea value={description} onChange={(e) => setDescription(e.target.value)} size="small" rows={2} placeholder="可选" />
      </div>
      <div style={{ fontSize: 11, color: '#999' }}>
        <div>创建时间: {formatTime(workflowCreatedAt)}</div>
        <div>最后更新: {formatTime(workflowUpdatedAt)}</div>
      </div>
    </div>
  );

  return (
    <div
      style={{
        height: 44,
        borderBottom: '1px solid #e8e8e8',
        display: 'flex',
        alignItems: 'center',
        padding: '0 16px',
        background: '#fff',
        gap: 4,
      }}
    >
      <Space>
        <Popover content={metaContent} title="工作流信息" trigger="click">
          <Button icon={<InfoCircleOutlined />} size="small">
            信息
          </Button>
        </Popover>
        <Button icon={<SaveOutlined />} loading={saving} onClick={handleSave} size="small">
          保存
        </Button>
        <Button type="primary" icon={<PlayCircleOutlined />} loading={isRunning} onClick={handleRun} size="small" disabled={isRunning}>
          运行
        </Button>
        <Button icon={<StopOutlined />} size="small" disabled={!isRunning} onClick={handleStop} danger={isRunning}>
          停止
        </Button>
        <Button icon={<ImportOutlined />} onClick={handleImport} size="small">
          导入
        </Button>
        <Button icon={<ExportOutlined />} onClick={handleExport} size="small">
          导出
        </Button>
        <Button
          icon={isFullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
          onClick={onFullscreenToggle}
          size="small"
          type={isFullscreen ? 'primary' : 'default'}
        >
          {isFullscreen ? '退出全屏' : '全屏'}
        </Button>
      </Space>
      <span style={{ marginLeft: 16, color: '#666', fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {name}
      </span>
    </div>
  );
};

export default Toolbar;
