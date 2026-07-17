/**
 * JenkinsDeploy 节点 — 通过级联选择触发 Jenkins 打包/热更任务
 *
 * 级联结构：
 * 1. 分支: Mainline / Preonline
 * 2. 操作: 打包 / 热更
 * 3. 环境: 线上 / 开发环境
 * 4. 跨服: 是 / 否 (仅打包)
 *
 * 根据选择组合，动态显示对应的参数字段和任务链接预览
 */

import React, { memo, useCallback, useEffect, useMemo, useState } from 'react';
import { NodeProps, useReactFlow } from 'reactflow';
import { Checkbox, Select } from 'antd';
import BaseNode, { NodeField } from '../BaseNode';
import { PortDefinition } from '../PortTypes';
import { FlowApi } from '../../services/FlowApi';
import { StyledSelect, TypedOption } from '../SharedStyledSelect';

/* ─── Server option type (shared with Seal node) ──────────────────────── */
interface ServerOption {
  label: string;
  value: string;
  type: 'server' | 'group';
  namespace?: string;
  server_id?: number | string;
  tree_id?: number | null;
  seal_env?: string;
}

/* ─── Job Configuration Map ─────────────────────────────────────────── */
interface JobConfig {
  job_name: string;
  url: string;        // browser-visible URL for preview
  params: string[];   // which param keys this job needs
}

const JENKINS_BASE_URL = 'https://game-hangzhou-jenkinsc7.test.gifshow.com';

// Map: branch_operation_env_cross → JobConfig
const JOB_MAP: Record<string, JobConfig> = {
  // 打包 - Mainline
  'mainline_pack_prod_no':       { job_name: 'Mainline_PublicServer_C7Deploy',        url: `${JENKINS_BASE_URL}/job/Mainline_PublicServer_C7Deploy/`, params: ['changelistID', 'serverName', 'trigger_seal', 'with_server_appendix', 'SERVER_BUILD_TYPE'] },
  'mainline_pack_dev_no':        { job_name: 'Deploy_Local_Mainline',                  url: `${JENKINS_BASE_URL}/view/Server/job/Deploy_Local_Mainline/`, params: ['changelistID', 'serverName', 'with_server_appendix', 'CLEAN_ALL_DB_DATA', 'SERVER_BUILD_TYPE'] },
  'mainline_pack_dev_cross':     { job_name: 'Deploy_Local_Machine_Cross',             url: `${JENKINS_BASE_URL}/job/Deploy_Local_Machine_Cross/`, params: ['changelistID', 'serverName', 'with_server_appendix', 'CLEAN_ALL_DB_DATA', 'SERVER_BUILD_TYPE'] },
  // 打包 - Preonline
  'preonline_pack_prod_no':      { job_name: 'Preonline_PublicServer_C7Deploy',        url: `${JENKINS_BASE_URL}/job/Preonline_PublicServer_C7Deploy/`, params: ['changelistID', 'serverName', 'trigger_seal', 'with_server_appendix', 'SERVER_BUILD_TYPE'] },
  'preonline_pack_dev_no':       { job_name: 'Deploy_Local_Preonline',                 url: `${JENKINS_BASE_URL}/job/Deploy_Local_Preonline/`, params: ['changelistID', 'serverName', 'with_server_appendix', 'CLEAN_ALL_DB_DATA', 'SERVER_BUILD_TYPE'] },
  'preonline_pack_dev_cross':    { job_name: 'Deploy_Local_Machine_Cross_Preonline',   url: `${JENKINS_BASE_URL}/job/Deploy_Local_Machine_Cross_Preonline/`, params: ['changelistID', 'serverName', 'with_server_appendix', 'CLEAN_ALL_DB_DATA', 'SERVER_BUILD_TYPE'] },
  // 热更 - Preonline only
  'preonline_hotfix_prod':       { job_name: 'Reload_Cloud_Preonline',                 url: `${JENKINS_BASE_URL}/job/Reload_Cloud_Preonline/`, params: ['changelistID', 'HOTFIX_TYPES', 'DEPLOY_MODE', 'serverName', 'serverGroup'] },
  'preonline_hotfix_dev':        { job_name: 'Preonline_GenerateHotfix',               url: `${JENKINS_BASE_URL}/job/Preonline_GenerateHotfix/`, params: ['changelistID', 'serverName', 'HOTFIX_TYPES'] },
};

/* ─── Cascading option types ────────────────────────────────────────── */
const BRANCH_OPTIONS: TypedOption[] = [
  { label: 'Mainline', value: 'mainline', type: '' },
  { label: 'Preonline', value: 'preonline', type: '' },
];

const OP_OPTIONS: TypedOption[] = [
  { label: '打包', value: 'pack', type: '' },
  { label: '热更', value: 'hotfix', type: '' },
];

const ENV_OPTIONS: TypedOption[] = [
  { label: '线上环境', value: 'prod', type: '' },
  { label: '开发环境', value: 'dev', type: '' },
];

const CROSS_OPTIONS: TypedOption[] = [
  { label: '非跨服', value: 'no', type: '' },
  { label: '跨服', value: 'cross', type: '' },
];

const BUILD_TYPE_OPTIONS: TypedOption[] = [
  { label: 'full（全量）', value: 'full', type: '' },
  { label: 'script（脚本）', value: 'script', type: '' },
  { label: 'lua（热更脚本）', value: 'lua', type: '' },
];

const DEPLOY_MODE_OPTIONS: TypedOption[] = [
  { label: 'namespace（指定服务器）', value: 'namespace', type: '' },
  { label: 'group（服务器组）', value: 'group', type: '' },
];

const HOTFIX_TYPE_OPTIONS = [
  { label: 'server', value: 'server' },
  { label: 'client', value: 'client' },
  { label: 'crates', value: 'crates' },
];

/* ─── Compute job key from selections ────────────────────────────────── */
function getJobKey(branch: string, op: string, env: string, cross: string): string | null {
  if (op === 'hotfix') {
    // 热更只有 Preonline
    if (branch !== 'preonline') return null;
    return `${branch}_hotfix_${env}`;
  }
  // 打包
  if (env === 'prod') {
    return `${branch}_pack_prod_no`;
  }
  return `${branch}_pack_dev_${cross}`;
}

/* ─── JenkinsDeployNode ──────────────────────────────────────────────── */
function JenkinsDeployNode({ data, id, selected }: NodeProps) {
  const { setNodes } = useReactFlow();
  const nodeData = data as Record<string, any>;
  const [allServerOptions, setAllServerOptions] = useState<ServerOption[]>([]);

  const branch = nodeData.branch || '';
  const op = nodeData.op || '';
  const env = nodeData.env || '';
  const cross = nodeData.cross || '';

  useEffect(() => {
    FlowApi.getC7ServerOptions()
      .then((opts) => setAllServerOptions(opts as ServerOption[]))
      .catch((err) => console.warn('[JenkinsDeployNode] Failed to load server options:', err));
  }, []);

  const updateNodeData = useCallback(
    (updater: (d: Record<string, any>) => Record<string, any>) => {
      setNodes((nds) =>
        nds.map((n) => (n.id === id ? { ...n, data: updater(n.data as Record<string, any>) } : n)),
      );
    },
    [id, setNodes],
  );

  /* Derived: which job config is selected */
  const jobKey = getJobKey(branch, op, env, cross);
  const jobConfig = jobKey ? JOB_MAP[jobKey] : null;

  /* Filtered server options based on env */
  const filteredServerOptions = useMemo<ServerOption[]>(() => {
    if (!env || !allServerOptions.length) return allServerOptions;
    if (env === 'prod') {
      // 线上: show servers WITH tree_id (Seal-managed)
      return allServerOptions.filter((s) => s.tree_id);
    }
    // 开发环境: show servers WITHOUT tree_id
    return allServerOptions.filter((s) => !s.tree_id);
  }, [allServerOptions, env]);

  /* Filtered group options for DEPLOY_MODE=group */
  const groupOptions = useMemo<TypedOption[]>(() => {
    // c7ServerTags groups — for now use groups from server options
    return allServerOptions
      .filter((s) => s.type === 'group')
      .map((s) => ({ label: s.label, value: s.value, type: s.type as any }));
  }, [allServerOptions]);

  /* Determine visible fields based on jobConfig.params */
  const visibleParams = jobConfig?.params || [];

  /* Whether cross selector should be shown */
  const showCross = op === 'pack' && env === 'dev';
  /* Whether hotfix fields should show */
  const isHotfix = op === 'hotfix';
  /* Whether deploy mode selector should show (hotfix + prod) */
  const showDeployMode = isHotfix && env === 'prod';
  /* Whether serverGroup should show (hotfix + prod + group mode) */
  const showServerGroup = showDeployMode && nodeData.DEPLOY_MODE === 'group';

  const JENKINS_FIELDS: NodeField[] = useMemo(() => {
    const fields: NodeField[] = [
      {
        key: 'branch',
        label: '分支',
        required: true,
        renderCustomField: (val, onChange, locked) => (
          <StyledSelect value={val || ''} options={BRANCH_OPTIONS} onChange={(v: string) => {
            updateNodeData((d) => {
              const next: Record<string, any> = { ...d, branch: v };
              // If hotfix selected but not preonline, auto-switch
              if (d.op === 'hotfix' && v !== 'preonline') next.op = '';
              return next;
            });
            onChange(v);
          }} locked={locked} required placeholder="Mainline / Preonline" />
        ),
      },
      {
        key: 'op',
        label: '操作',
        required: true,
        renderCustomField: (val, onChange, locked) => {
          const filteredOps = branch === 'mainline'
            ? OP_OPTIONS.filter((o) => o.value !== 'hotfix')
            : OP_OPTIONS;
          return (
            <StyledSelect value={val || ''} options={filteredOps} onChange={(v: string) => {
              updateNodeData((d) => {
                const next: Record<string, any> = { ...d, op: v };
                if (v === 'hotfix') next.branch = 'preonline';
                return next;
              });
              onChange(v);
            }} locked={locked} required placeholder="打包 / 热更" />
          );
        },
      },
      {
        key: 'env',
        label: '环境',
        required: true,
        renderCustomField: (val, onChange, locked) => (
          <StyledSelect value={val || ''} options={ENV_OPTIONS} onChange={(v: string) => {
            updateNodeData((d) => ({ ...d, env: v }));
            onChange(v);
          }} locked={locked} required placeholder="线上 / 开发环境" />
        ),
      },
    ];

    // Cross-server selector (only for pack + dev)
    if (showCross) {
      fields.push({
        key: 'cross',
        label: '跨服',
        required: true,
        renderCustomField: (val, onChange, locked) => (
          <StyledSelect value={val || ''} options={CROSS_OPTIONS} onChange={(v: string) => {
            updateNodeData((d) => ({ ...d, cross: v }));
            onChange(v);
          }} locked={locked} required placeholder="跨服 / 非跨服" />
        ),
      });
    }

    // ChangelistID (always present)
    if (visibleParams.includes('changelistID')) {
      fields.push({
        key: 'changelistID',
        label: 'ChangelistID（版本号）',
        type: 'text',
        required: true,
        placeholder: '如 1234567',
        linkedPortKey: 'changelistID',
      });
    }

    // SERVER_DEPLOY_NAMESPACE
    if (visibleParams.includes('serverName')) {
      fields.push({
        key: 'serverName',
        label: '目标服务器',
        required: true,
        linkedPortKey: 'serverName',
        renderCustomField: (val, onChange, locked) => (
          <StyledSelect
            value={val || ''}
            options={filteredServerOptions as TypedOption[]}
            onChange={(v: string) => { updateNodeData((d) => ({ ...d, serverName: v })); onChange(v); }}
            locked={locked}
            required
            placeholder={env === 'prod' ? '选择线上服务器（有tree_id）' : '选择开发服务器'}
            showTypeBadge
          />
        ),
      });
    }

    // Deploy mode (hotfix + prod only)
    if (showDeployMode) {
      fields.push({
        key: 'DEPLOY_MODE',
        label: '部署模式',
        required: true,
        renderCustomField: (val, onChange, locked) => (
          <StyledSelect value={val || 'namespace'} options={DEPLOY_MODE_OPTIONS} onChange={(v: string) => {
            updateNodeData((d) => ({ ...d, DEPLOY_MODE: v, serverName: v === 'group' ? '' : d.serverName, serverGroup: v === 'namespace' ? '' : d.serverGroup }));
            onChange(v);
          }} locked={locked} required placeholder="namespace / group" />
        ),
      });
    }

    // Server group (hotfix + prod + group mode)
    if (showServerGroup) {
      fields.push({
        key: 'serverGroup',
        label: '服务器组',
        required: true,
        linkedPortKey: 'serverGroup',
        renderCustomField: (val, onChange, locked) => (
          <StyledSelect value={val || ''} options={groupOptions} onChange={(v: string) => {
            updateNodeData((d) => ({ ...d, serverGroup: v }));
            onChange(v);
          }} locked={locked} required placeholder="选择服务器组" />
        ),
      });
    }

    // HOTFIX_TYPES (multiselect checkbox)
    if (visibleParams.includes('HOTFIX_TYPES')) {
      fields.push({
        key: 'HOTFIX_TYPES',
        label: '热更类型',
        required: true,
        renderCustomField: (val, onChange, locked) => (
          <div className="nodrag nopan nowheel" onWheel={(e) => e.stopPropagation()}>
            <Checkbox.Group
              disabled={locked}
              value={Array.isArray(val) ? val : (val ? [val] : [])}
              onChange={(v) => onChange(v as string[])}
              options={HOTFIX_TYPE_OPTIONS}
              style={{ fontSize: 11 }}
            />
          </div>
        ),
      });
    }

    // Checkbox params
    if (visibleParams.includes('trigger_seal')) {
      fields.push({
        key: 'trigger_seal',
        label: '触发海豹流程',
        renderCustomField: (val, onChange, locked) => (
          <Checkbox disabled={locked} checked={!!val} onChange={(e) => onChange(e.target.checked)} style={{ fontSize: 11 }}>
            trigger_seal
          </Checkbox>
        ),
      });
    }
    if (visibleParams.includes('with_server_appendix')) {
      fields.push({
        key: 'with_server_appendix',
        label: '包含额外覆盖文件',
        renderCustomField: (val, onChange, locked) => (
          <Checkbox disabled={locked} checked={!!val} onChange={(e) => onChange(e.target.checked)} style={{ fontSize: 11 }}>
            with_server_appendix
          </Checkbox>
        ),
      });
    }
    if (visibleParams.includes('CLEAN_ALL_DB_DATA')) {
      fields.push({
        key: 'CLEAN_ALL_DB_DATA',
        label: '清DB数据',
        renderCustomField: (val, onChange, locked) => (
          <Checkbox disabled={locked} checked={!!val} onChange={(e) => onChange(e.target.checked)} style={{ fontSize: 11 }}>
            CLEAN_ALL_DB_DATA
          </Checkbox>
        ),
      });
    }

    // SERVER_BUILD_TYPE (select)
    if (visibleParams.includes('SERVER_BUILD_TYPE')) {
      fields.push({
        key: 'SERVER_BUILD_TYPE',
        label: '更新模式',
        required: true,
        renderCustomField: (val, onChange, locked) => (
          <StyledSelect value={val || 'full'} options={BUILD_TYPE_OPTIONS} onChange={onChange} locked={locked} required placeholder="full / script / lua" />
        ),
      });
    }

    return fields;
  }, [branch, op, env, cross, visibleParams, showCross, showDeployMode, showServerGroup, filteredServerOptions, groupOptions, updateNodeData]);

  // Job URL preview as extraContentAfterFields
  const extraContentAfterFields = jobConfig ? (
    <div style={{ marginTop: 4, padding: '4px 6px', background: '#e6f7ff', border: '1px solid #91d5ff', borderRadius: 3, fontSize: 10 }}>
      <div style={{ fontWeight: 600, color: '#096dd9', marginBottom: 2 }}>📌 目标任务</div>
      <a href={jobConfig.url} target="_blank" rel="noopener noreferrer" style={{ color: '#1890ff', wordBreak: 'break-all' }}>
        {jobConfig.job_name}
      </a>
    </div>
  ) : (
    <div style={{ marginTop: 4, padding: '4px 6px', background: '#f5f5f5', border: '1px solid #e8e8e8', borderRadius: 3, fontSize: 10, color: '#999' }}>
      请选择分支、操作、环境来确定目标任务
    </div>
  );

  // Dynamic ports based on job type
  const dynamicPorts = useMemo<PortDefinition[]>(() => {
    const ports: PortDefinition[] = [
      { key: 'changelistID', label: '版本号', type: 'string', direction: 'input', maxConnections: 1 },
      { key: 'serverName', label: '服务器名', type: 'string', direction: 'input', maxConnections: 1 },
    ];
    ports.push(
      { key: 'success', label: '执行结果', type: 'boolean', direction: 'output' },
      { key: 'jobUrl', label: '任务链接', type: 'string', direction: 'output' },
      { key: 'buildNumber', label: '构建号', type: 'string', direction: 'output' },
    );
    return ports;
  }, []);

  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="🚀"
      label="Jenkins 部署"
      nodeType="jenkinsdeploy"
      fields={JENKINS_FIELDS}
      overridePorts={dynamicPorts}
      extraContentAfterFields={extraContentAfterFields}
    />
  );
}

export default memo(JenkinsDeployNode);
