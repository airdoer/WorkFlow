import React, { useEffect, useState } from 'react';
import { Modal, Table, Tag, Space, Button, Input, Checkbox, Tabs, Popconfirm, message, Empty, Card, Row, Col } from 'antd';
import { PlusOutlined, DeleteOutlined, EditOutlined, SaveOutlined, UserAddOutlined } from '@ant-design/icons';
import { FlowApi } from './services/FlowApi';

interface PermissionGroup {
  id: string;
  name: string;
  nodeTypes: string[];
  users: string[];
}

interface PendingUser {
  username: string;
  loginAt: string;
  groups: string[];
}

interface NodeTypeItem {
  type: string;
  name: string;
  category: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
}

const PermissionModal: React.FC<Props> = ({ open, onClose }) => {
  const [groups, setGroups] = useState<PermissionGroup[]>([]);
  const [allNodes, setAllNodes] = useState<NodeTypeItem[]>([]);
  const [pendingUsers, setPendingUsers] = useState<PendingUser[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [editingName, setEditingName] = useState<string>('');
  const [nameDraft, setNameDraft] = useState('');

  const selectedGroup = groups.find(g => g.id === selectedGroupId);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [gRes, nRes, pRes] = await Promise.all([
        FlowApi.getPermissionGroups(),
        FlowApi.getPermissionNodes(),
        FlowApi.getPendingUsers(),
      ]);
      setGroups(gRes.groups || []);
      setAllNodes(nRes.nodes || []);
      setPendingUsers(pRes.pendingUsers || []);
    } catch (err: any) {
      message.error(`加载权限数据失败: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) fetchData();
  }, [open]);

  const handleAddGroup = async () => {
    const newId = `g_${Date.now()}`;
    const newGroup: PermissionGroup = { id: newId, name: '新权限组', nodeTypes: [], users: [] };
    try {
      await FlowApi.savePermissionGroup(newGroup, 'save');
      setGroups([...groups, newGroup]);
      setSelectedGroupId(newId);
      message.success('新增成功');
    } catch (err: any) {
      message.error(`新增失败: ${err.message}`);
    }
  };

  const handleDeleteGroup = async (groupId: string) => {
    try {
      await FlowApi.savePermissionGroup({ id: groupId } as any, 'delete');
      setGroups(groups.filter(g => g.id !== groupId));
      if (selectedGroupId === groupId) setSelectedGroupId('');
      message.success('删除成功');
    } catch (err: any) {
      message.error(`删除失败: ${err.message}`);
    }
  };

  const handleToggleNode = async (nodeType: string, checked: boolean) => {
    if (!selectedGroup) return;
    const updated = {
      ...selectedGroup,
      nodeTypes: checked
        ? [...selectedGroup.nodeTypes, nodeType]
        : selectedGroup.nodeTypes.filter(t => t !== nodeType),
    };
    try {
      await FlowApi.savePermissionGroup(updated, 'save');
      setGroups(groups.map(g => g.id === updated.id ? updated : g));
    } catch (err: any) {
      message.error(`保存失败: ${err.message}`);
    }
  };

  const handleToggleUser = async (username: string, checked: boolean) => {
    if (!selectedGroup) return;
    if (selectedGroup.users.includes('*')) return; // 不能修改通配符组的用户
    const updated = {
      ...selectedGroup,
      users: checked
        ? [...selectedGroup.users, username]
        : selectedGroup.users.filter(u => u !== username),
    };
    try {
      await FlowApi.savePermissionGroup(updated, 'save');
      setGroups(groups.map(g => g.id === updated.id ? updated : g));
    } catch (err: any) {
      message.error(`保存失败: ${err.message}`);
    }
  };

  const handleRenameGroup = async () => {
    if (!selectedGroup || !nameDraft.trim()) return;
    const updated = { ...selectedGroup, name: nameDraft.trim() };
    try {
      await FlowApi.savePermissionGroup(updated, 'save');
      setGroups(groups.map(g => g.id === updated.id ? updated : g));
      setEditingName('');
      message.success('重命名成功');
    } catch (err: any) {
      message.error(`重命名失败: ${err.message}`);
    }
  };

  const handleAssignPending = async (username: string, groupIds: string[]) => {
    try {
      await FlowApi.assignPendingUser(username, groupIds);
      setPendingUsers(pendingUsers.filter(p => p.username !== username));
      fetchData(); // refresh groups
      message.success(`已分配 ${username} 到 ${groupIds.length} 个组`);
    } catch (err: any) {
      message.error(`分配失败: ${err.message}`);
    }
  };

  const handleDeletePending = async (username: string) => {
    try {
      await FlowApi.deletePendingUser(username);
      setPendingUsers(pendingUsers.filter(p => p.username !== username));
      message.success('已移除');
    } catch (err: any) {
      message.error(`移除失败: ${err.message}`);
    }
  };

  // Group nodes by category
  const nodesByCategory: Record<string, NodeTypeItem[]> = {};
  for (const n of allNodes) {
    if (!nodesByCategory[n.category]) nodesByCategory[n.category] = [];
    nodesByCategory[n.category].push(n);
  }
  const categoryNames: Record<string, string> = {
    datasource: '数据源', collection: '集合处理', builder: '构建器',
    expression: '表达式', ai: 'AI', controlflow: '流程控制',
    basic: '基础值', renderer: '渲染器', tool: '工具',
  };

  return (
    <Modal
      title={<span style={{ fontWeight: 700 }}>🔐 权限编辑</span>}
      open={open}
      onCancel={onClose}
      footer={null}
      width={1000}
      destroyOnHidden
      loading={loading}
    >
      <Tabs
        items={[
          {
            key: 'groups',
            label: '权限组',
            children: (
              <Row gutter={16} style={{ minHeight: 400 }}>
                {/* Left: group list */}
                <Col span={6}>
                  <div style={{ marginBottom: 8 }}>
                    <Button size="small" icon={<PlusOutlined />} onClick={handleAddGroup}>新增组</Button>
                  </div>
                  <div style={{ maxHeight: 380, overflowY: 'auto', border: '1px solid #f0f0f0', borderRadius: 4 }}>
                    {groups.map(g => (
                      <div
                        key={g.id}
                        onClick={() => { setSelectedGroupId(g.id); setNameDraft(g.name); }}
                        style={{
                          padding: '6px 10px',
                          cursor: 'pointer',
                          background: selectedGroupId === g.id ? '#e6f7ff' : 'transparent',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          borderBottom: '1px solid #f0f0f0',
                        }}
                      >
                        <span style={{ fontSize: 13 }}>
                          {g.name}
                          {g.users.includes('*') && <Tag color="blue" style={{ marginLeft: 4, fontSize: 10 }}>全员</Tag>}
                        </span>
                        {!g.users.includes('*') && (
                          <Popconfirm title="确认删除此权限组？" onConfirm={() => handleDeleteGroup(g.id)} okText="删除" cancelText="取消">
                            <DeleteOutlined style={{ color: '#999', fontSize: 12 }} />
                          </Popconfirm>
                        )}
                      </div>
                    ))}
                  </div>
                </Col>
                {/* Right: selected group detail */}
                <Col span={18}>
                  {!selectedGroup ? (
                    <Empty description="请选择左侧权限组" />
                  ) : (
                    <div>
                      {/* Group name */}
                      <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
                        {editingName === selectedGroup.id ? (
                          <>
                            <Input
                              size="small"
                              value={nameDraft}
                              onChange={e => setNameDraft(e.target.value)}
                              style={{ width: 180 }}
                              onPressEnter={handleRenameGroup}
                            />
                            <Button size="small" icon={<SaveOutlined />} onClick={handleRenameGroup} />
                          </>
                        ) : (
                          <>
                            <span style={{ fontWeight: 600, fontSize: 14 }}>{selectedGroup.name}</span>
                            {!selectedGroup.users.includes('*') && (
                              <Button size="small" type="link" icon={<EditOutlined />} onClick={() => { setEditingName(selectedGroup.id); setNameDraft(selectedGroup.name); }}>
                                改名
                              </Button>
                            )}
                          </>
                        )}
                      </div>

                      {/* Node types checkboxes grouped by category */}
                      <div style={{ maxHeight: 280, overflowY: 'auto', border: '1px solid #f0f0f0', borderRadius: 4, padding: 8 }}>
                        {Object.entries(nodesByCategory).map(([cat, nodes]) => (
                          <div key={cat} style={{ marginBottom: 8 }}>
                            <div style={{ fontWeight: 600, fontSize: 12, color: '#666', marginBottom: 4 }}>
                              {categoryNames[cat] || cat}
                            </div>
                            <Checkbox.Group
                              value={selectedGroup.nodeTypes}
                              onChange={() => {}} // handled by individual checkbox
                            >
                              <Row gutter={[8, 4]}>
                                {nodes.map(n => (
                                  <Col key={n.type}>
                                    <Checkbox
                                      checked={selectedGroup.nodeTypes.includes(n.type)}
                                      onChange={e => handleToggleNode(n.type, e.target.checked)}
                                    >
                                      <span style={{ fontSize: 12 }}>{n.name}</span>
                                    </Checkbox>
                                  </Col>
                                ))}
                              </Row>
                            </Checkbox.Group>
                          </div>
                        ))}
                      </div>

                      {/* Users */}
                      {!selectedGroup.users.includes('*') && (
                        <div style={{ marginTop: 12 }}>
                          <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>
                            组内用户 ({selectedGroup.users.length})
                          </div>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                            {selectedGroup.users.map(u => (
                              <Tag
                                key={u}
                                closable
                                onClose={() => handleToggleUser(u, false)}
                                style={{ cursor: 'pointer' }}
                              >
                                {u}
                              </Tag>
                            ))}
                            <AddUserTag onAdd={username => handleToggleUser(username, true)} />
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </Col>
              </Row>
            ),
          },
          {
            key: 'pending',
            label: `待分配用户 (${pendingUsers.length})`,
            children: (
              <Table
                dataSource={pendingUsers}
                rowKey="username"
                size="small"
                pagination={false}
                locale={{ emptyText: '暂无待分配用户' }}
                columns={[
                  {
                    title: '用户名', dataIndex: 'username', key: 'username', width: 140,
                  },
                  {
                    title: '最近登录', dataIndex: 'loginAt', key: 'loginAt', width: 170,
                    render: (v: string) => v ? new Date(v).toLocaleString('zh-CN') : '-',
                  },
                  {
                    title: '分配到组', key: 'assign',
                    render: (_: any, r: PendingUser) => (
                      <Space>
                        {groups.filter(g => !g.users.includes('*')).map(g => (
                          <Checkbox
                            key={g.id}
                            onChange={e => {
                              if (e.target.checked) {
                                handleAssignPending(r.username, [g.id]);
                              }
                            }}
                          >
                            <span style={{ fontSize: 12 }}>{g.name}</span>
                          </Checkbox>
                        ))}
                      </Space>
                    ),
                  },
                  {
                    title: '操作', key: 'action', width: 70,
                    render: (_: any, r: PendingUser) => (
                      <Popconfirm title="移除此记录？" onConfirm={() => handleDeletePending(r.username)} okText="移除" cancelText="取消">
                        <Button size="small" type="link" danger>移除</Button>
                      </Popconfirm>
                    ),
                  },
                ]}
              />
            ),
          },
        ]}
      />
    </Modal>
  );
};

/** Inline tag that adds a user on click */
const AddUserTag: React.FC<{ onAdd: (username: string) => void }> = ({ onAdd }) => {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState('');

  if (!editing) {
    return (
      <Tag onClick={() => setEditing(true)} style={{ cursor: 'pointer', background: '#fff', borderStyle: 'dashed' }}>
        <UserAddOutlined /> 添加用户
      </Tag>
    );
  }

  return (
    <span>
      <Input
        size="small"
        style={{ width: 100, height: 22, fontSize: 11 }}
        value={value}
        onChange={e => setValue(e.target.value)}
        onPressEnter={() => {
          if (value.trim()) {
            onAdd(value.trim());
            setValue('');
            setEditing(false);
          }
        }}
        onBlur={() => setEditing(false)}
        autoFocus
        placeholder="输入用户名"
      />
    </span>
  );
};

export default PermissionModal;
