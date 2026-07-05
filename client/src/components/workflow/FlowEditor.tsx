import React from 'react';

const FlowEditor: React.FC<{
  initialData?: any;
  workflowId?: string;
  workflowName?: string;
  onSave?: (id: string, name: string) => void;
}> = () => {
  return (
    <div style={{ padding: 24 }}>
      <h2>Workflow Editor</h2>
      <p>FlowGram editor will be integrated here.</p>
    </div>
  );
};

export default FlowEditor;
