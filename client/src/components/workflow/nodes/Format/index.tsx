import React, { memo, useCallback, useMemo } from 'react';
import { NodeProps, useReactFlow } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';
import { PortDefinition } from '../PortTypes';

/* ─── Variable item stored in nodeData.variables ─────────────────── */
interface VarItem {
  name: string;
}

/**
 * Default variable for new nodes.
 * Naming convention: str1, str2, str3, ... (auto-incremented)
 */
const DEFAULT_VAR: VarItem = { name: 'str1' };

function effectiveVariables(raw: VarItem[]): VarItem[] {
  return raw.length > 0 ? raw : [DEFAULT_VAR];
}

/**
 * Find the next available strN name.
 * Scans existing variable names for str{N} pattern and returns str{max+1}.
 */
function nextVarName(existing: VarItem[]): string {
  let maxN = 0;
  for (const v of existing) {
    const m = v.name.match(/^str(\d+)$/);
    if (m) maxN = Math.max(maxN, parseInt(m[1], 10));
  }
  return `str${maxN + 1}`;
}

/**
 * Build a template string from variable names.
 * Each variable gets a {{varName}} placeholder.
 * Preserves any non-{{strN}} text already in the template.
 */
function rebuildTemplate(vars: VarItem[], oldTemplate: string): string {
  // Extract all {{...}} placeholders that match strN pattern
  const strVars = vars.filter((v) => v.name.trim());
  // Replace the old strN placeholders with the new set
  // Strategy: remove all {{strN}} from old template, then append new ones
  let cleaned = oldTemplate.replace(/\{\{str\d+\}\}/g, '');
  // Append new placeholders
  const placeholders = strVars.map((v) => `{{${v.name}}}`).join('');
  return cleaned + placeholders;
}

/* ─── FormatNode ───────────────────────────────────────────────────── */
function FormatNode({ data, id, selected }: NodeProps) {
  const { setNodes } = useReactFlow();
  const nodeData = data as Record<string, any>;
  const rawVariables: VarItem[] = nodeData.variables || [];
  const variables = effectiveVariables(rawVariables);

  /* --- helpers that directly mutate nodeData via setNodes ---------- */
  const updateNodeData = useCallback(
    (updater: (d: Record<string, any>) => Record<string, any>) => {
      setNodes((nds) =>
        nds.map((n) => (n.id === id ? { ...n, data: updater(n.data as Record<string, any>) } : n)),
      );
    },
    [id, setNodes],
  );

  // Rename a variable — also migrate value and update template
  const updateVarName = useCallback(
    (index: number, newName: string) => {
      updateNodeData((d) => {
        const vars = [...(d.variables || [])];
        const oldName = vars[index]?.name || '';
        vars[index] = { ...vars[index], name: newName };
        const next = { ...d, variables: vars };
        // Migrate value
        if (oldName && oldName !== newName && d[oldName] !== undefined) {
          next[newName] = d[oldName];
          delete next[oldName];
        }
        // Update template: replace {{oldName}} with {{newName}}
        if (oldName && oldName !== newName) {
          next.template = (next.template || '').replace(
            new RegExp(`\\{\\{${oldName}\\}\\}`, 'g'),
            `{{${newName}}}`,
          );
        }
        return next;
      });
    },
    [updateNodeData],
  );

  // Add a new variable slot with auto-incremented name (str2, str3, ...)
  // Also auto-append {{strN}} to the template
  const addVariable = useCallback(() => {
    updateNodeData((d) => {
      const existing = d.variables || [];
      // If current list is empty (default str1 is virtual), materialize it first
      const base = existing.length === 0 ? [{ name: 'str1' }] : [...existing];
      const newName = nextVarName(base);
      const newVars = [...base, { name: newName }];
      // Auto-append {{newName}} to template
      const oldTemplate = d.template || '';
      const newTemplate = oldTemplate + `{{${newName}}}`;
      return { ...d, variables: newVars, template: newTemplate };
    });
  }, [updateNodeData]);

  // Remove a variable and its stored value; also remove {{name}} from template
  const removeVariable = useCallback(
    (index: number) => {
      updateNodeData((d) => {
        const vars = [...(d.variables || [])];
        const removedName = vars[index]?.name || '';
        vars.splice(index, 1);
        const next = { ...d, variables: vars };
        // Remove value
        if (removedName && next[removedName] !== undefined) {
          delete next[removedName];
        }
        // Remove {{removedName}} from template
        if (removedName) {
          next.template = (next.template || '').replace(
            new RegExp(`\\{\\{${removedName}\\}\\}`, 'g'),
            '',
          );
        }
        return next;
      });
    },
    [updateNodeData],
  );

  // Update a variable's value (stored under its name key in nodeData)
  const updateVarValue = useCallback(
    (varName: string, value: string) => {
      if (!varName.trim()) return;
      updateNodeData((d) => ({ ...d, [varName]: value }));
    },
    [updateNodeData],
  );

  /* --- dynamic ports from variables -------------------------------- */
  // Always include at least one input port (str1 as fallback)
  const dynamicPorts = useMemo<PortDefinition[]>(() => {
    const inputs: PortDefinition[] = variables
      .filter((v) => v.name.trim())
      .map((v) => ({
        key: v.name,
        label: v.name,
        type: 'string',
        direction: 'input' as const,
        maxConnections: 1,
      }));

    // Fallback: if no named variables, use str1 input (matches static PortTypes)
    if (inputs.length === 0) {
      inputs.push({ key: 'str1', label: 'str1', type: 'string', direction: 'input' as const, maxConnections: 1 });
    }

    return [
      ...inputs,
      { key: 'result', label: '结果', type: 'string', direction: 'output' as const },
    ];
  }, [variables]);

  /* --- fields: template textarea only ------------------------------ */
  const FORMAT_FIELDS: NodeField[] = useMemo(
    () => [
      {
        key: 'template',
        label: '格式',
        type: 'textarea',
        rows: 2,
        placeholder: 'http://{{str1}}:7800/c7_online_{{str2}}',
        required: true,
      },
    ],
    [],
  );

  /* --- variable rows (rendered BEFORE the template via extraContentBeforeFields) --- */
  const variableSection = (
    <div>
      <div style={{ fontSize: 10, color: '#888', marginBottom: 4 }}>变量</div>
      {variables.map((v, idx) => {
        const isDefault = rawVariables.length === 0 && idx === 0;
        const varKey = v.name.trim() ? v.name : (isDefault ? 'str1' : `__var_val_${idx}`);
        return (
          <div
            key={`var-row-${idx}`}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              marginBottom: 4,
            }}
          >
            {/* Variable name input */}
            <input
              className="nodrag"
              type="text"
              value={v.name}
              onChange={(e) => updateVarName(idx, e.target.value)}
              placeholder="变量名"
              style={{
                flex: '0 0 60px',
                fontSize: 11,
                padding: '3px 5px',
                border: '1px solid rgba(24,144,255,0.35)',
                borderRadius: 3,
                background: 'rgba(24,144,255,0.06)',
                color: '#1890ff',
                fontWeight: 600,
                outline: 'none',
              }}
            />
            {/* Value input — stored under variable name key in nodeData */}
            <input
              className="nodrag"
              type="text"
              defaultValue={nodeData[varKey] ?? ''}
              placeholder="连线或手动输入"
              onBlur={(e) => updateVarValue(varKey, e.target.value)}
              style={{
                flex: 1,
                fontSize: 11,
                padding: '3px 5px',
                border: '1px solid #d9d9d9',
                borderRadius: 3,
                outline: 'none',
                minWidth: 0,
              }}
            />
            {/* Delete button — not shown for the last remaining variable */}
            {variables.length > 1 && (
              <button
                onClick={() => removeVariable(idx)}
                title="删除此变量"
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#bbb',
                  cursor: 'pointer',
                  fontSize: 15,
                  lineHeight: 1,
                  padding: '0 2px',
                  flexShrink: 0,
                  transition: 'color 0.15s',
                }}
                onMouseEnter={(e) => { (e.target as HTMLElement).style.color = '#ff4d4f'; }}
                onMouseLeave={(e) => { (e.target as HTMLElement).style.color = '#bbb'; }}
              >
                ×
              </button>
            )}
          </div>
        );
      })}
      {/* Add variable button */}
      <div style={{ display: 'flex', justifyContent: 'center', padding: '3px 0 2px' }}>
        <button
          onClick={addVariable}
          style={{
            background: 'rgba(24, 144, 255, 0.08)',
            border: '1px dashed rgba(24, 144, 255, 0.4)',
            borderRadius: 4,
            color: '#1890ff',
            cursor: 'pointer',
            fontSize: 12,
            padding: '3px 14px',
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            transition: 'all 0.2s',
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLElement).style.background = 'rgba(24, 144, 255, 0.18)';
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLElement).style.background = 'rgba(24, 144, 255, 0.08)';
          }}
        >
          <span style={{ fontSize: 15, lineHeight: 1 }}>＋</span>
          添加变量
        </button>
      </div>
    </div>
  );

  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="🔤"
      label="Format 格式化"
      nodeType="format"
      fields={FORMAT_FIELDS}
      overridePorts={dynamicPorts}
      extraContentBeforeFields={variableSection}
    />
  );
}

/**
 * Initial data for a new Format node.
 * Called from FlowEditor when creating a Format node via QuickAddMenu or drag.
 */
export function getFormatInitialData(): Record<string, any> {
  return {
    variables: [{ name: 'str1' }],
    template: '{{str1}}',
  };
}

export default memo(FormatNode);
