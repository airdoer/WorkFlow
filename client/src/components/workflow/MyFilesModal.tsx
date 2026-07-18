import React, { useEffect, useState } from 'react';
import { Modal, Table, Button, Space, Popconfirm, message } from 'antd';
import { EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { history, useModel } from '@umijs/max';
import { FlowApi } from './services/FlowApi';

interface WorkflowRecord {
  id: string;
  name: string;
  author?: string;
  description?: string;
  createdAt?: string;
  updatedAt?: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
}

const MyFilesModal: React.FC<Props> = ({ open, onClose }) => {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<WorkflowRecord[]>([]);
  const { initialState } = useModel('@@initialState');
  const currentUser = initialState?.currentUser;
  const username = currentUser?.name || currentUser?.userid || '';

  const fetchList = async () => {
    setLoading(true);
    try {
      const result = await FlowApi.list(username);
      setData(result.list || []);
    } catch (err: any) {
      message.error(`加载失败: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) fetchList();
  }, [open]);

  const handleDelete = async (id: string) => {
    try {
      await FlowApi.delete(id);
      message.success('删除成功');
      fetchList();
    } catch (err: any) {
      message.error(`删除失败: ${err.message}`);
    }
  };

  const columns = [
    {
      title: '名称', dataIndex: 'name', key: 'name', ellipsis: true,
      render: (v: string, r: WorkflowRecord) => (
        <a onClick={() => {
          onClose();
          history.push(`/workflow/fullscreen?id=${r.id}`);
        }}>{v}</a>
      ),
    },
    {
      title: '描述', dataIndex: 'description', key: 'description', ellipsis: true,
      render: (v: string) => v || '-',
    },
    {
      title: '最后更新', dataIndex: 'updatedAt', key: 'updatedAt', width: 150,
      render: (v: string) => v ? new Date(v).toLocaleString('zh-CN') : '-',
      defaultSortOrder: 'descend' as const,
      sorter: (a: WorkflowRecord, b: WorkflowRecord) => (a.updatedAt || '').localeCompare(b.updatedAt || ''),
    },
    {
      title: '操作', key: 'action', width: 100,
      render: (_: any, record: WorkflowRecord) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => {
            onClose();
            history.push(`/workflow/fullscreen?id=${record.id}`);
          }}>
            编辑
          </Button>
          <Popconfirm title="确认删除？" onConfirm={() => handleDelete(record.id)} okText="删除" cancelText="取消">
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Modal
      title={<span style={{ fontWeight: 700 }}>📁 我的文件</span>}
      open={open}
      onCancel={onClose}
      footer={null}
      width={700}
      destroyOnHidden
    >
      <Table
        dataSource={data}
        columns={columns}
        rowKey="id"
        loading={loading}
        size="small"
        pagination={{ pageSize: 10 }}
        locale={{ emptyText: '暂无文件' }}
      />
    </Modal>
  );
};

export default MyFilesModal;
