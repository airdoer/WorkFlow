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
}

const WorkflowPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [workflowData, setWorkflowData] = useState<WorkflowMeta>({});
  const [searchParams] = useSearchParams();

  useEffect(() => {
    const workflowId = searchParams.get('id');
    if (workflowId) {
      setLoading(true);
      FlowApi.get(workflowId)
        .then((workflow) => {
          setWorkflowData({
            id: workflow.id,
            name: workflow.name,
            author: workflow.author,
            description: workflow.description,
            createdAt: workflow.createdAt,
            updatedAt: workflow.updatedAt,
            json: workflow.json,
          });
        })
        .catch((error) => {
          console.error('Failed to load workflow:', error);
        })
        .finally(() => {
          setLoading(false);
        });
    }
  }, [searchParams]);

  const handleSave = (id: string, name: string) => {
    setWorkflowData((prev) => ({ ...prev, id, name }));
    // Update URL so the ?id= param reflects the saved workflow (especially for new workflows)
    const currentPath = window.location.pathname;
    const currentId = searchParams.get('id');
    if (currentId !== id) {
      history.replace(`${currentPath}?id=${id}`);
    }
  };

  const handleFullscreenToggle = () => {
    const id = searchParams.get('id');
    const isFullscreen = window.location.pathname === '/workflow/fullscreen';
    if (isFullscreen) {
      // Exit fullscreen → go back to layout version
      history.push(`/workflow/editor${id ? `?id=${id}` : ''}`);
    } else {
      // Enter fullscreen → go to layout:false version
      history.push(`/workflow/fullscreen${id ? `?id=${id}` : ''}`);
    }
  };

  // Detect if currently in fullscreen route
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
      />
    </div>
  );
};

export default WorkflowPage;
