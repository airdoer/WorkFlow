import React, { memo, useEffect, useRef, useState } from 'react';
import ReactDOM from 'react-dom';
import { NodeProps } from 'reactflow';
import BaseNode, { type NodeField } from '../BaseNode';
import { FlowApi } from '../../services/FlowApi';

/* ─── 选项类型 ─────────────────────────────────────────────────────────────── */
interface ExcelFileOption {
  label: string;       // name
  value: string;       // key
  localPath: string;
  p4Path: string;
  description: string;
}

/* ─── Portal 下拉框 ──────────────────────────────────────────────────────── */
interface DropdownPortalProps {
  triggerRect: DOMRect;
  options: ExcelFileOption[];
  value: string;
  onSelect: (v: string) => void;
  onClose: () => void;
}

function DropdownPortal({ triggerRect, options, value, onSelect, onClose }: DropdownPortalProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef  = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState('');
  const [highlightIndex, setHighlightIndex] = useState<number>(-1);

  useEffect(() => { inputRef.current?.focus(); }, []);

  const filtered = query.trim()
    ? options.filter((opt) => {
        const q = query.trim().toLowerCase();
        return (
          opt.label.toLowerCase().includes(q) ||
          opt.value.toLowerCase().includes(q) ||
          opt.description.toLowerCase().includes(q) ||
          opt.localPath.toLowerCase().includes(q) ||
          opt.p4Path.toLowerCase().includes(q)
        );
      })
    : options;

  useEffect(() => { setHighlightIndex(-1); }, [query]);

  useEffect(() => {
    if (highlightIndex < 0 || !listRef.current) return;
    const item = listRef.current.children[highlightIndex] as HTMLElement | undefined;
    item?.scrollIntoView({ block: 'nearest' });
  }, [highlightIndex]);

  // 点击外部关闭
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) onClose();
    };
    document.addEventListener('mousedown', handler, true);
    return () => document.removeEventListener('mousedown', handler, true);
  }, [onClose]);

  // 滚动外部时关闭
  useEffect(() => {
    const closeIfOutside = (e: Event) => {
      if (panelRef.current && panelRef.current.contains(e.target as Node)) return;
      onClose();
    };
    window.addEventListener('scroll', closeIfOutside, true);
    window.addEventListener('wheel', closeIfOutside, true);
    window.addEventListener('resize', onClose);
    return () => {
      window.removeEventListener('scroll', closeIfOutside, true);
      window.removeEventListener('wheel', closeIfOutside, true);
      window.removeEventListener('resize', onClose);
    };
  }, [onClose]);

  // 阻止面板内滚轮冒泡
  useEffect(() => {
    const panel = panelRef.current;
    if (!panel) return;
    const onWheel = (e: WheelEvent) => { e.stopPropagation(); };
    panel.addEventListener('wheel', onWheel, { passive: true });
    return () => panel.removeEventListener('wheel', onWheel);
  }, []);

  const panelStyle: React.CSSProperties = {
    position: 'fixed',
    top: triggerRect.bottom + 2,
    left: triggerRect.left,
    width: Math.max(triggerRect.width, 260),
    zIndex: 99999,
    background: '#fff',
    border: '1px solid #d9d9d9',
    borderRadius: 4,
    boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
    display: 'flex',
    flexDirection: 'column',
    maxHeight: 300,
  };

  return ReactDOM.createPortal(
    <div ref={panelRef} style={panelStyle}>
      {/* 搜索框 */}
      <div style={{ padding: '6px 8px', borderBottom: '1px solid #f0f0f0', flexShrink: 0 }}>
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Escape')    { e.stopPropagation(); onClose(); return; }
            if (e.key === 'ArrowDown') {
              e.preventDefault(); e.stopPropagation();
              setHighlightIndex((i) => (i < filtered.length - 1 ? i + 1 : 0));
              return;
            }
            if (e.key === 'ArrowUp')   {
              e.preventDefault(); e.stopPropagation();
              setHighlightIndex((i) => (i > 0 ? i - 1 : filtered.length - 1));
              return;
            }
            if (e.key === 'Enter' && filtered.length > 0) {
              const idx = highlightIndex >= 0 && highlightIndex < filtered.length ? highlightIndex : 0;
              onSelect(filtered[idx].value);
              onClose();
            }
            e.stopPropagation();
          }}
          onMouseDown={(e) => e.stopPropagation()}
          placeholder="搜索 name / key / description / path"
          style={{
            width: '100%', boxSizing: 'border-box',
            fontSize: 11, padding: '3px 7px',
            border: '1px solid #d9d9d9', borderRadius: 3, outline: 'none',
          }}
        />
      </div>

      {/* 选项列表 */}
      <div ref={listRef} style={{ overflowY: 'auto', flex: 1 }}>
        {options.length === 0 ? (
          <div style={{ padding: '8px 10px', fontSize: 11, color: '#999' }}>加载中…</div>
        ) : filtered.length === 0 ? (
          <div style={{ padding: '8px 10px', fontSize: 11, color: '#999' }}>无匹配结果</div>
        ) : filtered.map((opt, idx) => {
          const isActive = opt.value === value;
          const isHighlighted = idx === highlightIndex;
          const pathText = opt.localPath || opt.p4Path || '';
          return (
            <div
              key={opt.value}
              onMouseDown={(e) => {
                e.preventDefault(); e.stopPropagation();
                onSelect(opt.value); onClose();
              }}
              onMouseEnter={() => setHighlightIndex(idx)}
              style={{
                padding: '6px 8px', cursor: 'pointer',
                background: isHighlighted ? '#e6f4ff' : isActive ? '#e6f7ff' : 'transparent',
                borderLeft: isActive
                  ? '2px solid #1890ff'
                  : isHighlighted ? '2px solid #91caff' : '2px solid transparent',
              }}
            >
              {/* 名称行 */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <span style={{ fontSize: 11 }}>📊</span>
                <span style={{
                  fontSize: 11, fontWeight: 600, color: '#262626',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1,
                }}>
                  {opt.label}
                </span>
                <span style={{
                  fontSize: 10, color: '#8c8c8c', flexShrink: 0,
                  background: '#f5f5f5', borderRadius: 2, padding: '0 4px',
                }}>
                  {opt.value}
                </span>
                {isActive && <span style={{ color: '#1890ff', fontSize: 10 }}>✓</span>}
              </div>
              {/* 路径 / 描述 */}
              {(pathText || opt.description) && (
                <div style={{ fontSize: 10, color: '#8c8c8c', marginTop: 2, paddingLeft: 18, lineHeight: 1.3 }}>
                  {pathText && (
                    <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {pathText}
                    </div>
                  )}
                  {opt.description && <div style={{ opacity: 0.8 }}>{opt.description}</div>}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>,
    document.body,
  );
}

/* ─── 触发器 ─────────────────────────────────────────────────────────────── */
interface StyledSelectProps {
  value: string;
  options: ExcelFileOption[];
  onChange: (v: string) => void;
  locked: boolean;
}

function StyledSelect({ value, options, onChange, locked }: StyledSelectProps) {
  const [open, setOpen] = useState(false);
  const [triggerRect, setTriggerRect] = useState<DOMRect | null>(null);
  const triggerRef = useRef<HTMLDivElement>(null);

  const handleOpen = useCallback(() => {
    if (locked) return;
    if (triggerRef.current) setTriggerRect(triggerRef.current.getBoundingClientRect());
    setOpen(true);
  }, [locked]);

  const handleClose = useCallback(() => setOpen(false), []);
  const selected = options.find((o) => o.value === value);

  return (
    <>
      <div
        ref={triggerRef}
        className="nodrag"
        onClick={handleOpen}
        style={{
          width: '100%', fontSize: 11, padding: '4px 6px',
          border: `1px solid ${open ? '#1890ff' : (!value ? '#ffccc7' : '#d9d9d9')}`,
          borderRadius: 3, background: locked ? '#f5f5f5' : '#fff',
          cursor: locked ? 'not-allowed' : 'pointer',
          display: 'flex', alignItems: 'center', gap: 5,
          boxSizing: 'border-box', userSelect: 'none',
          outline: open ? '2px solid rgba(24,144,255,0.2)' : 'none',
        }}
      >
        {selected ? (
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 5,
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              <span>📊</span>
              <span style={{ color: locked ? '#bbb' : '#262626', fontWeight: 600 }}>{selected.label}</span>
              <span style={{ fontSize: 10, color: '#8c8c8c' }}>{selected.value}</span>
            </div>
            {(selected.localPath || selected.p4Path) && (
              <div style={{
                fontSize: 10, color: '#8c8c8c', marginTop: 1,
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {selected.localPath || selected.p4Path}
              </div>
            )}
          </div>
        ) : (
          <span style={{ color: '#bfbfbf', flex: 1 }}>请选择 Excel 文件</span>
        )}
        <span style={{ color: '#bfbfbf', fontSize: 10, flexShrink: 0 }}>▼</span>
      </div>
      {open && triggerRect && (
        <DropdownPortal
          triggerRect={triggerRect}
          options={options}
          value={value}
          onSelect={onChange}
          onClose={handleClose}
        />
      )}
    </>
  );
}

/* ─── ExcelSearchNode ───────────────────────────────────────────────────── */
function ExcelSearchNode({ data, id, selected }: NodeProps) {
  const [options, setOptions] = useState<ExcelFileOption[]>([]);

  // 加载文件列表
  useEffect(() => {
    FlowApi.getExcelSearchOptions()
      .then((opts) => setOptions(opts))
      .catch(() => setOptions([]));
  }, []);

  const FIELDS = [
    {
      key: 'fileKey',
      label: 'Excel 文件',
      required: true,
      renderCustomField: (val: string, onChange: (v: any) => void, locked: boolean) => (
        <StyledSelect
          value={val || ''}
          options={options}
          onChange={onChange}
          locked={locked}
        />
      ),
    },
  ];

  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="🔍"
      label="Excel 搜索"
      nodeType="excelsearch"
      fields={FIELDS}
    />
  );
}

export default memo(ExcelSearchNode);
