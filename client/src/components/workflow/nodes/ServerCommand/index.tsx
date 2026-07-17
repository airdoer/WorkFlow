import React, { memo, useCallback, useMemo } from 'react';
import { NodeProps, useReactFlow } from 'reactflow';
import BaseNode, { NodeField } from '../BaseNode';
import { StyledSelect } from '../SharedStyledSelect';

/* ─── Example commands ─────────────────────────────────────────── */
const EXAMPLES: Record<string, { label: string; code: string; broadcast: boolean }> = {
  '': { label: '空白（广播）', code: '', broadcast: true },
  payNotifyUrl: {
    label: '修改configure配置',
    code: "Game.LogicConfig.gameConf['common']['payNotifyUrl']='http://10.73.1.206:7800/c7_partner/pay/gm_pay_order_received'",
    broadcast: true,
  },
  crossIp: {
    label: '修改跨服ip',
    code: 'cross_config = kg_require("Engine.Config.CrossConfig")\ncross_config.CROSS_SERVER_CONFIG[1800].host = "47.95.56.1"\ncross_config.CROSS_SERVER_CONFIG[1800].port = 30002',
    broadcast: true,
  },
  quest: {
    label: '修改Quest任务数据',
    code: 'quest_600005= require_raw_data("Data.Quest.Ring.600005")\nmake_data_table_mutable(quest_600005)\nquest_600005.QuestData[60000524].QuestTargets[1].Params.CutSceneID = 1000578\nmake_data_table_immutable(quest_600005)',
    broadcast: true,
  },
  sharedConst: {
    label: '修改SharedConst',
    code: 'shared_const = kg_require("Shared.Const")\nshared_const.AI_UPLOAD_VIDEO_CD = 3',
    broadcast: true,
  },
  const: {
    label: '修改Const',
    code: 'const = kg_require("Common.Const")\nconst.PLAYER_BAN_TYPE.ROLE_BAN_FORCE = 99',
    broadcast: true,
  },
  scriptOptions: {
    label: '修改_script.options引擎开关',
    code: '_script.options.default_client_rpc_burst_tokens = 3',
    broadcast: true,
  },
  serviceVar: {
    label: '修改Service变量',
    code: 'for _, s in ipairs(getservice("WorldService")) do s.registerLogicNum = 66 end',
    broadcast: true,
  },
  simpleFunc: {
    label: '修改简单函数',
    code: 'Game.GlobalCallback.testServerMsg = function(self, a, b, c)\n    LOG_INFO_FMT("ServerCommand testServerMsg hotfix %s %s %s %s", self.serverHotfixManager, a, b, c)\nend',
    broadcast: true,
  },
  switch: {
    label: '修改开关',
    code: 'serverID = 0\nmodifySwitches = {EnableAIVideoQueueSize = "3", EnableAIVideoQueue = "true"}\nGame.Process:CallService("GlobalDataService", "SSReqModifySwitches", nil):Args(serverID, modifySwitches)',
    broadcast: false,
  },
  serverHotfix: {
    label: '服务器手动热更',
    code: 'debugUtils = kg_require("Logic.Utils.DebugUtils")\ndebugUtils.doHotfixTest("hotfix_Const")',
    broadcast: true,
  },
};

const EXAMPLE_OPTIONS = Object.entries(EXAMPLES).map(([key, val]) => ({
  label: val.label,
  value: key,
  type: '' as const,
}));

/* ─── ServerCommandNode ─────────────────────────────────────────── */
function ServerCommandNode({ data, id, selected }: NodeProps) {
  const { setNodes } = useReactFlow();
  const nodeData = data as Record<string, any>;

  const updateNodeData = useCallback(
    (updater: (d: Record<string, any>) => Record<string, any>) => {
      setNodes((nds) =>
        nds.map((n) => (n.id === id ? { ...n, data: updater(n.data as Record<string, any>) } : n)),
      );
    },
    [id, setNodes],
  );

  // Load an example into the command field
  const loadExample = useCallback(
    (key: string) => {
      const ex = EXAMPLES[key];
      if (!ex) return;
      // Single setNodes call: update exampleKey + command + broadcast + stale hint
      updateNodeData((d) => {
        const prevStatus = (d._runStatusHint as string) || (d._runStatus as string) || 'idle';
        const newHint = (prevStatus === 'success' || prevStatus === 'error') ? 'stale' : prevStatus;
        return {
          ...d,
          command: ex.code,
          broadcast: ex.broadcast,
          exampleKey: key,
          _runStatusHint: newHint,
        };
      });
    },
    [updateNodeData],
  );

  const SC_FIELDS: NodeField[] = useMemo(() => [
    {
      key: 'exampleKey',
      label: '加载示例',
      required: false,
      renderCustomField: (val, onChange, locked) => (
        <StyledSelect
          value={val || ''}
          options={EXAMPLE_OPTIONS}
          onChange={(v: string) => {
            // loadExample handles all field updates (exampleKey + command + broadcast + stale)
            // Do NOT call onChange(v) here — it would trigger a second setNodes
            // that overwrites command/broadcast with stale data
            loadExample(v);
          }}
          locked={locked}
          placeholder="选择示例模板..."
        />
      ),
    },
    {
      key: 'broadcast',
      label: '广播',
      type: 'select',
      required: false,
      options: [
        { label: '是（broadcastCommand）', value: 'true' },
        { label: '否（直接执行）', value: 'false' },
      ],
    },
    {
      key: 'command',
      label: 'Lua 指令',
      type: 'textarea',
      rows: 4,
      placeholder: '输入 Lua 代码或选择示例...',
      required: true,
    },
  ], [loadExample]);

  return (
    <BaseNode
      data={data as Record<string, unknown>}
      id={id}
      selected={!!selected}
      icon="⌨️"
      label="ServerCommand 指令"
      nodeType="servercommand"
      fields={SC_FIELDS}
    />
  );
}

export default memo(ServerCommandNode);
