import React, { useEffect, useState } from 'react';
import { Table, Button, Space, Popconfirm, message, Input, Segmented } from 'antd';
import { PlusOutlined, DeleteOutlined, EditOutlined } from '@ant-design/icons';
import { history, useModel, useSearchParams } from '@umijs/max';
import { FlowApi } from '@/components/workflow/services/FlowApi';

interface WorkflowRecord {
  id: string;
  name: string;
  author?: string;
  description?: string;
  createdAt?: string;
  updatedAt?: string;
}

const FlowHistory: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<WorkflowRecord[]>([]);
  const { initialState } = useModel('@@initialState');
  const currentUser = initialState?.currentUser;
  const username = currentUser?.name || currentUser?.userid || '';
  const [searchParams, setSearchParams] = useSearchParams();
  const [filter, setFilter] = useState<string>(searchParams.get('filter') || 'all');

  const fetchList = async () => {
    setLoading(true);
    try {
      const author = filter === 'mine' ? username : undefined;
      const result = await FlowApi.list(author);
      setData(result.list || []);
    } catch (err: any) {
      message.error(`加载失败: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchList();
  }, [filter]);

  const handleDelete = async (id: string) => {
    try {
      await FlowApi.delete(id);
      message.success('删除成功');
      fetchList();
    } catch (err: any) {
      message.error(`删除失败: ${err.message}`);
    }
  };

  const handleEdit = (id: string) => {
    history.push(`/workflow?id=${id}`);
  };

  const handleCreate = () => {
    history.push('/workflow');
  };

  const columns = [
    {
      title: '名称', dataIndex: 'name', key: 'name', ellipsis: true,
    },
    {
      title: '作者', dataIndex: 'author', key: 'author', width: 120,
      render: (v: string) => v || '-',
    },
    {
      title: '描述', dataIndex: 'description', key: 'description', ellipsis: true,
      render: (v: string) => v || '-',
    },
    {
      title: '创建时间', dataIndex: 'createdAt', key: 'createdAt', width: 180,
      render: (v: string) => v ? new Date(v).toLocaleString('zh-CN') : '-',
    },
    {
      title: '最后更新', dataIndex: 'updatedAt', key: 'updatedAt', width: 180,
      render: (v: string) => v ? new Date(v).toLocaleString('zh-CN') : '-',
      defaultSortOrder: 'descend' as const,
      sorter: (a: WorkflowRecord, b: WorkflowRecord) => (a.updatedAt || '').localeCompare(b.updatedAt || ''),
    },
    {
      title: '操作', key: 'action', width: 140,
      render: (_: any, record: WorkflowRecord) => (
        <Space>
          <Button type="link" icon={<EditOutlined />} onClick={() => handleEdit(record.id)}>
            编辑
          </Button>
          <Popconfirm
            title="确认删除？"
            onConfirm={() => handleDelete(record.id)}
            okText="删除"
            cancelText="取消"
          >
            <Button type="link" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Space>
          <h2 style={{ margin: 0 }}>工作流历史</h2>
          <Segmented
            value={filter}
            onChange={(v) => setFilter(v as string)}
            options={[
              { label: '全部', value: 'all' },
              { label: `我的 (${username})`, value: 'mine' },
            ]}
          />
        </Space>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
          新建工作流
        </Button>
      </div>
      <Table
        columns={columns}
        dataSource={data}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 10 }}
      />
    </div>
  );
};

export default FlowHistory;
