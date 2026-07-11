import React, { memo, useCallback, useEffect, useRef, useState } from 'react';
import ReactDOM from 'react-dom';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';
import { FlowApi } from '../../services/FlowApi';

/* ─── option type ─────────────────────────────────────────────────────────── */
interface ServerOption {
  label: string;
  value: string;
  type: 'server' | 'group';
  namespace?: string;
  server_id?: number | string;
}

/* ─── tag styles ──────────────────────────────────────────────────────────── */
const TAG_STYLE: Record<ServerOption['type'], React.CSSProperties> = {
  server: { backgroundColor: 'rgba(64,169,255,0.12)', borderColor: '#40a9ff', color: '#1890ff' },
  group:  { backgroundColor: 'rgba(135,208,104,0.12)', borderColor: '#87d068', color: '#52c41a' },
};
const TAG_ICON: Record<ServerOption['type'], string> = { server: '🖥️', group: '🗂️' };
const TAG_TEXT: Record<ServerOption['type'], string> = { server: '服务器', group: '分组' };

function TypeBadge({ type }: { type: ServerOption['type'] }) {
  const s = TAG_STYLE[type];
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 3,
      fontSize: 10, padding: '1px 5px', borderRadius: 3,
      border: `1px solid ${s.borderColor}`,
      backgroundColor: s.backgroundColor as string,
      color: s.color as string,
      flexShrink: 0, lineHeight: 1.4,
    }}>
      <span>{TAG_ICON[type]}</span>
      <span>{TAG_TEXT[type]}</span>
    </span>
  );
}

/* ─── Portal dropdown ─────────────────────────────────────────────────────── */
interface DropdownPortalProps {
  triggerRect: DOMRect;
  options: ServerOption[];
  value: string;
  onSelect: (v: string) => void;
  onClose: () => void;
}

function DropdownPortal({ triggerRect, options, value, onSelect, onClose }: DropdownPortalProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState('');
  const [highlightIndex, setHighlightIndex] = useState<number>(-1);

  // Auto-focus input on open
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Filter options by query: match name (label), namespace (value), or server_id
  const filtered = query.trim()
    ? options.filter((opt) => {
        const q = query.trim().toLowerCase();
        if (opt.label.toLowerCase().includes(q)) return true;
        if (opt.namespace && opt.namespace.toLowerCase().includes(q)) return true;
        if (opt.server_id != null && String(opt.server_id).includes(q)) return true;
        return false;
      })
    : options;

  // Reset highlight when filtered list changes
  useEffect(() => {
    setHighlightIndex(-1);
  }, [query]);

  // Scroll highlighted item into view
  useEffect(() => {
    if (highlightIndex < 0 || !listRef.current) return;
    const item = listRef.current.children[highlightIndex] as HTMLElement | undefined;
    item?.scrollIntoView({ block: 'nearest' });
  }, [highlightIndex]);

  // Close on outside click/mousedown
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener('mousedown', handler, true);
    return () => document.removeEventListener('mousedown', handler, true);
  }, [onClose]);

  // Close when user scrolls OUTSIDE the panel
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

  // Intercept wheel events on the panel
  useEffect(() => {
    const panel = panelRef.current;
    if (!panel) return;
    const onWheel = (e: WheelEvent) => { e.stopPropagation(); };
    panel.addEventListener('wheel', onWheel, { passive: true, capture: false });
    return () => panel.removeEventListener('wheel', onWheel);
  }, []);

  const panelStyle: React.CSSProperties = {
    position: 'fixed',
    top: triggerRect.bottom + 2,
    left: triggerRect.left,
    width: Math.max(triggerRect.width, 220),
    zIndex: 99999,
    background: '#fff',
    border: '1px solid #d9d9d9',
    borderRadius: 4,
    boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
    display: 'flex',
    flexDirection: 'column',
    maxHeight: 280,
  };

  return ReactDOM.createPortal(
    <div ref={panelRef} style={panelStyle}>
      {/* Search input */}
      <div style={{ padding: '6px 8px', borderBottom: '1px solid #f0f0f0', flexShrink: 0 }}>
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Escape') { e.stopPropagation(); onClose(); return; }
            if (e.key === 'ArrowDown') {
              e.preventDefault();
              e.stopPropagation();
              setHighlightIndex((i) => (i < filtered.length - 1 ? i + 1 : 0));
              return;
            }
            if (e.key === 'ArrowUp') {
              e.preventDefault();
              e.stopPropagation();
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
          placeholder="搜索 name / namespace / server_id"
          style={{
            width: '100%',
            boxSizing: 'border-box',
            fontSize: 11,
            padding: '3px 7px',
            border: '1px solid #d9d9d9',
            borderRadius: 3,
            outline: 'none',
          }}
        />
      </div>

      {/* Options list */}
      <div ref={listRef} style={{ overflowY: 'auto', flex: 1 }}>
        {options.length === 0 ? (
          <div style={{ padding: '8px 10px', fontSize: 11, color: '#999' }}>加载中…</div>
        ) : filtered.length === 0 ? (
          <div style={{ padding: '8px 10px', fontSize: 11, color: '#999' }}>无匹配结果</div>
        ) : (
          filtered.map((opt, idx) => {
            const isActive = opt.value === value;
            const isHighlighted = idx === highlightIndex;
            return (
              <div
                key={opt.value}
                onMouseDown={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  onSelect(opt.value);
                  onClose();
                }}
                onMouseEnter={() => setHighlightIndex(idx)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  padding: '5px 8px', cursor: 'pointer',
                  background: isHighlighted ? '#e6f4ff' : isActive ? '#e6f7ff' : 'transparent',
                  borderLeft: isActive ? '2px solid #1890ff' : isHighlighted ? '2px solid #91caff' : '2px solid transparent',
                  transition: 'background 0.1s',
                }}
              >
                <TypeBadge type={opt.type} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontSize: 11, color: '#262626',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }}>
                    {opt.label}
                  </div>
                  {(opt.namespace || opt.server_id != null) && (
                    <div style={{ fontSize: 10, color: '#8c8c8c', marginTop: 1 }}>
                      {opt.namespace && <span style={{ marginRight: 6 }}>{opt.namespace}</span>}
                      {opt.server_id != null && <span style={{ color: '#b37feb' }}>#{opt.server_id}</span>}
                    </div>
                  )}
                </div>
                {isActive && <span style={{ color: '#1890ff', fontSize: 10, flexShrink: 0 }}>✓</span>}
              </div>
            );
          })
        )}
      </div>
    </div>,
    document.body,
  );
}

/* ─── StyledSelect ────────────────────────────────────────────────────────── */
interface StyledSelectProps {
  value: string;
  options: ServerOption[];
  onChange: (v: string) => void;
  locked: boolean;
  required?: boolean;
}

function StyledSelect({ value, options, onChange, locked, required }: StyledSelectProps) {
  const [open, setOpen] = useState(false);
  const [triggerRect, setTriggerRect] = useState<DOMRect | null>(null);
  const triggerRef = useRef<HTMLDivElement>(null);

  const handleOpen = useCallback(() => {
    if (locked) return;
    if (triggerRef.current) {
      setTriggerRect(triggerRef.current.getBoundingClientRect());
    }
    setOpen(true);
  }, [locked]);

  const handleClose = useCallback(() => setOpen(false), []);

  const selected = options.find((o) => o.value === value);

  const triggerStyle: React.CSSProperties = {
    width: '100%', fontSize: 11, padding: '4px 6px',
    border: `1px solid ${open ? '#1890ff' : (required && !value ? '#ffccc7' : '#d9d9d9')}`,
    borderRadius: 3,
    background: locked ? '#f5f5f5' : '#fff',
    cursor: locked ? 'not-allowed' : 'pointer',
    display: 'flex', alignItems: 'center', gap: 5,
    boxSizing: 'border-box',
    userSelect: 'none',
    transition: 'border-color 0.2s',
    outline: open ? '2px solid rgba(24,144,255,0.2)' : 'none',
  };

  return (
    <>
      <div
        ref={triggerRef}
        className="nodrag"
        style={triggerStyle}
        onClick={handleOpen}
      >
        {selected ? (
          <>
            <TypeBadge type={selected.type} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                color: locked ? '#bbb' : '#262626',
              }}>
                {selected.label}
              </div>
              {(selected.namespace || selected.server_id != null) && (
                <div style={{ fontSize: 10, color: '#8c8c8c', marginTop: 1 }}>
                  {selected.namespace && <span style={{ marginRight: 6 }}>{selected.namespace}</span>}
                  {selected.server_id != null && <span style={{ color: '#b37feb' }}>#{selected.server_id}</span>}
                </div>
              )}
            </div>
          </>
        ) : (
          <span style={{ color: '#bfbfbf', flex: 1 }}>请选择服务器或分组</span>
        )}
        <span style={{
          color: open ? '#1890ff' : '#bfbfbf',
          fontSize: 9, marginLeft: 'auto', flexShrink: 0,
          transform: open ? 'rotate(180deg)' : 'none',
          transition: 'transform 0.2s',
        }}>▼</span>
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

/* ─── C7ServerNode ──────────────────────────────────────────────────────────── */
function C7ServerNode({ data, id, selected }: NodeProps) {
  const [options, setOptions] = useState<ServerOption[]>([]);

  useEffect(() => {
    FlowApi.getC7ServerOptions()
      .then((opts) => setOptions(opts as ServerOption[]))
      .catch((err) => console.warn('[C7ServerNode] Failed to load options:', err));
  }, []);

  const C7_FIELDS: NodeField[] = [
    {
      key: 'serverName',
      label: '服务器名',
      required: true,
      renderCustomField: (val, onChange, locked) => (
        <StyledSelect
          value={val || ''}
          options={options}
          onChange={onChange}
          locked={locked}
          required
        />
      ),
    },
  ];

  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="🖥️"
      label="C7 服务器"
      nodeType="c7server"
      fields={C7_FIELDS}
    />
  );
}

export default memo(C7ServerNode);
