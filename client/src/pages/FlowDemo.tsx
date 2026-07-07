import React, { useEffect, useState } from 'react';
import { Spin } from 'antd';
import FlowEditor from '@/components/workflow/FlowEditor';
import { FlowApi } from '@/components/workflow/services/FlowApi';
import type { WorkflowJSON } from '@/components/workflow/types';

const WorkflowPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [workflowData, setWorkflowData] = useState<{
    id?: string;
    name?: string;
    json?: WorkflowJSON;
  }>({});

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const workflowId = params.get('id');
    const importData = params.get('import');

    if (workflowId) {
      setLoading(true);
      FlowApi.get(workflowId)
        .then((workflow) => {
          setWorkflowData({
            id: workflow.id,
            name: workflow.name,
            json: workflow.json,
          });
        })
        .catch((error) => {
          console.error('Failed to load workflow:', error);
        })
        .finally(() => {
          setLoading(false);
        });
    } else if (importData) {
      try {
        const json = JSON.parse(decodeURIComponent(importData));
        setWorkflowData({ json });
      } catch (error) {
        console.error('Failed to import workflow:', error);
      }
    }
  }, []);

  const handleSave = (id: string, name: string) => {
    setWorkflowData((prev) => ({ ...prev, id, name }));
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div style={{ height: '100vh', overflow: 'hidden' }}>
      <FlowEditor
        initialData={workflowData.json}
        workflowId={workflowData.id}
        workflowName={workflowData.name}
        onSave={handleSave}
      />
    </div>
  );
};

export default WorkflowPage;
