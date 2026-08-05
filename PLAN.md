# 计划：hermes-memory-manager 插件 —— 快速查看/编辑当前 profile 的 memory 文件

## 现状（调查结论）

- Hermes 的 memory 文件：`<profile home>/memories/MEMORY.md`（agent 记忆）+ `USER.md`（profile 记忆），条目用 `§` 分隔
- 默认 profile home = `%LOCALAPPDATA%\hermes`；其他 profile home = `%LOCALAPPDATA%\hermes\profiles\<名称>`（macOS/Linux = `~/.hermes`）
- 现有 4 个 profile：creator（有）、hermes-daily（有 9KB）、deeptutor（空）、voicetest（空）——**空 profile 的 memories 目录存在但无文件**
- 插件结构：后端 `dashboard/manifest.json` + `plugin_api.py`（`router = APIRouter()`）；桌面 UI `plugin.js`（runtime door，**per-profile**：App 切到哪个 profile 就加载哪个 profile 的 desktop-plugins）
- 样板参考：gateway-pill（状态栏 menu 项 1:1）、kanban（ctx.rest）、opencode-usage（后端自包含）
- **需求确认**：① 面板上端 MEMORY/USER 两个按钮切换；② 只能编辑**当前 profile**（前后端都限）；③ **发布通用**——不硬编码本机路径/profile 名；④ bundled 安装（后端所有 profile 共享，桌面 UI 每 profile 一份）

## 步骤

1. ✅ **后端 v1 `dashboard/`**（已完成，后续按 v2 改）：manifest.json + plugin_api.py，三个接口全部通过自测
2. ✅ **后端 v1 自测**（已完成）：27/27 通过
3. ✅ **后端 v2（当前 profile 语义）**（已完成）：`_current_profile()` 从 HERMES_HOME 推导；`GET /profile` 只返回当前 profile；`GET/PUT /content?source=` 无 profile 参数、固定当前 profile
4. ✅ **后端 v2 自测**（已完成）：21/21 通过——当前 profile 推导、越权面消失（无 profile 参数）、CRLF、MemoryStore 兼容、缺失文件新建
5. ✅ **前端 v2 `plugin.js`**（已完成）：chip → 面板顶部 MEMORY/USER 双按钮 tab（按 source 缓存编辑不丢失），条目逐条编辑 + 新增/删除 + 保存；10s 超时、保存/刷新中 disabled；chip 副标题显示当前 profile 条目数；无本机硬编码
6. ✅ **bundled 安装**（已完成）：后端 → `hermes-agent/plugins/hermes-memory-manager/dashboard/`；plugin.js → 默认 + creator/deeptutor/hermes-daily/voicetest 各一份（md5 一致）；config.yaml 已复原
7. ✅ **桌面 App 验证**（已部分验证）：chip 曾出现（popover 版）→ 用户反馈宽度裁剪/重叠 → 改为完整页面
8. ✅ **v3 页面版**（已完成）：去掉 chip；侧边栏导航项（codicon database，label Memory）→ `/memory-manager` 完整页面（kanban 模式，`ROUTES_AREA` + `SIDEBAR_NAV_AREA`）；页面顶部 MEMORY/USER 双按钮 tab + 条目计数，搜索 + 折叠条目 + 新增/删除 + 保存；已同步 5 个安装位置（fs-watch 热重载）
9. ✅ **发布收尾**（已完成）：README.md（安装说明、数据格式、无凭据声明）

## 风险

- **profile 目录推导**：非默认 profile 下 `HERMES_HOME` 指向 profile home，反推 profiles 根目录要兼容 `C:/` 与 `C:\` 两种盘符写法（参考 MEMORY.md 里的教训：MSYS `/c/` 会写错目录）
- **并发写**：Hermes agent 进程也在写 memory 文件（带 `.lock`）——插件直接覆盖写可能和 agent 写冲突；先做简单覆盖写，冲突检测（文件 mtime 变化提示）作为可选项，不放进第一版
- **编码**：Windows 下文件读写必须指定 `utf-8`，防止中文乱码
- **状态栏 vs 面板形态**：先按状态栏 chip 做（"快速打开"）；如果用户想要完整编辑界面再考虑 tab 页
- **生产版 App 的 jsx 坑**：props 必传、children 放 props 里（opencode-usage 插件就踩了 `reading 'key'` 的坑挂了）
