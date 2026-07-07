# WorkFlow Spec 设计文档

## 一、项目概述

基于 **React Flow** 开源前端流程搭建引擎，构建一个可视化工作流平台。支持 P4File、Excel、Lua、JSON、Prompt 五类节点，通过**端口类型系统**实现数据源与渲染器的解耦连接，实现文件获取、解析、AI 处理等操作的流程化编排。

### 技术选型

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端画布 | `reactflow` ^11.11.0 | 基于 React 的节点/边图编辑器，节点可任意放置，自由连线 |
| 前端表单 | `antd` + `@ant-design/icons` | 项目已有，节点属性面板 + 节点运行状态图标 |
| 前端渲染 | `antd Table` + `highlight.js` | Excel 表格渲染 / Lua 语法高亮 / JSON 自定义树 |
| 前端运行时 | 自实现 Runtime + Event Bus | 前端 DAG 调度 + 节点成功后级联触发下游 |
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
            ├── FlowEditor.tsx               // ReactFlow 初始化 + 选中节点管理 + 级联执行
            ├── Toolbar.tsx                  // 保存 / 导入 / 导出 / 运行
            ├── PropertyPanel.tsx             // 右侧属性面板（五段式）+ 运行按钮 + 弹窗查看
            ├── Toolbox.tsx                  // 左侧节点工具箱（分类 + 点击创建节点）
            ├── NodeRegistry.tsx             // 注册所有节点类型 → NodeComponent / Icon / Category
            ├── PortTypes.ts                 // 端口类型系统 + 兼容性矩阵
            ├── NodeEventBus.ts              // 节点事件总线（级联执行通信）
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
            └── nodes/
                ├── BaseNode.tsx              // 通用节点基座组件（三段式布局 + 端口 Handle + 必填校验）
                ├── FlowingEdge.tsx           // 自定义边组件（三种视觉状态）
                │
                ├── P4File/
                │   ├── index.tsx             // P4File 节点（数据源）
                │   ├── executor.ts           // （仅类型导出）
                │   └── icon.tsx              // Toolbox 图标
                │
                ├── Excel/
                │   ├── index.tsx             // 基于 BaseNode，定义 fields 配置
                │   └── ExcelRenderer.tsx      // antd Table 渲染器
                │
                ├── Lua/
                │   ├── index.tsx
                │   └── LuaRenderer.tsx        // highlight.js 语法高亮渲染器
                │
                ├── Json/
                │   ├── index.tsx
                │   └── JsonRenderer.tsx        // 自定义 JSON 树渲染器
                │
                └── Prompt/
                    ├── index.tsx
                    └── executor.ts
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
│       ├── workflowImp.py                   // 工作流 CRUD 实现 + DAG 运行时
│       ├── nodeExecutor.py                  // 节点执行器基类 + 分发
│       ├── p4FileExecutor.py                // P4File 节点执行（p4Utils 下载 + 文件类型检测）
│       ├── excelExecutor.py                 // Excel 节点执行（接收上游 fileContent / localPath）
│       ├── luaExecutor.py                   // Lua 节点执行（接收上游 fileContent）
│       ├── jsonExecutor.py                  // JSON 节点执行（接收上游 fileContent + jsonPath 过滤）
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

### 3.2 P4File 节点（数据源）

**设计原则：** P4File 是独立的数据源节点，负责同步 P4 文件并输出文件内容。下游渲染器节点（Excel / JSON / Lua）不再内置 P4 路径，而是通过端口连线接收上游输出。

**Schema:**

```typescript
interface P4FileConfig {
  p4Path: string;       // P4 文件路径，如 //C7/Development/Mainline/Server/config/c7_video.json（必填）
}
```

**端口定义:**

| 方向 | key | label | type |
|------|-----|-------|------|
| output | fileContent | 文件内容 | file-content |

**执行流程:**

```
1. 接收 config.p4Path
2. 调用 p4Utils.update_file 下载文件到 P4_WORKSPACE_DIRECTORY
3. 读取文件内容
4. 检测文件类型（json → "json", .xlsx → "excel", .lua → "lua" 等）
5. 返回 { filePath, localPath, fileType, fileContent, size }
```

**输出:** `{ filePath: string, localPath: string, fileType: string, fileContent: string, size: number }`

### 3.3 Excel 节点（渲染器）

**Schema:**

```typescript
interface ExcelConfig {
  sheet?: string;            // 工作表名（可选，默认第一个）
  rowFilter?: string[];      // 行筛选（可选，1-based 行号列表）
  columnFilter?: string[];   // 列筛选（可选，列名列表）
}
```

**端口定义:**

| 方向 | key | label | type |
|------|-----|-------|------|
| input | fileContent | 文件内容 | file-content |
| output | tableData | 表格数据 | table-data |

**执行流程:**

```
1. 从 input_data 获取 localPath（优先，用于 xlsx 二进制）或 fileContent
2. 格式校验：如果输入是 JSON 格式，返回错误提示"请使用 JSON 节点"
3. localPath 存在 → openpyxl.load_workbook 解析
4. 仅 fileContent → 尝试 BytesIO 加载，失败则尝试 CSV 解析
5. 按 sheet / rowFilter / columnFilter 过滤
6. None 列头替换为 "Col{i+1}"，避免类型比较错误
7. 返回 { columns, rows, sheetNames }
```

**输出:** `{ columns: string[], rows: Record<string, any>[], sheetNames: string[] }`

### 3.4 JSON 节点（渲染器）

**Schema:**

```typescript
interface JsonConfig {
  jsonPath?: string;   // JSON Path 过滤（可选，如 $.data.items）
}
```

**端口定义:**

| 方向 | key | label | type |
|------|-----|-------|------|
| input | fileContent | 文件内容 | file-content |
| output | jsonData | JSON 数据 | json-data |

**执行流程:**

```
1. 从 input_data 获取 fileContent
2. json.loads 解析
3. 如指定 jsonPath → 按 dot notation 过滤
4. 如未指定 jsonPath → 返回完整解析数据
```

**输出:** `{ data: any, path?: string }`

### 3.5 Lua 节点（渲染器）

**Schema:**

```typescript
interface LuaConfig {
  entryFunction?: string;  // 入口函数名（可选）
}
```

**端口定义:**

| 方向 | key | label | type |
|------|-----|-------|------|
| input | fileContent | 文件内容 | file-content |
| output | textOutput | 文本输出 | text |

**执行流程:**

```
1. 从 input_data 获取 fileContent
2. 返回内容
3. 如指定 entryFunction → 提取该函数体
```

**输出:** `{ content: string, functionName?: string, functionContent?: string }`

### 3.6 Prompt 节点

**Schema:**

```typescript
interface PromptConfig {
  prompt: string;           // 提示词内容，支持 {{nodeId.outputKey}} 变量插值（必填）
  temperature?: number;     // 温度，默认 0.7
  model?: string;           // 模型名称，默认由后端配置
}
```

**端口定义:**

| 方向 | key | label | type |
|------|-----|-------|------|
| input | context | 上下文 | any |
| output | result | 结果 | text |

**执行流程:**

```
1. 接收上游节点输出作为变量
2. 替换 prompt 中的 {{}} 变量占位符
3. 调用后端 API（LLM 接口 / DashScope）
4. 后端: 组装 prompt → 调用 LLM → 返回结果
```

**输出:** `{ content: string, model: string, usage: { promptTokens: number, completionTokens: number } }`

---

## 四、端口类型系统

### 4.1 端口定义

```typescript
// PortTypes.ts
interface PortDefinition {
  key: string;        // 端口唯一标识，如 'fileContent'
  label: string;      // 显示名称，如 '文件内容'
  type: string;       // 端口类型，如 'file-content'
  direction: 'input' | 'output';
}
```

### 4.2 端口兼容性矩阵

```typescript
const PORT_TYPE_COMPATIBILITY: Record<string, string[]> = {
  'file-content': ['file-content', 'any'],     // file-content 可连接到自身或 any
  'table-data':   ['table-data', 'any'],
  'json-data':    ['json-data', 'any'],
  'text':         ['text', 'any'],
  'any':          ['file-content', 'table-data', 'json-data', 'text', 'any'],
};
```

### 4.3 各节点端口定义

| 节点 | Input Ports | Output Ports |
|------|-------------|-------------|
| P4File | — | fileContent (file-content) |
| Excel | fileContent (file-content) | tableData (table-data) |
| JSON | fileContent (file-content) | jsonData (json-data) |
| Lua | fileContent (file-content) | textOutput (text) |
| Prompt | context (any) | result (text) |

### 4.4 端口颜色

| type | 颜色 | Hex |
|------|------|-----|
| file-content | 蓝色 | #1890ff |
| file-path | 紫色 | #722ed1 |
| any | 灰色 | #8c8c8c |
| text | 橙色 | #fa8c16 |
| table-data | 绿色 | #52c41a |
| json-data | 青色 | #13c2c2 |

---

## 五、边（Edge）视觉状态

### 5.1 FlowingEdge 自定义边

| 状态 | 视觉效果 | 触发条件 |
|------|----------|----------|
| **mismatched** | 红色虚线 + ✗ 标记 | 端口类型不兼容 |
| **matched_idle** | 灰色实线 | 端口类型匹配，上游未运行 |
| **activated** | 绿色实线 + 流动圆点动画 + ✓ 标记 | 上游节点执行成功，数据已流过 |

### 5.2 边数据结构

```typescript
interface EdgeData {
  sourcePortType: string;     // 源端口类型
  targetPortType: string;     // 目标端口类型
  matchStatus: 'matched' | 'mismatched' | 'unknown';
  activated: boolean;         // 上游节点执行成功后设为 true
}
```

### 5.3 状态流转

```
连接时 → onConnect 计算 matchStatus → matched/mismatched
         ↓
上游节点执行成功 → NodeEventBus.emit → FlowEditor 标记 activated: true
         ↓
边缘视觉变化 → matched_idle (灰) → activated (绿+流动+✓)
         ↓
级联触发 → 自动运行下游节点
```

---

## 六、React Flow 集成方案

### 6.1 npm 包

```json
{
  "dependencies": {
    "reactflow": "^11.11.0"
  }
}
```

### 6.2 BaseNode 三段式布局

节点采用固定的三段式布局，不支持折叠：

```
┌─────────────────────────────────────┐
│ Section 1: Header                    │
│  [icon] [label]          [run ▶]     │
├─────────────────────────────────────┤
│ Section 2: Port Row                  │
│  ● 文件内容          文件内容 ●       │  ← input 左 / output 右
│  (Handle在端口点)    (Handle在端口点) │
├─────────────────────────────────────┤
│ Section 3: Content                   │
│  [字段编辑]                           │
│  [运行结果/渲染器]                     │
└─────────────────────────────────────┘
```

**关键设计：**

- **Handle 定位**：Handle 绝对定位于每个端口行的左侧/右侧边缘，与端口彩色圆点重合
- **端口间距**：左右列 padding 22px，label 与 Handle 间 margin 4px，确保 Handle 不与文字重叠
- **必填字段**：`NodeField.required: boolean` — 必填且为空时红色边框 + 红色 `*` 标记，运行按钮禁用
- **不可折叠**：始终显示所有字段和结果，无双击编辑/折叠行为

### 6.3 NodeField 接口

```typescript
interface NodeField {
  key: string;
  label: string;
  placeholder?: string;
  type?: 'text' | 'textarea' | 'number' | 'select' | 'multiselect';
  rows?: number;          // textarea 行数
  step?: number;          // number 步长
  options?: { label: string; value: string }[];  // select/multiselect 选项
  required?: boolean;     // 是否必填（必填且为空时禁用运行按钮）
}
```

### 6.4 各节点 fields 定义

| 节点 | icon | category | fields |
|------|------|----------|--------|
| P4File | 📁 | 数据源 | p4Path(text, **required**) |
| Excel | 📊 | 渲染器 | sheet(text), rowFilter(multiselect), columnFilter(multiselect) |
| JSON | 📋 | 渲染器 | jsonPath(text) |
| Lua | 🌙 | 渲染器 | entryFunction(text) |
| Prompt | 🤖 | AI | prompt(textarea, **required**), model(text), temperature(number,0.1) |

### 6.5 节点类型注册

```tsx
// NodeRegistry.tsx
export const nodeTypes: NodeTypes = {
  p4file: P4FileNode,
  excel: ExcelNode,
  lua: LuaNode,
  json: JsonNode,
  prompt: PromptNode,
};

export const nodeRegistryList: NodeRegistryEntry[] = [
  { type: 'p4file', label: 'P4 文件', icon: <P4FileIcon />, category: '数据源' },
  { type: 'excel', label: 'Excel', icon: <ExcelIcon />, category: '渲染器' },
  { type: 'json', label: 'JSON', icon: <JsonIcon />, category: '渲染器' },
  { type: 'lua', label: 'Lua', icon: <LuaIcon />, category: '渲染器' },
  { type: 'prompt', label: 'Prompt', icon: <PromptIcon />, category: 'AI' },
];
```

### 6.6 运行数据存储

运行状态和结果存储在 `node.data` 的内部字段中：

```typescript
node.data._runStatus: 'idle' | 'running' | 'success' | 'error'
node.data._runOutput: any  // 运行结果或错误信息
```

**运行按钮禁用逻辑：**

```typescript
const canRun = fields
  .filter((f) => f.required)
  .every((f) => data[f.key] !== undefined && String(data[f.key]).trim() !== '');
```

---

## 七、级联执行机制

### 7.1 NodeEventBus

节点间通过事件总线通信，实现上游成功后自动触发下游：

```typescript
// NodeEventBus.ts
export const NodeEventBus = {
  subscribe(fn: (nodeId: string, output: any) => void): () => void;
  emit(nodeId: string, output: any): void;
};
```

### 7.2 级联流程

```
1. 用户点击节点运行按钮 → BaseNode.handleRun()
2. 调用 FlowApi.runNode(nodeType, cleanConfig, upstreamInput)
3. 运行成功 → NodeEventBus.emit(id, output)
4. FlowEditor 订阅 → handleNodeSuccess(succeededNodeId, output)
   a. 标记出边 activated: true
   b. 查找下游节点 → 收集输入 → 自动运行
   c. 下游成功 → 继续 emit → 继续级联
```

### 7.3 上游输入收集

BaseNode 和 PropertyPanel 在运行时通过 `getNodes()` + `getEdges()` 读取当前节点状态：

```typescript
const collectUpstreamInput = () => {
  const edges = getEdges();
  const incoming = edges.filter((e) => e.target === id && e.targetHandle);
  const nodes = getNodes();
  const input: Record<string, any> = {};
  for (const edge of incoming) {
    const srcNode = nodes.find((n) => n.id === edge.source);
    const srcOutput = srcNode?.data?._runOutput;
    if (!srcOutput || srcOutput.error) continue;
    if (edge.sourceHandle && srcOutput[edge.sourceHandle] !== undefined) {
      input[edge.targetHandle || edge.sourceHandle] = srcOutput[edge.sourceHandle];
    } else {
      Object.assign(input, srcOutput);
    }
  }
  return input;
};
```

### 7.4 Config 清理

发送到后端的 config 只包含字段值，过滤掉内部状态键（`_runStatus`、`_runOutput` 等）：

```typescript
const cleanConfig: Record<string, any> = {};
for (const [k, v] of Object.entries(nodeData)) {
  if (!k.startsWith('_') && v !== undefined) {
    cleanConfig[k] = v;
  }
}
```

---

## 八、PropertyPanel 五段式设计

### 8.1 面板结构

| Section | 标题 | 内容 |
|---------|------|------|
| **1. 端口信息** | 端口信息 | Input/Output 端口列表 + 类型 Tag + 连接匹配状态 |
| **2. 参数** | 参数 | 节点类型对应的字段输入框 |
| **3. 输入内容** | 输入内容 | 按端口显示上游数据：端口标签 + 数据状态 + 内容预览 + 弹窗查看 |
| **4. 运行信息** | 运行信息 | 运行状态（idle/running/success/error）+ 错误提示 |
| **5. 输出内容** | 输出内容 | 格式化输出 + 弹窗查看 |

### 8.2 Section 组件

每个 Section 支持折叠/展开，标题行显示 ▼/▶ 切换图标：

```tsx
function Section({ title, children, defaultOpen = true }: {
  title: string; children: React.ReactNode; defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  // ... 渲染标题 + 折叠内容
}
```

### 8.3 输入内容详情

每个输入端口显示：

```
● 文件内容 [已接收] [弹窗查看]
来自 p4file_xxx → fileContent
┌──────────────────────┐
│ {                    │  ← 预览（maxHeight: 80px）
│   "key": "value",    │
│   ...                │
└──────────────────────┘
```

- **Tag 状态**：`已接收`（绿色，有数据）/ `未接收`（橙色，上游未运行）
- **内容预览**：`<pre>` 块，maxHeight 80px，可滚动
- **弹窗查看**：点击按钮打开 Modal，800px 宽，70vh 高度，支持复制

### 8.4 弹窗查看

统一的 Modal 组件，用于输入内容和输出内容的完整查看：

```tsx
<Modal
  title={modalTitle}          // "输入内容 - 文件内容" 或 "输出内容"
  open={inputModalOpen || outputModalOpen}
  width={800}
  footer={[
    <Button icon={<CopyOutlined />} onClick={() => copyToClipboard(modalContent)}>复制</Button>,
    <Button type="primary" onClick={close}>关闭</Button>,
  ]}
>
  <pre>{modalContent}</pre>   // maxHeight: 70vh, 可滚动，可搜索
</Modal>
```

### 8.5 剪贴板兼容

`navigator.clipboard.writeText` 需要 HTTPS（Docker HTTP 访问不支持），使用 fallback：

```typescript
const copyToClipboard = (text: string) => {
  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(text);
  } else {
    // Fallback: textarea + execCommand
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
  }
};
```

---

## 九、前端渲染器

### 9.1 JSON 渲染器（自定义树）

- 递归可折叠 JSON 树
- Object → `Object{keyCount}` 展开显示子键
- Array → `Array[length]` 展开显示元素
- 字符串值、数值、布尔值、null 各有颜色区分

### 9.2 Excel 渲染器（antd Table）

- 使用 `antd` 的 `Table` 组件
- 支持列筛选和行筛选
- 从上游 `runOutput.columns` / `runOutput.rows` 获取数据

### 9.3 Lua 渲染器（highlight.js）

- 使用 `highlight.js` 进行 Lua 语法高亮
- 暗色背景主题
- 支持入口函数提取显示

### 9.4 延迟加载

渲染器使用 `React.lazy` + `Suspense` 按需加载：

```tsx
const ExcelRenderer = lazy(() => import('./Excel/ExcelRenderer'));
const JsonRenderer = lazy(() => import('./Json/JsonRenderer'));
const LuaRenderer = lazy(() => import('./Lua/LuaRenderer'));
```

---

## 十、API 设计

### 10.1 前端 API 封装

```typescript
// services/FlowApi.ts
const API_BASE = (typeof window !== 'undefined' && (window as any).FLASK_BACKEND_URL) || '';

// 开发环境（localhost）：API_BASE 为空，请求走 UMI proxy
// Docker 开发（172.28.x.x）：public/env-config.js 自动检测 hostname，注入 http://{host}:16666
// 生产环境：deploy/dist/env-config.js 注入 window.FLASK_BACKEND_URL
```

**环境自动检测（public/env-config.js）：**

```javascript
(function() {
  if (window.FLASK_BACKEND_URL) return;
  var hostname = window.location.hostname;
  if (hostname !== 'localhost' && hostname !== '127.0.0.1') {
    window.FLASK_BACKEND_URL = 'http://' + hostname + ':16666';
  }
})();
```

### 10.2 UMI Proxy 配置

```typescript
// config/proxy.ts
export default {
  dev: {
    '/api/workflow/': {
      target: process.env.FLASK_BACKEND_URL || 'http://localhost:16666',
      changeOrigin: true,
    },
  },
};
```

### 10.3 REST API

| Method | Path | 说明 | 请求体 | 响应 |
|--------|------|------|--------|------|
| POST | `/api/workflow/save` | 保存工作流 | `{ name, json, id?, author?, description? }` | `{ id, name }` |
| GET | `/api/workflow/<id>` | 获取工作流 | - | `{ id, name, json, ... }` |
| GET | `/api/workflow/list` | 工作流列表 | - | `{ list: [...] }` |
| DELETE | `/api/workflow/<id>` | 删除工作流 | - | `{ success }` |
| POST | `/api/workflow/node/run` | 运行单个节点 | `{ type, config, input }` | `{ output }` |
| POST | `/api/workflow/run` | 运行整个工作流 | `{ workflowId }` | `{ taskId }` |
| GET | `/api/workflow/run/<taskId>/status` | 查询运行状态 | - | `{ status, nodes }` |
| POST | `/api/workflow/run/<taskId>/cancel` | 取消运行 | - | `{ success }` |
| GET | `/api/workflow/executors` | 列出注册的执行器 | - | `{ executors: [{ type, class }] }` |

---

## 十一、后端执行器设计

### 11.1 执行器基类

```python
class BaseNodeExecutor(ABC):
    @property
    @abstractmethod
    def type(self) -> str:
        pass

    @abstractmethod
    async def execute(self, config: dict, input_data: dict) -> dict:
        pass

class ExecutorManager:
    _executors: dict = {}

    @classmethod
    def register(cls, executor):
        cls._executors[executor.type] = executor

    @classmethod
    async def run_node(cls, node_type: str, config: dict, input_data: dict) -> dict:
        executor = cls.get(node_type)
        if not executor:
            raise ValueError(f"Unknown node type: {node_type}")
        return await executor.execute(config, input_data)
```

### 11.2 P4File 执行器

```python
class P4FileExecutor(BaseNodeExecutor):
    type = "p4file"

    async def execute(self, config: dict, input_data: dict) -> dict:
        p4_path = config.get("p4Path", "")
        local_path = self._p4_sync(p4_path)
        content = open(local_path, 'r', encoding='utf-8', errors='replace').read()
        file_type = self._detect_file_type(p4_path, content)
        return {
            "filePath": p4_path,
            "localPath": local_path,
            "fileType": file_type,
            "fileContent": content,
            "size": os.path.getsize(local_path),
        }
```

### 11.3 Excel 执行器

关键设计：接收上游 `input_data` 而非内置 P4 路径；格式校验拒绝 JSON 输入；None 列头安全处理。

```python
class ExcelExecutor(BaseNodeExecutor):
    type = "excel"

    async def execute(self, config: dict, input_data: dict) -> dict:
        local_path = input_data.get("localPath", "")
        file_content = input_data.get("fileContent", "")
        file_type = input_data.get("fileType", "")

        # Format validation: reject JSON input
        if file_type == "json" or (not local_path and file_content and not file_content.startswith("PK")):
            try:
                json.loads(file_content[:500])
                return {"error": "Input content is JSON format, not Excel. Use the JSON node instead."}
            except (json.JSONDecodeError, ValueError):
                pass

        # Parse: localPath (xlsx binary) > fileContent (bytes/CSV)
        # Column safety: None headers → "Col{i+1}", filter uses set() for membership test
        ...
```

### 11.4 JSON 执行器

```python
class JsonExecutor(BaseNodeExecutor):
    type = "json"

    async def execute(self, config: dict, input_data: dict) -> dict:
        file_content = input_data.get("fileContent", "")
        json_path = config.get("jsonPath", "")

        if not file_content:
            return {"error": "No input content. Connect an upstream node or provide content."}

        data = json.loads(file_content)
        if json_path:
            data = self._query_json_path(data, json_path)

        return {"data": data, "path": json_path or None}
```

### 11.5 Lua 执行器

```python
class LuaExecutor(BaseNodeExecutor):
    type = "lua"

    async def execute(self, config: dict, input_data: dict) -> dict:
        file_content = input_data.get("fileContent", "")
        entry_function = config.get("entryFunction", "")

        if not file_content:
            return {"error": "No input content. Connect an upstream node or provide content."}

        result = {"content": file_content, "filePath": input_data.get("filePath", "")}
        if entry_function:
            # Extract function body by regex
            ...
        return result
```

---

## 十二、运行时设计（Runtime）

### 12.1 后端 WorkflowRuntime

```python
class WorkflowRuntime:
    @classmethod
    async def run(cls, workflow_json, task_id):
        # 1. DAG 构建 + 拓扑排序
        # 2. 按序执行每个节点
        # 3. 端口映射：edge.sourceHandle → edge.targetHandle
        # 4. 上下文传递：上游输出 → 下游 input_data
        for nid in order:
            node = node_map[nid]
            input_edges = [e for e in edges if e.get('target') == nid]
            input_data = {}
            for edge in input_edges:
                src_output = context.get(edge['source'], {})
                if edge.get('targetHandle') and edge.get('sourceHandle'):
                    if edge['sourceHandle'] in src_output:
                        input_data[edge['targetHandle']] = src_output[edge['sourceHandle']]
                else:
                    input_data.update(src_output)
            output = await ExecutorManager.run_node(node['type'], node['data'], input_data)
            context[nid] = output
```

---

## 十三、整体数据流架构

```
┌──────────────────────────────────────────────────┐
│              React + React Flow                   │
│                                                   │
│  ReactFlowProvider                                │
│       ├── ReactFlow (Canvas)                     │
│       │     ├── nodeTypes: 5 种节点               │
│       │     ├── edgeTypes: FlowingEdge            │
│       │     ├── Background / Controls / MiniMap    │
│       │     └── onConnect: 端口类型匹配 → 边 data  │
│       ├── Toolbox (分类: 数据源/渲染器/AI)          │
│       ├── BaseNode (三段式布局 + 端口Handle)        │
│       │     ├── Section1: Header + 运行按钮        │
│       │     ├── Section2: Port Row (Handle=端口点) │
│       │     └── Section3: Fields + Renderer       │
│       ├── PropertyPanel (五段式: 端口/参数/输入/运行/输出)│
│       │     └── 弹窗查看 (输入+输出, 复制按钮在弹窗内) │
│       ├── Toolbar (保存/导入/导出/运行)              │
│       ├── NodeEventBus (级联执行通信)               │
│       └── FlowEditor (订阅事件 → 标记边activated → 触发下游)│
│                                                   │
│  数据流:                                          │
│    P4File(fileContent) ──matched edge──→ JSON     │
│         │                                         │
│         └──matched edge──→ Excel / Lua            │
│                                                   │
│  运行状态:                                        │
│    上游成功 → NodeEventBus.emit                    │
│           → FlowEditor.handleNodeSuccess           │
│           → edges[activated=true] + 级联触发下游     │
│                                                   │
└──────────┬────────────────────────────────────────┘
           │
     HTTP REST (UMI proxy / env-config.js auto-detect)
           │
           ▼
┌──────────────────────────────────────────────────┐
│         Flask + gevent (Python)                  │
│                                                  │
│  routers/WorkFlow.py                             │
│       ├── CRUD: save / get / list / delete       │
│       ├── POST /api/workflow/node/run             │
│       └── POST /api/workflow/run + status         │
│                                                  │
│  Implement/workflowImpl/                         │
│       ├── ExecutorManager (5 个执行器注册)         │
│       ├── P4FileExecutor (数据源: p4 sync + 输出)  │
│       ├── ExcelExecutor (渲染器: 接收上游内容)       │
│       ├── JsonExecutor  (渲染器: 接收上游内容)       │
│       ├── LuaExecutor   (渲染器: 接收上游内容)       │
│       └── PromptExecutor (AI: LLM 调用)            │
│                                                  │
└──────────────────────────────────────────────────┘
```

---

## 十四、依赖清单

### 14.1 前端 npm 依赖

| 包名 | 版本 | 说明 |
|------|------|------|
| `reactflow` | ^11.11.0 | React Flow 画布编辑器 |
| `@ant-design/icons` | 项目已有 | 节点运行状态图标 |
| `antd` | ^6.5.0 | 属性面板 Button / Modal / Tag / Table 等组件 |
| `highlight.js` | ^11.x | Lua 语法高亮渲染 |

### 14.2 后端 Python 依赖

| 包名 | 版本 | 说明 |
|------|------|------|
| `openpyxl` | 已有 | Excel 文件解析 |
| `gevent` | 已有 | WSGIServer 运行模式 |

---

## 十五、实施阶段

### Phase 1: 基础框架搭建 ✅（已完成）
1. ~~安装 ReactFlow 依赖包~~ ✅
2. ~~创建 Workflow 页面入口~~ ✅
3. ~~初始化 ReactFlowProvider + useNodesState / useEdgesState~~ ✅
4. ~~实现 Toolbox（5 种节点分类创建）~~ ✅
5. ~~实现 PropertyPanel（五段式属性面板）~~ ✅
6. ~~实现 Toolbar（保存/加载/导入/导出 JSON）~~ ✅
7. ~~实现 FlowApi（后端 API 封装 + proxy 配置 + env-config.js 自动检测）~~ ✅
8. ~~实现 NodeRegistry（5 种节点类型注册 + 分类）~~ ✅

### Phase 2: 节点组件 ✅（已完成）
1. ~~实现 BaseNode 三段式布局（Header / Port Row / Content）~~ ✅
2. ~~端口 Handle 内联定位于端口点（左侧 input / 右侧 output）~~ ✅
3. ~~实现 5 种节点（P4File / Excel / Lua / JSON / Prompt）~~ ✅
4. ~~必填字段校验 + 运行按钮禁用~~ ✅
5. ~~选中节点 ID 而非快照（解决数据过期问题）~~ ✅
6. ~~运行结果存储在 node.data（节点间隔离）~~ ✅

### Phase 3: 端口类型系统与连线 ✅（已完成）
1. ~~实现 PortTypes.ts（端口定义 + 兼容性矩阵 + isPortTypeCompatible）~~ ✅
2. ~~实现 FlowingEdge 自定义边（三状态：mismatched / matched_idle / activated）~~ ✅
3. ~~onConnect 自动计算 matchStatus → 存入边 data~~ ✅
4. ~~上游节点成功 → 标记出边 activated: true → 边变绿+流动+✓~~ ✅

### Phase 4: 节点执行与级联 ✅（已完成）
1. ~~实现后端 BaseNodeExecutor + ExecutorManager~~ ✅
2. ~~实现 P4File / Excel / Lua / JSON / Prompt 执行器~~ ✅
3. ~~P4File 独立数据源节点（p4 sync + 文件类型检测 + 输出）~~ ✅
4. ~~渲染器节点接收上游 input_data（非内置 P4 路径）~~ ✅
5. ~~Excel 格式校验（拒绝 JSON 输入）~~ ✅
6. ~~前端级联执行：NodeEventBus + FlowEditor 订阅 → 自动触发下游~~ ✅
7. ~~上游输入实时收集（collectUpstreamInput 在运行时读取最新状态）~~ ✅
8. ~~Config 清理（过滤内部 `_` 前缀键，不发送到后端）~~ ✅

### Phase 5: 前端渲染与面板 ✅（已完成）
1. ~~JSON 渲染器（自定义可折叠树）~~ ✅
2. ~~Excel 渲染器（antd Table + 行列筛选）~~ ✅
3. ~~Lua 渲染器（highlight.js 语法高亮）~~ ✅
4. ~~PropertyPanel 五段式（端口信息/参数/输入内容/运行信息/输出内容）~~ ✅
5. ~~输入内容：按端口显示上游数据预览 + 弹窗查看~~ ✅
6. ~~输出内容：格式化显示 + 弹窗查看（复制按钮在弹窗内）~~ ✅
7. ~~剪贴板 HTTP fallback（textarea + execCommand）~~ ✅

### Phase 6: 整体运行（待实现）
1. 实现 GraphParser（DAG 解析 + 拓扑排序 + 环检测）
2. 实现前端 Runtime（按拓扑序调度节点）
3. 完善 `/api/workflow/run` 路由 + 端口映射
4. Socket.IO 运行状态推送（如需要）

### Phase 7: 增强（待实现）
1. 节点拖拽排序（React Flow dnd 支持）
2. 运行历史记录
3. 错误处理与重试
4. Undo / Redo 支持
