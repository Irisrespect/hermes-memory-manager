# Hermes Memory Manager

在 Hermes 桌面端里可视化查看 / 编辑 agent 的 memory 文件（`MEMORY.md` / `USER.md`），按 § 条目逐条编辑，与 Hermes `MemoryStore` 格式完全兼容。

这是一款 **Desktop 插件**：侧边栏「Memory」入口打开一个全页面编辑界面，支持：

- 当前 profile 的 `MEMORY.md`（agent 记忆）/ `USER.md`（profile 记忆）双文件切换
- 条目以卡片形式横向排布，点击展开编辑，底部拖拽条滚动
- 全文搜索、新增、删除条目
- 修改后通过后端原子写回文件（temp + rename，绝不写坏）
- CRLF/LF 自动兼容（Windows 写的文件也能安全解析）
- 多 profile 支持（`/profiles` 接口列出所有 profile 的记忆文件状态）

## 安装

二选一：**方式一（一键）** 或 **方式二（手动）**，选一种完成安装，然后统一做【启用】。

### 方式一：一键安装（推荐）

在你的 Hermes 桌面端里打开这个链接（点击，或复制到浏览器地址栏回车）：

```
hermes://plugin/install?repo=Irisrespect/hermes-memory-manager&enable=1
```

> [安装到 Hermes](hermes://plugin/install?repo=Irisrespect/hermes-memory-manager&enable=1)

Hermes 会弹出安装确认框（显示插件名、来源、组件）——勾选 **agent 端** 和 **桌面端** 组件，确认安装。
`enable=1` 会自动帮你打开**后端开关**，所以方式一只剩桌面端开关要手动开（见【启用】）。

### 方式二：手动复制

```bash
# Windows (默认): %LOCALAPPDATA%\hermes\plugins\
# macOS/Linux (默认): ~/.hermes/plugins/
cp -r hermes-memory-manager "$HERMES_HOME/plugins/"
```

最终目录结构：

```
$HERMES_HOME/plugins/hermes-memory-manager/
├── desktop/
│   └── plugin.js          # 桌面端 UI（侧边栏入口 + 全页面编辑器）
└── dashboard/
    ├── manifest.json      # { "name": "hermes-memory-manager", "api": "plugin_api.py" }
    ├── plugin_api.py      # 后端 API（读写 memory 文件）
    └── dist/index.js      # dashboard 占位入口（tab 已隐藏，仅安全网）
```

### ⚠️ 启用（安装后必须做，官方安全边界）

插件装完**默认不生效**——这是官方设计（插件可执行代码，必须你亲手激活），不是故障。共两个开关：

**开关 1 — 桌面端（必须手动开，方式一/方式二都一样）：**

> Hermes 桌面端 → 右上角 **设置** → 左侧 **插件** → 找到 **Memory Manager** → 打开启用开关

**开关 2 — 后端：**

- 方式一：链接里的 `enable=1` **已经帮你开好了**，跳过
- 方式二：跑一条官方命令（自动写白名单，不会弄坏配置）：

```bash
hermes plugins enable hermes-memory-manager
```

> 备选（不推荐，容易写错格式）：手动编辑 `$HERMES_HOME/config.yaml`，在 `plugins.enabled` 列表加入 `hermes-memory-manager`。

最后 **重启 Hermes**（或 `hermes gateway restart`），侧边栏出现「Memory」即可使用。

## 卸载

- 删除 `$HERMES_HOME/plugins/hermes-memory-manager/` 文件夹
- 从 `config.yaml` 的 `plugins.enabled` 移除该项
- 桌面端 Settings → Plugins 中移除

## 开发 / 调试

- 桌面端插件热重载：改 `desktop/plugin.js` 保存即生效；**页面类改动（ROUTES_AREA）需重启桌面端**才刷新路由（已知行为）
- 后端改动需重启 Hermes gateway
- 日志：`hermes logs gui -f` / `hermes logs agent -f`

## 兼容性

- Hermes Agent 桌面端 v0.20+（桌面插件 SDK 需要）
- 后端从 `HERMES_HOME` 解析一切，无任何写死的机器路径
- 需要 `plugins.enabled` 含 `hermes-memory-manager`（后端挂载）

## License

MIT