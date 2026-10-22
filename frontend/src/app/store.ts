// Application state and actions, ported from the pre-React ui/app.js. React
// subscribes through useApp; verification scripts drive the same actions via
// window.lal. The backend stays the authority for availability, faults,
// notifications and processing: this file only presents its answers.
import { useSyncExternalStore } from "react";
import { type AssetApi, type Bridge, type Json, libraryApi, sourceApi } from "./api";
import { describeActive, notificationContent, notificationKey, operationActive, type Tone } from "./format";

export type Page = "home" | "library" | "collections" | "processing" | "settings" | "source";
export type SettingsTab = "general" | "asset-sources";
export interface Route {
  page: Page;
  tab?: SettingsTab;
  key?: string;
  /** Asset processing: the source a notification pointed at. */
  focus?: string;
}
export type CollectionId = "library" | "source";
export type InspectorTab = "overview" | "sources" | "evidence";

export interface Thumb {
  image?: string;
  pixelArt?: boolean;
  placeholder?: string;
  reason?: string;
  badge?: { label: string; tone: "review" | "fault" };
  card?: Json;
  presentation?: Json;
}
export interface Detail {
  assetId: string;
  format: string | null;
  view: string;
  loading: boolean;
  result: Json | null;
  error: string | null;
  /** Bumped by actions that move focus to the inspector heading. */
  focusToken: number;
}
export interface Collection {
  id: CollectionId;
  key: string | null;
  items: Json[];
  thumbs: Record<string, Thumb>;
  version: string | null;
  generation: number;
  selected: string | null;
  detail: Detail | null;
  total: number;
  offset: number;
  loading: boolean;
  finished: boolean;
  status: string;
  error: string | null;
  emptyText: string;
}
export interface Filters {
  asset_type: string;
  pack: string;
  format: string;
  triangles: string;
  rigged: string;
  transparent: string;
  size_class: string;
  mode: string;
  limit: string;
  reference_asset: string;
  reference_view: string;
}
export const DEFAULT_FILTERS: Filters = {
  asset_type: "", pack: "", format: "", triangles: "", rigged: "", transparent: "", size_class: "",
  mode: "combined", limit: "20", reference_asset: "", reference_view: "three_quarter",
};
export interface SearchState {
  phase: "idle" | "browse" | "search";
  busy: boolean;
  title: string;
  status: string;
  statusTitle: string;
  error: string | null;
  lastSettings: Json | null;
  candidateNote: boolean;
  queryUsed: string;
  modeUsed: string;
  count: number;
}
export interface Toast {
  id: number;
  tone: Tone;
  title: string;
  body: string;
  notification?: Json;
}
export interface AppState {
  api: Bridge | null;
  ready: boolean;
  startupError: string | null;
  context: Json | null;
  history: Route[];
  historyIndex: number;
  query: string;
  filters: Filters;
  filtersOpen: boolean;
  search: SearchState;
  referenceOptions: { id: string; label: string }[];
  library: Collection;
  source: Collection;
  inspector: { open: boolean; width: number; tab: InspectorTab };
  sources: Json[];
  sourcesRevision: string | null;
  sourcesMessage: string;
  notifications: Json[];
  notificationsOpen: boolean;
  toasts: Toast[];
  failures: { loading: boolean; assets: number; paths: string[]; unavailable: Json[]; error: string | null; loaded: boolean };
  general: { loading: boolean; busy: boolean; message: string; values: Json | null };
  appearance: string;
  runReport: Json | null;
  imageBackground: string;
  coverage: string;
}

const emptyCollection = (id: CollectionId): Collection => ({
  id, key: null, items: [], thumbs: {}, version: null, generation: 0, selected: null, detail: null,
  total: 0, offset: 0, loading: false, finished: false, status: "", error: null, emptyText: "",
});
const idleSearch: SearchState = {
  phase: "idle", busy: false, title: "", status: "", statusTitle: "", error: null, lastSettings: null,
  candidateNote: false, queryUsed: "", modeUsed: "combined", count: 0,
};

const boot = window.LAL_BOOT || { appearance: "system", inspector_width: 440 };
let state: AppState = {
  api: null, ready: false, startupError: null, context: null,
  history: [{ page: "home" }], historyIndex: 0,
  query: "", filters: { ...DEFAULT_FILTERS }, filtersOpen: false, search: idleSearch, referenceOptions: [],
  library: emptyCollection("library"), source: emptyCollection("source"),
  inspector: { open: false, width: boot.inspector_width, tab: "overview" },
  sources: [], sourcesRevision: null, sourcesMessage: "", notifications: [], notificationsOpen: false, toasts: [],
  failures: { loading: false, assets: 0, paths: [], unavailable: [], error: null, loaded: false },
  general: { loading: false, busy: false, message: "", values: null },
  appearance: boot.appearance, runReport: null, imageBackground: "checker", coverage: "",
};

const listeners = new Set<() => void>();
export const getState = () => state;
export function setState(patch: Partial<AppState> | ((current: AppState) => Partial<AppState>)) {
  const next = typeof patch === "function" ? patch(state) : patch;
  state = { ...state, ...next };
  for (const listener of listeners) listener();
}
const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};
export function useApp<T>(selector: (current: AppState) => T): T {
  return useSyncExternalStore(subscribe, () => selector(state));
}
function patchCollection(id: CollectionId, patch: Partial<Collection> | ((current: Collection) => Partial<Collection>)) {
  setState((s) => {
    const current = s[id];
    return { [id]: { ...current, ...(typeof patch === "function" ? patch(current) : patch) } } as Partial<AppState>;
  });
}
function patchSearch(patch: Partial<SearchState>) {
  setState((s) => ({ search: { ...s.search, ...patch } }));
}
const api = () => {
  if (!state.api) throw Error("Desktop bridge unavailable");
  return state.api;
};
export const route = () => state.history[state.historyIndex];
export const activeCollectionId = (s: AppState = state): CollectionId => (s.history[s.historyIndex].page === "source" ? "source" : "library");
export function collectionApi(id: CollectionId): AssetApi {
  return id === "source" && state.source.key ? sourceApi(api(), state.source.key) : libraryApi(api());
}

/* ------------------------------- navigation ------------------------------ */

const sameRoute = (a: Route, b: Route) => a.page === b.page && a.tab === b.tab && a.key === b.key;
export function navigate(next: Route) {
  const current = route();
  if (sameRoute(current, next)) {
    if (next.focus !== current.focus) setState((s) => ({ history: s.history.map((r, i) => (i === s.historyIndex ? next : r)) }));
    return;
  }
  window.LALPreview?.pause();
  setState((s) => ({ history: [...s.history.slice(0, s.historyIndex + 1), next], historyIndex: s.historyIndex + 1, filtersOpen: false }));
  enterRoute(next, current);
}
export function goBack() {
  if (state.historyIndex === 0) return;
  const previous = route();
  window.LALPreview?.pause();
  setState((s) => ({ historyIndex: s.historyIndex - 1, filtersOpen: false }));
  enterRoute(route(), previous);
}
export function goForward() {
  if (state.historyIndex >= state.history.length - 1) return;
  const previous = route();
  window.LALPreview?.pause();
  setState((s) => ({ historyIndex: s.historyIndex + 1, filtersOpen: false }));
  enterRoute(route(), previous);
}
function enterRoute(next: Route, previous: Route) {
  if (next.page === "settings") void Promise.all([loadGeneralSettings(), loadSources()]);
  if (next.page === "processing") void Promise.all([loadSources(), loadImportFailures()]);
  if (next.page === "source" && next.key && (state.source.key !== next.key || previous.page !== "source")) void openSourceBrowser(next.key);
  // Returning to a collection re-resolves its selection so a paused 3D preview remounts.
  const id = activeCollectionId();
  const selected = state[id].selected;
  if (selected && state.inspector.open && (next.page !== "source" || state.source.key === next.key))
    void selectAsset(id, selected, state[id].detail?.format ?? null, state[id].detail?.view ?? "three_quarter", false);
}

/* --------------------------------- search -------------------------------- */

let searchGeneration = 0;
let activeSearchSettings: string | null = null;

function filterArgs(f: Filters = state.filters) {
  const out: Json = {};
  if (f.asset_type) out.asset_type = f.asset_type;
  if (f.transparent) out.transparent = f.transparent === "true";
  if (f.size_class) out.size_class = f.size_class;
  if (f.pack) out.pack = f.pack;
  if (f.format) out.format = f.format;
  if (f.triangles !== "") out.max_triangles = Number(f.triangles);
  if (f.rigged) out.rigged = f.rigged === "true";
  return out;
}
export function searchSettings(): Json {
  const f = state.filters;
  const args: Json = { mode: f.mode, filters: filterArgs(f), limit: Number(f.limit) };
  if (f.mode === "reference") {
    args.reference_asset_id = f.reference_asset;
    args.reference_view = f.reference_view;
  } else args.query = state.query;
  return args;
}
function rememberReferenceOptions(items: Json[]) {
  setState((s) => {
    const known = new Set(s.referenceOptions.map((o) => o.id));
    const added = items.filter((i) => !known.has(i.asset_id)).map((i) => ({ id: i.asset_id, label: `${i.name} · ${packLabel(i.pack)}` }));
    return added.length ? { referenceOptions: [...s.referenceOptions, ...added] } : {};
  });
}
const packLabel = (value: string) => (value || "").replace(/^kenney_/, "Kenney · ").replace(/^quaternius_/, "Quaternius · ").replaceAll("_", " ").replaceAll("-", " ");

function showResults(id: CollectionId, items: Json[], generation: number, append = false) {
  patchCollection(id, (c) => ({ items: append ? c.items.concat(items) : items, thumbs: append ? c.thumbs : {}, generation }));
  if (id === "library") rememberReferenceOptions(items);
}

export async function browse(resetPage = true) {
  activeSearchSettings = null;
  if (resetPage) patchCollection("library", { offset: 0 });
  const generation = ++searchGeneration;
  patchSearch({ phase: "browse", busy: false, lastSettings: null, candidateNote: false, error: null, title: "Library assets", status: "Loading this page…", queryUsed: "", modeUsed: state.filters.mode });
  patchCollection("library", { loading: true });
  try {
    const result = await api().browse(filterArgs(), state.library.offset, 40);
    if (generation !== searchGeneration) return;
    if (result.status === "faulty") throw Error(result.reason);
    if (result.generation !== state.context?.generation) throw Error("Published version changed; refreshing context.");
    showResults("library", result.items, generation);
    patchCollection("library", { total: result.total_count, version: result.generation });
    patchSearch({ status: `${result.total_count} matching assets · thumbnails load as they become visible`, count: result.total_count });
  } catch (error) {
    if (generation === searchGeneration) patchSearch({ error: (error as Error).message, status: "Browse unavailable. Refresh the published view to load its current version." });
  } finally {
    if (generation === searchGeneration) patchCollection("library", { loading: false });
  }
}
export function pageBrowse(direction: 1 | -1) {
  patchCollection("library", (c) => ({ offset: Math.max(0, c.offset + direction * 40) }));
  return browse(false);
}

export async function search() {
  const args = searchSettings();
  if (state.search.busy && JSON.stringify(args) === activeSearchSettings) return;
  if (args.mode !== "reference" && !String(args.query).trim()) return browse();
  const generation = ++searchGeneration;
  activeSearchSettings = JSON.stringify(args);
  patchSearch({
    phase: "search", busy: true, lastSettings: null, candidateNote: args.mode !== "keyword", error: null, title: "Search shortlist",
    status: args.mode === "keyword" ? "Searching the library…" : "Searching the library… First model load can take longer; the window remains available.",
    statusTitle: "", queryUsed: args.mode === "reference" ? "" : args.query, modeUsed: args.mode,
  });
  patchCollection("library", { loading: true });
  try {
    const result = await api().search(args);
    if (generation !== searchGeneration) return;
    const payload = result.payload || {};
    if (result.is_error || result.status === "faulty" || payload.status === "faulty") throw Error(payload.reason || result.reason || "Search failed");
    if (payload.generation !== state.context?.generation) throw Error("Published version changed; refresh the view.");
    showResults("library", payload.results, generation);
    patchCollection("library", { version: payload.generation, total: payload.results.length });
    patchSearch({
      lastSettings: structuredClone(result.arguments), count: payload.results.length,
      status: `${payload.results.length} candidates · ${result.elapsed_seconds.toFixed(2)} s${payload.truncated ? " · shortlist truncated by the shared response cap" : ""}${payload.fault_count ? " · " + payload.fault_count + " recorded exclusion / preview faults" : ""}`,
      statusTitle: payload.faults?.length ? payload.faults.map((f: Json) => `${f.channel}: ${f.reason}`).join("\n") : "",
    });
  } catch (error) {
    if (generation === searchGeneration) patchSearch({ error: (error as Error).message, status: "Search is faulty. No fallback or automatic retry. Earlier cards are retained." });
  } finally {
    if (generation === searchGeneration) {
      activeSearchSettings = null;
      patchSearch({ busy: false });
      patchCollection("library", { loading: false });
    }
  }
}
/** Enter or the arrow button: search, or browse the filtered library when the query is empty. */
export function submitSearch() {
  if (route().page !== "home") navigate({ page: "home" });
  setState({ filtersOpen: false });
  return search();
}
export function setQuery(query: string) {
  setState({ query });
}
export function clearSearch() {
  ++searchGeneration;
  activeSearchSettings = null;
  closeDetail("library");
  setState({ query: "", search: idleSearch });
  patchCollection("library", { items: [], thumbs: {}, total: 0, offset: 0, loading: false });
}
export function applyFilters(filters: Filters) {
  setState({ filters, filtersOpen: false });
  if (filters.mode === "reference" && filters.reference_asset) return search();
  if (state.search.phase !== "idle") return state.search.phase === "browse" ? browse() : search();
}
export function setFiltersOpen(open: boolean) {
  setState({ filtersOpen: open });
  if (open && !state.referenceOptions.length) void loadReferenceOptions();
}
async function loadReferenceOptions() {
  try {
    const result = await api().browse({}, 0, 100);
    if (result.status !== "faulty") rememberReferenceOptions(result.items || []);
  } catch {
    // Reference options also come from any browsed or searched cards.
  }
}

/* ------------------------------- thumbnails ------------------------------ */

const thumbQueue: { id: CollectionId; item: Json; generation: number; version: string | null }[] = [];
let thumbWorkers = 0;
const requested = new Set<string>();
export function requestThumb(id: CollectionId, item: Json) {
  const c = state[id];
  const token = `${id}:${c.generation}:${item.asset_id}`;
  if (requested.has(token) || c.thumbs[item.asset_id]) return;
  requested.add(token);
  thumbQueue.push({ id, item, generation: c.generation, version: c.version ?? state.context?.generation ?? null });
  while (thumbWorkers < 3 && thumbQueue.length) {
    thumbWorkers++;
    void drainThumbs().finally(() => thumbWorkers--);
  }
}
async function drainThumbs() {
  while (thumbQueue.length) {
    const { id, item, generation, version } = thumbQueue.shift()!;
    if (generation !== state[id].generation) continue;
    let result: Json;
    try {
      result = await collectionApi(id).thumbnail(item.asset_id, version);
    } catch (error) {
      result = { reason: (error as Error).message };
    }
    if (generation !== state[id].generation) continue;
    if (result.status === "stale") {
      if (id === "library") patchSearch({ status: "Library version changed; refresh the published view." });
      else patchCollection("source", { error: "Saved source contents changed. Return to asset sources and reopen this source.", finished: true });
      continue;
    }
    const payload = result.payload || {};
    const thumb: Thumb = { card: payload.card, presentation: payload.presentation };
    if (result.image) {
      thumb.image = result.image;
      thumb.pixelArt = Boolean(payload.pixel_art_candidate);
    } else {
      const pending = payload.preview?.status === "pending";
      const excluded = payload.preview?.status === "excluded";
      thumb.placeholder = excluded ? "Preview not selected" : pending ? "Preview not generated" : "Preview unavailable";
      thumb.reason = payload.preview?.reason || payload.reason || result.reason || "Requested three-quarter preview unavailable";
      thumb.badge = { label: excluded ? "Preview excluded" : pending ? "Preview pending" : "Preview fault", tone: pending || excluded ? "review" : "fault" };
    }
    patchCollection(id, (c) => ({ thumbs: { ...c.thumbs, [item.asset_id]: thumb } }));
  }
}

/* --------------------------------- detail -------------------------------- */

let detailGeneration = { library: 0, source: 0 };
export async function selectAsset(id: CollectionId, assetId: string, format: string | null = null, view = "three_quarter", moveFocus = true) {
  window.LALPreview?.dispose();
  const generation = ++detailGeneration[id];
  setState((s) => ({ inspector: { ...s.inspector, open: true } }));
  patchCollection(id, (c) => ({
    selected: assetId,
    detail: { assetId, format, view, loading: true, result: c.detail?.assetId === assetId ? c.detail.result : null, error: null, focusToken: (c.detail?.focusToken ?? 0) + (moveFocus ? 1 : 0) },
  }));
  try {
    const result = await collectionApi(id).asset(assetId, format, view, state[id].version ?? state.context?.generation ?? null);
    if (generation !== detailGeneration[id]) return;
    if (!result.payload) throw Error(result.reason || "Asset detail unavailable");
    patchCollection(id, (c) => ({ detail: c.detail && { ...c.detail, loading: false, result } }));
  } catch (error) {
    if (generation === detailGeneration[id]) patchCollection(id, (c) => ({ detail: c.detail && { ...c.detail, loading: false, result: null, error: (error as Error).message } }));
  }
}
export function closeDetail(id: CollectionId = activeCollectionId()) {
  if (id === activeCollectionId()) window.LALPreview?.dispose();
  ++detailGeneration[id];
  patchCollection(id, { selected: null, detail: null });
}
export function setInspectorOpen(open: boolean) {
  if (!open) window.LALPreview?.pause();
  setState((s) => ({ inspector: { ...s.inspector, open } }));
  // Showing the panel again re-resolves the retained selection and its 3D preview.
  const id = activeCollectionId();
  const c = state[id];
  if (open && c.selected && c.detail && !c.detail.loading) void selectAsset(id, c.selected, c.detail.format, c.detail.view, false);
}
export function setInspectorTab(tab: InspectorTab) {
  setState((s) => ({ inspector: { ...s.inspector, tab } }));
}
let widthTimer: ReturnType<typeof setTimeout> | undefined;
export function setInspectorWidth(width: number, persist = false) {
  setState((s) => ({ inspector: { ...s.inspector, width: Math.round(width) } }));
  if (!persist) return;
  clearTimeout(widthTimer);
  widthTimer = setTimeout(() => void api().save_interface_settings(null, Math.round(state.inspector.width)).catch(() => {}), 250);
}

export async function copyText(text: string, message: string) {
  try {
    const result = await api().copy_text(text);
    if (result.status !== "copied") throw Error(result.reason);
    pushToast({ tone: "success", title: "Copied", body: message });
  } catch (error) {
    pushToast({ tone: "fault", title: "Could not copy", body: (error as Error).message });
  }
}

/* ------------------------------ library context -------------------------- */

export async function refreshContext(force = false) {
  if (!state.api) return;
  try {
    const context = await api().context();
    if (context.status === "faulty") throw Error(context.reason);
    const changed = context.generation !== state.context?.generation || context.sources_revision !== state.context?.sources_revision;
    if (changed || force) {
      const phase = state.search.phase;
      let selected = state.library.selected;
      ++searchGeneration;
      ++detailGeneration.library;
      activeSearchSettings = null;
      setState({ context });
      patchSearch({ busy: false, lastSettings: null });
      if (context.visible_asset_ids) {
        const visible = new Set<string>(context.visible_asset_ids);
        patchCollection("library", (c) => ({ items: c.items.filter((item) => visible.has(item.asset_id)), thumbs: {}, generation: searchGeneration, version: context.generation }));
        if (selected && !visible.has(selected)) {
          closeDetail("library");
          selected = null;
        }
      }
      setState((s) => ({
        filters: {
          ...s.filters,
          pack: context.packs.includes(s.filters.pack) ? s.filters.pack : "",
          format: context.formats.includes(s.filters.format) ? s.filters.format : "",
        },
      }));
      if (phase === "browse") await browse(false);
      else if (phase === "search") await search();
      if (selected && activeCollectionId() === "library") await selectAsset("library", selected, null, "three_quarter", false);
    }
    renderCoverage(context);
  } catch (error) {
    pushToast({ tone: "fault", title: "Library refresh failed", body: (error as Error).message });
  }
}
function renderCoverage(context: Json) {
  const source = context.working_coverage || context.coverage;
  const packs = Object.values(source?.packs || {}) as Json[];
  const pending = packs.reduce((n, p) => n + (p.stages?.caption?.pending || 0), 0);
  const failed = packs.reduce((n, p) => n + (p.stages?.caption?.failed || 0), 0);
  setState({ coverage: `${context.coverage?.membership ?? 0} in the library · ${pending} without descriptions · ${failed} description failures` });
}

/* --------------------------------- sources ------------------------------- */

let loadingSources = false;
export async function loadSources() {
  if (!state.api || loadingSources) return;
  loadingSources = true;
  try {
    const result = await api().sources();
    if (result.status === "faulty") throw Error(result.reason);
    const changed = state.sourcesRevision !== result.revision;
    setState({ sources: result.sources || [], sourcesRevision: result.revision });
    updateNotifications(result.notifications || []);
    if (route().page === "processing" && changed) await loadImportFailures();
    if (changed && state.context && result.revision !== state.context.sources_revision) await refreshContext();
  } catch (error) {
    setState({ sourcesMessage: (error as Error).message });
  } finally {
    loadingSources = false;
  }
}
export async function sourceAction(action: string, key: string | null = null, directory: string | null = null, enabled: boolean | null = null) {
  // Scans and processing never invalidate visible cards; library changes arrive through refreshContext.
  try {
    const result = await api().source_action(action, key, directory, enabled);
    if (result.status === "faulty") throw Error(result.reason);
    if (action === "cancel")
      setState((s) => ({ sources: s.sources.map((source) => (source.key === key ? { ...source, operation: { ...source.operation, status: "cancelling", phase: result.reason } } : source)) }));
    setState({ sourcesMessage: result.reason || "" });
    if (["enabled", "remove", "images"].includes(action)) {
      closeDetail("library");
      await refreshContext(true);
    }
    await loadSources();
    return result;
  } catch (error) {
    setState({ sourcesMessage: (error as Error).message });
    if (route().page !== "settings") pushToast({ tone: "fault", title: "Source action failed", body: (error as Error).message });
    await loadSources();
    return { status: "faulty", reason: (error as Error).message };
  }
}
export async function chooseSourceDirectory() {
  const result = await api().choose_source_directory();
  if (result.status === "faulty") setState({ sourcesMessage: result.reason });
  return result.status === "selected" ? (result.directory as string) : null;
}

/* ----------------------------- source browser ---------------------------- */

let sourceGeneration = 0;
export async function openSourceBrowser(key: string) {
  ++detailGeneration.source;
  const generation = ++sourceGeneration;
  setState({ source: { ...emptyCollection("source"), key, generation } });
  await browseSource(generation);
}
export async function browseSource(generation = state.source.generation) {
  const c = state.source;
  if (!c.key || c.loading || c.finished || generation !== c.generation) return;
  patchCollection("source", { loading: true, status: c.items.length ? `Loading more assets · ${c.items.length} shown…` : "Loading saved source contents…" });
  try {
    const result = await api().source_browse(c.key, c.items.length, 40);
    if (generation !== state.source.generation) return;
    if (result.status === "faulty") throw Error(result.reason);
    if (state.source.version && state.source.version !== result.generation) throw Error("Saved source contents changed. Return to asset sources and reopen this source.");
    const append = state.source.items.length > 0;
    patchCollection("source", (s) => ({ items: append ? s.items.concat(result.items) : result.items, version: result.generation, total: result.total_count }));
    const total = result.total_count;
    patchCollection("source", (s) => ({
      finished: s.items.length >= total,
      status: `${total} ${total === 1 ? "saved asset" : "saved assets"}${result.source?.enabled ? "" : " · Disabled in library searches"}`,
      emptyText: result.reason || "This source has no saved assets.",
    }));
  } catch (error) {
    if (generation === state.source.generation)
      patchCollection("source", (s) => ({ finished: true, error: (error as Error).message, status: s.items.length ? `${s.items.length} assets shown · could not load the rest` : "Source contents unavailable." }));
  } finally {
    if (generation === state.source.generation) patchCollection("source", { loading: false });
  }
}

/* ------------------------- importing failures report --------------------- */

let loadingFailures = false;
export async function loadImportFailures() {
  if (!state.api || loadingFailures) return;
  loadingFailures = true;
  setState((s) => ({ failures: { ...s.failures, loading: true } }));
  try {
    const result = await api().importing_failures();
    if (result.status === "faulty") throw Error(result.reason);
    setState({ failures: { loading: false, loaded: true, assets: result.assets || 0, paths: result.paths || [], unavailable: result.unavailable || [], error: null } });
  } catch (error) {
    setState((s) => ({ failures: { ...s.failures, loading: false, loaded: true, error: (error as Error).message } }));
  } finally {
    loadingFailures = false;
  }
}

/* ------------------------------ general settings ------------------------- */

export async function loadGeneralSettings() {
  setState((s) => ({ general: { ...s.general, loading: true, message: "Loading settings…" } }));
  try {
    const result = await api().general_settings();
    if (result.status === "faulty") throw Error(result.reason);
    setState({ general: { loading: false, busy: false, message: "", values: result } });
  } catch (error) {
    setState((s) => ({ general: { ...s.general, loading: false, message: (error as Error).message } }));
  }
}
export async function saveGeneralSettings(budget: string, formats: string[], batch: string) {
  setState((s) => ({ general: { ...s.general, busy: true, message: "Saving…" } }));
  try {
    const result = await api().save_general_settings(budget, formats, batch);
    if (result.status === "faulty") throw Error(result.reason);
    setState({
      general: {
        loading: false, busy: false, values: result,
        message: result.processing_formats.length
          ? `Saved. Storage budget: ${result.storage_budget_gib} GiB. Description batch size: ${result.caption_batch_size}. Selected formats apply to new processing batches.`
          : "Saved. Processing is paused because no formats are selected. Scanning and existing results remain available.",
      },
    });
    await loadSources();
  } catch (error) {
    setState((s) => ({ general: { ...s.general, busy: false, message: (error as Error).message } }));
  }
}

/* -------------------------------- appearance ----------------------------- */

const darkQuery = window.matchMedia("(prefers-color-scheme: dark)");
export function resolvedTheme(appearance = state.appearance) {
  return appearance === "system" ? (darkQuery.matches ? "dark" : "light") : appearance;
}
function applyTheme() {
  document.documentElement.dataset.theme = resolvedTheme();
  document.documentElement.dataset.appearance = state.appearance;
}
darkQuery.addEventListener("change", () => state.appearance === "system" && applyTheme());
export async function setAppearance(appearance: string) {
  const previous = state.appearance;
  setState({ appearance });
  applyTheme();
  try {
    const result = await api().save_interface_settings(appearance, null);
    if (result.status === "faulty") throw Error(result.reason);
  } catch (error) {
    setState({ appearance: previous });
    applyTheme();
    pushToast({ tone: "fault", title: "Appearance not saved", body: (error as Error).message });
  }
}

/* ------------------------------ notifications ---------------------------- */

let notificationKeys: Set<string> | null = null;
function updateNotifications(items: Json[]) {
  const known = notificationKeys;
  notificationKeys = new Set(items.map(notificationKey));
  setState({ notifications: items });
  // Only notices that arrive while the app is open pop up; earlier ones wait under the bell.
  if (known && !state.notificationsOpen)
    for (const item of items) if (!item.read && !known.has(notificationKey(item))) pushToast({ ...notificationContent(item), notification: item });
}
export async function saveNotification(action: string, identifier: string | null = null) {
  const result = await api().notification_action(action, identifier);
  if (result.status === "faulty") {
    pushToast({ tone: "fault", title: "Could not update notifications", body: result.reason });
    return;
  }
  notificationKeys = new Set(result.notifications.map(notificationKey));
  setState({ notifications: result.notifications });
}
export function setNotificationsOpen(open: boolean) {
  if (open === state.notificationsOpen) return;
  setState(open ? { notificationsOpen: true, toasts: [] } : { notificationsOpen: false });
  // Closing the panel marks what was shown as read.
  if (!open && state.notifications.some((item) => !item.read)) void saveNotification("read_all");
}
export async function generateDescriptions(key: string) {
  const source = state.sources.find((item) => item.key === key);
  try {
    const result = await api().source_action("describe", key, null, null);
    if (result.status === "faulty" || result.status === "busy") throw Error(result.reason);
    if (!state.notificationsOpen && route().page !== "processing")
      pushToast({ tone: "info", title: "Generating descriptions", body: `${source?.name || key} · runs in the background. Follow progress under the bell or in Asset processing.` });
  } catch (error) {
    pushToast({ tone: "fault", title: "Could not start descriptions", body: (error as Error).message });
  }
  await loadSources();
}
/** Processing notifications lead to Asset processing, focused on their source. */
export async function openProcessing(key?: string, report?: Json) {
  setNotificationsOpen(false);
  navigate({ page: "processing", focus: key });
  if (report) setState({ runReport: report });
}
export async function notificationAction(action: string, item: Json) {
  if (action === "generate") return generateDescriptions(item.source_key);
  if (action === "view" || action === "report") {
    if (!item.read) await saveNotification("read", item.id);
    return openProcessing(item.source_key, action === "report" ? item : undefined);
  }
  if (action === "dismiss") return saveNotification("dismiss", item.id);
}
export const runningDescriptions = (s: AppState = state) => s.sources.filter(describeActive);
export const processingAttention = (s: AppState) =>
  s.sources.some((source) => source.needs_processing || source.scan_fault || operationActive(source.operation));

/* --------------------------------- toasts -------------------------------- */

let toastId = 0;
export function pushToast(toast: Omit<Toast, "id">) {
  const id = ++toastId;
  setState((s) => ({ toasts: [...s.toasts, { ...toast, id }].slice(-3) }));
  return id;
}
export function dismissToast(id: number) {
  setState((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
}

/* ------------------------------ change polling --------------------------- */

const tokens = { library: null as string | null, sources: null as string | null };
let checking = false;
const workerMessages: Record<string, string> = {
  loading_libraries: "Searching the library… Preparing the search runtime; the window remains available.",
  loading_model: "Searching the library… Loading the search model (first search only); the window remains available.",
};
async function watchChanges() {
  const first = await api().changes();
  if (first.status !== "faulty") Object.assign(tokens, { library: first.library, sources: first.sources });
  // One cheap stat-only poll; library and source data reload only when their token changes.
  setInterval(async () => {
    if (checking) return;
    checking = true;
    try {
      const next = await api().changes();
      if (next.status === "faulty") return;
      const sourcesChanged = next.sources !== tokens.sources;
      const libraryChanged = next.library !== tokens.library;
      if (state.search.busy && workerMessages[next.worker]) patchSearch({ status: workerMessages[next.worker] });
      Object.assign(tokens, { library: next.library, sources: next.sources });
      if (libraryChanged) await refreshContext();
      // Running operations also report worker liveness, which is not a file change.
      if (sourcesChanged || state.sources.some((source) => operationActive(source.operation))) await loadSources();
    } finally {
      checking = false;
    }
  }, 1500);
}

/* --------------------------------- startup ------------------------------- */

export async function start(bridge: Bridge) {
  setState({ api: bridge });
  try {
    const context = await bridge.context();
    if (context.status === "faulty") throw Error(context.reason);
    setState({ context, ready: true });
    patchCollection("library", { version: context.generation });
    renderCoverage(context);
    await loadSources();
    void watchChanges();
    if (context.managed_sources) await sourceAction("scan");
  } catch (error) {
    setState({ startupError: (error as Error).message, ready: true });
  }
}
