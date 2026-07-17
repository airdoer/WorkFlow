/**
 * DiffNode
 * - 接受两个 string 输入（内容1 = contentA / 内容2 = contentB）
 * - 输出 isSame（bool）
 * - 运行后用 Monaco DiffEditor 展示 side-by-side diff
 */

import React, { memo, useCallback, lazy, Suspense } from 'react';
import { NodeProps, useReactFlow, useStore } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';
import { useWorkflowContext } from '../../WorkflowContext';
import DiffSummary from './DiffSummary';

const DiffRenderer = lazy(() => import('./DiffRenderer'));

function DiffNode({ data, id, selected }: NodeProps) {
  const { getRunOutput } = useWorkflowContext();
  const nodeData = data as Record<string, unknown>;

  const runOutput = getRunOutput(id);
  const runStatus = (nodeData._runStatusHint as string) || 'idle';

  const hasContentAEdge = useStore(
    useCallback((s) => s.edges.some((e) => e.target === id && e.targetHandle === 'contentA'), [id]),
  );
  const hasContentBEdge = useStore(
    useCallback((s) => s.edges.some((e) => e.target === id && e.targetHandle === 'contentB'), [id]),
  );

  // Get upstream content for preview
  const upstreamContentA = useStore(
    useCallback((s) => {
      if (!hasContentAEdge) return undefined;
      const edge = s.edges.find((e) => e.target === id && e.targetHandle === 'contentA');
      if (!edge) return undefined;
      const srcOutput = getRunOutput(edge.source);
      if (!srcOutput) return undefined;
      return srcOutput[edge.sourceHandle] ?? srcOutput.value ?? '';
    }, [id, hasContentAEdge, getRunOutput]),
  );
  const upstreamContentB = useStore(
    useCallback((s) => {
      if (!hasContentBEdge) return undefined;
      const edge = s.edges.find((e) => e.target === id && e.targetHandle === 'contentB');
      if (!edge) return undefined;
      const srcOutput = getRunOutput(edge.source);
      if (!srcOutput) return undefined;
      return srcOutput[edge.sourceHandle] ?? srcOutput.value ?? '';
    }, [id, hasContentBEdge, getRunOutput]),
  );

  const isSameResult = runOutput?.isSame;
  const diffStats = runOutput?.stats as { additions?: number; deletions?: number } | undefined;

  const contentA = runOutput?.contentA ?? upstreamContentA ?? '';
  const contentB = runOutput?.contentB ?? upstreamContentB ?? '';
  const showDiff = runOutput && runStatus === 'success';

  const fields: NodeField[] = [];

  // DiffSummary or DiffRenderer as extraContentAfterFields
  const extraContentAfterFields = showDiff ? (
    <div style={{ marginTop: 4 }}>
      <DiffSummary isSame={isSameResult} stats={diffStats} />
      {contentA && contentB && (
        <Suspense fallback={<div style={{ fontSize: 10, color: '#999' }}>加载 Diff 渲染器...</div>}>
          <DiffRenderer original={String(contentA)} modified={String(contentB)} />
        </Suspense>
      )}
    </div>
  ) : undefined;

  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="🔀"
      label="Diff"
      nodeType="diff"
      fields={fields}
      extraContentAfterFields={extraContentAfterFields}
    />
  );
}

export default memo(DiffNode);
