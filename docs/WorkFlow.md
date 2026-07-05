做一个画板的相关功能，其中画板需要支持几类节点，分别是：
1. Excel展示节点
2. lua文件展示
3. json文件展示
4. 自己写的提示词
这几个节点希望走单独的文件，存入client/src/views/flow/下
其中，节点本身的功能：
1. 需要能支持输入参数，也就是节点本身的配置
比如1-3节点都支持p4路径的填写
2. 节点还需要支持运行，比如p4路径点击运行后就是获取文件
3. 节点之间需要支持连线，前一个节点的输出内容作为下一个节点的输入
4. 整个Canvas要有一个运行，支持让所有源节点一致运行到最终节点

我建议采用下面这种目录，比后期维护容易很多：

client/
└── src/
    ├── pages/
    │   └── Workflow/
    │       └── index.tsx              // 页面入口
    │
    ├── components/
    │   └── workflow/
    │       ├── FlowEditor.tsx
    │       ├── Toolbar.tsx
    │       ├── PropertyPanel.tsx
    │       ├── Toolbox.tsx
    │       ├── NodeRegistry.ts
    │       ├── Runtime.ts
    │       ├── types.ts
    │       ├── services/
    │       │      FlowApi.ts
    │       │
    │       └── nodes/
    │              Excel/
    │              Lua/
    │              Json/
    │              Prompt/

这样 pages 只负责页面，所有 Workflow 逻辑都在 components/workflow。

根据你的需求，我会把整个系统拆成下面几个模块
Workflow

├── UI(Editor)
│
├── Node Registry
│
├── Runtime
│
├── Node Executor
│
└── Backend API

实际上 Runtime 才是最核心的。

我建议的 Spec
一、目录结构
src/

pages/

    Workflow/

        index.tsx                // 页面

components/

    workflow/

        FlowEditor.tsx           // FlowGram 初始化

        PropertyPanel.tsx        // 节点属性

        Toolbox.tsx              // 左侧节点

        Toolbar.tsx              // 保存/运行

        NodeRegistry.ts          // 注册节点

        Runtime.ts               // 整体运行器

        GraphParser.ts           // DAG解析

        types.ts                 // 所有类型

        services/

            FlowApi.ts

        nodes/

            Excel/

                index.tsx

                executor.ts

                schema.ts

                icon.tsx

            Lua/

            Json/

            Prompt/
            

二、每个节点目录

例如 Excel：

Excel/

    index.tsx

    schema.ts

    executor.ts

    icon.tsx
index.tsx

负责：

UI

例如：

Excel

📄 excel.xlsx
schema.ts

负责：

节点配置

例如：

export interface ExcelConfig{

    p4Path:string;

    sheet:string;

}

FlowGram PropertyPanel 就读取这里。

executor.ts

负责：

真正执行。

例如：

读取P4

↓

下载文件

↓

解析Excel

↓

输出JSON

以后 Runtime：

Executor.run(node)

调用这里。

icon.tsx

就是：

左边 Toolbox 的图标。

三、PropertyPanel

例如：

点击 Excel

右边：

P4 Path

[____________]

Sheet

[____________]

Run

Save

点击 Lua：

P4 Path

Entry Function

Run

点击 Prompt：

Prompt

xxxxxxxx

Temperature

0.7

PropertyPanel 不写 if else。

而是：

schema

↓

自动生成Form
四、Runtime

这是整个系统最重要。

我建议：

Runtime

↓

GraphParser

↓

Topological Sort

↓

Execute

↓

Collect Result

例如：

Excel

↓

Prompt

↓

Lua

↓

Json

Runtime：

Excel.run()

↓

Prompt.run(excel.output)

↓

Lua.run(prompt.output)

↓

Json.run(lua.output)
五、每个节点统一接口

例如：

export interface WorkflowNodeExecutor{

    run(input:any,config:any):Promise<any>;

}

Excel：

class ExcelExecutor

Lua：

class LuaExecutor

Prompt：

class PromptExecutor

Runtime 根本不用知道是什么节点。

统一：

executor.run()

即可。

六、FlowEditor

这里只负责：

Canvas

↓

保存JSON

↓

加载JSON

↓

Node Registry

不要写任何业务。

七、Toolbar

例如：

保存

运行

停止

导出

导入

Undo

Redo

其中：

点击运行：

Toolbar

↓

Runtime.run(flow)
八、NodeRegistry

这里只负责：

Excel

↓

ExcelNode

↓

ExcelExecutor

↓

ExcelSchema

例如：

Registry

↓

register

↓

Node Type

↓

Executor

↓

Schema

以后 Runtime：

registry.getExecutor(node.type)

即可。

九、后端API

建议：

POST

/api/workflow/save
GET

/api/workflow/{id}
POST

/api/node/run

运行单个节点。

POST

/api/workflow/run

运行整个流程。

以后：

Toolbar

↓

workflow/run

↓

Server

↓

Runtime

↓

返回结果
十、数据流

整个系统建议设计成下面这样：

FlowGram(Canvas)

        │

        ▼

Workflow JSON

        │

        ▼

Runtime

        │

Topological Sort

        │

        ▼

NodeExecutor

        │

Excel Executor
Lua Executor
Json Executor
Prompt Executor

        │

        ▼

Result

        │

        ▼

PropertyPanel / Output Panel
我还会增加两个目录（强烈推荐）

随着项目推进，你很快会发现仅有节点还不够，我建议一开始就预留：

components/workflow/
├── runtime/
│   ├── Runtime.ts          // 调度器
│   ├── GraphParser.ts      // DAG 解析
│   ├── ExecutorManager.ts  // 根据节点类型获取执行器
│   └── Context.ts          // 节点上下文（变量、输出缓存）
│
└── models/
    ├── Node.ts
    ├── Edge.ts
    ├── Workflow.ts
    └── ExecutionResult.ts

这样 UI（FlowGram） 与 执行引擎（Runtime） 完全解耦。以后即使你把 FlowGram 换成别的编辑器，只要输出相同的 Workflow JSON，Runtime 基本无需修改。这种分层对于长期维护和扩展（增加新节点类型、支持断点运行、并行执行等）会更加稳健。

              React + FlowGram
                      │
        ┌─────────────┴─────────────┐
        │                           │
     HTTP REST                 WebSocket
        │                           │
        │                    推送运行状态
        │                    推送节点输出
        │                    推送日志
        │                    推送LLM流式输出
        │
        ▼
               FastAPI
                    │
             Workflow Runtime
                    │
             Executor Manager
                    │
        Excel  Lua  Json  Prompt

这样职责很清晰：

HTTP（短连接）：负责所有 CRUD、保存流程、加载流程、触发运行等请求。
WebSocket（长连接）：负责运行时状态、节点进度、日志、流式输出等实时事件。

这是目前大多数工作流平台（包括 AI Workflow 产品）采用的模式，也是最容易扩展的架构。