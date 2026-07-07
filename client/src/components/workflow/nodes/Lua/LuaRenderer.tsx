import React, { useEffect, useRef } from 'react';
import hljs from 'highlight.js/lib/core';
import lua from 'highlight.js/lib/languages/lua';

// Register Lua language
hljs.registerLanguage('lua', lua);

/**
 * Lua code renderer with syntax highlighting via highlight.js.
 */
interface LuaRendererProps {
  content: string;
  functionName?: string;
  functionContent?: string;
}

const LuaRenderer: React.FC<LuaRendererProps> = ({ content, functionName, functionContent }) => {
  const codeRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (codeRef.current) {
      // Clear previous highlighting
      codeRef.current.innerHTML = '';
      codeRef.current.textContent = functionContent || content;
      try {
        hljs.highlightElement(codeRef.current);
      } catch {
        // Fallback: just show plain text
      }
    }
  }, [content, functionContent]);

  const displayContent = functionContent || content;

  return (
    <div style={{ fontSize: 11, background: '#1e1e1e', borderRadius: 4, overflow: 'hidden' }}>
      {functionName && (
        <div style={{
          padding: '4px 8px',
          background: '#2d2d2d',
          color: '#569cd6',
          fontSize: 10,
          borderBottom: '1px solid #3d3d3d',
          fontWeight: 600,
        }}>
          function {functionName}()
        </div>
      )}
      <div style={{ maxHeight: 300, overflowY: 'auto', padding: 8 }}>
        <pre style={{ margin: 0 }}>
          <code
            ref={codeRef}
            className="language-lua hljs"
            style={{ background: 'transparent', fontSize: 11, lineHeight: 1.5 }}
          >
            {displayContent}
          </code>
        </pre>
      </div>
    </div>
  );
};

export default LuaRenderer;
