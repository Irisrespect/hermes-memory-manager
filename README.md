# Hermes Memory Manager

Hermes 桌面 App 插件：快速查看/编辑**当前 profile** 的 memory 文件（`MEMORY.md` agent 记忆 + `USER.md` profile 记忆），按 `§` 条目逐条编辑，保存即写回本地文件。

[![Install in Hermes](https://img.shields.io/badge/Install_in-Hermes-blue)](hermes://plugin/install?repo=Irisrespect/hermes-memory-manager&enable=1)

> 一键安装（含后端启用）；桌面端 Settings → Plugins 里的开关还需手动打开一次（官方安全设计，任何方式都绕不开）。

- 侧边栏导航 "Memory" 项 → 完整页面（kanban 式）
- 页面顶部 **MEMORY / USER** 两个按钮切换文件（tab）
- 条目为竖长卡片、同一行横排不换行，超出宽度用底部滑块横向拖动；点击卡片展开编辑
- 每张卡片支持新增/删除，保存按钮一次写回全部条目
- 只作用于当前 profile（后端从 `HERMES_HOME` 推导，无 profile 参数可越权）
- 完全通用：不硬编码任何本机路径/profile 名，无凭据、无密钥

## 结构

```text
dashboard/                          # 后端（FastAPI APIRouter，只依赖 fastapi + 标准库）
  manifest.json
  plugin_api.py                     # GET /profile、GET /profiles、GET/PUT /content?source=memory|profile
desktop/plugin.js                   # 桌面 UI（纯 ESM，无构建）
test_backend.py                     # 后端自测（临时目录模拟 Hermes home，⚠️ 待升级到新版 API）
```

## 安装

### 一键安装（桌面 App，推荐）

点击 **[Install in Hermes](hermes://plugin/install?repo=Irisrespect/hermes-memory-manager&enable=1)**（`enable=1` 自动开后端开关），然后到桌面端 Settings → Plugins 手动打开本插件 → 完全退出 App 重开。

### 脚本安装（PowerShell，Windows）

1. 解压发布包
2. 在解压出的文件夹里打开 PowerShell，运行：

```powershell
.\install.ps1                # 默认 profile
.\install.ps1 -AllProfiles   # 额外装到所有命名 profile（推荐）
```

脚本自动定位 Hermes 目录并完成全部复制；装完后**完全退出桌面 App 再重新打开**（后端进程缓存插件，仅 Reload 不够），左侧导航出现 "Memory"。

#### 全新环境（刚装好的 Hermes）

1. 确保 Hermes 桌面 App 已安装并至少启动过一次（生成 `config.yaml`，install.ps1 靠它定位 Hermes home）
2. 解压发布包 → 在该目录打开 PowerShell → `\install.ps1 -AllProfiles`（全新环境没有命名 profile，`-AllProfiles` 自动跳过）
3. 完全退出桌面 App 再重新打开
4. 侧边栏出现 "Memory"；首次进入时 memory 文件不存在会显示空态，添加条目并保存即自动创建文件

特殊情况：

- Hermes 装在非标准位置：`\install.ps1 -HermesHome "D:\路径\hermes"`
- macOS/Linux：脚本是 Windows PowerShell；请用下方手动安装

### 手动安装

后端装到 user 位置（`$HERMES_HOME/plugins/`，Hermes 更新不删除；不要装进 `hermes-agent/plugins/`，ZIP-fallback 更新会整体覆盖那里）：

```bash
cp -r dashboard "$HERMES_HOME/plugins/hermes-memory-manager/dashboard"
hermes plugins enable hermes-memory-manager   # 进 plugins.enabled 白名单（每个要用的 profile 各执行一次）
```

桌面 UI 按 profile 各放一份（App 切到哪个 profile 就加载哪个的）：

```bash
# 默认 profile
mkdir -p "$HERMES_HOME/desktop-plugins/hermes-memory-manager"
cp desktop/plugin.js "$HERMES_HOME/desktop-plugins/hermes-memory-manager/"
# 每个命名 profile（可只装你要用的）
for p in <profile 名>; do
  mkdir -p "$HERMES_HOME/profiles/$p/desktop-plugins/hermes-memory-manager"
  cp desktop/plugin.js "$HERMES_HOME/profiles/$p/desktop-plugins/hermes-memory-manager/"
done
```

`HERMES_HOME`：Windows = `%LOCALAPPDATA%\hermes`，macOS/Linux = `~/.hermes`。

### 生效

1. **完全退出桌面 App 再重新打开**（后端路由挂载是启动时一次性，后端代码变更必须重启；仅 Reload 不够）
2. 桌面端 Settings → Plugins 找到 Memory Manager 并打开
3. 左侧边栏出现 "Memory"

## 使用

1. 点左侧边栏 "Memory"
2. 顶部切 MEMORY.md / USER.md（切换不丢失未保存的编辑）
3. 逐条编辑/删除，或「新增条目」
4. 点「保存」写回本地文件（成功有通知；空条目自动丢弃）

## 数据格式

与 Hermes `MemoryStore`（tools/memory_tool.py）完全一致：

- 分隔符：`"\n§\n"`（§ 独占一行）
- 读取：split + 去首尾空白 + 丢弃空条目（容忍 CRLF）
- 写入：`"\n§\n".join(entries)`，原子写（临时文件 + rename），强制 LF

## 开发

后端自测（不依赖真实 Hermes 环境，用临时目录模拟 home）：

```bash
python test_backend.py
```

## 说明

- 只读写 `<当前 profile home>/memories/MEMORY.md` 与 `USER.md`，文件不存在时保存会新建
- 超时兜底 10s（gateway 断连不卡死），保存/刷新按钮带进行中状态
- 后端装在 user 位置（`$HERMES_HOME/plugins/`），`hermes update`（含 ZIP-fallback 整包覆盖）不会删除；完全重装 Hermes 后需重新安装
