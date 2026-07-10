import React, { useEffect, useState } from 'react';
import { Spin } from 'antd';
import { useSearchParams, history } from '@umijs/max';
import FlowEditor from '@/components/workflow/FlowEditor';
import { FlowApi } from '@/components/workflow/services/FlowApi';
import type { WorkflowJSON } from '@/components/workflow/types';

interface WorkflowMeta {
  id?: string;
  name?: string;
  author?: string;
  description?: string;
  createdAt?: string;
  updatedAt?: string;
  json?: WorkflowJSON;
  // key forces FlowEditor to remount when switching workflows
  key?: string;
}

const WorkflowPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [workflowData, setWorkflowData] = useState<WorkflowMeta>({});
  const [searchParams] = useSearchParams();

  const loadWorkflow = async (workflowId: string) => {
    setLoading(true);
    try {
      const workflow = await FlowApi.get(workflowId);
      setWorkflowData({
        key: workflowId,
        id: workflow.id,
        name: workflow.name,
        author: workflow.author,
        description: workflow.description,
        createdAt: workflow.createdAt,
        updatedAt: workflow.updatedAt,
        json: workflow.json,
      });
    } catch (error) {
      console.error('Failed to load workflow:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const workflowId = searchParams.get('id');
    if (workflowId) {
      loadWorkflow(workflowId);
    } else {
      // New empty workflow
      setWorkflowData({ key: '__new__' });
    }
  }, [searchParams]);

  const handleSave = (id: string, name: string) => {
    if (!id) return; // guard against empty id from switch signal
    setWorkflowData((prev) => ({ ...prev, id, name }));
    // Update URL so ?id= reflects saved workflow (especially for new workflows)
    const currentPath = window.location.pathname;
    const currentId = searchParams.get('id');
    if (currentId !== id) {
      history.replace(`${currentPath}?id=${id}`);
    }
  };

  const handleSwitchWorkflow = (id: string) => {
    const currentPath = window.location.pathname;
    if (id === '__new__') {
      // Navigate to new empty workflow
      history.push(currentPath);
      setWorkflowData({ key: `new_${Date.now()}` });
    } else {
      history.push(`${currentPath}?id=${id}`);
      loadWorkflow(id);
    }
  };

  const handleFullscreenToggle = () => {
    const id = searchParams.get('id') || workflowData.id;
    const isFullscreen = window.location.pathname === '/workflow/fullscreen';
    if (isFullscreen) {
      history.push(`/workflow/editor${id ? `?id=${id}` : ''}`);
    } else {
      history.push(`/workflow/fullscreen${id ? `?id=${id}` : ''}`);
    }
  };

  const isFullscreen = window.location.pathname === '/workflow/fullscreen';

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: isFullscreen ? '100vh' : '100%' }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div style={{ height: isFullscreen ? '100vh' : '100%', overflow: 'hidden' }}>
      <FlowEditor
        key={workflowData.key}
        initialData={workflowData.json}
        workflowId={workflowData.id}
        workflowName={workflowData.name}
        workflowAuthor={workflowData.author}
        workflowDescription={workflowData.description}
        workflowCreatedAt={workflowData.createdAt}
        workflowUpdatedAt={workflowData.updatedAt}
        isFullscreen={isFullscreen}
        onFullscreenToggle={handleFullscreenToggle}
        onSave={handleSave}
        onSwitchWorkflow={handleSwitchWorkflow}
      />
    </div>
  );
};

export default WorkflowPage;
