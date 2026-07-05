# WorkFlow Spec 设计文档

## 一、项目概述

基于字节跳动开源的 **FlowGram.AI** 前端流程搭建引擎，构建一个可视化工作流平台。支持 Excel、Lua、JSON、Prompt 四类节点，实现文件获取、解析、AI 处理等操作的流程化编排。

### 技术选型

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端画布 | `@flowgram.ai/free-layout-editor` | 自由连线布局，节点可任意放置 |
| 前端表单 | `@flowgram.ai/form-core` + `@flowgram.ai/form-antd-materials` | 节点属性面板，配合项目已有 antd |
| 变量引擎 | `@flowgram.ai/variable-core` + `@flowgram.ai/variable-plugin` | 节点间数据流类型推导（由 free-layout-editor 内含） |
| 前端运行时 | `@flowgram.ai/runtime-js` | 前端 DAG 调度（预览/调试） |
| 后端框架 | Flask (Python) + flask_socketio | 项目已有服务端，socketio 补充 WebSocket 能力 |
| 通信协议 | HTTP REST + WebSocket (Socket.IO) | REST 负责 CRUD，Socket.IO 推送运行状态和流式输出 |

---

## 二、目录结构

### 2.1 前端

```
client/
└── src/
    ├── pages/
    │   └── Workflow/
    │       └── index.tsx                    // 页面入口，挂载 FlowEditor
    │
    └── components/
        └── workflow/
            ├── FlowEditor.tsx               // FreeLayoutEditor 初始化 + 保存/加载 JSON
            ├── Toolbar.tsx                  // 保存 / 运行 / 停止 / 导入 / 导出 / Undo / Redo
            ├── PropertyPanel.tsx             // 右侧属性面板，根据 schema 自动生成表单
            ├── Toolbox.tsx                  // 左侧节点工具箱（拖拽创建节点）
            ├── NodeRegistry.ts              // 注册所有节点类型 → Executor / Schema / Icon
            ├── types.ts                     // 全局类型定义
            │
            ├── services/
            │   └── FlowApi.ts               // 封装所有后端 API 调用
            │
            ├── runtime/
            │   ├── Runtime.ts               // 整体运行调度器
            │   ├── GraphParser.ts           // DAG 解析 + 拓扑排序
            │   ├── ExecutorManager.ts        // 根据 node.type 获取对应执行器
            │   └── Context.ts               // 节点运行上下文（变量、输出缓存）
            │
            ├── models/
            │   ├── Node.ts                  // 节点数据模型
            │   ├── Edge.ts                  // 连边数据模型
            │   ├── Workflow.ts              // 工作流整体模型
            │   └── ExecutionResult.ts       // 执行结果模型
            │
            └── nodes/
                ├── Excel/
                │   ├── index.tsx             // 节点 UI 渲染（FlowGram 注册用）
                │   ├── schema.ts             // 节点配置 Schema（PropertyPanel 自动读取）
                │   ├── executor.ts           // 节点执行器（前端预览 + 后端调用）
                │   └── icon.tsx              // Toolbox 图标
                │
                ├── Lua/
                │   ├── index.tsx
                │   ├── schema.ts
                │   ├── executor.ts
                │   └── icon.tsx
                │
                ├── Json/
                │   ├── index.tsx
                │   ├── schema.ts
                │   ├── executor.ts
                │   └── icon.tsx
                │
                └── Prompt/
                    ├── index.tsx
                    ├── schema.ts
                    ├── executor.ts
                    └── icon.tsx
```

### 2.2 后端

```
server/
├── routers/
│   └── WorkFlow.py                         // HTTP REST + Socket.IO 事件路由
│
├── Implement/
│   └── workflowImpl/
│       ├── __init__.py
│       ├── workflowImp.py                   // 工作流 CRUD 实现
│       ├── nodeExecutor.py                  // 节点执行器基类 + 分发
│       ├── excelExecutor.py                 // Excel 节点执行（P4 拉取 + openpyxl 解析）
│       ├── luaExecutor.py                   // Lua 节点执行（P4 拉取 + 内容读取）
│       ├── jsonExecutor.py                  // JSON 节点执行（P4 拉取 + 内容读取）
│       └── promptExecutor.py                // Prompt 节点执行（调用 LLM API）
│
└── requirements.txt                         // 新增 flask-socketio
```

---

## 三、节点设计

### 3.1 统一节点接口

```typescript
// 前端统一执行器接口
interface WorkflowNodeExecutor {
  run(input: any, config: any): Promise<any>;
}
```

```python
# 后端统一执行器接口
class BaseNodeExecutor(ABC):
    @property
    @abstractmethod
    def type(self) -> str:
        pass

    @abstractmethod
    async def execute(self, config: dict, input_data: dict) -> dict:
        pass
```

### 3.2 Excel 节点

**Schema:**

```typescript
interface ExcelConfig {
  p4Path: string;       // P4 文件路径，如 //C7/Development/Mainline/Server/Data/Excel/角色表.xlsx
  sheet?: string;        // 工作表名（可选，默认第一个）
}
```

**执行流程:**

```
1. 接收 p4Path 配置
2. 调用后端 API /api/workflow/node/run
3. 后端: p4 sync 拉取文件 → openpyxl 解析指定 sheet → 输出 JSON
4. 返回解析后的结构化数据
```

**输出:** `{ columns: string[], rows: Record<string, any>[] }`

### 3.3 Lua 节点

**Schema:**

```typescript
interface LuaConfig {
  p4Path: string;          // P4 文件路径
  entryFunction?: string;  // 入口函数名（可选）
}
```

**执行流程:**

```
1. 接收 p4Path 配置
2. 调用后端 API
3. 后端: p4 sync 拉取文件 → 读取内容 → 返回源码文本
4. 如指定 entryFunction，提取该函数内容
```

**输出:** `{ content: string, functionName?: string, functionContent?: string }`

### 3.4 JSON 节点

**Schema:**

```typescript
interface JsonConfig {
  p4Path: string;      // P4 文件路径
  jsonPath?: string;   // JSON Path 过滤（可选，如 $.data.items）
}
```

**执行流程:**

```
1. 接收 p4Path 配置
2. 调用后端 API
3. 后端: p4 sync 拉取文件 → json.loads 解析 → 按 jsonPath 过滤 → 返回
```

**输出:** `{ data: any, path?: string }`

### 3.5 Prompt 节点

**Schema:**

```typescript
interface PromptConfig {
  prompt: string;           // 提示词内容，支持 {{nodeId.outputKey}} 变量插值
  temperature?: number;     // 温度，默认 0.7
  model?: string;           // 模型名称，默认由后端配置
  maxTokens?: number;       // 最大 token 数
}
```

**执行流程:**

```
1. 接收上游节点输出作为变量
2. 替换 prompt 中的 {{}} 变量占位符
3. 调用后端 API（LLM 接口 / DashScope）
4. 后端: 组装 prompt → 调用 LLM → 返回结果
5. 流式输出通过 Socket.IO 推送
```

**输出:** `{ content: string, model: string, usage: { promptTokens: number, completionTokens: number } }`

---

## 四、FlowGram 集成方案

### 4.1 已安装的 npm 包

> **注意:** 项目 npm 全局 registry 指向内部 `npm.corp.kuaishou.com`，需在 `client/.npmrc` 中配置 `@flowgram.ai:registry=https://registry.npmmirror.com` 使 FlowGram 包走公网镜像源。

```json
{
  "dependencies": {
    "@flowgram.ai/free-layout-editor": "^1.0.12",
    "@flowgram.ai/free-layout-core": "^1.0.12",
    "@flowgram.ai/form-core": "^1.0.12",
    "@flowgram.ai/node": "^1.0.12",
    "@flowgram.ai/form-antd-materials": "^1.0.12",
    "@flowgram.ai/background-plugin": "^1.0.12",
    "@flowgram.ai/minimap-plugin": "^1.0.12",
    "@flowgram.ai/free-snap-plugin": "^1.0.12",
    "@flowgram.ai/free-auto-layout-plugin": "^1.0.12",
    "@flowgram.ai/free-history-plugin": "^1.0.12",
    "@flowgram.ai/shortcuts-plugin": "^1.0.12",
    "@flowgram.ai/export-plugin": "^1.0.12",
    "@flowgram.ai/runtime-js": "^1.0.12"
  }
}
```

**自动拉取的间接依赖（无需手动安装）:**

| 包名 | 说明 |
|------|------|
| `@flowgram.ai/variable-core` | 变量引擎核心 |
| `@flowgram.ai/variable-layout` | 变量布局 |
| `@flowgram.ai/variable-plugin` | 变量引擎插件 |
| `@flowgram.ai/node-core-plugin` | 节点核心插件 |
| `@flowgram.ai/node-variable-plugin` | 节点-变量关联插件 |
| `@flowgram.ai/materials-plugin` | 物料插件 |
| `@flowgram.ai/form` | 表单引擎 |
| `@flowgram.ai/core` | 画布核心 |
| `@flowgram.ai/document` | 文档模型 |
| `@flowgram.ai/renderer` | 渲染引擎 |
| `@flowgram.ai/command` | 命令模式 |
| `@flowgram.ai/history` | 撤销/重做 |
| `@flowgram.ai/reactive` | 响应式工具 |
| `@flowgram.ai/utils` | 通用工具 |

### 4.2 Editor 初始化

```tsx
// FlowEditor.tsx
import { FreeLayoutEditorProvider, EditorRenderer } from '@flowgram.ai/free-layout-editor';
import { createBackgroundPlugin } from '@flowgram.ai/background-plugin';
import { createMinimapPlugin } from '@flowgram.ai/minimap-plugin';
import { createFreeSnapPlugin } from '@flowgram.ai/free-snap-plugin';
import { createFreeHistoryPlugin } from '@flowgram.ai/free-history-plugin';
import { createShortcutsPlugin } from '@flowgram.ai/shortcuts-plugin';
import { createExportPlugin } from '@flowgram.ai/export-plugin';

function FlowEditor({ initialData }) {
  const editorRef = useRef<FreeLayoutPluginContext>();

  return (
    <FreeLayoutEditorProvider
      ref={editorRef}
      initialData={initialData}
      nodeRegistries={[ExcelNodeRegistry, LuaNodeRegistry, JsonNodeRegistry, PromptNodeRegistry]}
      nodeEngine={{ enable: true }}
      variableEngine={{ enable: true }}
      plugins={() => [
        createBackgroundPlugin(),
        createMinimapPlugin(),
        createFreeSnapPlugin(),
        createFreeHistoryPlugin(),
        createShortcutsPlugin(),
        createExportPlugin(),
      ]}
    >
      <EditorRenderer className="workflow-canvas" />
      <Toolbox />
      <PropertyPanel />
      <Toolbar editorRef={editorRef} />
    </FreeLayoutEditorProvider>
  );
}
```

### 4.3 节点注册（以 Excel 为例）

```tsx
// nodes/Excel/index.tsx
import { WorkflowNodeRegistry, ValidateTrigger } from '@flowgram.ai/free-layout-editor';

export const ExcelNodeRegistry: WorkflowNodeRegistry = {
  type: 'excel',
  meta: {
    defaultPorts: [{ type: 'output' }, { type: 'input' }],
  },
  formMeta: {
    validateTrigger: ValidateTrigger.onChange,
    validate: {
      p4Path: ({ value }) => (value ? undefined : 'P4 路径必填'),
    },
    render: ({ form }) => (
      <div>
        <Field name="p4Path"><Input placeholder="P4 文件路径" /></Field>
        <Field name="sheet"><Input placeholder="工作表名（可选）" /></Field>
      </div>
    ),
  },
};
```

### 4.4 数据流序列化

```typescript
// WorkflowJSON 结构（FlowGram 原生）
interface WorkflowJSON {
  nodes: Array<{
    id: string;
    type: string;       // 'excel' | 'lua' | 'json' | 'prompt'
    meta: { position: { x: number; y: number } };
    data: object;        // 节点配置数据（schema 中定义的字段）
    blocks: Array<...>;
    edges: Array<...>;
  }>;
  edges: Array<{
    sourceNodeID: string;
    targetNodeID: string;
    sourcePortID?: string;
    targetPortID?: string;
  }>;
}
```

---

## 五、运行时设计（Runtime）

### 5.1 整体流程

```
用户点击"运行"
    │
    ▼
Toolbar → Runtime.run(workflowJSON)
    │
    ▼
GraphParser.parse(nodes, edges)
    │
    ▼
拓扑排序 → 得到执行顺序 [nodeA, nodeB, nodeC, ...]
    │
    ▼
ExecutorManager.getExecutor(node.type)
    │
    ▼
按顺序执行每个节点:
  - Excel → 调用 POST /api/workflow/node/run { type: "excel", config, input }
  - Lua   → 调用 POST /api/workflow/node/run { type: "lua", config, input }
  - Json  → 调用 POST /api/workflow/node/run { type: "json", config, input }
  - Prompt→ 调用 POST /api/workflow/node/run { type: "prompt", config, input }
    │
    ▼
Context 缓存每个节点输出
    │
    ▼
下游节点从 Context 获取输入
    │
    ▼
全部完成 → 返回最终结果
```

### 5.2 GraphParser（DAG 解析）

```typescript
class GraphParser {
  // 解析 WorkflowJSON，返回拓扑排序后的节点列表
  static parse(json: WorkflowJSON): string[] {
    // 1. 构建 DAG（邻接表）
    // 2. 检测环路（有环则报错）
    // 3. 拓扑排序（Kahn 算法）
    // 4. 返回有序节点 ID 列表
  }
}
```

### 5.3 Runtime

```typescript
class Runtime {
  private socket = io('/workflow');

  async run(json: WorkflowJSON): Promise<ExecutionResult> {
    const order = GraphParser.parse(json);
    const context = new Context();

    for (const nodeId of order) {
      const node = json.nodes.find(n => n.id === nodeId);
      const inputEdges = json.edges.filter(e => e.targetNodeID === nodeId);

      // 收集上游输出作为本节点输入
      const input = {};
      for (const edge of inputEdges) {
        const upstreamOutput = context.getOutput(edge.sourceNodeID);
        Object.assign(input, upstreamOutput);
      }

      // 通过后端 API 执行节点
      const output = await FlowApi.runNode(node.type, node.data, input);
      context.setOutput(nodeId, output);

      // 通过 Socket.IO 推送节点完成状态
      this.socket.emit('node:completed', { nodeId, output });
    }

    return context.getAllOutputs();
  }
}
```

### 5.4 Context（节点上下文）

```typescript
class Context {
  private outputs: Map<string, any> = new Map();

  getOutput(nodeId: string): any {
    return this.outputs.get(nodeId);
  }

  setOutput(nodeId: string, output: any): void {
    this.outputs.set(nodeId, output);
  }

  getAllOutputs(): Record<string, any> {
    return Object.fromEntries(this.outputs);
  }
}
```

---

## 六、后端 API 设计

### 6.1 REST API

| Method | Path | 说明 | 请求体 | 响应 |
|--------|------|------|--------|------|
| POST | `/api/workflow/save` | 保存工作流 | `{ name, json: WorkflowJSON }` | `{ id, name }` |
| GET | `/api/workflow/<id>` | 获取工作流 | - | `{ id, name, json }` |
| GET | `/api/workflow/list` | 工作流列表 | - | `{ list: [{ id, name, updatedAt }] }` |
| DELETE | `/api/workflow/<id>` | 删除工作流 | - | `{ success }` |
| POST | `/api/workflow/node/run` | 运行单个节点 | `{ type, config, input }` | `{ output }` |
| POST | `/api/workflow/run` | 运行整个工作流 | `{ workflowId }` | `{ taskId }` |
| GET | `/api/workflow/run/<taskId>/status` | 查询运行状态 | - | `{ status, nodes: { [nodeId]: status } }` |
| POST | `/api/workflow/run/<taskId>/cancel` | 取消运行 | - | `{ success }` |

### 6.2 Socket.IO 事件

> Flask 原生不支持 WebSocket，通过 `flask-socketio` 提供 Socket.IO 协议支持。前端对应使用 `socket.io-client` 连接。

**后端初始化:**

```python
# app.py
from flask_socketio import SocketIO

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="gevent")
```

**事件定义:**

| 事件名 | 方向 | 数据 | 说明 |
|--------|------|------|------|
| `workflow:started` | Server → Client | `{ taskId }` | 工作流开始运行 |
| `node:started` | Server → Client | `{ taskId, nodeId }` | 节点开始执行 |
| `node:completed` | Server → Client | `{ taskId, nodeId, output }` | 节点执行完成 |
| `node:failed` | Server → Client | `{ taskId, nodeId, error }` | 节点执行失败 |
| `node:stream` | Server → Client | `{ taskId, nodeId, chunk }` | LLM 流式输出（逐 chunk 推送） |
| `workflow:completed` | Server → Client | `{ taskId, result }` | 工作流运行完成 |
| `workflow:failed` | Server → Client | `{ taskId, error }` | 工作流运行失败 |

**后端推送示例:**

```python
from flask_socketio import emit

# 节点开始
emit('node:started', {'taskId': task_id, 'nodeId': node_id}, room=sid)

# LLM 流式输出
for chunk in llm_stream:
    emit('node:stream', {'taskId': task_id, 'nodeId': node_id, 'chunk': chunk}, room=sid)

# 节点完成
emit('node:completed', {'taskId': task_id, 'nodeId': node_id, 'output': output}, room=sid)

# 工作流完成
emit('workflow:completed', {'taskId': task_id, 'result': result}, room=sid)
```

**前端监听示例:**

```typescript
import { io } from 'socket.io-client';

const socket = io('/workflow');

socket.on('node:started', (data) => {
  // 更新节点状态为 running
});

socket.on('node:stream', (data) => {
  // 追加 LLM 流式输出到 Prompt 节点输出面板
});

socket.on('node:completed', (data) => {
  // 更新节点状态为 success，缓存输出
});

socket.on('workflow:completed', (data) => {
  // 整体运行完成
});
```

---

## 七、后端执行器设计

### 7.1 执行器基类

```python
# Implement/workflowImpl/nodeExecutor.py
from abc import ABC, abstractmethod

class BaseNodeExecutor(ABC):
    @property
    @abstractmethod
    def type(self) -> str:
        pass

    @abstractmethod
    async def execute(self, config: dict, input_data: dict) -> dict:
        pass

class ExecutorManager:
    _executors: dict[str, BaseNodeExecutor] = {}

    @classmethod
    def register(cls, executor: BaseNodeExecutor):
        cls._executors[executor.type] = executor

    @classmethod
    def get(cls, node_type: str) -> BaseNodeExecutor:
        return cls._executors.get(node_type)

    @classmethod
    async def run_node(cls, node_type: str, config: dict, input_data: dict) -> dict:
        executor = cls.get(node_type)
        if not executor:
            raise ValueError(f"Unknown node type: {node_type}")
        return await executor.execute(config, input_data)
```

### 7.2 Excel 执行器

```python
# Implement/workflowImpl/excelExecutor.py
import openpyxl
import json
import subprocess

class ExcelExecutor(BaseNodeExecutor):
    type = "excel"

    async def execute(self, config: dict, input_data: dict) -> dict:
        p4_path = config.get("p4Path")
        sheet_name = config.get("sheet")

        # 1. p4 sync 拉取文件
        local_path = self._p4_sync(p4_path)

        # 2. openpyxl 解析
        wb = openpyxl.load_workbook(local_path, data_only=True)
        ws = wb[sheet_name] if sheet_name else wb.active

        # 3. 提取列名和数据行
        columns = [cell.value for cell in ws[1]]
        rows = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            rows.append(dict(zip(columns, row)))

        return {"columns": columns, "rows": rows}

    def _p4_sync(self, p4_path: str) -> str:
        # 调用 p4 sync 同步文件到本地
        result = subprocess.run(["p4", "sync", p4_path], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"P4 sync failed: {result.stderr}")
        # 推导本地路径
        return p4_path.replace("//", "/").split("...")[0]
```

### 7.3 Prompt 执行器

```python
# Implement/workflowImpl/promptExecutor.py
import openai

class PromptExecutor(BaseNodeExecutor):
    type = "prompt"

    async def execute(self, config: dict, input_data: dict, socketio=None, sid=None, task_id=None) -> dict:
        prompt = config.get("prompt", "")
        temperature = config.get("temperature", 0.7)
        model = config.get("model", "qwen-plus")
        max_tokens = config.get("maxTokens", 4096)

        # 变量插值：替换 {{nodeId.outputKey}} 为上游输出值
        for key, value in self._flatten(input_data).items():
            prompt = prompt.replace(f"{{{{{key}}}}}", str(value))

        # 调用 DashScope / OpenAI 兼容接口
        client = openai.AsyncOpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

        # 流式调用，通过 Socket.IO 逐 chunk 推送
        if socketio and sid:
            full_content = ""
            stream = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                full_content += delta
                socketio.emit('node:stream', {
                    'taskId': task_id,
                    'nodeId': config.get('_nodeId'),
                    'chunk': delta,
                }, room=sid)
            return {
                "content": full_content,
                "model": model,
                "usage": {"promptTokens": 0, "completionTokens": 0},
            }

        # 非流式调用
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return {
            "content": response.choices[0].message.content,
            "model": model,
            "usage": {
                "promptTokens": response.usage.prompt_tokens,
                "completionTokens": response.usage.completion_tokens,
            }
        }

    def _flatten(self, data: dict, prefix: str = "") -> dict:
        result = {}
        for k, v in data.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                result.update(self._flatten(v, key))
            else:
                result[key] = v
        return result
```

---

## 八、PropertyPanel 自动生成方案

PropertyPanel 不使用 if-else 硬编码，而是根据各节点的 `schema.ts` 自动生成表单：

```tsx
// PropertyPanel.tsx
function PropertyPanel() {
  const { formData, nodeType } = useNodeRender();
  const registry = NodeRegistry.get(nodeType);
  const schema = registry.schema;

  return (
    <div className="property-panel">
      <h3>{registry.meta.title}</h3>
      {schema.fields.map(field => (
        <FormField key={field.name} field={field} form={formData} />
      ))}
      <Button onClick={() => handleRunNode()}>运行</Button>
      <Button onClick={() => handleSaveNode()}>保存</Button>
    </div>
  );
}
```

FlowGram 原生支持通过 `formMeta.render` 在节点内部渲染表单，也支持通过 `useForm()` 在外部 PropertyPanel 中渲染。推荐使用 **外部 PropertyPanel** 方案，与 FlowGram 解耦。

---

## 九、整体数据流架构

```
┌──────────────────────────────────────────────────┐
│              React + FlowGram.AI                  │
│                                                  │
│  FreeLayoutEditorProvider                        │
│       ├── EditorRenderer (Canvas)                │
│       ├── Toolbox (拖拽创建节点)                  │
│       ├── PropertyPanel (节点配置)                │
│       ├── Toolbar (保存/运行/停止)                 │
│       └── Runtime (前端调度)                      │
│            │                                     │
│            ├── GraphParser (DAG + 拓扑排序)       │
│            ├── ExecutorManager (分发)             │
│            └── Context (缓存输出)                 │
│                                                  │
└──────────┬───────────────────────┬───────────────┘
           │                       │
     HTTP REST                 Socket.IO
           │                       │
           │                推送运行状态
           │                推送节点输出
           │                推送 LLM 流式输出
           │                       │
           ▼                       ▼
┌──────────────────────────────────────────────────┐
│         Flask + flask_socketio (Python)           │
│                                                  │
│  routers/WorkFlow.py                            │
│       ├── POST /api/workflow/save                │
│       ├── GET  /api/workflow/<id>                 │
│       ├── POST /api/workflow/node/run             │
│       └── POST /api/workflow/run                  │
│                                                  │
│  Socket.IO Events                               │
│       ├── workflow:started / completed / failed   │
│       ├── node:started / completed / failed       │
│       └── node:stream (LLM 流式)                  │
│                                                  │
│  Implement/workflowImpl/                         │
│       ├── ExecutorManager                        │
│       ├── ExcelExecutor (p4 + openpyxl)          │
│       ├── LuaExecutor   (p4 + 读取)              │
│       ├── JsonExecutor  (p4 + json)              │
│       └── PromptExecutor (变量插值 + LLM)         │
│                                                  │
└──────────────────────────────────────────────────┘
```

---

## 十、依赖清单

### 10.1 前端 npm 依赖（已安装）

**直接依赖（package.json）:**

| 包名 | 版本 | 说明 |
|------|------|------|
| `@flowgram.ai/free-layout-editor` | ^1.0.12 | 自由布局编辑器 |
| `@flowgram.ai/free-layout-core` | ^1.0.12 | 自由布局核心 |
| `@flowgram.ai/form-core` | ^1.0.12 | 表单引擎核心 |
| `@flowgram.ai/node` | ^1.0.12 | 节点引擎 |
| `@flowgram.ai/form-antd-materials` | ^1.0.12 | Ant Design 物料 |
| `@flowgram.ai/background-plugin` | ^1.0.12 | 画布背景 |
| `@flowgram.ai/minimap-plugin` | ^1.0.12 | 小地图 |
| `@flowgram.ai/free-snap-plugin` | ^1.0.12 | 对齐/吸附 |
| `@flowgram.ai/free-auto-layout-plugin` | ^1.0.12 | 自动布局 |
| `@flowgram.ai/free-history-plugin` | ^1.0.12 | 撤销/重做 |
| `@flowgram.ai/shortcuts-plugin` | ^1.0.12 | 快捷键 |
| `@flowgram.ai/export-plugin` | ^1.0.12 | 导出 |
| `@flowgram.ai/runtime-js` | ^1.0.12 | 运行时 |
| `socket.io-client` | ^4.x | Socket.IO 客户端 ✅ |

**.npmrc 配置:**

```
legacy-peer-deps=true
@flowgram.ai:registry=https://registry.npmmirror.com
```

### 10.2 后端 Python 依赖（需更新 requirements.txt）

| 包名 | 版本 | 说明 |
|------|------|------|
| `flask-socketio` | >=5.3.0 | Flask WebSocket 支持（新增） |
| `gevent` | 已有 | flask-socketio 的 async_mode |

---

## 十一、实施阶段规划

### Phase 1: 基础框架搭建 ✅（已完成）
1. ~~安装 FlowGram 依赖包~~ ✅
2. ~~安装 socket.io-client 前端依赖~~ ✅
3. ~~更新 requirements.txt 添加 flask-socketio~~ ✅
4. ~~创建 Workflow 页面入口~~ ✅（FlowDemo.tsx + FlowEditor）
5. ~~初始化 FreeLayoutEditorProvider~~ ✅（FlowEditor.tsx）
6. ~~实现 Toolbox（4 种节点拖拽创建）~~ ✅
7. ~~实现 PropertyPanel（根据 schema 自动生成）~~ ✅
8. ~~实现 Toolbar（保存/加载 JSON）~~ ✅
9. ~~实现 WorkflowJSON 的保存/加载 API~~ ✅（FlowApi.ts）

**已实现的前端文件:**
- `components/workflow/FlowEditor.tsx` — FreeLayoutEditor + 插件 + 拖拽创建节点
- `components/workflow/Toolbox.tsx` — 4 种节点拖拽工具箱
- `components/workflow/PropertyPanel.tsx` — 右侧属性面板 + 运行按钮
- `components/workflow/Toolbar.tsx` — 保存/运行/停止/撤销/重做/导入/导出
- `components/workflow/NodeRegistry.tsx` — 注册 4 种节点类型
- `components/workflow/types.ts` — WorkflowJSON + WorkflowNodeExecutor 接口
- `components/workflow/nodes/Excel/` — index.tsx + schema.ts + executor.ts + icon.tsx
- `components/workflow/nodes/Lua/` — index.tsx + schema.ts + executor.ts + icon.tsx
- `components/workflow/nodes/Json/` — index.tsx + schema.ts + executor.ts + icon.tsx
- `components/workflow/nodes/Prompt/` — index.tsx + schema.ts + executor.ts + icon.tsx
- `components/workflow/services/FlowApi.ts` — 所有后端 API 封装
- `components/workflow/runtime/Runtime.ts` — 整体运行调度器
- `components/workflow/runtime/GraphParser.ts` — DAG 解析 + 拓扑排序
- `components/workflow/runtime/ExecutorManager.ts` — 节点执行器分发
- `components/workflow/runtime/Context.ts` — 节点输出缓存
- `components/workflow/models/` — Node.ts + Edge.ts + Workflow.ts + ExecutionResult.ts

### Phase 2: 节点执行 ✅（已完成）
1. ~~实现后端 BaseNodeExecutor + ExecutorManager~~ ✅
2. ~~实现 ExcelExecutor（p4 sync + openpyxl）~~ ✅
3. ~~实现 LuaExecutor（p4 sync + 读取）~~ ✅
4. ~~实现 JsonExecutor（p4 sync + json 解析）~~ ✅
5. ~~实现 PromptExecutor（变量插值 + DashScope LLM）~~ ✅
6. ~~实现 `/api/workflow/node/run` 路由~~ ✅

**已实现的后端文件:**
- `routers/WorkFlow.py` — 全部 REST API 路由
- `Implement/workflowImpl/workflowImp.py` — WorkflowManager + WorkflowRuntime
- `Implement/workflowImpl/nodeExecutor.py` — BaseNodeExecutor + ExecutorManager
- `Implement/workflowImpl/excelExecutor.py` — Excel 执行器
- `Implement/workflowImpl/luaExecutor.py` — Lua 执行器
- `Implement/workflowImpl/jsonExecutor.py` — JSON 执行器
- `Implement/workflowImpl/promptExecutor.py` — Prompt 执行器

### Phase 3: 整体运行
1. 实现 GraphParser（DAG 解析 + 拓扑排序 + 环检测）
2. 实现前端 Runtime（按拓扑序调度节点）
3. 初始化 flask_socketio，注册 Socket.IO 事件
4. 实现 `/api/workflow/run` 路由
5. 实现 Socket.IO 运行状态推送
6. 实现 LLM 流式输出推送

### Phase 4: 增强
1. 变量引擎集成（节点间类型推导）
2. 节点输出预览面板
3. 运行历史记录
4. 错误处理与重试
5. 导入/导出工作流
