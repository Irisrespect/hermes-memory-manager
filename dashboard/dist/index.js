/**
 * hermes-memory-manager dashboard entry (stub).
 *
 * 本插件的 UI 是桌面端侧边栏插件（desktop/plugin.js，路由 /memory-manager），
 * dashboard 侧只提供后端 API
 * （/api/plugins/hermes-memory-manager/*），manifest 的 tab.hidden=true，
 * 因此 dashboard 不会渲染本入口。此 stub 仅作安全网：
 * 若将来被取消隐藏，加载后直接注册一个占位组件，避免空白页。
 */
(function () {
  const g = typeof window !== "undefined" ? window : globalThis;
  const api = g.__HERMES_PLUGINS__;
  if (api && typeof api.register === "function") {
    api.register("hermes-memory-manager", function MemoryManagerPlaceholder() {
      return null;
    });
  }
})();