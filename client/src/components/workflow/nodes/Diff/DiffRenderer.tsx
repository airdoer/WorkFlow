import React, { useRef, useEffect, useMemo, useState } from 'react';
import { DiffEditor } from '@monaco-editor/react';

/**
 * DiffRenderer — uses Monaco DiffEditor to display side-by-side diff of two strings.
 *
 * NOTE: Monaco DiffEditor does NOT automatically update its content when `original`/`modified`
 * props change after mount. We work around this by storing the editor instance in a ref
 * and manually calling setValue() whenever the props change.
 */
interface DiffRendererProps {
  /** The original (left) string */
  original: string;
  /** The modified (right) string */
  modified: string;
  /** Language for syntax highlighting (default: 'plaintext') */
  language?: string;
  /** Height of the editor (default: 300) */
  height?: number;
  /** Whether the diff is read-only (default: true) */
  readOnly?: boolean;
  /** Show the toolbar with display options (default: false) */
  showToolbar?: boolean;
}

const DiffRenderer: React.FC<DiffRendererProps> = ({
  original,
  modified,
  language = 'plaintext',
  height = 300,
  readOnly = true,
  showToolbar = false,
}) => {
  const editorRef = useRef<any>(null);
  const [renderSideBySide, setRenderSideBySide] = useState(true);
  const [wordWrap, setWordWrap] = useState<'on' | 'off'>('on');
  const [ignoreWhitespace, setIgnoreWhitespace] = useState<'none' | 'trailing' | 'all'>('none');

  // When original / modified change AFTER the editor is mounted, update the models manually.
  useEffect(() => {
    if (!editorRef.current) return;
    try {
      const origEditor = editorRef.current.getOriginalEditor();
      const modEditor = editorRef.current.getModifiedEditor();
      const origModel = origEditor?.getModel();
      const modModel = modEditor?.getModel();
      if (origModel) origModel.setValue(original ?? '');
      if (modModel) modModel.setValue(modified ?? '');
    } catch (_) {}
  }, [original, modified]);

  // Update editor options when toolbar settings change
  useEffect(() => {
    if (!editorRef.current) return;
    try {
      editorRef.current.updateOptions({
        renderSideBySide,
        wordWrap,
        diffWordWrap: wordWrap,
        ignoreTrimWhitespace: ignoreWhitespace !== 'none',
      });
    } catch (_) {}
  }, [renderSideBySide, wordWrap, ignoreWhitespace]);

  const editorOptions = useMemo(
    () => ({
      readOnly,
      renderSideBySide,
      scrollBeyondLastLine: false,
      minimap: { enabled: false },
      fontSize: 12,
      lineNumbers: 'on' as const,
      automaticLayout: true,
      folding: true,
      wordWrap,
      ignoreTrimWhitespace: ignoreWhitespace !== 'none',
    }),
    [readOnly, renderSideBySide, wordWrap, ignoreWhitespace],
  );

  const btnBase: React.CSSProperties = {
    padding: '3px 10px', fontSize: 11, border: '1px solid #d9d9d9',
    borderRadius: 4, cursor: 'pointer', userSelect: 'none',
  };
  const btnActive: React.CSSProperties = { ...btnBase, background: '#1890ff', color: '#fff', borderColor: '#1890ff' };
  const btnInactive: React.CSSProperties = { ...btnBase, background: '#fff', color: '#595959' };

  return (
    <div style={{ border: '1px solid #e8e8e8', borderRadius: 4, overflow: 'hidden' }}>
      {showToolbar && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px',
          background: '#fafafa', borderBottom: '1px solid #e8e8e8', flexWrap: 'wrap',
        }}>
          {/* Side-by-side / Inline toggle */}
          <span style={{ fontSize: 11, color: '#888', marginRight: 2 }}>视图：</span>
          <button
            style={renderSideBySide ? btnActive : btnInactive}
            onClick={() => setRenderSideBySide(true)}
          >
            并排
          </button>
          <button
            style={!renderSideBySide ? btnActive : btnInactive}
            onClick={() => setRenderSideBySide(false)}
          >
            内联
          </button>

          <span style={{ width: 1, height: 16, background: '#e8e8e8', margin: '0 4px' }} />

          {/* Word wrap */}
          <span style={{ fontSize: 11, color: '#888', marginRight: 2 }}>换行：</span>
          <button
            style={wordWrap === 'on' ? btnActive : btnInactive}
            onClick={() => setWordWrap((v) => (v === 'on' ? 'off' : 'on'))}
          >
            {wordWrap === 'on' ? '开' : '关'}
          </button>

          <span style={{ width: 1, height: 16, background: '#e8e8e8', margin: '0 4px' }} />

          {/* Ignore whitespace */}
          <span style={{ fontSize: 11, color: '#888', marginRight: 2 }}>空白：</span>
          <button
            style={ignoreWhitespace === 'none' ? btnActive : btnInactive}
            onClick={() => setIgnoreWhitespace('none')}
          >
            保留
          </button>
          <button
            style={ignoreWhitespace === 'trailing' ? btnActive : btnInactive}
            onClick={() => setIgnoreWhitespace('trailing')}
          >
            忽略行尾
          </button>
          <button
            style={ignoreWhitespace === 'all' ? btnActive : btnInactive}
            onClick={() => setIgnoreWhitespace('all')}
          >
            忽略全部
          </button>
        </div>
      )}
      <DiffEditor
        original={original}
        modified={modified}
        language={language}
        height={height}
        options={editorOptions}
        theme="vs"
        onMount={(editor) => {
          editorRef.current = editor;
        }}
      />
    </div>
  );
};

export default DiffRenderer;
