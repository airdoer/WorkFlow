import React, { memo, useCallback, useEffect, useRef, useState } from 'react';
import ReactDOM from 'react-dom';
import { NodeProps } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';
import { FlowApi } from '../../services/FlowApi';

/* ─── Server option type ──────────────────────────────────────────────── */
interface ServerOption {
  label: string;
  value: string;
  type: 'server' | 'group';
  namespace?: string;
  server_id?: number | string;
}

/* ─── Operation option type ────────────────────────────────────────────── */
interface OperationOption {
  label: string;
  value: string;
  template_id?: number;
  description: string;
}

/* ─── Tag styles ──────────────────────────────────────────────────────── */
const SERVER_TAG_STYLE: Record<ServerOption['type'], React.CSSProperties> = {
  server: { backgroundColor: 'rgba(64,169,255,0.12)', borderColor: '#40a9ff', color: '#1890ff' },
  group:  { backgroundColor: 'rgba(135,208,104,0.12)', borderColor: '#87d068', color: '#52c41a' },
};
const SERVER_TAG_ICON: Record<ServerOption['type'], string> = { server: '🖥️', group: '🗂️' };
const SERVER_TAG_TEXT: Record<ServerOption['type'], string> = { server: '服务器', group: '分组' };

function TypeBadge({ type }: { type: ServerOption['type'] }) {
  const s = SERVER_TAG_STYLE[type];
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 3,
      fontSize: 10, padding: '1px 5px', borderRadius: 3,
      border: `1px solid ${s.borderColor}`,
      backgroundColor: s.backgroundColor as string,
      color: s.color as string,
      flexShrink: 0, lineHeight: 1.4,
    }}>
      <span>{SERVER_TAG_ICON[type]}</span>
      <span>{SERVER_TAG_TEXT[type]}</span>
    </span>
  );
}

/* ─── Generic Portal dropdown ─────────────────────────────────────────── */
interface DropdownPortalProps {
  triggerRect: DOMRect;
  options: { label: string; value: string; type?: string; description?: string }[];
  value: string;
  onSelect: (v: string) => void;
  onClose: () => void;
  placeholder?: string;
  showTypeBadge?: boolean;
  showDescription?: boolean;
}

function DropdownPortal({
  triggerRect, options, value, onSelect, onClose,
  placeholder = '搜索...', showTypeBadge = false, showDescription = false,
}: DropdownPortalProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState('');
  const [highlightIndex, setHighlightIndex] = useState<number>(-1);

  useEffect(() => { inputRef.current?.focus(); }, []);

  const filtered = query.trim()
    ? options.filter((opt) => {
        const q = query.trim().toLowerCase();
        if (opt.label.toLowerCase().includes(q)) return true;
        if (opt.value.toLowerCase().includes(q)) return true;
        if (opt.description && opt.description.toLowerCase().includes(q)) return true;
        return false;
      })
    : options;

  useEffect(() => { setHighlightIndex(-1); }, [query]);

  useEffect(() => {
    if (highlightIndex < 0 || !listRef.current) return;
    const item = listRef.current.children[highlightIndex] as HTMLElement | undefined;
    item?.scrollIntoView({ block: 'nearest' });
  }, [highlightIndex]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) onClose();
    };
    document.addEventListener('mousedown', handler, true);
    return () => document.removeEventListener('mousedown', handler, true);
  }, [onClose]);

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
      <div style={{ padding: '6px 8px', borderBottom: '1px solid #f0f0f0', flexShrink: 0 }}>
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Escape') { e.stopPropagation(); onClose(); return; }
            if (e.key === 'ArrowDown') {
              e.preventDefault(); e.stopPropagation();
              setHighlightIndex((i) => (i < filtered.length - 1 ? i + 1 : 0));
              return;
            }
            if (e.key === 'ArrowUp') {
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
          placeholder={placeholder}
          style={{
            width: '100%', boxSizing: 'border-box', fontSize: 11,
            padding: '3px 7px', border: '1px solid #d9d9d9',
            borderRadius: 3, outline: 'none',
          }}
        />
      </div>
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
                onMouseDown={(e) => { e.preventDefault(); e.stopPropagation(); onSelect(opt.value); onClose(); }}
                onMouseEnter={() => setHighlightIndex(idx)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  padding: '5px 8px', cursor: 'pointer',
                  background: isHighlighted ? '#e6f4ff' : isActive ? '#e6f7ff' : 'transparent',
                  borderLeft: isActive ? '2px solid #1890ff' : isHighlighted ? '2px solid #91caff' : '2px solid transparent',
                  transition: 'background 0.1s',
                }}
              >
                {showTypeBadge && (opt as any).type && <TypeBadge type={(opt as any).type as ServerOption['type']} />}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 11, color: '#262626', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {opt.label}
                  </div>
                  {showDescription && opt.description && (
                    <div style={{ fontSize: 10, color: '#8c8c8c', marginTop: 1 }}>
                      {opt.description}
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

/* ─── Generic StyledSelect ─────────────────────────────────────────────── */
interface StyledSelectProps {
  value: string;
  options: { label: string; value: string; type?: string; description?: string }[];
  onChange: (v: string) => void;
  locked: boolean;
  required?: boolean;
  placeholder?: string;
  showTypeBadge?: boolean;
  showDescription?: boolean;
}

function StyledSelect({
  value, options, onChange, locked, required,
  placeholder = '请选择...', showTypeBadge = false, showDescription = false,
}: StyledSelectProps) {
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

  const triggerStyle: React.CSSProperties = {
    width: '100%', fontSize: 11, padding: '4px 6px',
    border: `1px solid ${open ? '#1890ff' : (required && !value ? '#ffccc7' : '#d9d9d9')}`,
    borderRadius: 3,
    background: locked ? '#f5f5f5' : '#fff',
    cursor: locked ? 'not-allowed' : 'pointer',
    display: 'flex', alignItems: 'center', gap: 5,
    boxSizing: 'border-box', userSelect: 'none',
    transition: 'border-color 0.2s',
    outline: open ? '2px solid rgba(24,144,255,0.2)' : 'none',
  };

  return (
    <>
      <div ref={triggerRef} className="nodrag" style={triggerStyle} onClick={handleOpen}>
        {selected ? (
          <>
            {showTypeBadge && (selected as any).type && (
              <TypeBadge type={(selected as any).type as ServerOption['type']} />
            )}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: locked ? '#bbb' : '#262626' }}>
                {selected.label}
              </div>
            </div>
          </>
        ) : (
          <span style={{ color: '#bfbfbf', flex: 1 }}>{placeholder}</span>
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
          placeholder={`搜索${placeholder.replace('请选择', '')}...`}
          showTypeBadge={showTypeBadge}
          showDescription={showDescription}
        />
      )}
    </>
  );
}

/* ─── SealNode ─────────────────────────────────────────────────────────── */
function SealNode({ data, id, selected }: NodeProps) {
  const [serverOptions, setServerOptions] = useState<ServerOption[]>([]);
  const [operationOptions, setOperationOptions] = useState<OperationOption[]>([]);

  useEffect(() => {
    FlowApi.getC7ServerOptions()
      .then((opts) => setServerOptions(opts as ServerOption[]))
      .catch((err) => console.warn('[SealNode] Failed to load server options:', err));
  }, []);

  useEffect(() => {
    FlowApi.getSealOperationOptions()
      .then((opts) => setOperationOptions(opts as OperationOption[]))
      .catch((err) => console.warn('[SealNode] Failed to load operation options:', err));
  }, []);

  const SEAL_FIELDS: NodeField[] = [
    {
      key: 'serverName',
      label: '目标服务器',
      required: true,
      linkedPortKey: 'serverName',
      renderCustomField: (val, onChange, locked) => (
        <StyledSelect
          value={val || ''}
          options={serverOptions}
          onChange={onChange}
          locked={locked}
          required
          placeholder="请选择服务器或分组"
          showTypeBadge
        />
      ),
    },
    {
      key: 'operation',
      label: '流程',
      required: true,
      renderCustomField: (val, onChange, locked) => (
        <StyledSelect
          value={val || ''}
          options={operationOptions}
          onChange={onChange}
          locked={locked}
          required
          placeholder="请选择流程"
          showDescription
        />
      ),
    },
    {
      key: 'executor',
      label: '执行人',
      type: 'text',
      placeholder: 'chenzhixu',
    },
  ];

  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="🐾"
      label="Seal 海豹"
      nodeType="seal"
      fields={SEAL_FIELDS}
    />
  );
}

export default memo(SealNode);
