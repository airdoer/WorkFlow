# 配置目录结构

## 1. P4 仓库结构

```
//C7/Development/Mainline/Server/config/
├── production/                          # 生产环境配置目录
│   ├── c7_partner.json                 # partner 环境配置
│   ├── c7_partner_service.json         # partner 服务配置
│   ├── c7_weekly.json                  # weekly 环境配置
│   ├── c7_weekly_service.json          # weekly 服务配置
│   ├── c7_online.json                  # 线上环境配置
│   ├── c7_daily.json                   # 日常环境配置
│   └── ...                             # 其他环境配置
├── local/                               # 本地/测试环境配置目录
│   ├── c7_dev_weekly.json              # 开发周版本配置
│   ├── c7_dev_weekly.generated.json    # 自动生成的合并配置
│   ├── c7_qa1.json                     # QA1 测试环境
│   ├── c7_qa1.generated.json           # QA1 生成配置
│   ├── c7_dev.json                     # 开发环境配置
│   └── ...                             # 其他测试环境配置
├── PayRsa/                              # 支付 RSA 密钥目录
│   ├── app_private_key_c7.pem
│   ├── app_public_key.pem
│   └── sdk_public_key.pem
├── conf_base.json                       # 基础配置（所有环境的根配置）
├── conf_linux.json                      # Linux 环境通用配置
├── conf_personal_base.json              # 个人环境基础配置
├── service_base.json                    # 服务基础配置
├── service_base_online.json             # 线上服务配置
├── rsa_prikey.pem                       # RSA 私钥
├── rsa_pubkey.pem                       # RSA 公钥
└── readme.md                            # 配置说明文档
```

## 2. 本地工作区映射

### 2.1 Windows 本地路径
```
E:\Project\C7_project\Server\config\
├── production\
├── local\
├── PayRsa\
└── *.json
```

### 2.2 路径映射关系
| P4 路径 | 本地路径 | 说明 |
|---------|----------|------|
| `//C7/Development/Mainline/Server/config/` | `E:\Project\C7_project\Server\config\` | 主干分支配置根目录 |
| `//C7/Development/Weekly/Server/config/` | 分支配置目录 | weekly 分支 |
| `//C7/Release/Preonline/Server/config/` | 分支配置目录 | preonline 预发布分支 |
| `//C7/Development/Mainline/Server/config/production/` | `E:\Project\C7_project\Server\config\production\` | 生产配置目录 |

## 3. 目录功能说明

### 3.1 production/ 目录
- **用途**: 存放生产环境和预生产环境的配置
- **特点**:
  - 配置较为完整和稳定
  - 包含真实的服务器集群配置
  - 通常包含多个进程实例（如 logic_1 到 logic_18）
- **命名规范**: `c7_<env_name>.json`

### 3.2 local/ 目录
- **用途**: 存放本地开发和测试环境的配置
- **特点**:
  - 配置相对简化
  - 适合单机或小规模集群
  - 通常继承 production 配置并覆盖部分字段
  - 包含 `.generated.json` 自动生成文件
- **命名规范**: `c7_<env_name>.json` 和 `c7_<env_name>.generated.json`

### 3.3 根目录配置文件
- **conf_base.json**: 所有环境的根配置，定义公共字段
- **conf_linux.json**: Linux 环境特定配置，继承自 `conf_base.json`
- **conf_personal_base.json**: 个人开发环境的基础配置
- **service_*.json**: 服务配置模板

## 4. 配置文件类型

### 4.1 环境配置文件
文件名格式: `c7_<env_name>.json`

**示例**:
- `c7_partner.json` - partner 环境
- `c7_weekly.json` - weekly 环境
- `c7_online.json` - 线上环境
- `c7_dev_weekly.json` - 开发周版本

**关键字段 - namespace**:
- `namespace` 是配置文件中最重要的唯一标识符
- 位于 `common` 配置块中，用于区分不同的环境
- **作用**:
  - 环境唯一标识：每个环境必须有唯一的 namespace
  - 新建配置的 Key：创建新环境时使用 namespace 作为唯一键
  - 运行时识别：服务器进程通过 namespace 识别当前运行环境
  - 日志标记：日志中使用 namespace 标识来源环境
- **命名规范**: 通常与配置文件名保持一致（去掉 `.json` 后缀）
  
**示例**:
```json
{
  "parent": "conf_linux.json",
  "common": {
    "namespace": "c7_partner",    // 环境唯一标识
    "logLevel": "info",
    "serverZoneId": 217
  }
}
```

**注意事项**:
- ⚠️ namespace 必须全局唯一，不能重复
- ⚠️ 一旦创建，不建议修改（会影响运行中的服务）
- ✅ 新建配置时，namespace 应与文件名一致
- ✅ 示例：文件 `c7_partner.json` 的 namespace 应为 `c7_partner`

### 4.2 生成配置文件
文件名格式: `c7_<env_name>.generated.json`

**特点**:
- 由配置工具自动生成
- 包含完整合并后的配置
- 不应手动修改
- 主要用于本地调试

### 4.3 服务配置文件
文件名格式: `c7_<env_name>_service.json`

**用途**:
- 定义服务启动参数
- 进程管理配置
- 资源限制配置

### 4.4 基础配置文件
文件名格式: `conf_*.json`

**用途**:
- 定义公共配置
- 作为其他配置的 parent
- 减少重复配置

## 5. 文件命名约定

### 5.1 环境名称前缀
- `c7_` - C7 项目通用前缀
- 后跟环境名称，使用下划线分隔

### 5.2 环境类型
| 前缀 | 说明 | 示例 |
|------|------|------|
| `online` | 线上生产环境 | `c7_online.json` |
| `weekly` | 周版本测试环境 | `c7_weekly.json` |
| `daily` | 日常测试环境 | `c7_daily.json` |
| `partner` | 合作伙伴环境 | `c7_partner.json` |
| `dev` | 开发环境 | `c7_dev.json` |
| `qa` | QA 测试环境 | `c7_qa1.json` |
| `stress` | 压测环境 | `c7_stress.json` |

## 6. 目录访问规则

### 6.1 读取优先级
1. 先尝试从本地缓存读取
2. 缓存失效时从 P4 同步
3. 解析并合并配置
4. 缓存结果

### 6.2 路径解析规则
```python
# 相对路径（相对于当前文件所在目录）
"parent": "./conf_base.json"
"parent": "../conf_linux.json"

# 绝对路径（相对于配置根目录）
"parent": "conf_linux.json"
"parent": "production/c7_weekly.json"
```

### 6.3 P4 路径转换
```python
def p4_path_to_local(p4_path: str) -> str:
    """
    将 P4 路径转换为本地路径
    例: //C7/Development/Mainline/Server/config/production/c7_weekly.json
    转换为: E:/Project/C7_project/Server/config/production/c7_weekly.json
    """
    return p4_path.replace("//C7/Development/Mainline/Server/config/", 
                           config.CONFIG_ROOT_DIR)
```

## 7. 分支配置

### 7.1 Mainline 分支
- P4 路径: `//C7/Development/Mainline/Server/config/`
- 用途: 主干开发配置
- 特点: 包含最新的开发中配置

### 7.2 Weekly 分支
- P4 路径: `//C7/Development/Weekly/Server/config/`
- 用途: 周版本发布配置
- 特点: 每周更新，用于测试环境

### 7.3 Preonline 分支
- P4 路径: `//C7/Release/Preonline/Server/config/`
- 用途: 预发布环境配置
- 特点: 正式发布前的最后验证环境，配置与线上环境高度一致

### 7.4 分支选择
通过 API 参数 `branchType` 指定：
- `mainline` - 主干分支（默认值）
- `weekly` - 周版本分支
- `preonline` - 预发布分支
- 默认值: `mainline`

## 8. 文件权限和安全

### 8.1 敏感文件
以下文件包含敏感信息，需特别保护：
- `PayRsa/*.pem` - 支付密钥
- `rsa_prikey.pem` - RSA 私钥
- 包含 `password`、`secret`、`key` 字段的配置文件

### 8.2 访问控制
- 生产环境配置需要权限审批
- 本地配置可自由修改
- 密钥文件不应提交到版本控制系统（需在 .gitignore 中排除）
