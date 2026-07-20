import React, { useMemo } from 'react';
import { EdgeProps, getBezierPath } from 'reactflow';

/**
 * Custom edge with four visual states:
 * - mismatched: red dashed + ✗
 * - matched (not activated): gray line (types compatible but no data flowing yet)
 * - flowing: blue solid + blue flowing dot animation + ⏳ (upstream node is running/polling)
 * - activated: green solid + green flowing dot animation + ✓
 *   (upstream node executed successfully and data flowed through)
 */
const FlowingEdge: React.FC<EdgeProps> = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  markerEnd,
}) => {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const matchStatus: 'matched' | 'mismatched' | 'unknown' =
    (data?.matchStatus as any) || 'unknown';
  const activated: boolean = (data?.activated as boolean) || false;
  const flowing: boolean = (data?.flowing as boolean) || false;

  // Visual state determination:
  // mismatched → always red dashed
  // matched + activated → green with flow (success)
  // matched/unknown + flowing → blue with flow (running/polling)
  // matched + NOT activated/flowing → gray (neutral, types match but no data flow)
  // unknown + NOT activated/flowing → gray (neutral)
  const visualState = useMemo(() => {
    if (matchStatus === 'mismatched') return 'mismatched' as const;
    if ((matchStatus === 'matched' || matchStatus === 'unknown') && activated) return 'activated' as const;
    if ((matchStatus === 'matched' || matchStatus === 'unknown') && flowing) return 'flowing' as const;
    if (matchStatus === 'matched') return 'matched_idle' as const;
    return 'unknown' as const;
  }, [matchStatus, activated, flowing]);

  const edgeStyle = useMemo(() => {
    switch (visualState) {
      case 'activated':
        return { stroke: '#52c41a', strokeWidth: 2.5 };
      case 'flowing':
        return { stroke: '#1890ff', strokeWidth: 2.5 };
      case 'matched_idle':
        // Types match but no data flowing yet — neutral gray
        return { stroke: '#bfbfbf', strokeWidth: 1.5 };
      case 'mismatched':
        return { stroke: '#ff4d4f', strokeWidth: 2, strokeDasharray: '6 3' };
      default:
        return { stroke: '#bfbfbf', strokeWidth: 1.5 };
    }
  }, [visualState]);

  const glowColor = useMemo(() => {
    switch (visualState) {
      case 'activated': return 'rgba(82, 196, 26, 0.2)';
      case 'flowing': return 'rgba(24, 144, 255, 0.15)';
      default: return null;
    }
  }, [visualState]);

  return (
    <g className="react-flow__edge">
      {/* Glow for activated/flowing edges */}
      {glowColor && (
        <path
          d={edgePath}
          fill="none"
          stroke={glowColor}
          strokeWidth={8}
          strokeLinecap="round"
        />
      )}
      {/* Main edge path */}
      <path
        d={edgePath}
        fill="none"
        strokeLinecap="round"
        {...edgeStyle}
        markerEnd={markerEnd}
      />
      {/* Flowing dot animation — for activated and flowing edges */}
      {(visualState === 'activated' || visualState === 'flowing') && (
        <>
          {visualState === 'activated' ? (
            <>
              <circle r="3.5" fill="#52c41a" opacity="0.9">
                <animateMotion dur="1.5s" repeatCount="indefinite" path={edgePath} />
              </circle>
              <circle r="2.5" fill="#95de64" opacity="0.5">
                <animateMotion dur="1.5s" repeatCount="indefinite" path={edgePath} begin="0.75s" />
              </circle>
            </>
          ) : (
            <>
              <circle r="3.5" fill="#1890ff" opacity="0.9">
                <animateMotion dur="2s" repeatCount="indefinite" path={edgePath} />
              </circle>
              <circle r="2.5" fill="#69c0ff" opacity="0.5">
                <animateMotion dur="2s" repeatCount="indefinite" path={edgePath} begin="1s" />
              </circle>
            </>
          )}
        </>
      )}
      {/* Checkmark at midpoint — only for activated edges */}
      {visualState === 'activated' && (
        <g transform={`translate(${labelX}, ${labelY})`}>
          <rect
            x={-10}
            y={-8}
            width={20}
            height={16}
            rx={4}
            fill="#f6ffed"
            stroke="#b7eb8f"
            strokeWidth={1}
          />
          <text
            textAnchor="middle"
            dominantBaseline="central"
            fontSize={10}
            fontWeight={700}
            fill="#389e0d"
          >
            ✓
          </text>
        </g>
      )}
      {/* Flowing indicator — only for flowing (running) edges */}
      {visualState === 'flowing' && (
        <g transform={`translate(${labelX}, ${labelY})`}>
          <rect
            x={-12}
            y={-8}
            width={24}
            height={16}
            rx={4}
            fill="#e6f7ff"
            stroke="#91d5ff"
            strokeWidth={1}
          />
          <text
            textAnchor="middle"
            dominantBaseline="central"
            fontSize={9}
            fontWeight={700}
            fill="#096dd9"
          >
            ⏳
          </text>
        </g>
      )}
      {/* Mismatch indicator — only for mismatched edges */}
      {visualState === 'mismatched' && (
        <g transform={`translate(${labelX}, ${labelY})`}>
          <rect
            x={-10}
            y={-8}
            width={20}
            height={16}
            rx={4}
            fill="#fff2f0"
            stroke="#ffccc7"
            strokeWidth={1}
          />
          <text
            textAnchor="middle"
            dominantBaseline="central"
            fontSize={10}
            fontWeight={700}
            fill="#cf1322"
          >
            ✗
          </text>
        </g>
      )}
    </g>
  );
};

export default FlowingEdge;
