/**
 * TableNode
 * - 接受上游数据（tableInput 端口：string / json-data / any）
 * - 解析为结构化表格：数组 → 单表，字典 → 多表
 * - 在节点卡片中直接渲染 antd Table，支持搜索筛选
 */

import React, { memo, useCallback, useState, useMemo } from 'react';
import { NodeProps, useReactFlow } from 'reactflow';
import { Table, Input } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import BaseNode, { NodeField } from '../BaseNode';
import { useWorkflowContext } from '../../WorkflowContext';

interface TableData {
  title?: string | null;
  columns: string[];
  rows: string[][];
}

export type { TableData };

function buildAntdTable(table: TableData) {
  const antdColumns = table.columns.map((col) => ({
    title: col,
    dataIndex: col,
    key: col,
    ellipsis: true,
    width: 100,
  }));
  const antdDataSource = table.rows.map((row, i) => {
    const rec: Record<string, string> = { _key: String(i) };
    table.columns.forEach((col, j) => { rec[col] = row[j] ?? ''; });
    return rec;
  });
  return { antdColumns, antdDataSource };
}

const MiniTable: React.FC<{ table: TableData; maxRows?: number; compact?: boolean }> = ({ table, maxRows, compact }) => {
  const [searchText, setSearchText] = useState('');
  const { antdColumns, antdDataSource } = useMemo(() => buildAntdTable(table), [table]);

  const filteredData = searchText
    ? antdDataSource.filter((r) => table.columns.some((c) => (r[c] ?? '').toLowerCase().includes(searchText.toLowerCase())))
    : antdDataSource;

  const scrollY = compact ? (maxRows ? maxRows * 22 : 180) : 180;

  return (
    <div style={{ fontSize: 10 }}>
      {table.title && <div style={{ fontWeight: 600, marginBottom: 4, fontSize: 11 }}>{table.title}</div>}
      {!compact && (
        <Input
          size="small"
          placeholder="搜索..."
          prefix={<SearchOutlined />}
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          style={{ marginBottom: 4, fontSize: 10 }}
          className="nodrag"
          allowClear
        />
      )}
      <Table
        columns={antdColumns}
        dataSource={filteredData}
        rowKey="_key"
        size="small"
        pagination={false}
        scroll={{ x: true, y: scrollY }}
        style={{ fontSize: 10 }}
      />
    </div>
  );
};

export { MiniTable };

function TableNode({ data, id, selected }: NodeProps) {
  const { getRunOutput } = useWorkflowContext();
  const nodeData = data as Record<string, unknown>;

  // Parse tables from output
  const runStatus = (nodeData._runStatusHint as string) || 'idle';
  const runOutput = getRunOutput(id);
  const tables: TableData[] | null = (() => {
    if (!runOutput || runStatus === 'idle' || runStatus === 'running') return null;
    if (runOutput.error) return null;
    if (Array.isArray(runOutput.tables)) return runOutput.tables as TableData[];
    return null;
  })();

  const fields: NodeField[] = [];

  const extraContentAfterFields = tables && tables.length > 0 ? (
    <div style={{ marginTop: 4, width: '100%', overflow: 'hidden' }}>
      {tables.map((t, i) => (
        <MiniTable key={i} table={t} />
      ))}
    </div>
  ) : undefined;

  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="📊"
      label="Table"
      nodeType="table"
      fields={fields}
      extraContentAfterFields={extraContentAfterFields}
    />
  );
}

export default memo(TableNode);
