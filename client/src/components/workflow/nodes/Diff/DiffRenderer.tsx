import React, { useMemo } from 'react';
import DiffEditor, { DiffEditorProps } from '@monaco-editor/react';

/**
 * DiffRenderer — uses Monaco DiffEditor to display side-by-side diff of two strings.
 * Used in the Diff node and NodeDetailModal for rendering diff output.
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
      />
    </div>
  );
};

export default DiffRenderer;
