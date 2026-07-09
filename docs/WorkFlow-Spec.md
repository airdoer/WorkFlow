# WorkFlow Spec 设计文档

## 一、项目概述

基于 **React Flow** 开源前端流程搭建引擎，构建一个可视化工作流平台。支持 P4File、Excel、Lua、JSON、Prompt 五类节点以及 **String / Bool / Number** 三类基础值节点，通过**端口类型系统**实现数据源与渲染器的解耦连接，实现文件获取、解析、AI 处理等操作的流程化编排。

### 技术选型

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端画布 | `reactflow` ^11.11.0 | 基于 React 的节点/边图编辑器，节点可任意放置，自由连线 |
| 前端表单 | `antd` + `@ant-design/icons` | 项目已有，节点属性面板 + 节点运行状态图标 |
| 前端渲染 | `antd Table` + `highlight.js` | Excel 表格渲染 / Lua 语法高亮 / JSON 自定义树 |
| 前端运行时 | WorkflowContext + onNodeUpdate | 统一节点执行回调，WebSocket 推送更新节点状态 + 激活边 |
| 后端框架 | Flask (Python) + gevent | 项目已有服务端，gevent WSGIServer 运行 |
| 通信协议 | HTTP REST + Socket.IO WebSocket | REST 负责 CRUD；WebSocket 负责节点执行 + 实时状态推送 |
| P4 集成 | `p4Utils` (项目已有) | 使用 `p4 print -q` 下载文件，不依赖 client root |
| 实时通信 | `socket.io-client` ^4.x | WebSocket 长连接，节点执行状态实时推送 |

---

## 二、目录结构

### 2.1 前端

```
client/
└── src/
    ├── pages/
    │   ├── Workflow/
    │   │   └── index.tsx                    // 页面入口，挂载 FlowEditor
    │   ├── FlowDemo.tsx                      // 工作流编辑器页面（ADP 布局）
    │   └── FlowHistory.tsx                   // 工作流历史列表页
    │
    └── components/
        └── workflow/
            ├── FlowEditor.tsx               // ReactFlow 初始化 + 选中节点管理 + handleNodeUpdate
            ├── Toolbar.tsx                  // 保存 / 导入 / 导出 / 运行
            ├── PropertyPanel.tsx             // 右侧属性面板（五段式）+ 运行按钮（runNodeWS）+ 弹窗查看
            ├── Toolbox.tsx                  // 左侧节点工具箱（分类 + 点击创建节点）
            ├── NodeRegistry.tsx             // 注册所有节点类型 → NodeComponent / Icon / Category
            ├── PortTypes.ts                 // 端口类型系统 + 兼容性矩阵
            ├── WorkflowContext.tsx           // React Context：提供 workflowId + onNodeUpdate 回调
            ├── NodeEventBus.ts              // [已废弃] 节点事件总线，保留兼容
            ├── types.ts                     // 全局类型定义
            │
            ├── services/
            │   └── FlowApi.ts               // 封装所有后端 API 调用（REST + Socket.IO）
            │
            ├── runtime/
            │   ├── ExecutorManager.ts        // 根据 node.type 获取对应执行器（前端侧，已弃用独立调度）
            │   └── ...                       // 其他运行时辅助文件
            │
            └── nodes/
                ├── BaseNode.tsx              // 通用节点基座组件（三段式布局 + 端口 Handle + 必填校验 + runNodeWS）
                ├── ValueNode.tsx             // 基础值节点基座（String/Bool/Number 共用 + runNodeWS）
                ├── FlowingEdge.tsx           // 自定义边组件（三种视觉状态）
                ├── NodeDetailModal.tsx       // 节点详情弹窗（参数编辑 + 运行 + 输出渲染 + runNodeWS）
                │
                ├── P4File/
                │   ├── index.tsx             // P4File 节点（数据源，基于 BaseNode）
                │   ├── executor.ts           // 前端执行器代理
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
                │   ├── index.tsx             // JSON 节点（自定义组件，双输入端口 + runNodeWS）
                │   ├── JsonRenderer.tsx        // 自定义 JSON 树渲染器
                │   └── executor.ts
                │
                ├── Prompt/
                │   ├── index.tsx
                │   └── executor.ts
                │
                ├── String/
                │   ├── index.tsx             // 基于 ValueNode
                │   └── executor.ts
                │
                ├── Bool/
                │   ├── index.tsx             // 基于 ValueNode
                │   └── executor.ts
                │
                └── Number/
                    ├── index.tsx             // 基于 ValueNode
                    └── executor.ts
```

### 2.2 后端

```
server/
├── routers/
│   └── WorkFlow.py                         // HTTP REST 路由 + Socket.IO 事件处理
│
├── Implement/
│   └── workflowImpl/
│       ├── __init__.py
│       ├── workflowImp.py                   // 工作流 CRUD 实现 + DAG 运行时（支持子图执行）
│       ├── nodeExecutor.py                  // 节点执行器基类 + 分发
│       ├── p4FileExecutor.py                // P4File 节点执行（p4Utils 下载 + 文件类型检测）
│       ├── excelExecutor.py                 // Excel 节点执行（接收上游 fileContent / localPath）
│       ├── luaExecutor.py                   // Lua 节点执行（接收上游 fileContent）
│       ├── jsonExecutor.py                  // JSON 节点执行（接收上游 fileContent + jsonPath 过滤）
│       ├── promptExecutor.py                // Prompt 节点执行（调用 LLM API）
│       ├── stringExecutor.py               // String 节点执行（输出字符串值）
│       ├── boolExecutor.py                  // Bool 节点执行（输出布尔值）
│       └── numberExecutor.py               // Number 节点执行（输出数值）
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
| input | jsonPath | JSON Path | json-path |
| output | jsonData | JSON 数据 | json-data |

**执行流程:**

```
1. 从 input_data 获取 fileContent
2. jsonPath 来源：config.jsonPath（手动输入）或 input_data.jsonPath（连线从 String 接收）
   连线优先，两者同时存在时使用连线值
3. json.loads 解析
4. 如指定 jsonPath → 按 dot notation 过滤
5. 如未指定 jsonPath → 返回完整解析数据
```

**输出:** `{ jsonData: any }`

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

### 3.7 String 节点（基础值）

**设计原则：** String 是基础值节点，支持手动输入或通过连线接收上游输入。使用通用 `ValueNode` 组件。

**Schema:**

```typescript
interface StringConfig {
  value: string;   // 字符串值（手动输入或连线接收）
}
```

**端口定义:**

| 方向 | key | label | type |
|------|-----|-------|------|
| input | valueIn | 输入值 | string |
| output | value | 字符串 | string |

**执行流程:**

```
1. 如有连线输入 → 使用 input_data.valueIn
2. 否则 → 使用 config.value
3. 返回 { value: String(rawValue) }
```

**输出:** `{ value: string }`

### 3.8 Bool 节点（基础值）

**端口定义:**

| 方向 | key | label | type |
|------|-----|-------|------|
| input | valueIn | 输入值 | boolean |
| output | value | 布尔值 | boolean |

**输出:** `{ value: boolean }`

### 3.9 Number 节点（基础值）

**端口定义:**

| 方向 | key | label | type |
|------|-----|-------|------|
| input | valueIn | 输入值 | number |
| output | value | 数值 | number |

**输出:** `{ value: number }`

### 3.10 ValueNode 通用基础值组件

String / Bool / Number 三类节点共用 `ValueNode` 组件，支持两种输入模式（互斥）：

1. **手动输入**：在节点上直接输入值
2. **连线输入**：通过 `valueIn` 输入端口从上游节点获取

```typescript
interface ValueNodeProps {
  id: string;
  data: Record<string, unknown>;
  selected: boolean;
  icon: string;           // emoji 图标
  label: string;          // 显示名
  nodeType: string;       // 'string' | 'bool' | 'number'
  valueKey: string;       // 存放值的 data key，通常为 'value'
  portColor: string;      // 输出端口颜色
  inputType: 'text' | 'number' | 'boolean';  // 输入控件类型
  outputPortKey?: string; // 输出端口 key
  outputPortLabel?: string;
  inputPortKey?: string;  // 输入端口 key
  inputPortLabel?: string;
}
```

**连线覆盖行为：** 当有连线输入时，手动输入框被禁用并显示「🔗 由连线提供」提示；如手动已有值且连线接入，短暂显示覆盖警告。

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
  'file-path':    ['file-path', 'any'],
  'table-data':   ['table-data', 'any'],
  'json-data':    ['json-data', 'any'],
  'text':         ['text', 'any', 'string'],    // text 兼容 string
  'any':          ['file-content', 'file-path', 'table-data', 'json-data', 'text', 'any', 'boolean', 'string', 'number', 'json-path'],
  'boolean':      ['boolean', 'any'],
  'string':       ['string', 'any', 'text'],    // string 兼容 text
  'number':       ['number', 'any'],
  'json-path':    ['json-path', 'string', 'any'], // json-path 兼容 string（String→JSON Path 连线）
};
```

### 4.3 各节点端口定义

| 节点 | Input Ports | Output Ports |
|------|-------------|-------------|
| P4File | — | fileContent (file-content) |
| Excel | fileContent (file-content) | tableData (table-data) |
| JSON | fileContent (file-content), jsonPath (json-path) | jsonData (json-data) |
| Lua | fileContent (file-content) | textOutput (text) |
| Prompt | context (any) | result (text) |
| String | valueIn (string) | value (string) |
| Bool | valueIn (boolean) | value (boolean) |
| Number | valueIn (number) | value (number) |

### 4.4 端口颜色

| type | 颜色 | Hex |
|------|------|-----|
| file-content | 蓝色 | #1890ff |
| file-path | 紫色 | #722ed1 |
| any | 灰色 | #8c8c8c |
| text | 橙色 | #fa8c16 |
| table-data | 绿色 | #52c41a |
| json-data | 青色 | #13c2c2 |
| boolean | 粉色 | #eb2f96 |
| string | 橙色 | #fa8c16 |
| number | 青色 | #13c2c2 |
| json-path | 紫色 | #722ed1 |

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
上游节点执行成功 → onNodeUpdate(status='success')
         → setEdges: activated: true（边变绿+流动）
         ↓
边缘视觉变化 → matched_idle (灰) → activated (绿+流动+✓)
         ↓
后端子图执行 → 自动级联执行下游节点
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
- **放大查看按钮**：运行按钮左侧的 `ExpandOutlined` 按钮，点击打开 NodeDetailModal 大窗体

### 6.3 NodeDetailModal（节点详情弹窗）

点击节点 Header 的放大按钮，打开一个较大的 Modal 窗体（80vw × 80vh），集中查看和编辑节点所有信息：

```
┌──────────────────────────────────────────────────┐
│ 📁 P4File                              [运行 ▶]  │
├──────────────────────────────────────────────────┤
│ ● 运行状态: ✅ 运行成功                            │
├──────────────────────────────────────────────────┤
│ ▼ 输入内容                                        │
│   ● 文件内容 [已接收]                              │
│   来自 p4file_xxx → fileContent                   │
│   ┌──────────────────────────────────────┐        │
│   │  (上游数据预览，可折叠)                │        │
│   └──────────────────────────────────────┘        │
├──────────────────────────────────────────────────┤
│ 参数                                              │
│   P4 路径: [__________________]  *必填             │
│   ...                                             │
├──────────────────────────────────────────────────┤
│ 输出内容                                          │
│   ┌──────────────────────────────────────┐        │
│   │  (渲染器结果 / JSON树 / 表格 / 高亮)   │        │
│   │  尽量不用滚动条，充分利用大窗体空间      │        │
│   └──────────────────────────────────────┘        │
│                              [复制] [关闭]         │
└──────────────────────────────────────────────────┘
```

**设计要点：**

| 功能 | 说明 |
|------|------|
| **状态显示** | 顶部显示节点运行状态（idle/running/success/error），红/绿色标识 |
| **输入内容** | 按端口显示上游数据，可折叠，含端口类型彩色圆点 + 来源信息 + 数据预览 |
| **参数编辑** | 所有字段可编辑，修改后实时同步到 `node.data`（通过 `setNodes`） |
| **运行按钮** | 弹窗内运行按钮，点击后即时显示结果，同步状态到图中节点 |
| **结果渲染** | 复用 BaseNode 的渲染器（Excel Table / JSON Tree / Lua 高亮） |
| **无滚动** | 窗体足够大（80vw × 80vh），内容区域尽量不出现滚动条 |
| **复制** | footer 复制按钮，复制输出内容 |

### 6.4 NodeField 接口

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
| JSON | 📋 | 渲染器 | jsonPath(text, linkedPortKey='jsonPath') |
| Lua | 🌙 | 渲染器 | entryFunction(text) |
| Prompt | 🤖 | AI | prompt(textarea, **required**), model(text), temperature(number,0.1) |
| String | 📝 | 基础值 | value(text, **required**) — 使用 ValueNode |
| Bool | 🔘 | 基础值 | value(boolean, **required**) — 使用 ValueNode |
| Number | 🔢 | 基础值 | value(number, **required**) — 使用 ValueNode |

### 6.5 节点类型注册

```tsx
// NodeRegistry.tsx
export const nodeTypes: NodeTypes = {
  p4file: P4FileNode,
  excel: ExcelNode,
  lua: LuaNode,
  json: JsonNode,
  prompt: PromptNode,
  string: StringNode,
  bool: BoolNode,
  number: NumberNode,
};

export const nodeRegistryList: NodeRegistryEntry[] = [
  { type: 'p4file', label: 'P4 文件', icon: <P4FileIcon />, category: '数据源' },
  { type: 'excel', label: 'Excel', icon: <ExcelIcon />, category: '渲染器' },
  { type: 'json', label: 'JSON', icon: <JsonIcon />, category: '渲染器' },
  { type: 'lua', label: 'Lua', icon: <LuaIcon />, category: '渲染器' },
  { type: 'prompt', label: 'Prompt', icon: <PromptIcon />, category: 'AI' },
  { type: 'string', label: 'String', icon: <StringIcon />, category: '基础值' },
  { type: 'bool', label: 'Bool', icon: <BoolIcon />, category: '基础值' },
  { type: 'number', label: 'Number', icon: <NumberIcon />, category: '基础值' },
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

## 七、执行模式

### 7.1 统一执行模型（WebSocket）

**设计原则：** 所有节点执行入口统一使用 `FlowApi.runNodeWS()` 通过 Socket.IO WebSocket 与后端通信，后端执行子图并实时推送状态更新。不再使用 HTTP REST 的 `FlowApi.runNode()` 进行节点级联。

| 执行入口 | 组件 | 调用方式 | 说明 |
|----------|------|----------|------|
| 节点 Header ▶ 按钮 | `BaseNode.handleRun` | `FlowApi.runNodeWS()` | P4/Excel/Lua/Prompt 等节点 |
| 节点 Header ▶ 按钮 | `ValueNode.handleRun` | `FlowApi.runNodeWS()` | String/Bool/Number 节点 |
| JSON 节点 ▶ 按钮 | `JsonNode.handleRun` | `FlowApi.runNodeWS()` | JSON 节点（自定义组件） |
| 详情弹窗运行 | `NodeDetailModal.handleRun` | `FlowApi.runNodeWS()` | 所有节点通用 |
| 侧边栏运行 | `PropertyPanel.handleRunNode` | `FlowApi.runNodeWS()` | 所有节点通用 |
| 工具栏整图运行 | `Toolbar → FlowEditor.handleRun` | `FlowApi.runWorkflowWS()` | 整图 DAG 运行 |

**关键区别：** `runNodeWS` 和 `runWorkflowWS` 共用同一套后端 `WorkflowRuntime.run()`，唯一区别是：
- `runWorkflowWS`：`start_node_id` 为空，执行整图所有节点
- `runNodeWS`：指定 `start_node_id`，执行该节点及其所有下游节点（子图）

### 7.2 单节点子图执行（runNodeWS）

**触发路径：**

```
1. 用户点击节点 Header ▶ → BaseNode/ValueNode/JsonNode.handleRun()
2. 前端立即将本节点标记为 running（视觉反馈）
3. 构造 nodeDataOverrides：
   a. 当前节点：{ fieldKey: value } — 最新字段值（可能未保存）
   b. 其他节点：{ nodeId: _runOutput } — 上游节点的缓存输出
4. FlowApi.runNodeWS(workflowId, startNodeId, nodeDataOverrides, onNodeUpdate, onDone)
   a. socket.emit('workflow:run_from_node', { workflowId, startNodeId, nodeDataOverrides })
5. 后端收到 'workflow:run_from_node' 事件：
   a. 加载完整工作流 JSON（nodes + edges）
   b. BFS 从 startNodeId 出发找到所有下游节点（子图）
   c. 拓扑排序确定执行顺序
   d. 上游节点（不在子图中）不执行，使用 nodeDataOverrides 中的缓存输出
   e. 按拓扑序并发执行子图中的节点
6. 每个节点完成 → emit('workflow:node_update', { taskId, nodeId, status, output })
   - 前端收到 → onNodeUpdate(nodeId, status, output)
   - 更新节点 _runStatus / _runOutput
   - 节点 success → 标记出边 activated: true（边变绿+流动）
7. 全部子图节点完成 → emit('workflow:done', { taskId, status, error })
```

**nodeDataOverrides 结构：**

```typescript
// 节点执行时传递给后端的数据覆盖
const nodeDataOverrides: Record<string, any> = {};

// 1. 当前节点的最新字段值
nodeDataOverrides[startNodeId] = { p4Path: '//C7/...', value: 'hello' };

// 2. 其他节点的缓存输出（上游节点不重新执行，后端用这些做端口映射）
for (const n of allNodes) {
  if (n.id !== startNodeId) {
    const runOutput = n.data._runOutput;
    if (runOutput && !runOutput.error) {
      nodeDataOverrides[n.id] = runOutput;
    }
  }
}
```

### 7.3 整图运行（runWorkflowWS）

与 7.2 共用后端 `WorkflowRuntime.run()`，区别是 `start_node_id` 为空，执行所有节点。

**设计原则：**

- 上游数据完全在后端 context 中流转，**不经前端中转**，避免大文件二次传输
- 后端并发调度所有节点（`asyncio.gather`），根节点立即执行，共享节点等待所有前驱完成
- 前端通过 **Socket.IO WebSocket 长连接**实时接收节点状态推送，无轮询延迟

**触发路径：**

```
1. Toolbar「运行」按钮 → handleRun(json, workflowId)
2. 前端重置所有节点状态为 idle、所有边 activated=false
3. FlowApi.runWorkflowWS(workflowId, onNodeUpdate, onDone)
   a. socket.emit('workflow:run', { workflowId })
4. 后端收到 'workflow:run' 事件：
   a. 生成 task_id，客户端 sid 自动加入 room(task_id)
   b. emit('workflow:started', { taskId }) 回客户端
   c. socketio.start_background_task → asyncio 执行 WorkflowRuntime.run
5. 节点状态变化 → emit('workflow:node_update', { taskId, nodeId, status, output }) 推送到 room
   - 前端收到 → onNodeUpdate(nodeId, status, output)
   - 更新节点 _runStatus / _runOutput
   - 节点 success → 标记出边 activated: true（边变绿+流动）
6. 所有节点完成 → emit('workflow:done', { taskId, status, error })
   - 前端收到 → onDone(status, error) → setRunCancelFn(null)
```

### 7.4 handleNodeUpdate — 统一节点状态回调

**所有执行入口**的节点状态更新都通过 `FlowEditor.handleNodeUpdate` 回调处理：

```typescript
const handleNodeUpdate = useCallback(
  (nodeId: string, nodeStatus: string, output: any) => {
    const frontendStatus = statusMap[nodeStatus] ?? nodeStatus;
    // 1. 更新节点运行状态和输出
    setNodes((nds) =>
      nds.map((n) =>
        n.id === nodeId
          ? { ...n, data: { ...n.data, _runStatus: frontendStatus, _runOutput: output } }
          : n,
      ),
    );
    // 2. 节点成功 → 激活所有出边（matched 边变绿+流动）
    if (nodeStatus === 'success') {
      setEdges((eds) =>
        eds.map((e) =>
          e.source === nodeId && e.data?.matchStatus === 'matched'
            ? { ...e, data: { ...e.data, activated: true } }
            : e,
        ),
      );
    }
  },
  [setNodes, setEdges],
);
```

此回调通过 `WorkflowContext` 传递给所有节点组件：

```typescript
// WorkflowContext.tsx
export const WorkflowContext = React.createContext<{
  workflowId?: string;
  onNodeUpdate: (nodeId: string, status: string, output: any) => void;
}>({ workflowId: undefined, onNodeUpdate: () => {} });

// FlowEditor.tsx
<WorkflowContext.Provider value={{ workflowId, onNodeUpdate: handleNodeUpdate }}>
```

**Socket.IO 事件协议：**

| 方向 | 事件名 | payload |
|------|--------|---------|
| Client → Server | `workflow:run` | `{ workflowId }` |
| Client → Server | `workflow:run_from_node` | `{ workflowId, startNodeId, nodeDataOverrides }` |
| Server → Client | `workflow:started` | `{ taskId }` |
| Server → Client | `workflow:node_update` | `{ taskId, nodeId, status, output }` |
| Server → Client | `workflow:done` | `{ taskId, status, error }` |
| Server → Client | `workflow:error` | `{ error }` |
| Client → Server | `workflow:cancel` | `{ taskId }` |

**status 枚举映射：**

| 后端 status | 前端 _runStatus |
|------------|----------------|
| `idle` | `idle` |
| `processing` | `running` |
| `success` | `success` |
| `error` | `error` |

**FlowApi.runWorkflowWS 接口：**

```typescript
// 整图运行 — 返回 cancelFn
const cancelFn = FlowApi.runWorkflowWS(
  workflowId,
  (nodeId, status, output) => { /* onNodeUpdate — 更新节点状态 */ },
  (status, error) => { /* 运行结束回调 */ },
);
// 停止时：cancelFn()
```

**FlowApi.runNodeWS 接口：**

```typescript
// 子图执行 — 从指定节点开始，执行该节点及所有下游
const cancelFn = FlowApi.runNodeWS(
  workflowId,           // 已保存的工作流 ID
  startNodeId,          // 起始节点 ID
  nodeDataOverrides,    // { nodeId: fieldConfig | runOutput }
  onNodeUpdate,         // (nodeId, status, output) => void
  onDone,               // (status, error) => void
);
// 取消时：cancelFn()
```

**停止运行：**

Toolbar「停止」按钮调用 `runCancelFn()`，前端立即清除监听器并向服务端发送 `workflow:cancel` 事件。服务端将任务状态标记为 `canceled` 并推送 `workflow:done`。

### 7.5 NodeEventBus（已弃用）

> **注意：** NodeEventBus 已不再使用。早期设计中单节点级联通过前端 NodeEventBus 通信，
> 现已统一为后端子图执行模式（`runNodeWS`），级联由后端 WorkflowRuntime 自动处理。
> 文件保留仅为兼容，无活跃消费者。

```typescript
// NodeEventBus.ts — 已弃用，保留兼容
export const NodeEventBus = {
  subscribe(fn: (nodeId: string, output: any) => void): () => void;
  emit(nodeId: string, output: any): void;
};
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
| POST | `/api/workflow/node/run` | 运行单个节点（同步，节点 ▶ 按钮） | `{ type, config, input }` | `{ output }` |
| GET | `/api/workflow/run/<taskId>/status` | 查询任务状态（REST 调试用） | - | `{ status, nodes, result }` |
| GET | `/api/workflow/executors` | 列出注册的执行器 | - | `{ executors: [{ type, class }] }` |

### 10.4 Socket.IO 事件协议（整图运行 + 子图执行）

| 方向 | 事件名 | payload | 说明 |
|------|--------|---------|------|
| C→S | `workflow:run` | `{ workflowId }` | 触发整图运行，客户端自动加入 task room |
| C→S | `workflow:run_from_node` | `{ workflowId, startNodeId, nodeDataOverrides }` | 触发子图执行：从 startNodeId 开始执行该节点及所有下游节点 |
| S→C | `workflow:started` | `{ taskId }` | 任务已创建，taskId 用于标识本次运行 |
| S→C | `workflow:node_update` | `{ taskId, nodeId, status, output }` | 节点状态变化（processing/success/error） |
| S→C | `workflow:done` | `{ taskId, status, error }` | 所有节点执行完毕 |
| S→C | `workflow:error` | `{ error }` | 运行前校验失败（如 workflowId 不存在） |
| C→S | `workflow:cancel` | `{ taskId }` | 取消运行（停止推送，标记任务为 canceled） |
| C→S | `workflow:join` | `{ taskId }` | 手动加入 task room（断线重连时使用） |
| C→S | `workflow:leave` | `{ taskId }` | 离开 task room |

**`workflow:run_from_node` 详解：**

```typescript
// 前端调用
FlowApi.runNodeWS(
  workflowId,          // 已保存的工作流 ID
  startNodeId,         // 起始节点 ID
  nodeDataOverrides,   // { nodeId: fieldConfig | runOutput }
  onNodeUpdate,        // 节点状态回调
  onDone,              // 完成回调
);

// 后端处理流程
1. 加载 workflow JSON（nodes + edges）
2. BFS 从 startNodeId 找到所有下游节点 → 子图节点集
3. 拓扑排序子图节点 → exec_nodes
4. 不在子图中的上游节点：不执行，用 nodeDataOverrides 填充 context
5. 按拓扑序并发执行子图节点（与整图运行共用 WorkflowRuntime.run）
6. 每个节点完成 → emit node_update
7. 全部完成 → emit done
```

**连接配置：**

```typescript
// 开发环境：通过 UMI proxy 代理 /socket.io/ 到 localhost:16666
// 生产/Docker：直连 window.FLASK_BACKEND_URL
const socket = io(socketUrl, {
  transports: ['websocket', 'polling'],
  path: '/socket.io/',
});
```

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

**执行策略：**

| 场景 | 触发事件 | 行为 |
|------|----------|------|
| **整图 run** | `workflow:run` | 在后台线程+独立 event loop 中异步执行整个 DAG，所有节点并发调度 |
| **子图 run** | `workflow:run_from_node` | BFS 找出 startNodeId 的所有下游节点，只执行子图。上游节点不执行，用 nodeDataOverrides 填充 context |
| **单节点 run** | `POST /api/workflow/node/run` | 只执行当前节点本身，不触发下游，无工作流上下文。**仅用于无 workflowId 的调试场景** |

**子图执行流程（run_from_node）：**

```
1. 加载完整 workflow JSON（nodes + edges）
2. BFS 从 startNodeId 出发，沿 adj 找到所有可达下游节点 → subgraph_nodes
3. 按全图拓扑排序，筛选出子图节点 → exec_nodes
4. 预填充 context：将 nodeDataOverrides 中非子图节点的数据写入 context
   （上游节点不重新执行，其输出从前端缓存传入）
5. 将不在子图中的节点的 node_done Event 设为已 set（不等待它们）
6. 按拓扑序并发执行子图中的节点（与整图运行共用 execute_node 逻辑）
   - 端口映射时，上游数据从 context 中读取（包括预填充的上游输出）
7. 每个节点完成 → emit node_update
8. 全部完成 → emit done
```

**整图/子图 run 共用的并发调度流程：**

```
1. 构建邻接表（adj）、前驱表（predecessors）、按目标索引的边表（edges_by_target）
2. 拓扑排序做环检测（Kahn 算法），有环则报错退出
3. 为每个节点创建 asyncio.Event（node_done[nid]）
4. 一次性 asyncio.gather 所有节点 coroutine（并发调度）
   - 根节点（无前驱）：立即开始执行
   - 下游节点：await asyncio.gather(*[node_done[p].wait() for p in preds]) 等待所有前驱完成
   - 公共节点（多个前驱）：等待所有上游的 Event 都 set 后才开始，保证只执行一次
5. 节点执行完毕 → 输出写入 context（asyncio.Lock 保护） → node_done[nid].set()
6. 上游若有 error → 下游跳过执行，状态标为 error
7. 全部完成 → 更新 task status 为 success / error
```

**公共节点（多前驱）示意：**

```
  RootA ─────┐
              ├──▶ SharedNode ──▶ LeafNode
  RootB ─────┘

SharedNode 会等待 RootA 和 RootB 都完成（两个 Event 都 set）后才开始执行
```

**代码结构：**

```python
class WorkflowRuntime:
    _tasks: dict = {}

    @classmethod
    async def run(cls, workflow_json, task_id,
                 start_node_id: str = None,
                 node_data_overrides: dict = None):
        # 1. 构建 adj / predecessors / edges_by_target
        # 2. 拓扑排序环检测
        # 3. 确定执行节点集（整图 or 子图 BFS）
        if start_node_id:
            # BFS from start_node_id → subgraph_nodes
            exec_nodes = [nid for nid in topo_order if nid in subgraph_nodes]
        else:
            exec_nodes = list(topo_order)

        # 4. 预填充 context（node_data_overrides 中的上游输出）
        context: dict = {}
        if node_data_overrides:
            for nid, override_data in node_data_overrides.items():
                if nid not in exec_nodes:
                    context[nid] = override_data  # 上游节点不执行，用前端缓存

        # 5. 不在执行集中的节点的 Event 预设为 set
        for nid in node_map:
            if nid not in exec_set:
                node_done[nid].set()

        # 6. 初始化 task 状态
        context_lock = asyncio.Lock()
        node_done: dict[str, asyncio.Event] = {nid: asyncio.Event() for nid in node_map}

        async def execute_node(nid: str):
            # 等待所有前驱完成
            await asyncio.gather(*[node_done[p].wait() for p in predecessors[nid]])
            # 检查上游是否有 error，有则跳过
            # 从 context 收集 input_data（按端口映射）
            # 合并 node_data_overrides 中的字段覆盖
            # 执行节点
            output = ExecutorManager.run_node(node_type, node_data, input_data)
            async with context_lock:
                context[nid] = output
            node_done[nid].set()  # 通知下游可以继续

        # 并发启动子图/整图中的所有节点
        await asyncio.gather(*[execute_node(nid) for nid in exec_nodes])

    @classmethod
    def get_task_status(cls, task_id): ...

    @classmethod
    def cancel_task(cls, task_id): ...
```

### 12.2 日志规范

后端各模块均使用 Python 标准 `logging` 模块（`logging.getLogger(__name__)`），日志格式：

```
[模块名.方法名] <关键字段>=<值>, ...
```

| 级别 | 场景 |
|------|------|
| `INFO` | API 请求入口、出口（成功）、任务启动/完成 |
| `WARNING` | 参数缺失、资源未找到、执行器返回 error 字段、上游节点失败导致跳过 |
| `DEBUG` | 状态查询（高频轮询接口）、节点 Event set 等细粒度事件 |
| `ERROR` / `EXCEPTION` | 未预期异常（含完整 traceback）|

---

## 十三、整体数据流架构

```
┌──────────────────────────────────────────────────┐
│              React + React Flow                   │
│                                                   │
│  ReactFlowProvider                                │
│       ├── ReactFlow (Canvas)                     │
│       │     ├── nodeTypes: 8 种节点               │
│       │     │   (P4File/Excel/Lua/JSON/Prompt     │
│       │     │    String/Bool/Number)               │
│       │     ├── edgeTypes: FlowingEdge            │
│       │     ├── Background / Controls / MiniMap    │
│       │     └── onConnect: 端口类型匹配 → 边 data  │
│       ├── Toolbox (分类: 数据源/渲染器/AI/基础值)   │
│       ├── BaseNode (三段式布局 + runNodeWS)        │
│       ├── ValueNode (基础值节点 + runNodeWS)        │
│       ├── JsonNode (双输入端口 + runNodeWS)        │
│       ├── PropertyPanel (五段式 + runNodeWS)        │
│       ├── NodeDetailModal (弹窗运行 + runNodeWS)    │
│       ├── Toolbar (整图运行: runWorkflowWS)         │
│       └── FlowEditor (handleNodeUpdate → 更新状态/激活边)│
│                                                   │
│  WorkflowContext:                                 │
│    workflowId + onNodeUpdate → 所有组件共享          │
│                                                   │
│  运行模型:                                        │
│    单节点 ▶ → runNodeWS(startNodeId)               │
│            → 后端执行子图 → node_update 推送        │
│            → onNodeUpdate → 更新节点状态 + 激活边    │
│                                                   │
│    整图 ▶ → runWorkflowWS()                        │
│           → 后端执行全部节点 → node_update 推送      │
│           → onNodeUpdate → 更新节点状态 + 激活边     │
│                                                   │
└──────────┬────────────────────────────────────────┘
           │
     Socket.IO WebSocket (主) + HTTP REST (CRUD)
     UMI proxy / env-config.js auto-detect
           │
           ▼
┌──────────────────────────────────────────────────┐
│         Flask + gevent (Python)                  │
│                                                  │
│  routers/WorkFlow.py                             │
│       ├── CRUD: save / get / list / delete       │
│       ├── Socket: workflow:run (整图)             │
│       ├── Socket: workflow:run_from_node (子图)   │
│       └── REST: POST /api/workflow/node/run (单节点,无上下文) │
│                                                  │
│  Implement/workflowImpl/                         │
│       ├── ExecutorManager (8 个执行器注册)         │
│       ├── P4FileExecutor (数据源: p4 sync + 输出)  │
│       ├── ExcelExecutor (渲染器: 接收上游内容)       │
│       ├── JsonExecutor  (渲染器: 接收上游内容+jsonPath) │
│       ├── LuaExecutor   (渲染器: 接收上游内容)       │
│       ├── PromptExecutor (AI: LLM 调用)            │
│       ├── StringExecutor  (基础值: 输出字符串)       │
│       ├── BoolExecutor    (基础值: 输出布尔值)       │
│       └── NumberExecutor  (基础值: 输出数值)       │
│                                                  │
│  WorkflowRuntime.run(workflow_json, task_id,      │
│                      start_node_id=None,          │
│                      node_data_overrides=None)     │
│       ├── 整图: 执行全部节点                        │
│       └── 子图: BFS下游 + 预填充上游context        │
│                                                  │
└──────────────────────────────────────────────────┘
```

---

## 十四、依赖清单

### 14.1 前端 npm 依赖

| 包名 | 版本 | 说明 |
|------|------|------|
| `reactflow` | ^11.11.0 | React Flow 画布编辑器 |
| `socket.io-client` | ^4.x | Socket.IO 客户端，WebSocket 长连接 |
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

### Phase 5.5: NodeDetailModal ✅（已完成）
1. ~~节点 Header 添加放大按钮（ExpandOutlined，运行按钮左侧）~~ ✅
2. ~~NodeDetailModal 大窗体（80vw × 80vh）~~ ✅
3. ~~运行状态显示（顶部状态栏 + 红/绿色标识）~~ ✅
4. ~~输入内容（可折叠 Section，端口类型彩色圆点 + 来源 + 数据预览）~~ ✅
5. ~~参数编辑（grid 布局，修改实时同步到 node.data）~~ ✅
6. ~~运行按钮（弹窗内运行，即时显示结果，同步状态到图中节点）~~ ✅
7. ~~输出渲染（复用 Excel/JSON/Lua 渲染器）~~ ✅
8. ~~端口信息（底部可折叠 Section）~~ ✅

### Phase 6: 整体运行 ✅（已完成）
1. ~~实现后端 WorkflowRuntime 并发调度：asyncio.gather + asyncio.Event 等待前驱~~ ✅
2. ~~公共节点等待所有上游前驱完成后再执行~~ ✅
3. ~~上游 error 自动跳过下游节点~~ ✅
4. ~~端口映射（targetHandle/sourceHandle）~~ ✅
5. ~~flask-socketio 初始化（gevent 模式），app.py 改用 socketio.run~~ ✅
6. ~~WorkflowRuntime 节点状态变化时通过 socketio.emit 推送到 room(task_id)~~ ✅
7. ~~WorkFlow.py Socket.IO 事件处理（workflow:run / workflow:cancel）~~ ✅
8. ~~前端 FlowApi.runWorkflowWS：Socket.IO 连接管理 + 事件监听 + cancelFn~~ ✅
9. ~~FlowEditor.handleRun：WebSocket 整图 run + 实时节点状态更新 + 边激活~~ ✅
10. ~~Toolbar 运行/停止按钮接入 WebSocket run / cancelFn~~ ✅

### Phase 7: 基础值节点 ✅（已完成）
1. ~~实现 ValueNode 通用组件（手动输入 + 连线输入双模式）~~ ✅
2. ~~实现 String / Bool / Number 节点（基于 ValueNode）~~ ✅
3. ~~后端实现 StringExecutor / BoolExecutor / NumberExecutor~~ ✅
4. ~~添加 string / boolean / number / json-path 端口类型~~ ✅
5. ~~端口兼容性矩阵更新（string↔text, json-path↔string 等）~~ ✅
6. ~~JSON 节点添加 jsonPath 输入端口（连线从 String 接收 JSON Path）~~ ✅

### Phase 8: 统一执行模型 ✅（已完成）
1. ~~所有节点执行入口统一为 FlowApi.runNodeWS()（WebSocket 子图执行）~~ ✅
2. ~~BaseNode.handleRun 改用 runNodeWS~~ ✅
3. ~~ValueNode.handleRun 从 FlowApi.runNode() 改为 runNodeWS~~ ✅
4. ~~NodeDetailModal.handleRun 从 FlowApi.runNode() 改为 runNodeWS~~ ✅
5. ~~PropertyPanel.handleRunNode 已使用 runNodeWS~~ ✅
6. ~~WorkflowContext 提供 workflowId + onNodeUpdate 回调~~ ✅
7. ~~后端实现 workflow:run_from_node 事件处理（BFS 子图 + 预填充上游 context）~~ ✅
8. ~~节点成功 → onNodeUpdate → 出边 activated:true（边变绿+流动）~~ ✅
9. ~~后端 CORS 允许 DELETE 方法（修复工作流删除失败）~~ ✅
10. ~~路由 name 使用英文 key 匹配 locale 翻译（修复 React Intl missing message）~~ ✅

### Phase 9: 增强（待实现）
1. 节点拖拽排序（React Flow dnd 支持）
2. 运行历史记录
3. 错误处理与重试
4. Undo / Redo 支持
