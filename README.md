# Hermes Memory Manager

Hermes 桌面 App 插件：快速查看/编辑**当前 profile** 的 memory 文件（`MEMORY.md` agent 记忆 + `USER.md` profile 记忆），按 `§` 条目逐条编辑，保存即写回本地文件。

- 状态栏 "Memory" chip → 弹出卡片
- 卡片顶部 **MEMORY / USER** 两个按钮切换文件
- 每个条目独立编辑框，支持新增/删除，一次保存全部写回
- 只作用于当前 profile（后端从 `HERMES_HOME` 推导，无 profile 参数可越权）
- 完全通用：不硬编码任何本机路径/profile 名，无凭据、无密钥

## 结构

```text
dashboard/                          # 后端（FastAPI APIRouter，只依赖 fastapi + 标准库）
  manifest.json
  plugin_api.py                     # GET /profile、GET/PUT /content?source=memory|profile
desktop-plugins/hermes-memory-manager/plugin.js   # 桌面 UI（纯 ESM，无构建）
test_backend.py                     # 后端自测（临时目录模拟 Hermes home）
```

## 安装

### 方式 A：bundled（推荐，所有 profile 可用）

后端放进 Hermes 安装目录的插件区（所有 profile 共享、默认启用，免配置）：

```bash
cp -r dashboard "$HERMES_AGENT/plugins/hermes-memory-manager/dashboard/"
# HERMES_AGENT = Hermes 安装目录（Windows: %LOCALAPPDATA%\hermes\hermes-agent，macOS/Linux: 安装位置的 hermes-agent）
```

桌面 UI 按 profile 各放一份（App 切到哪个 profile 就加载哪个的）：

```bash
# 默认 profile
mkdir -p "$HERMES_HOME/desktop-plugins/hermes-memory-manager"
cp desktop-plugins/hermes-memory-manager/plugin.js "$HERMES_HOME/desktop-plugins/hermes-memory-manager/"
# 每个命名 profile（可只装你要用的）
for p in <profile 名>; do
  mkdir -p "$HERMES_HOME/profiles/$p/desktop-plugins/hermes-memory-manager"
  cp desktop-plugins/hermes-memory-manager/plugin.js "$HERMES_HOME/profiles/$p/desktop-plugins/hermes-memory-manager/"
done
```

`HERMES_HOME`：Windows = `%LOCALAPPDATA%\hermes`，macOS/Linux = `~/.hermes`。

### 方式 B：user（只对默认 profile 生效）

```bash
cp -r dashboard "$HERMES_HOME/plugins/hermes-memory-manager/"
mkdir -p "$HERMES_HOME/desktop-plugins/hermes-memory-manager"
cp desktop-plugins/hermes-memory-manager/plugin.js "$HERMES_HOME/desktop-plugins/hermes-memory-manager/"
```

然后在 `$HERMES_HOME/config.yaml` 的 `plugins.enabled` 列表加入 `hermes-memory-manager`（先备份 config.yaml）。

### 生效

1. 重启 gateway（`hermes gateway restart` 或桌面 App 内重启）
2. 桌面 App 里 Ctrl+K → **Reload desktop plugins**
3. 状态栏出现 "Memory" chip

## 使用

1. 点状态栏 "Memory" chip
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
- `hermes update`（git pull）不会删除 untracked 插件；完全重装 Hermes 后需重新复制
