/**
 * PanelSection — 可折叠面板块，供 PropertyPanel 和 NodeDetailModal 共用。
 *
 * 样式：深灰色标题栏（#e6e6e6）+ 白色内容区 + 圆角边框，与 NodeDetailModal 保持一致。
 */
import React, { useState } from 'react';

interface PanelSectionProps {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
  /** 标题右侧额外内容（如 Tag、统计数字等） */
  extra?: React.ReactNode;
  /** 紧凑模式：使用更小的 padding，适合 PropertyPanel 侧边栏 */
  compact?: boolean;
}

export function PanelSection({
  title,
  children,
  defaultOpen = true,
  extra,
  compact = false,
}: PanelSectionProps) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div
      style={{
        marginBottom: 10,
        border: '1px solid #d9d9d9',
        borderRadius: 6,
        overflow: 'hidden',
      }}
    >
      <div
        onClick={() => setOpen(!open)}
        style={{
          padding: compact ? '7px 10px' : '10px 14px',
          background: '#e6e6e6',
          fontWeight: compact ? 600 : 700,
          fontSize: compact ? 12 : 13,
          color: '#333',
          cursor: 'pointer',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          userSelect: 'none',
        }}
      >
        <span>{title}</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {extra}
          <span style={{ fontSize: 10, color: '#666' }}>{open ? '▼' : '▶'}</span>
        </span>
      </div>
      {open && (
        <div
          style={{
            padding: compact ? '8px 10px' : '12px 14px',
            background: '#fff',
          }}
        >
          {children}
        </div>
      )}
    </div>
  );
}

export default PanelSection;
