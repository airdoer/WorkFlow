import React, { useEffect, useState } from 'react';
import { Modal, Table, Tag, Space, Button } from 'antd';
import { history, useModel } from '@umijs/max';
import { FlowApi } from './services/FlowApi';

interface GlobalRecord {
  id: string;
  startedAt: string;
  finishedAt?: string;
  status: string;
  trigger: string;
  username: string;
  nodeCount: number;
  summary?: { succeeded: number; failed: number };
  workflowId?: string;
  workflowName?: string;
  workflowAuthor?: string;
}

const statusColorMap: Record<string, string> = {
  success: 'green',
  error: 'red',
  canceled: 'orange',
  processing: 'blue',
  unknown: 'default',
};

const statusLabelMap: Record<string, string> = {
  success: '成功',
  error: '失败',
  canceled: '已取消',
  processing: '运行中',
  unknown: '未知',
};

const GlobalExecutionModal: React.FC<{ open: boolean; onClose: () => void }> = ({ open, onClose }) => {
  const [loading, setLoading] = useState(false);
  const [records, setRecords] = useState<GlobalRecord[]>([]);
  const { initialState } = useModel('@@initialState');
  const currentUser = initialState?.currentUser;

  const fetchData = async () => {
    setLoading(true);
    try {
      const author = currentUser?.name || currentUser?.userid || '';
      const data = await FlowApi.getRecentHistory(author, 100);
      setRecords(data.records || []);
    } catch {
      setRecords([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) fetchData();
  }, [open]);

  const columns = [
    {
      title: '工作流', dataIndex: 'workflowName', key: 'workflowName', ellipsis: true,
      render: (v: string, r: GlobalRecord) => (
        <Button type="link" size="small" onClick={() => {
          const url = `/workflow?id=${r.workflowId}`;
          window.open(url, '_blank');
        }}>
          {v || r.workflowId || '-'}
        </Button>
      ),
    },
    {
      title: '时间', dataIndex: 'startedAt', key: 'startedAt', width: 170,
      render: (v: string) => v ? new Date(v).toLocaleString('zh-CN') : '-',
      defaultSortOrder: 'descend' as const,
      sorter: (a: GlobalRecord, b: GlobalRecord) => (a.startedAt || '').localeCompare(b.startedAt || ''),
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 70,
      render: (v: string) => <Tag color={statusColorMap[v] || 'default'}>{statusLabelMap[v] || v}</Tag>,
    },
    {
      title: '节点数', dataIndex: 'nodeCount', key: 'nodeCount', width: 60,
    },
    {
      title: '耗时', key: 'duration', width: 80,
      render: (_: any, r: GlobalRecord) => {
        if (!r.startedAt || !r.finishedAt) return '-';
        const ms = new Date(r.finishedAt).getTime() - new Date(r.startedAt).getTime();
        if (ms < 1000) return `${ms}ms`;
        return `${(ms / 1000).toFixed(1)}s`;
      },
    },
  ];

  return (
    <Modal
      title={<span style={{ fontWeight: 700 }}>⚡ 我的执行</span>}
      open={open}
      onCancel={onClose}
      footer={null}
      width={750}
      destroyOnHidden
    >
      <Table
        dataSource={records}
        columns={columns}
        rowKey="id"
        loading={loading}
        size="small"
        pagination={{ pageSize: 15 }}
        locale={{ emptyText: '暂无执行记录' }}
        scroll={{ y: 450 }}
      />
    </Modal>
  );
};

export default GlobalExecutionModal;
