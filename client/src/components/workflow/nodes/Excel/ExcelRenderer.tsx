import React, { useMemo } from 'react';
import { Table } from 'antd';

/**
 * Excel result renderer using antd Table.
 * Displays structured Excel data (columns + rows) as a filterable table.
 */
interface ExcelRendererProps {
  data: {
    columns?: string[];
    rows?: Record<string, any>[];
  };
  columnFilter?: string[];
  rowFilter?: string[];
}

const ExcelRenderer: React.FC<ExcelRendererProps> = ({ data, columnFilter, rowFilter }) => {
  const { columns = [], rows = [] } = data || {};

  const filteredColumns = useMemo(() => {
    const displayCols = columnFilter && columnFilter.length > 0
      ? columns.filter((c) => columnFilter.includes(c))
      : columns;

    return displayCols.map((col) => ({
      title: col,
      dataIndex: col,
      key: col,
      ellipsis: true,
      width: 150,
    }));
  }, [columns, columnFilter]);

  const filteredRows = useMemo(() => {
    let result = rows;
    if (rowFilter && rowFilter.length > 0) {
      result = rows.filter((_, idx) => rowFilter.includes(String(idx + 1)));
    }
    // Only include filtered column keys in each row
    if (columnFilter && columnFilter.length > 0) {
      result = result.map((row) => {
        const filtered: Record<string, any> = {};
        columnFilter.forEach((col) => {
          if (col in row) filtered[col] = row[col];
        });
        return filtered;
      });
    }
    return result.map((row, idx) => ({ ...row, _key: idx }));
  }, [rows, rowFilter, columnFilter]);

  if (!columns.length && !rows.length) {
    return <div style={{ color: '#999', fontSize: 12, padding: 8 }}>暂无 Excel 数据</div>;
  }

  return (
    <Table
      dataSource={filteredRows}
      columns={filteredColumns}
      rowKey="_key"
      size="small"
      scroll={{ x: 'max-content', y: 300 }}
      pagination={false}
      style={{ fontSize: 12 }}
    />
  );
};

export default ExcelRenderer;
