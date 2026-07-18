import React, { useEffect, useState } from 'react';
import { Modal, Table, Tag, Space } from 'antd';
import { FlowApi } from './services/FlowApi';

interface ExecutionRecord {
  id: string;
  startedAt: string;
  finishedAt?: string;
  status: string;
  trigger: string;
  username: string;
  nodeCount: number;
  summary?: { succeeded: number; failed: number };
  startNodeId?: string;
}

interface Props {
  workflowId?: string;
  open: boolean;
  onClose: () => void;
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

const ExecutionHistoryModal: React.FC<Props> = ({ workflowId, open, onClose }) => {
  const [loading, setLoading] = useState(false);
  const [records, setRecords] = useState<ExecutionRecord[]>([]);

  const fetchHistory = async () => {
    if (!workflowId) return;
    setLoading(true);
    try {
      const data = await FlowApi.getHistory(workflowId);
      setRecords(data.records || []);
    } catch {
      setRecords([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open && workflowId) fetchHistory();
  }, [open, workflowId]);

  const columns = [
    {
      title: '时间', dataIndex: 'startedAt', key: 'startedAt', width: 180,
      render: (v: string) => v ? new Date(v).toLocaleString('zh-CN') : '-',
      defaultSortOrder: 'descend' as const,
      sorter: (a: ExecutionRecord, b: ExecutionRecord) => (a.startedAt || '').localeCompare(b.startedAt || ''),
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 80,
      render: (v: string) => <Tag color={statusColorMap[v] || 'default'}>{statusLabelMap[v] || v}</Tag>,
    },
    {
      title: '触发', dataIndex: 'trigger', key: 'trigger', width: 70,
      render: (v: string) => v === 'cron' ? '定时' : '手动',
    },
    {
      title: '用户', dataIndex: 'username', key: 'username', width: 100,
    },
    {
      title: '节点数', dataIndex: 'nodeCount', key: 'nodeCount', width: 70,
    },
    {
      title: '结果', key: 'summary', width: 120,
      render: (_: any, r: ExecutionRecord) => {
        const s = r.summary;
        if (!s) return '-';
        return (
          <Space size={4}>
            <Tag color="green">{s.succeeded} 成功</Tag>
            {s.failed > 0 && <Tag color="red">{s.failed} 失败</Tag>}
          </Space>
        );
      },
    },
    {
      title: '耗时', key: 'duration', width: 80,
      render: (_: any, r: ExecutionRecord) => {
        if (!r.startedAt || !r.finishedAt) return '-';
        const ms = new Date(r.finishedAt).getTime() - new Date(r.startedAt).getTime();
        if (ms < 1000) return `${ms}ms`;
        return `${(ms / 1000).toFixed(1)}s`;
      },
    },
  ];

  return (
    <Modal
      title={<span style={{ fontWeight: 700 }}>📋 执行历史</span>}
      open={open}
      onCancel={onClose}
      footer={null}
      width={800}
      destroyOnHidden
    >
      <Table
        dataSource={records}
        columns={columns}
        rowKey="id"
        loading={loading}
        size="small"
        pagination={false}
        locale={{ emptyText: '暂无执行记录' }}
        scroll={{ y: 400 }}
      />
    </Modal>
  );
};

export default ExecutionHistoryModal;
