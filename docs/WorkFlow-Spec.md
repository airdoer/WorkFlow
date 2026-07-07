# WorkFlow Spec 设计文档

## 一、项目概述

基于 **React Flow** 开源前端流程搭建引擎，构建一个可视化工作流平台。支持 Excel、Lua、JSON、Prompt 四类节点，实现文件获取、解析、AI 处理等操作的流程化编排。

### 技术选型

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端画布 | `reactflow` ^11.11.0 | 基于 React 的节点/边图编辑器，节点可任意放置，自由连线 |
| 前端表单 | `antd` + `@ant-design/icons` | 项目已有，节点属性面板 + 节点运行状态图标 |
| 前端运行时 | 自实现 Runtime | 前端 DAG 调度（预览/调试） |
| 后端框架 | Flask (Python) + gevent | 项目已有服务端，gevent WSGIServer 运行 |
| 通信协议 | HTTP REST | REST 负责 CRUD + 节点执行 |
| P4 集成 | `p4Utils` (项目已有) | 使用 `p4 print -q` 下载文件，不依赖 client root |

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
            ├── FlowEditor.tsx               // ReactFlow 初始化 + 选中节点管理
            ├── Toolbar.tsx                  // 保存 / 导入 / 导出 / 运行
            ├── PropertyPanel.tsx             // 右侧属性面板 + 运行按钮 + 结果展示
            ├── Toolbox.tsx                  // 左侧节点工具箱（点击创建节点）
            ├── NodeRegistry.tsx             // 注册所有节点类型 → NodeComponent / Icon
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
                ├── BaseNode.tsx              // 通用节点基座组件（内联编辑 + 运行按钮 + 结果展示）
                │
                ├── Excel/
                │   ├── index.tsx             // 基于 BaseNode，定义 fields 配置
                │   ├── schema.ts             // ExcelConfig 类型
                │   └── icon.tsx              // Toolbox 图标
                │
                ├── Lua/
                │   ├── index.tsx
                │   ├── schema.ts
                │   └── icon.tsx
                │
                ├── Json/
                │   ├── index.tsx
                │   ├── schema.ts
                │   └── icon.tsx
                │
                └── Prompt/
                    ├── index.tsx
                    ├── schema.ts
                    └── icon.tsx
```

### 2.2 后端

```
server/
├── routers/
│   └── WorkFlow.py                         // HTTP REST 路由
│
├── Implement/
│   └── workflowImpl/
│       ├── __init__.py
│       ├── workflowImp.py                   // 工作流 CRUD 实现
│       ├── nodeExecutor.py                  // 节点执行器基类 + 分发
│       ├── excelExecutor.py                 // Excel 节点执行（p4Utils + openpyxl）
│       ├── luaExecutor.py                   // Lua 节点执行（p4Utils + 内容读取）
│       ├── jsonExecutor.py                  // JSON 节点执行（p4Utils + json 解析）
│       └── promptExecutor.py                // Prompt 节点执行（调用 LLM API）
│
├── utility/
│   └── p4Utils.py                          // P4 工具库（download_file / update_file / list_dir 等）
│
└── config.py                               // P4_WORKSPACE_DIRECTORY 等配置
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
3. 后端: p4Utils.update_file 下载文件到 P4_WORKSPACE_DIRECTORY → openpyxl 解析指定 sheet
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
3. 后端: p4Utils.update_file 下载文件 → 读取内容 → 返回源码文本
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
3. 后端: p4Utils.update_file 下载文件 → json.loads 解析 → 按 jsonPath 过滤 → 返回
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
```

**输出:** `{ content: string, model: string, usage: { promptTokens: number, completionTokens: number } }`

---

## 四、React Flow 集成方案

### 4.1 npm 包

```json
{
  "dependencies": {
    "reactflow": "^11.11.0"
  }
}
```

React Flow v11 为单一包，内置以下能力（无需额外安装）：

| 能力 | 对应组件 | 说明 |
|------|----------|------|
| 画布背景 | `<Background />` | 网格/点状背景 |
| 小地图 | `<MiniMap />` | 缩略导航 |
| 控制面板 | `<Controls />` | 缩放/居中按钮 |
| 键盘删除 | `deleteKeyCode` | 支持 Delete/Backspace 删除节点 |
| 导入/导出 | `instance.toObject()` / `initialState` | JSON 序列化/反序列化 |

**.npmrc 配置:**

```
legacy-peer-deps=true
```

### 4.2 Editor 初始化

```tsx
// FlowEditor.tsx
import ReactFlow, {
  Node, Edge,
  ReactFlowProvider,
  useNodesState, useEdgesState,
  Background, Controls, MiniMap,
} from 'reactflow';
import 'reactflow/dist/style.css';

function FlowEditorInner({ initialData }: { initialData?: WorkflowJSON }) {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialData?.nodes || []);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialData?.edges || []);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  // 通过 selectedNodeId + useMemo 从 nodes 数组实时获取最新节点数据
  // 避免 onNodeClick 快照导致的数据过期问题
  const selectedNode = useMemo(
    () => (selectedNodeId ? nodes.find((n) => n.id === selectedNodeId) ?? null : null),
    [selectedNodeId, nodes],
  );

  const onNodeClick = useCallback((_, node) => setSelectedNodeId(node.id), []);

  const onNodesDelete = useCallback(
    (deleted: Node[]) => {
      if (deleted.some((n) => n.id === selectedNodeId)) {
        setSelectedNodeId(null);
      }
    },
    [selectedNodeId],
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
      <Toolbar nodes={nodes} edges={edges} setNodes={setNodes} setEdges={setEdges} />
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        <Toolbox nodes={nodes} setNodes={setNodes} />
        <div style={{ flex: 1, minHeight: 0 }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onPaneClick={() => setSelectedNodeId(null)}
            onNodesDelete={onNodesDelete}
            nodeTypes={nodeTypes}
            deleteKeyCode={['Delete', 'Backspace']}
            fitView
          >
            <Background />
            <Controls />
            <MiniMap />
          </ReactFlow>
        </div>
        <PropertyPanel selectedNode={selectedNode} setNodes={setNodes} />
      </div>
    </div>
  );
}

function FlowEditor({ initialData }: { initialData?: WorkflowJSON }) {
  return (
    <ReactFlowProvider>
      <FlowEditorInner initialData={initialData} />
    </ReactFlowProvider>
  );
}
```

**关键设计决策:**

- **选中节点用 ID 而非快照**：`onNodeClick` 只记录 `selectedNodeId`，通过 `useMemo` 从 `nodes` 数组实时查找最新节点数据，解决了编辑属性后数据不同步的问题
- **Delete 键支持**：通过 `deleteKeyCode` 和 `onNodesDelete` 回调实现，删除后自动清除选中状态

### 4.3 BaseNode 通用节点组件

所有节点共享 `BaseNode` 组件，统一提供内联编辑、运行按钮和结果展示：

```tsx
// nodes/BaseNode.tsx
interface BaseNodeProps {
  data: Record<string, unknown>;
  id: string;
  selected: boolean;
  icon: string;          // 如 "📊"
  label: string;         // 如 "Excel"
  nodeType: string;      // 如 "excel"，用于调用后端 API
  fields: NodeField[];   // 节点属性字段定义
}

interface NodeField {
  key: string;
  label: string;
  placeholder?: string;
  type?: 'text' | 'textarea' | 'number';
  rows?: number;    // textarea 行数
  step?: number;    // number 步长
}
```

**BaseNode 功能:**

| 功能 | 交互方式 | 说明 |
|------|----------|------|
| 字段摘要 | 默认折叠 | 显示各字段值，末尾提示"双击编辑" |
| 内联编辑 | 双击节点 | 展开编辑表单，点击"收起"关闭 |
| 运行按钮 | 点击右上角按钮 | 调用 `FlowApi.runNode` 执行节点 |
| 运行状态 | 按钮图标 + 边框颜色 | idle=灰 / running=蓝旋转 / success=绿 / error=红 |
| 结果展示 | 节点底部面板 | 成功=绿色背景 / 失败=红色背景，maxHeight 120px + 滚动 |

**运行状态图标（@ant-design/icons）:**

| 状态 | 图标 | 颜色 | 边框 |
|------|------|------|------|
| idle | `PlayCircleOutlined` | 灰 `#8c8c8c` | 默认 |
| running | `LoadingOutlined` (spin) | 蓝 `#1890ff` | 蓝 |
| success | `CheckCircleOutlined` | 绿 `#52c41a` | 绿 |
| error | `CloseCircleOutlined` | 红 `#ff4d4f` | 红 |

**运行数据存储:** 运行状态和结果存储在 `node.data` 的内部字段中，实现节点间数据隔离：

```typescript
node.data._runStatus: 'idle' | 'running' | 'success' | 'error'
node.data._runOutput: any  // 运行结果或错误信息
```

### 4.4 具体节点实现

每种节点只需定义 `fields` 配置数组，然后调用 `BaseNode`：

```tsx
// nodes/Excel/index.tsx
const EXCEL_FIELDS: NodeField[] = [
  { key: 'p4Path', label: 'P4 路径', placeholder: '//C7/.../file.xlsx' },
  { key: 'sheet', label: '工作表', placeholder: '工作表名（可选）' },
];

function ExcelNode({ data, id, selected }: NodeProps) {
  return (
    <BaseNode
      data={data} id={id} selected={!!selected}
      icon="📊" label="Excel" nodeType="excel" fields={EXCEL_FIELDS}
    />
  );
}
```

各节点 fields 定义:

| 节点 | icon | fields |
|------|------|--------|
| Excel | 📊 | p4Path(text), sheet(text) |
| Lua | 🌙 | p4Path(text), entryFunction(text) |
| JSON | 📋 | p4Path(text), jsonPath(text) |
| Prompt | 🤖 | prompt(textarea,3), model(text), temperature(number,0.1) |

### 4.5 节点类型注册

```tsx
// NodeRegistry.tsx
export const nodeTypes: NodeTypes = {
  excel: ExcelNode,
  lua: LuaNode,
  json: JsonNode,
  prompt: PromptNode,
};

export const nodeRegistryList: NodeRegistryEntry[] = [
  { type: 'excel', label: 'Excel', icon: <ExcelIcon /> },
  { type: 'lua', label: 'Lua', icon: <LuaIcon /> },
  { type: 'json', label: 'JSON', icon: <JsonIcon /> },
  { type: 'prompt', label: 'Prompt', icon: <PromptIcon /> },
];
```

### 4.6 数据流序列化

```typescript
// WorkflowJSON 结构（React Flow 原生格式）
interface WorkflowJSON {
  nodes: Node[];    // React Flow Node 类型
  edges: Edge[];    // React Flow Edge 类型
  viewport?: { x: number; y: number; zoom: number };
}

// React Flow Node 结构
interface Node {
  id: string;
  type: string;       // 'excel' | 'lua' | 'json' | 'prompt'
  position: { x: number; y: number };
  data: Record<string, unknown>;  // 节点配置数据 + 运行状态字段（_runStatus, _runOutput）
}

// React Flow Edge 结构
interface Edge {
  id: string;
  source: string;       // 源节点 ID
  target: string;       // 目标节点 ID
  sourceHandle?: string;
  targetHandle?: string;
}
```

---

## 五、PropertyPanel 设计

### 5.1 数据源

PropertyPanel **直接从 `selectedNode.data` 读取运行状态和结果**，不使用独立的本地 state：

```tsx
const runStatus = (nodeData._runStatus as RunStatus) || 'idle';
const runOutput = nodeData._runOutput as any;
```

**设计决策:** 运行结果存储在节点 `data` 上而非 PropertyPanel 组件 state 中，原因：
1. **节点间隔离** — 每个节点的 `_runStatus` / `_runOutput` 独立存储在自己的 `node.data` 中，切换选中节点时自然显示对应节点的结果
2. **节点与面板同步** — 无论从节点上点击运行还是从面板点击运行，结果写入同一个 `node.data`，两边始终一致
3. **数据持久化** — 保存工作流时运行结果随节点数据一起持久化

### 5.2 功能清单

| 功能 | 说明 |
|------|------|
| 属性编辑 | 根据节点类型显示对应的输入字段，修改后通过 `setNodes` 更新 |
| 运行按钮 | 点击调用 `FlowApi.runNode`，将 `_runStatus` / `_runOutput` 写入节点 data |
| 结果展示 | 从 `node.data._runOutput` 读取，成功=绿色面板，失败=红色面板 |
| 高度限制 | 结果面板 maxHeight: 400px，超出用滚动条 |

---

## 六、API 设计

### 6.1 前端 API 封装

```typescript
// services/FlowApi.ts
const API_BASE = (typeof window !== 'undefined' && (window as any).FLASK_BACKEND_URL) || '';

// 开发环境：API_BASE 为空，请求走 UMI proxy（config/proxy.ts → localhost:16666）
// 生产环境：API_BASE 由 env-config.js 注入 window.FLASK_BACKEND_URL
```

**UMI Proxy 配置:**

```typescript
// config/proxy.ts
export default {
  dev: {
    '/api/workflow/': {
      target: 'http://localhost:16666',
      changeOrigin: true,
    },
  },
};
```

### 6.2 REST API

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

---

## 七、后端执行器设计

### 7.1 执行器基类

```python
# Implement/workflowImpl/nodeExecutor.py
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

### 7.2 P4 文件同步（统一实现）

所有 P4 节点执行器（Excel / Lua / JSON）使用相同的 `_p4_sync` 方法，基于项目已有的 `p4Utils.update_file`：

```python
def _p4_sync(self, p4_path: str) -> str:
    """
    使用 p4Utils.download_file 将文件同步到本地 P4_WORKSPACE_DIRECTORY。
    不依赖 p4 client root，直接用 p4 print 下载到指定路径。
    """
    p4_path = p4Utils.normalize_p4_path(p4_path)
    relative_path = p4_path.lstrip("/").replace("//", "")
    local_path = os.path.join(config.P4_WORKSPACE_DIRECTORY, relative_path)

    success = p4Utils.update_file(p4_path, local_path, force=True)
    if not success:
        raise RuntimeError(f"Failed to sync P4 file: {p4_path}")

    return local_path
```

**设计决策:** 不使用 `p4 sync` + `p4 info` 获取 client root 的方式，原因：
1. Docker 容器内 `p4 info` 可能返回宿主机的 client root（如 `C:\p4ws\...`）而非容器内路径
2. `p4 print -q` 直接下载文件内容，不依赖 client root，与项目中其他路由（configTool、hotfixTool）保持一致
3. `p4Utils.update_file` 自动创建目录、支持版本号、支持 force 强制重新下载

### 7.3 Excel 执行器

```python
class ExcelExecutor(BaseNodeExecutor):
    type = "excel"

    async def execute(self, config: dict, input_data: dict) -> dict:
        p4_path = config.get("p4Path", "")
        sheet_name = config.get("sheet")

        local_path = self._p4_sync(p4_path)
        wb = openpyxl.load_workbook(local_path, data_only=True)
        ws = wb[sheet_name] if sheet_name else wb.active

        columns = [cell.value for cell in ws[1]]
        rows = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            rows.append(dict(zip(columns, row)))

        return {"columns": columns, "rows": rows}
```

### 7.4 JSON 执行器

```python
class JsonExecutor(BaseNodeExecutor):
    type = "json"

    async def execute(self, config: dict, input_data: dict) -> dict:
        p4_path = config.get("p4Path", "")
        json_path = config.get("jsonPath")

        local_path = self._p4_sync(p4_path)
        with open(local_path, 'r', encoding='utf-8', errors='replace') as f:
            data = json.load(f)

        if json_path:
            data = self._query_json_path(data, json_path)

        return {"data": data, "path": json_path}

    def _query_json_path(self, data, path: str):
        parts = path.lstrip("$").lstrip(".").split(".")
        current = data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list) and part.isdigit():
                current = current[int(part)]
            else:
                return None
            if current is None:
                return None
        return current
```

### 7.5 Lua 执行器

```python
class LuaExecutor(BaseNodeExecutor):
    type = "lua"

    async def execute(self, config: dict, input_data: dict) -> dict:
        p4_path = config.get("p4Path", "")
        entry_function = config.get("entryFunction")

        local_path = self._p4_sync(p4_path)
        with open(local_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()

        result = {"content": content}
        if entry_function:
            pattern = rf'(?:function|local\s+function)\s+{re.escape(entry_function)}\s*\('
            match = re.search(pattern, content)
            if match:
                start = match.start()
                func_content = self._extract_function(content, start)
                result["functionName"] = entry_function
                result["functionContent"] = func_content

        return result
```

---

## 八、运行时设计（Runtime）

### 8.1 整体流程

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

### 8.2 GraphParser（DAG 解析）

```typescript
class GraphParser {
  static parse(nodes: Node[], edges: Edge[]): string[] {
    // 1. 构建 DAG（邻接表）— 从 edges 中提取 source → target 关系
    // 2. 检测环路（有环则报错）
    // 3. 拓扑排序（Kahn 算法）
    // 4. 返回有序节点 ID 列表
  }
}
```

### 8.3 Runtime

```typescript
class Runtime {
  async run(nodes: Node[], edges: Edge[]): Promise<ExecutionResult> {
    const order = GraphParser.parse(nodes, edges);
    const context = new Context();

    for (const nodeId of order) {
      const node = nodes.find(n => n.id === nodeId);
      const inputEdges = edges.filter(e => e.target === nodeId);

      const input = {};
      for (const edge of inputEdges) {
        const upstreamOutput = context.getOutput(edge.source);
        Object.assign(input, upstreamOutput);
      }

      const output = await FlowApi.runNode(node.type, node.data, input);
      context.setOutput(nodeId, output);
    }

    return context.getAllOutputs();
  }
}
```

---

## 九、整体数据流架构

```
┌──────────────────────────────────────────────────┐
│              React + React Flow                  │
│                                                  │
│  ReactFlowProvider                               │
│       ├── ReactFlow (Canvas)                     │
│       │     ├── Background / Controls / MiniMap   │
│       │     └── deleteKeyCode: Delete/Backspace   │
│       ├── Toolbox (点击创建节点)                   │
│       ├── BaseNode (内联编辑 + 运行按钮 + 结果)    │
│       ├── PropertyPanel (属性面板 + 运行 + 结果)    │
│       ├── Toolbar (保存/导入/导出/运行)              │
│       └── Runtime (前端 DAG 调度)                 │
│            ├── GraphParser (DAG + 拓扑排序)       │
│            ├── ExecutorManager (分发)             │
│            └── Context (缓存输出)                 │
│                                                  │
│  运行状态数据流:                                   │
│    FlowApi.runNode → node.data._runStatus         │
│                    → node.data._runOutput         │
│                    → BaseNode 按钮图标 + 结果面板   │
│                    → PropertyPanel 结果面板         │
│                                                  │
└──────────┬───────────────────────────────────────┘
           │
     HTTP REST (UMI proxy → localhost:16666)
           │
           ▼
┌──────────────────────────────────────────────────┐
│         Flask + gevent (Python)                   │
│                                                  │
│  routers/WorkFlow.py                            │
│       ├── POST /api/workflow/save                │
│       ├── GET  /api/workflow/<id>                 │
│       ├── POST /api/workflow/node/run             │
│       └── POST /api/workflow/run                  │
│                                                  │
│  Implement/workflowImpl/                         │
│       ├── ExecutorManager                        │
│       ├── ExcelExecutor (p4Utils + openpyxl)      │
│       ├── LuaExecutor   (p4Utils + 读取)          │
│       ├── JsonExecutor  (p4Utils + json)          │
│       └── PromptExecutor (变量插值 + LLM)         │
│                                                  │
│  utility/p4Utils.py                              │
│       ├── update_file (p4 print -q 下载)          │
│       ├── download_file (直接下载)                │
│       └── list_dir / get_latest_changelist       │
│                                                  │
└──────────────────────────────────────────────────┘
```

---

## 十、依赖清单

### 10.1 前端 npm 依赖

| 包名 | 版本 | 说明 |
|------|------|------|
| `reactflow` | ^11.11.0 | React Flow 画布编辑器 |
| `@ant-design/icons` | 项目已有 | 节点运行状态图标（PlayCircle / Loading / CheckCircle / CloseCircle） |
| `antd` | ^6.5.0 | 属性面板 Button / message 等组件 |
| `socket.io-client` | ^4.x | Socket.IO 客户端（Phase 3） |

### 10.2 后端 Python 依赖

| 包名 | 版本 | 说明 |
|------|------|------|
| `openpyxl` | 已有 | Excel 文件解析 |
| `gevent` | 已有 | WSGIServer 运行模式 |

---

## 十一、实施阶段

### Phase 1: 基础框架搭建 ✅（已完成）
1. ~~安装 ReactFlow 依赖包~~ ✅
2. ~~创建 Workflow 页面入口~~ ✅
3. ~~初始化 ReactFlowProvider + useNodesState / useEdgesState~~ ✅
4. ~~实现 Toolbox（4 种节点点击创建）~~ ✅
5. ~~实现 PropertyPanel（属性编辑 + 运行 + 结果展示）~~ ✅
6. ~~实现 Toolbar（保存/加载/导入/导出 JSON）~~ ✅
7. ~~实现 FlowApi（后端 API 封装 + proxy 配置）~~ ✅
8. ~~实现 NodeRegistry（4 种节点类型注册）~~ ✅

### Phase 2: 节点组件 ✅（已完成）
1. ~~实现 BaseNode 通用组件（内联编辑 + 运行按钮 + 状态图标 + 结果面板）~~ ✅
2. ~~实现 4 种节点（Excel / Lua / JSON / Prompt）基于 BaseNode~~ ✅
3. ~~Delete 键删除节点支持~~ ✅
4. ~~选中节点 ID 而非快照（解决数据过期问题）~~ ✅
5. ~~运行结果存储在 node.data（节点间隔离）~~ ✅

### Phase 3: 节点执行 ✅（已完成）
1. ~~实现后端 BaseNodeExecutor + ExecutorManager~~ ✅
2. ~~实现 Excel / Lua / JSON / Prompt 执行器~~ ✅
3. ~~统一使用 p4Utils.update_file 下载文件（不依赖 client root）~~ ✅
4. ~~实现 `/api/workflow/node/run` 路由~~ ✅

### Phase 4: 整体运行（待实现）
1. 实现 GraphParser（DAG 解析 + 拓扑排序 + 环检测）
2. 实现前端 Runtime（按拓扑序调度节点）
3. 实现 `/api/workflow/run` 路由
4. 实现 Socket.IO 运行状态推送（如需要）

### Phase 5: 增强（待实现）
1. 节点拖拽排序（React Flow dnd 支持）
2. 运行历史记录
3. 错误处理与重试
4. Undo / Redo 支持
