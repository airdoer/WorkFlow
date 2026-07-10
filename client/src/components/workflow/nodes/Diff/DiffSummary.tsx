/**
 * DiffSummary — compact diff overview for narrow spaces (node card / property panel).
 *
 * Parses the unified diff text and renders color-coded lines, along with a stats bar.
 * Use DiffRenderer (Monaco) for full-width, detail-level views.
 */
import React, { useMemo, useState } from 'react';

interface DiffStats {
  additions?: number;
  deletions?: number;
  changedLines?: number;
  lengthA?: number;
  lengthB?: number;
}

interface DiffSummaryProps {
  contentA: string;
  contentB: string;
  isSame: boolean;
  stats?: DiffStats;
  unifiedDiff?: string;
  /** Max diff lines to show before "show more" (default: 20) */
  maxLines?: number;
  /** Fixed height for the diff body; undefined = auto */
  height?: number;
}

/** Parse a unified diff string into typed lines for rendering */
function parseDiff(unified: string) {
  return unified.split('\n').map((line) => {
    if (line.startsWith('+++ ') || line.startsWith('--- ')) return { type: 'header' as const, text: line };
    if (line.startsWith('@@'))  return { type: 'hunk' as const, text: line };
    if (line.startsWith('+'))   return { type: 'add' as const, text: line };
    if (line.startsWith('-'))   return { type: 'del' as const, text: line };
    return { type: 'ctx' as const, text: line };
  });
}

const LINE_STYLES: Record<string, React.CSSProperties> = {
  header: { color: '#8c8c8c', background: 'transparent', fontStyle: 'italic' },
  hunk:   { color: '#1890ff', background: '#e6f7ff', borderRadius: 2 },
  add:    { color: '#389e0d', background: '#f6ffed' },
  del:    { color: '#cf1322', background: '#fff2f0' },
  ctx:    { color: '#595959', background: 'transparent' },
};

const DiffSummary: React.FC<DiffSummaryProps> = ({
  contentA,
  contentB,
  isSame,
  stats,
  unifiedDiff = '',
  maxLines = 20,
  height,
}) => {
  const [expanded, setExpanded] = useState(false);

  const lines = useMemo(() => parseDiff(unifiedDiff), [unifiedDiff]);
  // Skip pure file-header lines (--- / +++) for the main list
  const bodyLines = lines.filter((l) => l.type !== 'header');
  const visibleLines = expanded ? bodyLines : bodyLines.slice(0, maxLines);
  const hasMore = bodyLines.length > maxLines && !expanded;

  const additions = stats?.additions ?? 0;
  const deletions = stats?.deletions ?? 0;

  return (
    <div style={{ fontSize: 11, lineHeight: 1.4 }}>
      {/* ── Stats bar ── */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6,
        padding: '4px 6px', background: '#fafafa', borderRadius: 4,
        border: '1px solid #f0f0f0',
      }}>
        {/* isSame badge */}
        <span style={{
          padding: '1px 7px', borderRadius: 10, fontSize: 10, fontWeight: 600,
          background: isSame ? '#f6ffed' : '#fff2f0',
          color: isSame ? '#52c41a' : '#ff4d4f',
          border: `1px solid ${isSame ? '#b7eb8f' : '#ffccc7'}`,
          flexShrink: 0,
        }}>
          {isSame ? '完全相同' : '存在差异'}
        </span>

        {!isSame && (
          <>
            <span style={{ color: '#52c41a', fontWeight: 600 }}>+{additions}</span>
            <span style={{ color: '#ff4d4f', fontWeight: 600 }}>-{deletions}</span>
            {stats?.changedLines !== undefined && (
              <span style={{ color: '#8c8c8c' }}>{stats.changedLines} 行变动</span>
            )}
          </>
        )}

        <div style={{ flex: 1 }} />

        {/* Length comparison */}
        {stats?.lengthA !== undefined && (
          <span style={{ color: '#bfbfbf', fontSize: 10 }}>
            {stats.lengthA}→{stats.lengthB} 字符
          </span>
        )}
      </div>

      {/* ── Content preview / diff lines ── */}
      {isSame ? (
        /* Same: show content preview */
        <div style={{
          padding: '4px 6px', background: '#f6ffed', borderRadius: 4,
          border: '1px solid #d9f7be', maxHeight: height ?? 120, overflowY: 'auto',
          fontSize: 10, color: '#389e0d',
        }}>
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
            {contentA || '(空)'}
          </pre>
        </div>
      ) : unifiedDiff ? (
        /* Different: show unified diff */
        <div style={{
          background: '#fff', border: '1px solid #e8e8e8', borderRadius: 4,
          overflow: 'hidden',
        }}>
          <div style={{
            maxHeight: height ?? 200, overflowY: 'auto',
            fontFamily: 'ui-monospace, "Cascadia Code", "Source Code Pro", Menlo, Consolas, monospace',
          }}>
            {visibleLines.map((line, i) => (
              <div
                key={i}
                style={{
                  padding: '0 6px',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-all',
                  fontSize: 10,
                  ...LINE_STYLES[line.type],
                }}
              >
                {line.text || '\u00a0'}
              </div>
            ))}

            {hasMore && (
              <div
                onClick={() => setExpanded(true)}
                style={{
                  padding: '4px 6px', textAlign: 'center', fontSize: 10,
                  color: '#1890ff', cursor: 'pointer', background: '#f0f5ff',
                  borderTop: '1px solid #e8e8e8',
                }}
              >
                … 还有 {bodyLines.length - maxLines} 行，点击展开
              </div>
            )}

            {expanded && bodyLines.length > maxLines && (
              <div
                onClick={() => setExpanded(false)}
                style={{
                  padding: '4px 6px', textAlign: 'center', fontSize: 10,
                  color: '#8c8c8c', cursor: 'pointer', background: '#fafafa',
                  borderTop: '1px solid #e8e8e8',
                }}
              >
                收起
              </div>
            )}
          </div>
        </div>
      ) : (
        /* No diff text: show raw content comparison */
        <div style={{ display: 'flex', gap: 4 }}>
          {[{ label: '内容1', val: contentA }, { label: '内容2', val: contentB }].map(({ label, val }) => (
            <div key={label} style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 9, color: '#8c8c8c', marginBottom: 2 }}>{label}</div>
              <div style={{
                padding: '3px 5px', background: '#f5f5f5', borderRadius: 3,
                border: '1px solid #e8e8e8', maxHeight: 80, overflowY: 'auto',
                fontSize: 10, color: '#333', fontFamily: 'monospace',
              }}>
                <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                  {val || '(空)'}
                </pre>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default DiffSummary;
