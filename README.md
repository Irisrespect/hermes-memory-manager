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

### 方式一：一键安装（推荐）

在本机 Hermes 桌面端中打开此链接：

```
hermes://plugin/install?repo=<你的GitHub用户名>/hermes-memory-manager&enable=1
```

> 在 README 的在线版本中，下面的按钮会直接可用：
>
> [安装到 Hermes](hermes://plugin/install?repo=<你的GitHub用户名>/hermes-memory-manager&enable=1)

### 方式二：手动安装

这个仓库本身就是标准插件包（`desktop/plugin.js` + `dashboard/plugin_api.py`），把它放到 Hermes 插件目录：

```bash
# 以默认 HERMES_HOME 为例 (Windows: %LOCALAPPDATA%\hermes, 其他: ~/.hermes)
cp -r hermes-memory-manager "$HERMES_HOME/plugins/"
```

即最终目录结构：

```
$HERMES_HOME/plugins/hermes-memory-manager/
├── desktop/
│   └── plugin.js          # 桌面端 UI（侧边栏入口 + 全页面编辑器）
└── dashboard/
    ├── manifest.json      # { "name": "hermes-memory-manager", "api": "plugin_api.py" }
    ├── plugin_api.py      # 后端 API（读写 memory 文件）
    └── dist/index.js      # dashboard 占位入口（tab 已隐藏，仅安全网）
```

### ⚠️ 两个开关（安装后必须操作，官方安全边界）

| 开关 | 位置 | 说明 |
|---|---|---|
| 桌面端激活 | 桌面端 **Settings → Plugins** | 找到 Memory Manager，打开启用开关 |
| 后端激活 | `$HERMES_HOME/config.yaml` | `plugins.enabled` 列表加入 `hermes-memory-manager`，重启 gateway |

> 两个开关默认都是 **off**（官方对插件统一的安全策略），装完不启用则插件不工作——这是设计行为，不是故障。

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