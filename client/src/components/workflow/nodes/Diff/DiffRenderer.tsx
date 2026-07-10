import React, { useRef, useEffect, useMemo } from 'react';
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
}

const DiffRenderer: React.FC<DiffRendererProps> = ({
  original,
  modified,
  language = 'plaintext',
  height = 300,
  readOnly = true,
}) => {
  const editorRef = useRef<any>(null);

  // When original / modified change AFTER the editor is mounted, update the models manually.
  // @monaco-editor/react v4 does not synchronise prop changes to the internal Monaco models.
  useEffect(() => {
    if (!editorRef.current) return;
    try {
      const origEditor = editorRef.current.getOriginalEditor();
      const modEditor = editorRef.current.getModifiedEditor();
      const origModel = origEditor?.getModel();
      const modModel = modEditor?.getModel();
      if (origModel) origModel.setValue(original ?? '');
      if (modModel) modModel.setValue(modified ?? '');
    } catch (_) {
      // Editor may not be fully initialised yet — safe to ignore
    }
  }, [original, modified]);

  const editorOptions = useMemo(
    () => ({
      readOnly,
      renderSideBySide: true,
      scrollBeyondLastLine: false,
      minimap: { enabled: false },
      fontSize: 12,
      lineNumbers: 'on' as const,
      automaticLayout: true,
      folding: true,
      wordWrap: 'on' as const,
    }),
    [readOnly],
  );

  return (
    <div style={{ border: '1px solid #e8e8e8', borderRadius: 4, overflow: 'hidden' }}>
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
