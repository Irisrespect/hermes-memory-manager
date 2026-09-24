/**
 * Hermes Memory Manager — desktop runtime plugin.
 *
 * A sidebar nav entry ("Memory") opens a full page for the CURRENT profile's
 * memory files. MEMORY.md (agent memory) / USER.md (profile memory) switch
 * via two buttons; the file's entries render as vertical cards in ONE
 * horizontal row (no wrapping) — a draggable thumb at the bottom scrolls the
 * row when it overflows. Click a card to expand it into an editor; Save PUTs
 * the whole entry list through the dashboard API, which serializes with the
 * exact MemoryStore format ("\n§\n".join).
 *
 * Fully portable: no machine-specific paths or profile names anywhere —
 * the backend resolves everything from HERMES_HOME at runtime.
 *
 * Loaded as plain ESM (no build); imports are rewritten to the app's SDK
 * shims. Only @hermes/plugin-sdk + react — no JSX syntax, all jsx() calls.
 */

import {
	atom,
	Button,
	cn,
	host,
	icons,
	Loader,
	ROUTES_AREA,
	Separator,
	SIDEBAR_NAV_AREA,
	Textarea,
	useValue,
} from "@hermes/plugin-sdk";
import { useEffect, useRef, useState } from "react";
import { jsx } from "react/jsx-runtime";

const REQ_TIMEOUT_MS = 10_000;
const ROUTE = "/memory-manager";

const SOURCES = [
	{ key: "memory", file: "MEMORY.md" },
	{ key: "profile", file: "USER.md" },
];

// ── shared profile-info state (page header) ─────────────────────────────────

const $profileInfo = atom({ data: null, loading: false, error: null });

function withTimeout(promise, ms) {
	return Promise.race([
		promise,
		new Promise((_, reject) => {
			setTimeout(() => reject(new Error("请求超时（10s）")), ms);
		}),
	]);
}

const errMsg = (err) =>
	err && err.message ? err.message : String(err ?? "未知错误");

function loadProfile(ctx, { force = false } = {}) {
	const cur = $profileInfo.get();
	if (!force && (cur.loading || cur.data)) return Promise.resolve();
	$profileInfo.set({ ...cur, loading: true, error: null });
	return withTimeout(ctx.rest("/profile"), REQ_TIMEOUT_MS)
		.then((res) => {
			$profileInfo.set({ data: res, loading: false, error: null });
		})
		.catch((err) => {
			$profileInfo.set({
				data: $profileInfo.get().data,
				loading: false,
				error: errMsg(err),
			});
		});
}

// ── vertical entry cards, laid out horizontally in one row ──────────────────

function renderEntries(ed, { search, expanded, onToggle, onChange, onRemove }) {
	const q = search.trim().toLowerCase();
	const visible = ed.entries
		.map((text, i) => ({ text, i }))
		.filter(({ text }) => !q || text.toLowerCase().includes(q));

	if (visible.length === 0) {
		return [
			jsx("p", {
				key: "empty",
				className:
					"w-full self-center text-center text-xs text-(--ui-text-secondary)",
				children:
					ed.entries.length === 0
						? "没有条目——点下方「新增条目」开始"
						: `无匹配条目（共 ${ed.entries.length} 条）`,
			}),
		];
	}
	return visible.map(({ text, i }) => {
		const isOpen = Boolean(expanded[i]);
		return jsx(
			"div",
			{
				key: i,
				className:
					"flex w-44 shrink-0 flex-col rounded-lg border border-(--ui-stroke-secondary) bg-(--ui-bg-secondary) p-2",
				children: [
					isOpen
						? jsx(Textarea, {
								className:
									"min-h-32 w-full flex-1 resize-none rounded-[2.5px] border border-(--ui-stroke-secondary) bg-(--ui-bg-primary) px-2 py-1.5 text-xs leading-4 outline-none placeholder:text-(--ui-text-quaternary) focus:border-(--ui-accent)",
								value: text,
								onChange: (e) => onChange(i, e.target.value),
								placeholder: "条目内容…",
								autoFocus: true,
							})
						: jsx("button", {
								type: "button",
								className:
									"flex min-h-32 flex-1 flex-col items-stretch gap-1.5 text-left",
								onClick: () => onToggle(i),
								title: "展开编辑",
								children: [
									jsx("span", {
										className:
											"text-[0.62rem] leading-4 text-(--ui-text-tertiary) tabular-nums",
										children: `#${i + 1}`,
									}),
									jsx("span", {
										className: cn(
											"line-clamp-6 flex-1 whitespace-pre-wrap break-words text-xs leading-4",
											text
												? "text-(--ui-text-secondary)"
												: "text-(--ui-text-quaternary) italic",
										),
										children: text || "（空条目）",
									}),
								],
							}),
					jsx("div", {
						className:
							"mt-1.5 flex items-center justify-between border-t border-(--ui-stroke-tertiary) pt-1",
						children: [
							jsx(Button, {
								variant: "ghost",
								size: "icon-xs",
								className: "text-(--ui-text-secondary)",
								"aria-label": isOpen ? "折叠" : "展开编辑",
								title: isOpen ? "折叠" : "展开编辑",
								onClick: () => onToggle(i),
								children: isOpen ? jsx(icons.X, {}) : jsx(icons.Pencil, {}),
							}),
							jsx(Button, {
								variant: "ghost",
								size: "icon-xs",
								className: "text-(--ui-text-secondary) hover:text-(--ui-danger)",
								"aria-label": `删除条目 ${i + 1}`,
								title: "删除条目",
								onClick: () => onRemove(i),
								children: jsx(icons.Trash2, {}),
							}),
						],
					}),
				],
			},
			i,
		);
	});
}

// ── page ────────────────────────────────────────────────────────────────────

function MemoryPage({ ctx }) {
	const [source, setSource] = useState("memory");
	// source → { entries, meta, loading, error } — cached per source so
	// switching tabs never loses unsaved edits.
	const [editors, setEditors] = useState({});
	const [saving, setSaving] = useState(false);
	const [refreshing, setRefreshing] = useState(false);
	const [search, setSearch] = useState("");
	// entry index → expanded (Textarea visible).
	const [expanded, setExpanded] = useState({});
	const info = useValue($profileInfo);

	// Horizontal card row + draggable bottom thumb.
	const scrollerRef = useRef(null);
	const trackRef = useRef(null);
	const [bar, setBar] = useState({ thumbW: 0, maxScroll: 0, left: 0 });

	useEffect(() => {
		void loadProfile(ctx, { force: true });
	}, []);

	const fetchContent = (src) => {
		withTimeout(ctx.rest(`/content?source=${src}`), REQ_TIMEOUT_MS)
			.then((res) =>
				setEditors((prev) => ({
					...prev,
					[src]: {
						entries: res.entries ?? [],
						meta: res,
						loading: false,
						error: null,
					},
				})),
			)
			.catch((err) =>
				setEditors((prev) => ({
					...prev,
					[src]: {
						entries: [],
						meta: null,
						loading: false,
						error: errMsg(err),
					},
				})),
			);
	};

	const ensureLoaded = (src) => {
		setEditors((prev) => {
			if (prev[src]) return prev;
			fetchContent(src);
			return {
				...prev,
				[src]: { entries: [], meta: null, loading: true, error: null },
			};
		});
	};

	useEffect(() => {
		ensureLoaded(source);
	}, [source]);

	const refresh = () => {
		if (refreshing) return;
		setRefreshing(true);
		loadProfile(ctx, { force: true }).then(() => setRefreshing(false));
	};

	const setEntry = (i, text) =>
		setEditors((prev) => ({
			...prev,
			[source]: {
				...prev[source],
				entries: prev[source].entries.map((e, j) => (j === i ? text : e)),
			},
		}));

	const removeEntry = (i) => {
		setEditors((prev) => ({
			...prev,
			[source]: {
				...prev[source],
				entries: prev[source].entries.filter((_, j) => j !== i),
			},
		}));
		// Collapse: indices shift after removal.
		setExpanded({});
	};

	const addEntry = () => {
		const idx = editors[source]?.entries.length ?? 0;
		setEditors((prev) => ({
			...prev,
			[source]: { ...prev[source], entries: [...prev[source].entries, ""] },
		}));
		setExpanded((prev) => ({ ...prev, [idx]: true }));
		// Reveal the new card: scroll the row to its end.
		setTimeout(() => {
			const el = scrollerRef.current;
			if (el) el.scrollLeft = el.scrollWidth;
		}, 0);
	};

	const save = () => {
		const ed = editors[source];
		if (saving || !ed || ed.loading) return;
		setSaving(true);
		setEditors((prev) => ({
			...prev,
			[source]: { ...prev[source], error: null },
		}));
		withTimeout(
			ctx.rest(`/content?source=${source}`, {
				method: "PUT",
				body: { entries: ed.entries },
			}),
			REQ_TIMEOUT_MS,
		)
			.then((res) => {
				setSaving(false);
				setEditors((prev) => ({
					...prev,
					[source]: { ...prev[source], meta: res },
				}));
				host.notify({
					kind: "success",
					title: "Memory 已保存",
					message: `${SOURCES.find((s) => s.key === source)?.file ?? source} · ${res.entry_count} 条已写回本地文件`,
				});
				void loadProfile(ctx, { force: true });
			})
			.catch((err) => {
				setSaving(false);
				const msg = errMsg(err);
				setEditors((prev) => ({
					...prev,
					[source]: { ...prev[source], error: msg },
				}));
				host.notify({ kind: "error", title: "保存失败", message: msg });
			});
	};

	// ── scroll-bar measurement + thumb dragging ──────────────────────────────

	const entryCount = editors[source]?.entries.length ?? 0;

	useEffect(() => {
		const el = scrollerRef.current;
		if (!el) return;
		const measure = () => {
			const max = Math.max(0, el.scrollWidth - el.clientWidth);
			setBar((b) => ({
				...b,
				thumbW:
					max > 0
						? Math.max(40, (el.clientWidth / el.scrollWidth) * el.clientWidth)
						: 0,
				maxScroll: max,
				left: Math.min(el.scrollLeft, max),
			}));
		};
		const onScroll = () => setBar((b) => ({ ...b, left: el.scrollLeft }));
		measure();
		el.addEventListener("scroll", onScroll);
		const ro = new ResizeObserver(measure);
		ro.observe(el);
		return () => {
			el.removeEventListener("scroll", onScroll);
			ro.disconnect();
		};
	}, [source, entryCount]);

	const startThumbDrag = (e) => {
		if (bar.maxScroll <= 0) return;
		e.preventDefault();
		const startX = e.clientX;
		const startLeft = scrollerRef.current.scrollLeft;
		const moveRange = Math.max(1, trackRef.current.clientWidth - bar.thumbW);
		const onMove = (ev) => {
			const ratio = bar.maxScroll / moveRange;
			scrollerRef.current.scrollLeft =
				startLeft + (ev.clientX - startX) * ratio;
		};
		const onUp = () => {
			window.removeEventListener("pointermove", onMove);
			window.removeEventListener("pointerup", onUp);
		};
		window.addEventListener("pointermove", onMove);
		window.addEventListener("pointerup", onUp);
	};

	const trackClick = (e) => {
		if (bar.maxScroll <= 0) return;
		const rect = trackRef.current.getBoundingClientRect();
		const ratio =
			(e.clientX - rect.left - bar.thumbW / 2) /
			Math.max(1, rect.width - bar.thumbW);
		scrollerRef.current.scrollLeft = Math.max(
			0,
			Math.min(bar.maxScroll, ratio * bar.maxScroll),
		);
	};

	const ed = editors[source];
	const fileCount = (key) => {
		const e = editors[key];
		if (e) return e.entries.length;
		return info.data?.files?.[key]?.entry_count ?? 0;
	};
	const thumbRange = Math.max(
		1,
		(trackRef.current?.clientWidth ?? 0) - bar.thumbW,
	);
	const thumbLeft =
		bar.maxScroll > 0 ? (bar.left / bar.maxScroll) * thumbRange : 0;

	return jsx("div", {
		className:
			"relative flex h-full flex-col overflow-hidden",
		children: [
			jsx("div", {
				key: "head",
				className: "flex items-center justify-between gap-3 px-4 pt-3",
				children: [
					jsx("div", {
						className: "flex min-w-0 items-baseline gap-2",
						children: [
							jsx("h1", {
								className: "min-w-0 truncate text-sm font-semibold",
								children: "Memory Manager",
							}),
							jsx("span", {
								className: "min-w-0 truncate text-xs text-(--ui-text-secondary)",
								children: info.data
									? `${info.data.name} · ${info.data.memories_dir}`
									: "…",
							}),
						],
					}),
					jsx(Button, {
						variant: "ghost",
						size: "xs",
						disabled: refreshing || info.loading,
						onClick: refresh,
						children:
							refreshing || info.loading
								? "刷新中…"
								: [jsx(icons.RefreshCw, {}), "刷新"],
					}),
				],
			}),
			jsx("div", {
				key: "tabs",
				className: "flex gap-1 px-4 pt-2",
				children: SOURCES.map((s) =>
					jsx(
						Button,
						{
							key: s.key,
							variant: source === s.key ? "secondary" : "ghost",
							size: "sm",
							className: "flex-1",
							onClick: () => setSource(s.key),
							children: `${s.file} · ${fileCount(s.key)} 条`,
						},
						s.key,
					),
				),
			}),
			jsx(Separator, { key: "sep", className: "mt-2" }),
			jsx("div", {
				key: "body",
				className: "flex min-h-0 flex-1 flex-col",
				children: [
					ed && !ed.meta?.exists
						? jsx("p", {
								key: "hint",
								className:
									"px-4 pt-3 text-xs text-(--ui-warning)",
								children: "文件尚不存在——添加条目并保存将新建文件",
							})
						: null,
					ed?.error
						? jsx("p", {
								key: "error",
								className: "px-4 pt-3 text-xs text-(--ui-danger)",
								children: `错误：${ed.error}`,
							})
						: null,
					jsx("div", {
						key: "search",
						className: "px-4 pt-3",
						children: jsx("input", {
							className:
								"h-8 w-full rounded-md border border-(--ui-stroke-secondary) bg-(--ui-bg-input) px-2.5 text-xs text-(--ui-text-primary) outline-none placeholder:text-(--ui-text-tertiary) focus:border-(--ui-accent)",
							placeholder: "搜索条目…",
							value: search,
							onChange: (e) => setSearch(e.target.value),
						}),
					}),
					!ed || ed.loading
						? jsx("div", {
								key: "loading",
								className: "flex flex-1 items-center justify-center",
								children: jsx(Loader, {}),
							})
						: jsx("div", {
								key: "row",
								ref: scrollerRef,
								className: "min-h-0 flex-1 overflow-x-hidden px-4 py-2",
								children: jsx("div", {
									className: "flex h-full items-stretch gap-2",
									children: renderEntries(ed, {
										search,
										expanded,
										onToggle: (i) =>
											setExpanded((prev) => ({ ...prev, [i]: !prev[i] })),
										onChange: setEntry,
										onRemove: removeEntry,
									}),
								}),
							}),
					bar.maxScroll > 0
						? jsx("div", {
								key: "bar",
								className: "px-4 pb-1.5",
								children: jsx("div", {
									ref: trackRef,
									className:
										"relative h-2 cursor-pointer rounded-full bg-(--ui-bg-quaternary)",
									onPointerDown: trackClick,
									children: jsx("div", {
										className:
											"absolute top-0 h-full cursor-grab touch-none rounded-full bg-(--ui-text-tertiary) active:cursor-grabbing",
										style: { width: bar.thumbW, left: thumbLeft },
										onPointerDown: startThumbDrag,
									}),
								}),
							})
						: null,
					jsx("div", {
						key: "actions",
						className: "flex items-center justify-between gap-2 px-4 py-3",
						children: [
							jsx(Button, {
								variant: "outline",
								size: "sm",
								onClick: addEntry,
								children: [jsx(icons.Plus, {}), "新增条目"],
							}),
							jsx(Button, {
								variant: "default",
								size: "sm",
								disabled: saving || !ed || ed.loading,
								onClick: save,
								children: saving
									? "保存中…"
									: `保存 ${SOURCES.find((s) => s.key === source)?.file ?? ""}`,
							}),
						],
					}),
				],
			}),
		],
	});
}

// ── plugin ──────────────────────────────────────────────────────────────────

const plugin = {
	id: "hermes-memory-manager",
	name: "Memory Manager",
	register(ctx) {
		void loadProfile(ctx);

		ctx.registerMany([
			{
				id: "page",
				area: ROUTES_AREA,
				data: { path: ROUTE },
				title: "Memory Manager",
				render: () => jsx(MemoryPage, { ctx }),
			},
			{
				id: "nav",
				area: SIDEBAR_NAV_AREA,
				order: 50,
				data: {
					codicon: "database",
					label: "Memory",
					path: ROUTE,
				},
			},
		]);
	},
};

export default plugin;
