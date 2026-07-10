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

  // Close on outside click/mousedown
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    // Use capture so we get it before ReactFlow stops propagation
    document.addEventListener('mousedown', handler, true);
    return () => document.removeEventListener('mousedown', handler, true);
  }, [onClose]);

  // Close when user scrolls OUTSIDE the panel (e.g. page scroll / ReactFlow canvas pan)
  // but NOT when scrolling inside the panel itself
  useEffect(() => {
    const closeIfOutside = (e: Event) => {
      if (panelRef.current && panelRef.current.contains(e.target as Node)) return;
      onClose();
    };
    // scroll: covers normal page/container scroll
    window.addEventListener('scroll', closeIfOutside, true);
    // wheel: covers ReactFlow canvas zoom/pan (uses wheel, not scroll)
    window.addEventListener('wheel', closeIfOutside, true);
    window.addEventListener('resize', onClose);
    return () => {
      window.removeEventListener('scroll', closeIfOutside, true);
      window.removeEventListener('wheel', closeIfOutside, true);
      window.removeEventListener('resize', onClose);
    };
  }, [onClose]);

  // Intercept wheel events on the panel so they don't reach ReactFlow's canvas handler
  useEffect(() => {
    const panel = panelRef.current;
    if (!panel) return;
    const onWheel = (e: WheelEvent) => {
      // Always stop propagation so ReactFlow never sees this wheel event
      e.stopPropagation();
      // Let the panel scroll naturally (don't call preventDefault)
    };
    panel.addEventListener('wheel', onWheel, { passive: true, capture: false });
    return () => panel.removeEventListener('wheel', onWheel);
  }, []);

  const panelStyle: React.CSSProperties = {
    position: 'fixed',
    top: triggerRect.bottom + 2,
    left: triggerRect.left,
    width: triggerRect.width,
    zIndex: 99999,
    background: '#fff',
    border: '1px solid #d9d9d9',
    borderRadius: 4,
    boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
    maxHeight: 240,
    overflowY: 'auto',
  };

  return ReactDOM.createPortal(
    <div ref={panelRef} style={panelStyle}>
      {options.length === 0 ? (
        <div style={{ padding: '8px 10px', fontSize: 11, color: '#999' }}>加载中…</div>
      ) : (
        options.map((opt) => {
          const isActive = opt.value === value;
          return (
            <div
              key={opt.value}
              onMouseDown={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onSelect(opt.value);
                onClose();
              }}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '5px 8px', cursor: 'pointer',
                background: isActive ? '#e6f7ff' : 'transparent',
                borderLeft: isActive ? '2px solid #1890ff' : '2px solid transparent',
              }}
              onMouseEnter={(e) => {
                if (!isActive) (e.currentTarget as HTMLDivElement).style.background = '#f5f5f5';
              }}
              onMouseLeave={(e) => {
                if (!isActive) (e.currentTarget as HTMLDivElement).style.background = 'transparent';
              }}
            >
              <TypeBadge type={opt.type} />
              <span style={{
                fontSize: 11, color: '#262626', flex: 1,
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {opt.label}
              </span>
              {isActive && <span style={{ color: '#1890ff', fontSize: 10, flexShrink: 0 }}>✓</span>}
            </div>
          );
        })
      )}
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
            <span style={{
              flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              color: locked ? '#bbb' : '#262626',
            }}>
              {selected.label}
            </span>
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
