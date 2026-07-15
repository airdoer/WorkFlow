import React, { useCallback, useEffect, useRef, useState } from 'react';
import { nodeRegistryList } from './NodeRegistry';
import { getNodePorts, isPortTypeCompatible } from './PortTypes';

interface QuickAddMenuProps {
  /** ReactFlow canvas coordinates for positioning the new node */
  canvasPosition: { x: number; y: number };
  /** The source node id that the connection originates from */
  sourceId: string;
  /** The source handle (port key) that the connection originates from */
  sourceHandle: string;
  /** Port type of the source handle, used for compatibility filtering */
  sourcePortType?: string;
  /** Callback when user selects a node type */
  onSelect: (nodeType: string, targetHandle: string) => void;
  /** Close the menu */
  onClose: () => void;
  /** Position style (fixed positioning from mouse release point) */
  style?: React.CSSProperties;
}

const QuickAddMenu: React.FC<QuickAddMenuProps> = ({
  canvasPosition,
  sourceId,
  sourceHandle,
  sourcePortType,
  onSelect,
  onClose,
  style,
}) => {
  const [search, setSearch] = useState('');
  const [highlightIdx, setHighlightIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const itemRefs = useRef<(HTMLDivElement | null)[]>([]);

  // Auto-focus search on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Adjust position to stay within viewport
  useEffect(() => {
    if (!menuRef.current) return;
    const rect = menuRef.current.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    let adjusted = false;
    let left = parseFloat(String(menuRef.current.style.left)) || 0;
    let top = parseFloat(String(menuRef.current.style.top)) || 0;
    if (rect.right > vw) { left = vw - rect.width - 8; adjusted = true; }
    if (rect.bottom > vh) { top = vh - rect.height - 8; adjusted = true; }
    if (left < 0) { left = 8; adjusted = true; }
    if (top < 0) { top = 8; adjusted = true; }
    if (adjusted) {
      menuRef.current.style.left = `${left}px`;
      menuRef.current.style.top = `${top}px`;
    }
  }, []);

  // Close on Escape or click outside
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    };
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [onClose]);

  // Filter nodes by search + compatibility
  const filtered = search.trim()
    ? nodeRegistryList.filter((e) =>
        e.label.toLowerCase().includes(search.toLowerCase()) ||
        e.type.toLowerCase().includes(search.toLowerCase()) ||
        (e.category || '').toLowerCase().includes(search.toLowerCase()) ||
        (e.description || '').toLowerCase().includes(search.toLowerCase()),
      )
    : nodeRegistryList;

  // Find first compatible input port for a given node type
  const getTargetHandle = useCallback(
    (nodeType: string): string | null => {
      const inputPorts = getNodePorts(nodeType).filter((p) => p.direction === 'input');
      if (!inputPorts.length) return null;
      // Prefer compatible port
      if (sourcePortType) {
        const compatible = inputPorts.find((p) => isPortTypeCompatible(sourcePortType, p.type));
        if (compatible) return compatible.key;
      }
      // Fallback to first input port
      return inputPorts[0].key;
    },
    [sourcePortType],
  );

  // Only show node types that have at least one input port
  const connectable = filtered.filter((e) => getNodePorts(e.type).some((p) => p.direction === 'input'));

  // Keyboard navigation
  const handleSearchKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setHighlightIdx((i) => Math.min(i + 1, connectable.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setHighlightIdx((i) => Math.max(i - 1, 0));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (connectable[highlightIdx]) {
          const targetHandle = getTargetHandle(connectable[highlightIdx].type);
          if (targetHandle) {
            onSelect(connectable[highlightIdx].type, targetHandle);
          }
        }
      }
    },
    [connectable, highlightIdx, getTargetHandle, onSelect],
  );

  // Scroll highlighted item into view
  useEffect(() => {
    const el = itemRefs.current[highlightIdx];
    el?.scrollIntoView({ block: 'nearest' });
  }, [highlightIdx]);

  // Group by category
  const grouped = connectable.reduce<Record<string, typeof connectable>>((acc, entry) => {
    const cat = entry.category || '其他';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(entry);
    return acc;
  }, {});

  // Flatten for indexed access
  const flatItems = connectable;

  // Position the menu near the canvas position, convert to screen coords via CSS
  // We position this as a fixed overlay; the parent converts canvas→screen coords
  const menuStyle: React.CSSProperties = {
    position: 'fixed',
    zIndex: 1000,
    minWidth: 240,
    maxWidth: 320,
    maxHeight: 400,
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
    background: '#1f2f3f',
    border: '1px solid #3a4a5a',
    borderRadius: 8,
    boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
    color: '#e8edf2',
    fontSize: 13,
    left: style?.left ?? 0,
    top: style?.top ?? 0,
  };

  return (
    <div ref={menuRef} style={menuStyle}>
      {/* Search input */}
      <div style={{ padding: '8px 10px', borderBottom: '1px solid #2a3a4a', flexShrink: 0 }}>
        <input
          ref={inputRef}
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setHighlightIdx(0);
          }}
          onKeyDown={handleSearchKeyDown}
          placeholder="搜索节点..."
          style={{
            width: '100%',
            fontSize: 13,
            padding: '5px 8px',
            border: '1px solid #3a4a5a',
            borderRadius: 4,
            outline: 'none',
            background: '#2a3a4a',
            color: '#e8edf2',
            boxSizing: 'border-box',
          }}
        />
      </div>

      {/* Node list */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '4px 6px' }}>
        {flatItems.length === 0 ? (
          <div style={{ padding: 12, textAlign: 'center', color: '#888', fontSize: 12 }}>无匹配节点</div>
        ) : (
          Object.entries(grouped).map(([category, entries]) => (
            <div key={category}>
              <div style={{ fontSize: 10, color: '#888', padding: '4px 8px 2px', letterSpacing: 1 }}>
                {category}
              </div>
              {entries.map((entry) => {
                const idx = flatItems.indexOf(entry);
                const isHighlighted = idx === highlightIdx;
                const targetHandle = getTargetHandle(entry.type);
                const isCompatible =
                  sourcePortType && targetHandle
                    ? isPortTypeCompatible(
                        sourcePortType,
                        getNodePorts(entry.type).find((p) => p.key === targetHandle)?.type || '',
                      )
                    : true;
                return (
                  <div
                    key={entry.type}
                    ref={(el) => { itemRefs.current[idx] = el; }}
                    onClick={() => {
                      if (targetHandle) onSelect(entry.type, targetHandle);
                    }}
                    onMouseEnter={() => setHighlightIdx(idx)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '5px 8px',
                      margin: '1px 0',
                      borderRadius: 4,
                      cursor: targetHandle ? 'pointer' : 'not-allowed',
                      background: isHighlighted ? '#2a5080' : 'transparent',
                      transition: 'background 0.1s',
                      opacity: isCompatible ? 1 : 0.5,
                    }}
                    title={entry.description}
                  >
                    <span style={{ fontSize: 14 }}>{entry.icon}</span>
                    <span style={{ flex: 1 }}>{entry.label}</span>
                    {!isCompatible && (
                      <span style={{ fontSize: 10, color: '#ff6b6b' }}>⚠</span>
                    )}
                  </div>
                );
              })}
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default QuickAddMenu;
