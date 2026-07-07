import React, { useState } from 'react';
import type { Node, Edge } from 'reactflow';
import { useReactFlow } from 'reactflow';
import { Button, Space, message } from 'antd';
import { SaveOutlined, PlayCircleOutlined, StopOutlined, ExportOutlined, ImportOutlined, FullscreenOutlined, FullscreenExitOutlined } from '@ant-design/icons';
import { FlowApi } from './services/FlowApi';
import type { WorkflowJSON } from './types';

interface ToolbarProps {
  nodes: Node[];
  edges: Edge[];
  setNodes: React.Dispatch<React.SetStateAction<Node[]>>;
  setEdges: React.Dispatch<React.SetStateAction<Edge[]>>;
  workflowId?: string;
  workflowName?: string;
  onSave?: (id: string, name: string) => void;
  onRun?: (json: WorkflowJSON) => void;
}

const Toolbar: React.FC<ToolbarProps> = ({
  nodes,
  edges,
  setNodes,
  setEdges,
  workflowId,
  workflowName,
  onSave,
  onRun,
}) => {
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const reactFlowInstance = useReactFlow();

  const handleSave = async () => {
    setSaving(true);
    try {
      const json = reactFlowInstance.toObject();
      const name = workflowName || '未命名工作流';
      const result = await FlowApi.save(name, json, workflowId);
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
    setRunning(true);
    try {
      const json = reactFlowInstance.toObject();
      onRun?.(json);
      const result = await FlowApi.runWorkflow(workflowId);
      message.info(`工作流已提交，taskId: ${result.taskId}`);
    } catch (err: any) {
      message.error(`运行失败: ${err.message}`);
    } finally {
      setRunning(false);
    }
  };

  const handleExport = () => {
    const json = reactFlowInstance.toObject();
    const blob = new Blob([JSON.stringify(json, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${workflowName || 'workflow'}.json`;
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

  const handleFullscreen = () => {
    const el = document.documentElement;
    if (!document.fullscreenElement) {
      el.requestFullscreen().then(() => setFullscreen(true)).catch(() => {});
    } else {
      document.exitFullscreen().then(() => setFullscreen(false)).catch(() => {});
    }
  };

  // Sync state when user presses Esc to exit fullscreen
  React.useEffect(() => {
    const handler = () => setFullscreen(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', handler);
    return () => document.removeEventListener('fullscreenchange', handler);
  }, []);

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
        <Button icon={<SaveOutlined />} loading={saving} onClick={handleSave} size="small">
          保存
        </Button>
        <Button type="primary" icon={<PlayCircleOutlined />} loading={running} onClick={handleRun} size="small">
          运行
        </Button>
        <Button icon={<StopOutlined />} size="small" disabled>
          停止
        </Button>
        <Button icon={<ImportOutlined />} onClick={handleImport} size="small">
          导入
        </Button>
        <Button icon={<ExportOutlined />} onClick={handleExport} size="small">
          导出
        </Button>
        <Button
          icon={fullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
          onClick={handleFullscreen}
          size="small"
          type={fullscreen ? 'primary' : 'default'}
        >
          {fullscreen ? '退出全屏' : '全屏'}
        </Button>
      </Space>
      {workflowName && (
        <span style={{ marginLeft: 16, color: '#666', fontSize: 13 }}>{workflowName}</span>
      )}
    </div>
  );
};

export default Toolbar;
