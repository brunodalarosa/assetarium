// Application state and actions, ported from the pre-React ui/app.js. React
// subscribes through useApp; verification scripts drive the same actions via
// window.lal. The backend stays the authority for availability, faults,
// notifications and processing: this file only presents its answers.
import { useSyncExternalStore } from "react";
import { type AssetApi, type Bridge, type Json, libraryApi, sourceApi } from "./api";
import { describeActive, notificationContent, notificationKey, operationActive, plural, type Tone } from "./format";

export type Page = "home" | "library" | "collections" | "collection" | "processing" | "settings" | "sources";
export type SettingsTab = "general";
export interface Route {
  page: Page;
  tab?: SettingsTab;
  key?: string;
  /** Asset sources: the folder (inside library folder `key`) shown in the grid. */
  path?: string;
  /** Asset processing: the source a notification pointed at. */
  focus?: string;
}
/** A card grid with its own selection and inspection: Home, the Asset sources tab or an open collection. */
export type GridId = "library" | "source" | "collection";
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
  /** A collection member that can no longer be read; inspection shows its entry and reason. */
  unavailable?: Json;
}
export interface Grid {
  id: GridId;
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
  actions?: { label: string; run: () => void }[];
}
/** The open collection: its facts and the in-collection search; its cards live in the "collection" grid. */
export interface CollectionView {
  id: string | null;
  name: string;
  description: string;
  updatedAt: string;
  count: number;
  unavailable: number;
  loading: boolean;
  error: string | null;
  query: string;
  mode: string;
  phase: "all" | "search";
  busy: boolean;
  search: Json | null;
  /** Where each member opens (library or its source), kept across searches that show a subset. */
  members: Record<string, Json>;
}
export interface MenuRequest {
  id: number;
  kind: "asset" | "collection" | "export" | "folder" | "file";
  x: number;
  y: number;
  grid?: GridId;
  item: Json;
  returnFocus?: HTMLElement | null;
  /** Opened with the Menu key or Shift+F10: no pointer-origin animation. */
  keyboard?: boolean;
}
export interface ConfirmRequest {
  title: string;
  body: string;
  confirmLabel: string;
  /** Without run, the dialog only informs and offers Close. */
  run?: () => Promise<unknown>;
  /** Deletions are "danger" (the default); other confirmations are "neutral". */
  tone?: "danger" | "neutral";
}
/** The Asset sources tab (decision 0023): the tree, the shown folder and its filters. */
export interface SourcesView {
  tree: Json | null;
  loading: boolean;
  error: string | null;
  key: string | null;
  path: string;
  expanded: Record<string, boolean>;
  types: string[];
  states: string[];
  sort: "name" | "added" | "pending" | "assets";
  showFiles: boolean;
  list: boolean;
  /** What inspection shows: the selected asset, or the selected folder, pack or library folder. */
  panel: "asset" | "folder";
  files: Json[];
  counts: Json | null;
  /** Ctrl- or Shift-clicked assets for queue actions, Add to collection and Exclude. */
  picked: string[];
  pickAnchor: string | null;
}
export interface CreateRequest {
  assetIds: string[];
  sourceKey: string | null;
  name?: string;
}
export const SETUP_STEPS = ["welcome", "blender", "formats", "storage", "descriptions", "batch", "review"] as const;
export type SetupStep = (typeof SETUP_STEPS)[number];
/** What the wizard will save; nothing is written until Save (or Skip setup, which saves nothing). */
export interface SetupDraft {
  blenderPath: string;
  confirmRerender: boolean;
  engineHint: string;
  formats: string[];
  budget: string;
  descriptionsEnabled: boolean;
  engine: string;
  serverUrl: string;
  serverModel: string;
  searchDevice: string;
  batch: string;
  skipped: SetupStep[];
}
export interface SetupState {
  open: boolean;
  step: number;
  loading: boolean;
  error: string | null;
  info: Json | null;
  env: Json | null;
  blender: Json | null;
  check: Json | null;
  checking: boolean;
  storage: Json | null;
  measuring: boolean;
  server: Json | null;
  testing: boolean;
  saving: boolean;
  result: Json | null;
  draft: SetupDraft;
  /** Agent setup (decision 0016): the backend's panel state, shown once the user chose the agent path. */
  agent: Json | null;
  agentMode: boolean;
  agentBusy: string | null;
  /** Saved values the review starts from after an agent set them; only what the user changes is saved as theirs. */
  baseline: SetupDraft | null;
}
export interface BlenderState {
  report: Json | null;
  path: string;
  check: Json | null;
  checking: boolean;
  confirmRerender: boolean;
  /** The picker is open: always while no usable Blender is saved, else after Change Blender. */
  editing: boolean;
  saving: boolean;
  message: string;
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
  library: Grid;
  source: Grid;
  collection: Grid;
  collectionView: CollectionView;
  collections: { items: Json[]; total: number; loading: boolean; loaded: boolean; error: string | null; query: string };
  /** Batch removal in the open collection: cards toggle instead of opening inspection. */
  selection: { active: boolean; ids: string[]; anchor: string | null };
  menu: MenuRequest | null;
  confirm: ConfirmRequest | null;
  create: CreateRequest | null;
  knownTags: Json[];
  inspector: { open: boolean; width: number; tab: InspectorTab };
  sourcesView: SourcesView;
  /** The processing queue (decision 0023); null until first loaded. */
  queue: Json | null;
  sources: Json[];
  /** False until the first sources answer (or fault), so "no sources" is never shown early. */
  sourcesLoaded: boolean;
  sourcesRevision: string | null;
  sourcesMessage: string;
  /** Why the source list itself could not be loaded; the sources are not gone. */
  sourcesError: string | null;
  notifications: Json[];
  notificationsOpen: boolean;
  toasts: Toast[];
  failures: { loading: boolean; assets: number; paths: string[]; unavailable: Json[]; error: string | null; loaded: boolean };
  general: { loading: boolean; busy: boolean; message: string; values: Json | null };
  /** Rendering (decision 0022): device, renders at a time, memory and the speed test. */
  render: { loading: boolean; busy: boolean; message: string; values: Json | null };
  setup: SetupState;
  /** Settings → General → Search: the installed-runtime checklist per search device (read only). */
  searchCheck: { checking: boolean; devices: Json | null; error: string | null };
  /** Settings → General → Blender installation: its own choice and check, saved on its own. */
  blender: BlenderState;
  appearance: string;
  runReport: Json | null;
  imageBackground: string;
  coverage: string;
  /** The search worker's phase (desktop `changes`): it prepares libraries at startup. */
  worker: string;
  /** Thumbnail and cover requests queued or in flight, for the activity indicator. */
  previews: number;
}

const emptyGrid = (id: GridId): Grid => ({
  id, key: null, items: [], thumbs: {}, version: null, generation: 0, selected: null, detail: null,
  total: 0, offset: 0, loading: false, finished: false, status: "", error: null, emptyText: "",
});
function emptyCollectionView(): CollectionView {
  return { id: null, name: "", description: "", updatedAt: "", count: 0, unavailable: 0, loading: false, error: null, query: "", mode: "combined", phase: "all", busy: false, search: null, members: {} };
}
function emptySourcesView(): SourcesView {
  return { tree: null, loading: false, error: null, key: null, path: "", expanded: {}, types: [], states: [], sort: "name",
    showFiles: true, list: false, panel: "asset", files: [], counts: null, picked: [], pickAnchor: null };
}
const emptyBlender = (): BlenderState => ({ report: null, path: "", check: null, checking: false, confirmRerender: false, editing: false, saving: false, message: "" });
function emptySetup(): SetupState {
  return {
    open: false, step: 0, loading: false, error: null, info: null, env: null, blender: null, check: null, checking: false,
    storage: null, measuring: false, server: null, testing: false, saving: false, result: null,
    agent: null, agentMode: false, agentBusy: null, baseline: null,
    draft: { blenderPath: "", confirmRerender: false, engineHint: "", formats: [], budget: "", descriptionsEnabled: true, engine: "builtin", serverUrl: "", serverModel: "", searchDevice: "cuda", batch: "8", skipped: [] },
  };
}
const idleSearch: SearchState = {
  phase: "idle", busy: false, title: "", status: "", statusTitle: "", error: null, lastSettings: null,
  candidateNote: false, queryUsed: "", modeUsed: "combined", count: 0,
};

const boot = window.LAL_BOOT || { appearance: "system", inspector_width: 440 };
let state: AppState = {
  api: null, ready: false, startupError: null, context: null,
  history: [{ page: "home" }], historyIndex: 0,
  query: "", filters: { ...DEFAULT_FILTERS }, filtersOpen: false, search: idleSearch, referenceOptions: [],
  library: emptyGrid("library"), source: emptyGrid("source"), collection: emptyGrid("collection"),
  collectionView: emptyCollectionView(),
  collections: { items: [], total: 0, loading: false, loaded: false, error: null, query: "" },
  selection: { active: false, ids: [], anchor: null }, menu: null, confirm: null, create: null, knownTags: [],
  inspector: { open: false, width: boot.inspector_width, tab: "overview" },
  sourcesView: emptySourcesView(),
  queue: null,
  sources: [], sourcesLoaded: false, sourcesRevision: null, sourcesMessage: "", sourcesError: null, notifications: [], notificationsOpen: false, toasts: [],
  failures: { loading: false, assets: 0, paths: [], unavailable: [], error: null, loaded: false },
  general: { loading: false, busy: false, message: "", values: null },
  render: { loading: false, busy: false, message: "", values: null },
  setup: emptySetup(),
  searchCheck: { checking: false, devices: null, error: null },
  blender: emptyBlender(),
  appearance: boot.appearance, runReport: null, imageBackground: "checker", coverage: "",
  worker: "not_started", previews: 0,
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
function patchGrid(id: GridId, patch: Partial<Grid> | ((current: Grid) => Partial<Grid>)) {
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
export const activeGridId = (s: AppState = state): GridId => {
  const page = s.history[s.historyIndex].page;
  return page === "sources" ? "source" : page === "collection" ? "collection" : "library";
};
/** Collection members open through the library, or through their source when the library does not hold them. */
export function gridApi(id: GridId, assetId: string | null = null): AssetApi {
  if (id === "collection") {
    const target = assetId ?? state.collection.selected;
    const item = target ? state.collectionView.members[target] : null;
    return item && !item.in_library && item.source_key ? sourceApi(api(), item.source_key) : libraryApi(api());
  }
  return id === "source" && state.source.key ? sourceApi(api(), state.source.key) : libraryApi(api());
}
/** Stale checks compare one publication; collection members span several, so they skip it. */
// The Asset sources grid reads a folder's working data, which has no published version to compare.
export const gridVersion = (s: AppState, id: GridId): string | null => (id === "collection" || id === "source" ? null : (s[id].version ?? s.context?.generation ?? null));

/* ------------------------------- navigation ------------------------------ */

const sameRoute = (a: Route, b: Route) => a.page === b.page && a.tab === b.tab && a.key === b.key && (a.path ?? "") === (b.path ?? "");
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
  if (next.page === "settings") void Promise.all([loadGeneralSettings(), loadRenderSettings(), loadSources(), loadSetupState().catch(() => undefined), loadBlenderInstallation()]);
  if (next.page === "processing") void Promise.all([loadSources(), loadImportFailures()]);
  if (next.page === "sources") void enterSources(next, previous);
  if (next.page === "collections") void loadCollections();
  if (state.selection.active) cancelSelection();
  if (next.page === "collection" && next.key) {
    if (state.collectionView.id !== next.key) return void openCollectionView(next.key);
    void loadCollection(false);
  }
  // Returning to a grid re-resolves its selection so a paused 3D preview remounts.
  const id = activeGridId();
  const selected = state[id].selected;
  if (selected && state.inspector.open && next.page !== "sources")
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

function showResults(id: GridId, items: Json[], generation: number, append = false) {
  patchGrid(id, (c) => ({ items: append ? c.items.concat(items) : items, thumbs: append ? c.thumbs : {}, generation }));
  if (id === "library") rememberReferenceOptions(items);
}

export async function browse(resetPage = true) {
  activeSearchSettings = null;
  if (resetPage) patchGrid("library", { offset: 0 });
  const generation = ++searchGeneration;
  patchSearch({ phase: "browse", busy: false, lastSettings: null, candidateNote: false, error: null, title: "Library assets", status: "Loading this page…", queryUsed: "", modeUsed: state.filters.mode });
  patchGrid("library", { loading: true });
  try {
    const result = await api().browse(filterArgs(), state.library.offset, 40);
    if (generation !== searchGeneration) return;
    if (result.status === "faulty") throw Error(result.reason);
    if (result.generation !== state.context?.generation) throw Error("Published version changed; refreshing context.");
    showResults("library", result.items, generation);
    patchGrid("library", { total: result.total_count, version: result.generation });
    patchSearch({ status: `${result.total_count} matching assets · thumbnails load as they become visible`, count: result.total_count });
  } catch (error) {
    if (generation === searchGeneration) patchSearch({ error: (error as Error).message, status: "Browse unavailable. Refresh the published view to load its current version." });
  } finally {
    if (generation === searchGeneration) patchGrid("library", { loading: false });
  }
}
export function pageBrowse(direction: 1 | -1) {
  patchGrid("library", (c) => ({ offset: Math.max(0, c.offset + direction * 40) }));
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
  patchGrid("library", { loading: true });
  try {
    const result = await api().search(args);
    if (generation !== searchGeneration) return;
    const payload = result.payload || {};
    if (result.is_error || result.status === "faulty" || payload.status === "faulty") throw Error(payload.reason || result.reason || "Search failed");
    if (payload.generation !== state.context?.generation) throw Error("Published version changed; refresh the view.");
    showResults("library", payload.results, generation);
    patchGrid("library", { version: payload.generation, total: payload.results.length });
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
      patchGrid("library", { loading: false });
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
  patchGrid("library", { items: [], thumbs: {}, total: 0, offset: 0, loading: false });
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

const thumbQueue: { id: GridId; item: Json; generation: number; version: string | null }[] = [];
let thumbWorkers = 0;
let thumbsInFlight = 0;
/** Concurrent thumbnail requests (at most 3); read by verification scripts. */
export const thumbnailWorkers = () => thumbWorkers;
function syncPreviews() {
  const previews = thumbQueue.length + thumbsInFlight + coverQueue.length + coverWorkers;
  if (previews !== state.previews) setState({ previews });
}
const requested = new Set<string>();
export function requestThumb(id: GridId, item: Json) {
  const c = state[id];
  const token = `${id}:${c.generation}:${item.asset_id}`;
  if (requested.has(token) || c.thumbs[item.asset_id]) return;
  requested.add(token);
  if (item.availability === "unavailable") {
    // Nothing can be read for it; the card says why instead of asking the backend.
    patchGrid(id, (g) => ({ thumbs: { ...g.thumbs, [item.asset_id]: { placeholder: "Unavailable", reason: item.reason, badge: { label: "Unavailable", tone: "fault" } } } }));
    return;
  }
  thumbQueue.push({ id, item, generation: c.generation, version: gridVersion(state, id) });
  syncPreviews();
  while (thumbWorkers < 3 && thumbQueue.length) {
    thumbWorkers++;
    void drainThumbs().finally(() => thumbWorkers--);
  }
}
async function drainThumbs() {
  while (thumbQueue.length) {
    const { id, item, generation, version } = thumbQueue.shift()!;
    if (generation !== state[id].generation) {
      syncPreviews();
      continue;
    }
    let result: Json;
    thumbsInFlight++;
    try {
      result = await gridApi(id, item.asset_id).thumbnail(item.asset_id, version);
    } catch (error) {
      result = { reason: (error as Error).message };
    } finally {
      thumbsInFlight--;
      syncPreviews();
    }
    if (generation !== state[id].generation) continue;
    if (result.status === "stale") {
      if (id === "library") patchSearch({ status: "Library version changed; refresh the published view." });
      else patchGrid("source", { error: "This folder changed while it was shown; it is loaded again.", finished: true });
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
    patchGrid(id, (c) => ({ thumbs: { ...c.thumbs, [item.asset_id]: thumb } }));
  }
}

/* --------------------------------- detail -------------------------------- */

let detailGeneration = { library: 0, source: 0, collection: 0 };
export async function selectAsset(id: GridId, assetId: string, format: string | null = null, view = "three_quarter", moveFocus = true) {
  window.LALPreview?.dispose();
  if (id === "source" && state.sourcesView.panel !== "asset") setState((s) => ({ sourcesView: { ...s.sourcesView, panel: "asset" } }));
  const generation = ++detailGeneration[id];
  setState((s) => ({ inspector: { ...s.inspector, open: true } }));
  const missing = id === "collection" ? state.collection.items.find((item) => item.asset_id === assetId && item.availability === "unavailable") : null;
  if (missing) {
    patchGrid(id, (c) => ({ selected: assetId, detail: { assetId, format, view, loading: false, result: null, error: null, unavailable: missing, focusToken: (c.detail?.focusToken ?? 0) + (moveFocus ? 1 : 0) } }));
    return;
  }
  patchGrid(id, (c) => ({
    selected: assetId,
    detail: { assetId, format, view, loading: true, result: c.detail?.assetId === assetId ? c.detail.result : null, error: null, focusToken: (c.detail?.focusToken ?? 0) + (moveFocus ? 1 : 0) },
  }));
  try {
    const result = await gridApi(id, assetId).asset(assetId, format, view, gridVersion(state, id));
    if (generation !== detailGeneration[id]) return;
    if (!result.payload) throw Error(result.reason || "Asset detail unavailable");
    patchGrid(id, (c) => ({ detail: c.detail && { ...c.detail, loading: false, result } }));
  } catch (error) {
    if (generation === detailGeneration[id]) patchGrid(id, (c) => ({ detail: c.detail && { ...c.detail, loading: false, result: null, error: (error as Error).message } }));
  }
}
export function closeDetail(id: GridId = activeGridId()) {
  if (id === activeGridId()) window.LALPreview?.dispose();
  ++detailGeneration[id];
  patchGrid(id, { selected: null, detail: null });
}
export function setInspectorOpen(open: boolean) {
  if (!open) window.LALPreview?.pause();
  setState((s) => ({ inspector: { ...s.inspector, open } }));
  // Showing the panel again re-resolves the retained selection and its 3D preview.
  const id = activeGridId();
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

/** Select the original file in Explorer: the format open in the inspector for this asset, else its primary file. */
export async function revealAsset(id: GridId, assetId: string) {
  const detail = state[id].detail;
  const format = detail?.assetId === assetId ? detail.format : null;
  try {
    const result = await gridApi(id, assetId).reveal(assetId, format);
    if (result.status !== "revealed") throw Error(result.reason);
  } catch (error) {
    pushToast({ tone: "fault", title: "Could not show in Explorer", body: (error as Error).message });
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
      covers.clear();
      patchSearch({ busy: false, lastSettings: null });
      if (context.visible_asset_ids) {
        const visible = new Set<string>(context.visible_asset_ids);
        patchGrid("library", (c) => ({ items: c.items.filter((item) => visible.has(item.asset_id)), thumbs: {}, generation: searchGeneration, version: context.generation }));
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
      if (selected && activeGridId() === "library") await selectAsset("library", selected, null, "three_quarter", false);
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
    setState({ sources: result.sources || [], sourcesLoaded: true, sourcesRevision: result.revision, sourcesError: null });
    updateNotifications(result.notifications || []);
    if (route().page === "processing" && changed) await loadImportFailures();
    if (changed && state.context && result.revision !== state.context.sources_revision) await refreshContext();
  } catch (error) {
    setState({ sourcesError: (error as Error).message, sourcesLoaded: true });
  } finally {
    loadingSources = false;
  }
}
export async function sourceAction(action: string, key: string | null = null, directory: string | null = null, enabled: boolean | null = null) {
  // Scans and processing never invalidate visible cards; library changes arrive through refreshContext.
  // The switch shows the choice at once, so a second click before the reload is not a repeat; the reload corrects it.
  if (action === "enabled" && enabled !== null) setState((s) => ({ sources: s.sources.map((source) => (source.key === key ? { ...source, enabled } : source)) }));
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
/** Excluded folders and duplicate export folder answers (decision 0019); each saved change rescans the source. */
export async function sourceFolders(change: "exclusions" | "export" | "undo" | "textures" | "textures-undo", key: string, value: string[] | string | null, decision = "") {
  try {
    const result = change === "exclusions" ? await api().source_exclusions(key, value as string[])
      : change === "export" ? await api().source_export(key, value as string, decision)
      : change === "textures" ? await api().source_textures(key, value as string | null, decision === "single")
      : change === "textures-undo" ? await api().source_textures_undo(key)
      : await api().source_export_undo(key, value as string);
    if (result.status === "faulty") throw Error(result.reason);
    setState({ sourcesMessage: result.reason || "" });
    closeDetail("library");
    await refreshContext(true);
    await loadSources();
    return result;
  } catch (error) {
    setState({ sourcesMessage: (error as Error).message });
    await loadSources();
    return { status: "faulty", reason: (error as Error).message };
  }
}
export async function chooseSourceDirectory() {
  const result = await api().choose_source_directory();
  if (result.status === "faulty") setState({ sourcesMessage: result.reason });
  return result.status === "selected" ? (result.directory as string) : null;
}

/* ---------------------------- asset sources tab -------------------------- */

const patchSources = (patch: Partial<SourcesView> | ((current: SourcesView) => Partial<SourcesView>)) =>
  setState((s) => ({ sourcesView: { ...s.sourcesView, ...(typeof patch === "function" ? patch(s.sourcesView) : patch) } }));
let treeGeneration = 0;
/** Library folders → bundles → packs → folders, with counts and what needs the owner (read from saved data). */
export async function loadLibraryTree() {
  if (!state.api) return;
  const generation = ++treeGeneration;
  patchSources({ loading: true });
  try {
    const tree = await api().library_tree();
    if (generation !== treeGeneration) return;
    if (tree.status === "faulty") throw Error(tree.reason);
    patchSources({ tree, error: null });
  } catch (error) {
    if (generation === treeGeneration) patchSources({ error: (error as Error).message });
  } finally {
    if (generation === treeGeneration) patchSources({ loading: false });
  }
}
async function enterSources(next: Route, previous: Route) {
  if (!state.sourcesView.tree) await loadLibraryTree();
  else void loadLibraryTree();
  const folders: Json[] = state.sourcesView.tree?.folders || [];
  const key = next.key ?? state.sourcesView.key ?? folders[0]?.key ?? null;
  if (!key) return;
  const path = next.key ? next.path ?? "" : state.sourcesView.path;
  if (key !== state.sourcesView.key || path !== state.sourcesView.path || previous.page !== "sources" || !state.source.items.length) await showFolder(key, path, next.focus);
  else if (next.focus) void selectAsset("source", next.focus, null, "three_quarter", true);
}
/** Open the Asset sources tab at a folder (and an asset in it). */
export function openSources(key?: string, path = "", assetId?: string) {
  navigate({ page: "sources", key, path, focus: assetId });
}
/** Show in pack: a search result opens the Asset sources tab with its folder expanded and the asset selected. */
export async function showInPack(assetId: string) {
  try {
    const found = await api().library_locate(assetId);
    if (found.status === "faulty") throw Error(found.reason);
    openSources(found.key, found.path, assetId);
  } catch (error) {
    pushToast({ tone: "fault", title: "Not in a library folder", body: (error as Error).message });
  }
}
const ancestors = (key: string, path: string) => {
  const parts = path ? path.split("/") : [];
  return [key + ":", ...parts.map((_, i) => key + ":" + parts.slice(0, i + 1).join("/"))];
};
let folderGeneration = 0;
export async function showFolder(key: string, path = "", focus?: string) {
  ++detailGeneration.source;
  const generation = ++folderGeneration;
  const previous = state.sourcesView.key;
  const changedFolder = key !== previous;
  patchSources((v) => ({ key, path, panel: focus ? "asset" : v.panel, files: [], counts: null, picked: [], pickAnchor: null,
    expanded: { ...v.expanded, ...Object.fromEntries(ancestors(key, path).slice(0, -1).map((id) => [id, true])) } }));
  setState({ source: { ...emptyGrid("source"), key, generation } });
  // "+N new" counts from your last visit: leaving a library folder marks what you saw there as seen.
  if (changedFolder && previous) void api().library_visit(previous).catch(() => undefined);
  await loadFolderItems(generation);
  if (focus && generation === folderGeneration) void selectAsset("source", focus, null, "three_quarter", true);
}
export async function loadFolderItems(generation = state.source.generation) {
  const c = state.source, view = state.sourcesView;
  if (!c.key || c.loading || c.finished || generation !== c.generation) return;
  patchGrid("source", { loading: true, status: c.items.length ? `Loading more · ${c.items.length} shown…` : "Loading this folder…" });
  try {
    const offset = c.items.length + view.files.length;
    const result = await api().library_items(c.key, view.path, offset, 80, { types: view.types, states: view.states }, view.showFiles);
    if (generation !== state.source.generation) return;
    if (result.status === "faulty") throw Error(result.reason);
    const assets = result.items.filter((item: Json) => !item.file), files = result.items.filter((item: Json) => item.file);
    patchGrid("source", (s) => ({ items: s.items.concat(assets), total: result.total }));
    patchSources((v) => ({ files: v.files.concat(files), counts: result.counts }));
    patchGrid("source", (s) => ({
      finished: s.items.length + state.sourcesView.files.length >= result.total,
      status: plural(result.assets, "asset", "assets") + (result.files ? ` · ${plural(result.files, "other file", "other files")}` : ""),
      emptyText: view.types.length || view.states.length ? "Nothing here matches these filters." : "No assets in this folder.",
    }));
  } catch (error) {
    if (generation === state.source.generation)
      patchGrid("source", (s) => ({ finished: true, error: (error as Error).message, status: s.items.length ? `${s.items.length} shown · could not load the rest` : "This folder could not be read." }));
  } finally {
    if (generation === state.source.generation) patchGrid("source", { loading: false });
  }
}
/** Reload the shown folder in place after a scan or a finished item: states update, nothing jumps. */
async function refreshFolder() {
  const s = state.sourcesView;
  if (!s.key || !state.api) return;
  try {
    const shown = Math.max(80, state.source.items.length + s.files.length);
    const result = await api().library_items(s.key, s.path, 0, Math.min(200, shown), { types: s.types, states: s.states }, s.showFiles);
    if (result.status === "faulty" || state.sourcesView.key !== s.key || state.sourcesView.path !== s.path) return;
    const assets = result.items.filter((item: Json) => !item.file), files = result.items.filter((item: Json) => item.file);
    // Thumbnails of assets whose state changed are asked for again (a finished preview fades in).
    const before: Record<string, string> = Object.fromEntries(state.source.items.map((item: Json) => [item.asset_id, item.state]));
    for (const item of assets) if (before[item.asset_id] !== item.state) requested.delete(`source:${state.source.generation}:${item.asset_id}`);
    patchGrid("source", (g) => ({ items: assets, total: result.total, finished: assets.length + files.length >= result.total,
      thumbs: Object.fromEntries(Object.entries(g.thumbs).filter(([id]) => before[id] === assets.find((a: Json) => a.asset_id === id)?.state)) }));
    patchSources({ files, counts: result.counts });
  } catch {
    /* The next change poll tries again. */
  }
}
export function setSourcesFilter(patch: Partial<Pick<SourcesView, "types" | "states" | "sort" | "showFiles" | "list">>) {
  patchSources(patch);
  if (state.sourcesView.key && ("types" in patch || "states" in patch || "showFiles" in patch)) void showFolder(state.sourcesView.key, state.sourcesView.path);
}
export function toggleFolder(id: string, open?: boolean) {
  patchSources((v) => ({ expanded: { ...v.expanded, [id]: open ?? !v.expanded[id] } }));
}
export function expandAll(key: string, open: boolean) {
  const folder = (state.sourcesView.tree?.folders || []).find((f: Json) => f.key === key);
  patchSources((v) => ({ expanded: { ...v.expanded, ...Object.fromEntries((folder?.nodes || []).map((n: Json) => [key + ":" + n.path, open])) } }));
}
/** Click a folder or pack: show it in the grid and its panel in inspection. */
export function inspectFolder(key: string, path: string) {
  patchSources((v) => ({ panel: "folder", expanded: { ...v.expanded, [key + ":" + path]: true } }));
  setState((s) => ({ inspector: { ...s.inspector, open: true } }));
  if (key !== state.sourcesView.key || path !== state.sourcesView.path) navigate({ page: "sources", key, path });
}
export function pickAsset(assetId: string, range: boolean) {
  const items = state.source.items.map((item: Json) => item.asset_id);
  patchSources((v) => {
    if (range && v.pickAnchor) {
      const [a, b] = [items.indexOf(v.pickAnchor), items.indexOf(assetId)].sort((x, y) => x - y);
      return { picked: [...new Set([...v.picked, ...items.slice(a, b + 1)])] };
    }
    return { picked: v.picked.includes(assetId) ? v.picked.filter((id) => id !== assetId) : [...v.picked, assetId], pickAnchor: assetId };
  });
}
export const clearPicked = () => patchSources({ picked: [], pickAnchor: null });
/** Folder and pack answers (Make this a pack, Merge, image kinds, exclusions, Forget missing); most rescan. */
export async function folderAction(action: string, key: string, path = "", value: Json = null) {
  try {
    const result = await api().folder_action(action, key, path, value);
    if (result.status === "faulty") throw Error(result.reason);
    const told: Record<string, string> = {
      make_pack: "Saved as a pack; scanning again.", merge: "Merged into its parent pack; scanning again.", clear_pack: "Pack choice removed; scanning again.",
      image_kind: "Saved; scanning again.", exclude: "Folder excluded; scanning again. Nothing on disk is deleted.", include: "Folder included again; scanning again.",
      rename_pack: "Pack renamed.", forget_missing: `${plural(result.forgotten || 0, "missing asset", "missing assets")} forgotten.`,
    };
    pushToast({ tone: "info", title: told[action] || "Saved.", body: "" });
    await loadSources();
    await loadLibraryTree();
    if (state.sourcesView.key) void showFolder(state.sourcesView.key, state.sourcesView.path);
    return result;
  } catch (error) {
    pushToast({ tone: "fault", title: "Not saved", body: (error as Error).message });
    return { status: "faulty", reason: (error as Error).message };
  }
}
/** Show in Explorer, open with the default app, or copy the path of a library file or folder. */
export async function pathAction(action: "reveal" | "open" | "copy", key: string, relative = "") {
  try {
    const result = await api().path_action(action, key, relative);
    if (result.status === "faulty") throw Error(result.reason);
    if (action === "copy") pushToast({ tone: "info", title: "Path copied", body: "" });
  } catch (error) {
    pushToast({ tone: "fault", title: action === "reveal" ? "Could not show it in Explorer" : action === "open" ? "Could not open it" : "Could not copy the path", body: (error as Error).message });
  }
}
/** Add a library folder; one inside a library folder is refused, with Show it. One around library folders replaces them. */
export async function addLibraryFolder(directory: string) {
  try {
    const result = await api().source_action("add", null, directory, null);
    if (result.status === "faulty") {
      if (result.covered_by) {
        const key = result.covered_by as string;
        pushToast({ tone: "info", title: "Already covered", body: result.reason, actions: [{ label: "Show it", run: () => openSources(key, "") }] });
        return result;
      }
      throw Error(result.reason);
    }
    const replaced: string[] = result.replaced || [];
    pushToast({ tone: "success", title: "Library folder added", body: replaced.length
      ? `It replaces ${replaced.join(", ")}; their assets keep their IDs and results. Scanning now; nothing is processed until you ask.`
      : "Scanning now; nothing is processed until you ask." });
    await loadSources();
    await loadLibraryTree();
    const added = (state.sourcesView.tree?.folders || []).find((f: Json) => f.path.toLowerCase() === directory.toLowerCase().replace(/[\\/]+$/, ""));
    openSources(added?.key ?? state.sourcesView.key ?? undefined, "");
    return result;
  } catch (error) {
    pushToast({ tone: "fault", title: "Folder not added", body: (error as Error).message });
    return { status: "faulty", reason: (error as Error).message };
  }
}
/** A pack's cover image, read from its own preview file (a small thumbnail), or null. */
export async function libraryCover(key: string, relative: string): Promise<string | null> {
  try {
    const result = await api().library_cover(key, relative);
    return result.status === "ready" ? (result.image as string) : null;
  } catch {
    return null;
  }
}
/** Make previews for a folder, pack or picked assets: it starts at once or waits in line (decision 0023). */
export async function makePreviews(scope: { key: string; path?: string; asset_ids?: string[] }, count = 0) {
  return queueAction("previews", scope, count);
}
export async function makeDescriptions(scope: { key: string; path?: string; asset_ids?: string[] }, count = 0) {
  return queueAction("descriptions", scope, count);
}
export async function queueAction(action: "previews" | "descriptions", scope: Json, count = 0, confirmed = false): Promise<Json> {
  try {
    const result = await api().queue_add(action, scope, confirmed);
    if (result.status === "faulty") throw Error(result.reason);
    if (result.status === "confirm") {
      // Over 30 minutes, or the storage budget would be reached: ask first with the estimate.
      askConfirm({ title: result.title, body: result.body, confirmLabel: result.confirm_label, tone: "neutral",
        run: () => queueAction(action, scope, count, true) });
      return result;
    }
    const undo = result.undo ? [{ label: "Undo", run: () => void api().queue_remove(result.item.id).then(loadQueue) }] : undefined;
    pushToast({ tone: "info", title: result.title, body: result.body, actions: undo });
    void loadQueue();
    return result;
  } catch (error) {
    pushToast({ tone: "fault", title: action === "previews" ? "Previews not started" : "Descriptions not started", body: (error as Error).message });
    return { status: "faulty", reason: (error as Error).message };
  }
}
/** The processing queue (Running, Up next, Blocked, Recorded failures, Recent). */
export async function loadQueue() {
  if (!state.api) return;
  try {
    const queue = await api().queue_state();
    if (queue.status !== "faulty") setState({ queue });
  } catch {
    /* The Processing tab shows its own error on its next load. */
  }
}
export async function queueControl(action: string, id: string | null = null, value: Json = null) {
  try {
    const result = await api().queue_control(action, id, value);
    if (result.status === "faulty") throw Error(result.reason);
    if (result.queue) setState({ queue: result.queue });
    else void loadQueue();
    return result;
  } catch (error) {
    pushToast({ tone: "fault", title: "Queue not changed", body: (error as Error).message });
    return { status: "faulty", reason: (error as Error).message };
  }
}
export function openFolderMenu(item: Json, x: number, y: number, returnFocus: HTMLElement | null = null, keyboard = false) {
  setState({ menu: { id: ++menuId, kind: item.file ? "file" : "folder", x, y, item, returnFocus, keyboard } });
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
export interface DescriptionSettings {
  enabled: boolean;
  engine: string;
  server: { url: string; model: string };
}
export async function saveGeneralSettings(budget: string, formats: string[], batch: string, descriptions?: DescriptionSettings, searchDevice?: string, searchThreads?: string) {
  const previousDevice = state.general.values?.search_device;
  setState((s) => ({ general: { ...s.general, busy: true, message: "Saving…" } }));
  try {
    const result = await api().save_general_settings(budget, formats, batch, descriptions?.enabled ?? null, descriptions?.engine ?? null, descriptions?.server ?? null, searchDevice ?? null, searchThreads ?? null);
    if (result.status === "faulty") throw Error(result.reason);
    const described = !result.descriptions_enabled ? " Descriptions are off; existing descriptions are kept."
      : result.description_engine === "local-server" ? " Descriptions use the local model server." : ` Description batch size: ${result.caption_batch_size}.`;
    const searched = previousDevice && previousDevice !== result.search_device
      ? ` Search now runs on the ${result.search_device === "cpu" ? "CPU" : "NVIDIA GPU"}: run the search check again, then Make previews to rebuild search data.` : "";
    setState({
      general: {
        loading: false, busy: false, values: result,
        message: result.processing_formats.length
          ? `Saved. Storage budget: ${result.storage_budget_gib} GiB.${described}${searched} Selected formats apply to new processing batches.`
          : `Saved. Processing is paused because no formats are selected. Scanning and existing results remain available.${searched}`,
      },
    });
    await Promise.all([loadSources(), loadRenderSettings()]);
  } catch (error) {
    setState((s) => ({ general: { ...s.general, busy: false, message: (error as Error).message } }));
  }
}

/* -------------------------------- rendering ------------------------------ */

export async function loadRenderSettings() {
  setState((s) => ({ render: { ...s.render, loading: !s.render.values } }));
  try {
    const result = await api().render_settings();
    if (result.status === "faulty") throw Error(result.reason);
    setState((s) => ({ render: { ...s.render, loading: false, values: result } }));
  } catch (error) {
    setState((s) => ({ render: { ...s.render, loading: false, message: (error as Error).message } }));
  }
}
/** Saves the rendering choices ("auto" or an empty memory field mean automatic); false when refused. */
export async function saveRenderSettings(device: string, processes: string, memory: string) {
  setState((s) => ({ render: { ...s.render, busy: true, message: "" } }));
  try {
    const result = await api().save_render_settings(device === "auto" ? null : device, processes === "auto" ? null : Number(processes),
      memory.trim() ? Number(memory) : null);
    if (result.status === "faulty") throw Error(result.reason);
    setState({ render: { loading: false, busy: false, message: "", values: result } });
    return true;
  } catch (error) {
    setState((s) => ({ render: { ...s.render, busy: false, message: (error as Error).message } }));
    return false;
  }
}
export async function renderTest(action: "start" | "cancel") {
  setState((s) => ({ render: { ...s.render, busy: true, message: action === "start" ? "Starting the speed test…" : "Cancelling…" } }));
  try {
    const result = await api().render_test(action);
    if (result.status === "faulty" || result.status === "busy") throw Error(result.reason);
    setState((s) => ({ render: { ...s.render, busy: false, message: "" } }));
  } catch (error) {
    setState((s) => ({ render: { ...s.render, busy: false, message: (error as Error).message } }));
  }
  await loadRenderSettings();
}

/* ---------------------------------- setup -------------------------------- */
// The setup wizard (decision 0014). setup_core decides and validates; this only
// keeps the draft the user is editing and calls the bridge on explicit actions.

function patchSetup(patch: Partial<SetupState> | ((current: SetupState) => Partial<SetupState>)) {
  setState((s) => ({ setup: { ...s.setup, ...(typeof patch === "function" ? patch(s.setup) : patch) } }));
}
export function updateSetupDraft(patch: Partial<SetupDraft>) {
  patchSetup((s) => ({ draft: { ...s.draft, ...patch } }));
}
/** The batch step only applies to the built-in engine with descriptions on. */
export const setupStepNeeded = (step: SetupStep, draft: SetupDraft = state.setup.draft) =>
  step !== "batch" || (draft.descriptionsEnabled && draft.engine === "builtin");
export async function loadSetupState() {
  const info = await api().setup_state();
  if (info.status === "faulty") throw Error(info.reason);
  patchSetup({ info });
  return info;
}
/** The wizard's draft filled from what is saved now. */
function savedDraft(info: Json): SetupDraft {
  const values = info.settings || {};
  return {
    ...emptySetup().draft,
    blenderPath: info.blender?.configured || "",
    formats: values.processing_formats ?? ["fbx", "gltf", "obj"],
    budget: values.storage_budget_gib != null ? String(values.storage_budget_gib) : "",
    descriptionsEnabled: values.descriptions_enabled ?? true,
    engine: values.description_engine || "builtin",
    serverUrl: values.description_server?.url || "http://127.0.0.1:8080/v1",
    serverModel: values.description_server?.model || "",
    searchDevice: values.search_device || "cuda",
    batch: String(values.caption_batch_size ?? 8),
  };
}
/** Reads what is installed for each search device; never installs or starts the model. */
export async function checkSearchReadiness() {
  setState((s) => ({ searchCheck: { ...s.searchCheck, checking: true, error: null } }));
  try {
    const env = await api().setup_environment();
    setState({ searchCheck: env.status === "faulty" ? { checking: false, devices: null, error: env.reason } : { checking: false, devices: env.search_devices, error: null } });
  } catch (error) {
    setState({ searchCheck: { checking: false, devices: null, error: (error as Error).message } });
  }
}
export async function openSetup() {
  setNotificationsOpen(false);
  patchSetup({ ...emptySetup(), open: true, loading: true });
  try {
    const info = await loadSetupState();
    patchSetup({
      loading: false,
      draft: savedDraft(info),
      error: info.settings_fault || info.record_fault || null,
    });
    requestAnimationFrame(() => document.getElementById("setup-step-title")?.focus());
    // A session the user opened earlier is still running: show its panel instead of the choice.
    void loadAgentSetup().then((agent) => agent?.session?.open && patchSetup({ agentMode: true }));
    const [env, storage] = await Promise.all([api().setup_environment(), api().setup_storage_use(false)]);
    patchSetup({ env: env.status === "faulty" ? null : env, storage, error: env.status === "faulty" ? env.reason : state.setup.error });
    // A first run suggests where search runs from the GPU found; a saved or agent-set choice is never replaced.
    if (env.status !== "faulty" && info.first_run?.fresh && !info.set_by?.search_device && env.suggested_search_device)
      updateSetupDraft({ searchDevice: env.suggested_search_device });
  } catch (error) {
    patchSetup({ loading: false, error: (error as Error).message });
  }
}
export function closeSetup() {
  if (state.setup.checking) void api().setup_cancel_blender();
  patchSetup({ open: false });
  void loadGeneralSettings();
}
export function goToSetupStep(index: number) {
  const step = Math.max(0, Math.min(SETUP_STEPS.length - 1, index));
  patchSetup({ step });
  if (SETUP_STEPS[step] === "blender" && !state.setup.blender) void loadSetupBlender();
  requestAnimationFrame(() => document.getElementById("setup-step-title")?.focus());
}
function neighbour(direction: 1 | -1) {
  let index = state.setup.step + direction;
  while (index > 0 && index < SETUP_STEPS.length - 1 && !setupStepNeeded(SETUP_STEPS[index])) index += direction;
  return index;
}
export function setupNext(skip = false) {
  const step = SETUP_STEPS[state.setup.step];
  patchSetup((s) => ({ draft: { ...s.draft, skipped: skip ? [...new Set([...s.draft.skipped, step])] : s.draft.skipped.filter((item) => item !== step) } }));
  goToSetupStep(neighbour(1));
}
export function setupBack() {
  goToSetupStep(neighbour(-1));
}
export async function loadSetupBlender() {
  patchSetup({ blender: null });
  const blender = await api().setup_blender();
  if (blender.status === "faulty") return patchSetup({ error: blender.reason });
  patchSetup((s) => ({ blender, draft: { ...s.draft, blenderPath: s.draft.blenderPath || blender.used || "" } }));
}
let checkGeneration = 0;
/** setup_core.check_blender; a bridge fault becomes a failed check of that path. */
async function runBlenderCheck(path: string): Promise<Json> {
  const check = await api().setup_check_blender(path);
  return check.status === "faulty" && !check.checks ? { status: "failed", path, checks: [{ id: "file", label: "Executable", status: "failed", detail: check.reason }] } : check;
}
export async function checkBlender(path = state.setup.draft.blenderPath) {
  const generation = ++checkGeneration;
  patchSetup({ checking: true, check: null });
  const check = await runBlenderCheck(path);
  if (generation !== checkGeneration) return;
  patchSetup({ checking: false, check });
}
export async function cancelBlenderCheck() {
  await api().setup_cancel_blender();
}
export async function chooseBlenderExecutable() {
  const result = await api().choose_blender_executable();
  if (result.status === "faulty") return patchSetup({ error: result.reason });
  if (result.status !== "selected") return;
  updateSetupDraft({ blenderPath: result.path, confirmRerender: false });
  await checkBlender(result.path);
}
/* ------------------------- blender installation ------------------------ */
// Settings → General → Blender installation: the wizard's Blender step on its own (decision 0014).

function patchBlender(patch: Partial<BlenderState> | ((current: BlenderState) => Partial<BlenderState>)) {
  setState((s) => ({ blender: { ...s.blender, ...(typeof patch === "function" ? patch(s.blender) : patch) } }));
}
/** The saved Blender and what was found; the picker opens by itself while none usable is saved. */
export async function loadBlenderInstallation() {
  const report = await api().setup_blender();
  if (report.status === "faulty") return patchBlender({ message: report.reason });
  const saved = report.configured && report.configured_exists;
  // A Blender saved elsewhere (wizard, agent, CLI) replaces an edit in progress here.
  patchBlender((b) => {
    const keep = b.editing && !!b.path && (!b.report || b.report.configured === report.configured);
    return { report, path: keep ? b.path : report.configured_exists ? report.configured : report.used || "", editing: !saved || keep,
      ...(keep ? {} : { check: null, confirmRerender: false }) };
  });
}
export function updateBlenderInstallation(patch: Partial<Pick<BlenderState, "path" | "confirmRerender" | "editing">>) {
  patchBlender((b) => ({ ...patch, message: "", ...(patch.editing === false ? { path: b.report?.configured || b.path, check: null, confirmRerender: false } : {}) }));
}
let installationGeneration = 0;
export async function checkBlenderInstallation(path = state.blender.path) {
  const generation = ++installationGeneration;
  patchBlender({ checking: true, check: null, message: "" });
  const check = await runBlenderCheck(path);
  if (generation !== installationGeneration) return;
  patchBlender({ checking: false, check });
}
export async function chooseBlenderInstallation() {
  const result = await api().choose_blender_executable();
  if (result.status === "faulty") return patchBlender({ message: result.reason });
  if (result.status !== "selected") return;
  patchBlender({ path: result.path, confirmRerender: false });
  await checkBlenderInstallation(result.path);
}
export async function saveBlenderInstallation() {
  const { path, confirmRerender } = state.blender;
  patchBlender({ saving: true, message: "" });
  const result = await api().save_blender(path, confirmRerender);
  if (result.status === "faulty") return patchBlender({ saving: false, message: result.reason });
  patchBlender({ saving: false, editing: false, check: null, confirmRerender: false });
  pushToast({ tone: "success", title: "Blender saved", body: result.status === "saved" ? `Saved to ${result.file}. Make previews and the speed test use it right away.` : "Already the saved Blender; nothing was written." });
  await Promise.all([loadBlenderInstallation(), loadRenderSettings(), loadSetupState().catch(() => undefined)]);
}
export async function measureSetupStorage() {
  patchSetup({ measuring: true });
  const storage = await api().setup_storage_use(true);
  patchSetup({ measuring: false, storage: storage.status === "faulty" ? { status: "faulty", reason: storage.reason } : storage });
}
/** List a local model server's models (never generates text); shared by setup and Settings → General. */
export async function checkServer(url: string, model: string): Promise<Json> {
  try {
    return await api().setup_check_server(url, model);
  } catch (error) {
    return { status: "faulty", reason: (error as Error).message };
  }
}
export async function testSetupServer() {
  const { serverUrl, serverModel } = state.setup.draft;
  patchSetup({ testing: true, server: null });
  const server = await checkServer(serverUrl, serverModel);
  patchSetup((s) => ({
    testing: false, server,
    draft: server.status === "connected" && !s.draft.serverModel && server.models.length === 1 ? { ...s.draft, serverModel: server.models[0] } : s.draft,
  }));
}
/** The choices as setup_core.save_setup expects them; skipped steps keep their saved values. */
export function setupChoices(draft: SetupDraft = state.setup.draft): Json {
  const skipped = new Set(draft.skipped);
  const choices: Json = { skipped_steps: [...skipped] };
  if (!skipped.has("blender") && draft.blenderPath) Object.assign(choices, { blender_path: draft.blenderPath, confirm_rerender: draft.confirmRerender });
  if (!skipped.has("formats")) Object.assign(choices, { processing_formats: draft.formats, engine_hint: draft.engineHint || null });
  if (!skipped.has("storage") && draft.budget) choices.storage_budget_gib = draft.budget;
  if (!skipped.has("descriptions"))
    Object.assign(choices, { descriptions_enabled: draft.descriptionsEnabled, description_engine: draft.engine, description_server: { url: draft.serverUrl, model: draft.serverModel }, search_device: draft.searchDevice });
  if (!skipped.has("batch") && setupStepNeeded("batch", draft)) choices.caption_batch_size = draft.batch;
  return choices;
}
const STEP_FIELDS: Record<string, (keyof SetupDraft)[]> = {
  blender: ["blenderPath"], formats: ["formats", "engineHint"], storage: ["budget"],
  descriptions: ["descriptionsEnabled", "engine", "serverUrl", "serverModel", "searchDevice"], batch: ["batch"],
};
/** Which saved values a step shows, for "set by" badges. */
export const STEP_KEYS: Record<string, string[]> = {
  blender: ["blender"], formats: ["processing_formats"], storage: ["storage_budget_gib"],
  descriptions: ["descriptions_enabled", "description_engine", "description_server", "search_device"], batch: ["caption_batch_size"],
};
export const stepChanged = (step: string, draft: SetupDraft, baseline: SetupDraft) =>
  (STEP_FIELDS[step] || []).some((key) => JSON.stringify(draft[key]) !== JSON.stringify(baseline[key]));
/** After an agent set values, Save records only what the user changed, so the rest keeps "set by agent". */
function changedChoices(draft: SetupDraft, baseline: SetupDraft): Json {
  const unchanged = Object.keys(STEP_FIELDS).filter((step) => !stepChanged(step, draft, baseline)) as SetupStep[];
  return { ...setupChoices({ ...draft, skipped: [...new Set([...draft.skipped, ...unchanged])] }), skipped_steps: draft.skipped };
}
export async function saveSetup() {
  patchSetup({ saving: true, error: null });
  const { draft, baseline } = state.setup;
  const result = await api().save_setup(baseline ? changedChoices(draft, baseline) : setupChoices());
  patchSetup({ saving: false, ...(result.status === "faulty" ? { error: result.reason } : { result }) });
  if (result.status !== "faulty") {
    await Promise.all([loadGeneralSettings(), loadSources(), loadSetupState(), loadRenderSettings(), loadBlenderInstallation()]);
    requestAnimationFrame(() => document.getElementById("setup-saved-title")?.focus());
  }
}
export async function skipSetup() {
  const result = await api().skip_setup();
  if (result.status === "faulty") return patchSetup({ error: result.reason });
  patchSetup({ open: false });
  pushToast({ tone: "info", title: "Setup skipped", body: "Nothing was saved. Run setup any time from Settings → General." });
  await loadSetupState();
}
export function finishSetup(next: "sources" | "close") {
  closeSetup();
  if (next === "sources") navigate({ page: "sources" });
}

/* ------------------------------- agent setup ------------------------------ */
// Decision 0016: the backend gates agent writes behind a session only these clicks open,
// and applies a proposed Blender only on the user's Apply. This presents its state.

export async function loadAgentSetup() {
  const agent = await api().agent_setup_state();
  if (agent.status === "faulty") return patchSetup({ error: agent.reason });
  patchSetup({ agent });
  return agent;
}
/** The user's gesture: opens a 60-minute session in which agents may apply setup values. */
export async function startAgentSetup() {
  patchSetup({ agentMode: true, agentBusy: "open", error: null });
  const result = await api().open_agent_setup();
  patchSetup({ agentBusy: null, ...(result.status === "faulty" ? { error: result.reason } : {}) });
  await loadAgentSetup();
  requestAnimationFrame(() => document.getElementById("agent-setup-title")?.focus());
}
export async function endAgentSetup() {
  patchSetup({ agentBusy: "end" });
  const result = await api().end_agent_setup();
  patchSetup({ agentBusy: null, ...(result.status === "faulty" ? { error: result.reason } : {}) });
  await loadAgentSetup();
}
export function leaveAgentSetup() {
  patchSetup({ agentMode: false });
  setupNext(false);
}
export async function decideProposal(proposal: Json, decision: "apply" | "reject", confirmRerender = false) {
  patchSetup({ agentBusy: proposal.id + ":" + decision, error: null });
  const result = await api().decide_setup_proposal(proposal.id, decision, confirmRerender);
  patchSetup({ agentBusy: null });
  if (result.status === "faulty") pushToast({ tone: "fault", title: "Proposal not decided", body: result.reason });
  else if (result.status === "applied")
    pushToast({ tone: "success", title: "Blender applied", body: result.blender?.status === "saved" ? `Saved to ${result.blender.file}. Make previews and the speed test use it right away.` : "Already the saved Blender; nothing was written." });
  else if (result.status === "failed") pushToast({ tone: "fault", title: "Blender not applied", body: `${result.proposal.reason}. Ask your agent to check it again.` });
  else pushToast({ tone: "info", title: "Proposal rejected", body: "Nothing was saved. Your agent sees that you rejected it." });
  await Promise.all([loadAgentSetup(), loadSetupState(), loadRenderSettings(), loadBlenderInstallation()]);
}
/** The final review: the wizard's review step, filled with the values saved now. */
export async function reviewAgentSetup() {
  const info = await loadSetupState();
  const draft = savedDraft(info);
  patchSetup({ draft, baseline: draft, result: null });
  goToSetupStep(SETUP_STEPS.indexOf("review"));
}
export async function openAgentSetupFromSettings() {
  await openSetup();
  await startAgentSetup();
}
/** Notices of agent setup lead back to the panel; a pending proposal is decided there. */
export async function openAgentPanel() {
  if (!state.setup.open) await openSetup();
  patchSetup({ agentMode: true });
  goToSetupStep(0);
  await loadAgentSetup();
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
  // A toast whose notice is gone (a decided proposal, a deleted collection) offers nothing that can still work.
  const ids = new Set(items.map((item) => item.id));
  setState((s) => ({ notifications: items, toasts: s.toasts.filter((toast) => !toast.notification || ids.has(toast.notification.id)) }));
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
  if (action === "open_collection") {
    if (!item.read) await saveNotification("read", item.id);
    setNotificationsOpen(false);
    return openCollection(item.collection_id);
  }
  if (action === "view" || action === "report") {
    if (!item.read) await saveNotification("read", item.id);
    return openProcessing(item.source_key, action === "report" ? item : undefined);
  }
  if (action === "review_setup") {
    if (!item.read) await saveNotification("read", item.id);
    setNotificationsOpen(false);
    return openAgentPanel();
  }
  if (action === "dismiss") return saveNotification("dismiss", item.id);
}
export const runningDescriptions = (s: AppState = state) => s.sources.filter(describeActive);
export const processingAttention = (s: AppState) =>
  s.sources.some((source) => source.needs_processing || source.scan_fault || operationActive(source.operation));

/** Work running in the background, for the top-bar activity indicator; `source` opens Asset processing. */
export interface Activity {
  id: string;
  label: string;
  detail: string;
  progress?: number;
  source?: string;
}
const OPERATION_VERBS: Record<string, string> = { queued: "Queued", scanning: "Scanning", publishing: "Publishing", cancelling: "Cancelling", verifying: "Verifying" };
const WORKER_ACTIVITY: Record<string, [string, string]> = {
  loading_libraries: ["Preparing search", "Preparing the search runtime"],
  loading_model: ["Loading search model", "Loading the search model for the first ranked search"],
};
export function activities(ready: boolean, sources: Json[], worker: string, previews: number): Activity[] {
  const list: Activity[] = [];
  if (!ready) list.push({ id: "startup", label: "Opening library", detail: "Reading the published library." });
  for (const source of sources) {
    const operation = source.operation;
    if (!operationActive(operation)) continue;
    const verb = operation.operation === "describe" && operation.status !== "cancelling" ? "Describing" : OPERATION_VERBS[operation.status] || "Processing";
    const counted = operation.total ? ` · ${operation.completed || 0} / ${operation.total}` : "";
    const progress = ["queued", "scanning"].includes(operation.status) || !operation.progress ? undefined : Math.min(1, operation.progress);
    list.push({ id: "source:" + source.key, label: verb, detail: `${verb} ${source.name}${counted}`, progress, source: source.key });
  }
  if (WORKER_ACTIVITY[worker]) list.push({ id: "worker", label: WORKER_ACTIVITY[worker][0], detail: WORKER_ACTIVITY[worker][1] });
  if (previews > 0) list.push({ id: "previews", label: "Previews", detail: `Loading ${plural(previews, "preview", "previews")}`, progress: undefined });
  return list;
}

/* ------------------------------- collections ------------------------------ */
// Collections are owner organization data (decision 0012). The backend resolves
// membership and availability; these actions present it and keep views current.

let collectionsGeneration = 0;
export async function loadCollections(query = state.collections.query) {
  if (!state.api) return;
  const generation = ++collectionsGeneration;
  setState((s) => ({ collections: { ...s.collections, loading: true, query } }));
  try {
    const result = await api().collections(query, null);
    if (generation !== collectionsGeneration) return;
    if (result.status === "faulty") throw Error(result.reason);
    setState((s) => ({ collections: { ...s.collections, items: result.collections, total: result.total, loading: false, loaded: true, error: null } }));
  } catch (error) {
    if (generation === collectionsGeneration) setState((s) => ({ collections: { ...s.collections, loading: false, loaded: true, error: (error as Error).message } }));
  }
}
let collectionsTimer: ReturnType<typeof setTimeout> | undefined;
/** The Collections tab filters as you type: names, descriptions and what is inside. */
export function setCollectionsQuery(query: string) {
  setState((s) => ({ collections: { ...s.collections, query } }));
  clearTimeout(collectionsTimer);
  collectionsTimer = setTimeout(() => void loadCollections(query), 200);
}
/** Every collection, each marked when it already holds the asset (the "Add to a collection" menu). */
export async function collectionsFor(assetId: string): Promise<Json[]> {
  const result = await api().collections("", assetId);
  if (result.status === "faulty") throw Error(result.reason);
  return result.collections;
}
export function openCollection(id: string) {
  setState({ menu: null });
  navigate({ page: "collection", key: id });
}

let collectionGeneration = 0;
async function openCollectionView(id: string) {
  closeDetail("collection");
  setState((s) => ({
    collectionView: { ...emptyCollectionView(), id, mode: s.collectionView.mode, loading: true },
    collection: { ...emptyGrid("collection"), generation: s.collection.generation + 1 },
  }));
  await loadCollection();
}
/** All members in collection order, or the current in-collection search again. */
export async function loadCollection(resetThumbs = false): Promise<void> {
  const view = state.collectionView;
  if (!view.id || !state.api) return;
  if (view.phase === "search" && view.query.trim()) return searchCollection();
  const generation = ++collectionGeneration;
  setState((s) => ({ collectionView: { ...s.collectionView, loading: true } }));
  try {
    const result = await api().collection(view.id, "");
    if (generation !== collectionGeneration) return;
    if (result.status === "faulty") throw Error(result.reason);
    showCollection(result, result.items, resetThumbs);
  } catch (error) {
    if (generation === collectionGeneration) setState((s) => ({ collectionView: { ...s.collectionView, loading: false, error: (error as Error).message } }));
  }
}
function showCollection(result: Json, items: Json[], resetThumbs: boolean) {
  const previous = new Map(state.collection.items.map((item) => [item.asset_id, item]));
  setState((s) => ({
    collectionView: {
      ...s.collectionView, name: result.name, description: result.description, updatedAt: result.updated_at,
      count: result.asset_count, unavailable: result.unavailable_count, loading: false, error: null,
      members: { ...s.collectionView.members, ...Object.fromEntries(items.map((item) => [item.asset_id, item])) },
    },
    selection: { ...s.selection, ids: s.selection.ids.filter((id) => items.some((item) => item.asset_id === id)) },
  }));
  // Unchanged members keep their thumbnails, so agent edits and saves do not flash the grid.
  patchGrid("collection", (c) => {
    const same = (item: Json) => previous.get(item.asset_id)?.availability === item.availability && previous.get(item.asset_id)?.in_library === item.in_library;
    const thumbs = resetThumbs ? {} : Object.fromEntries(items.filter(same).filter((item) => c.thumbs[item.asset_id]).map((item) => [item.asset_id, c.thumbs[item.asset_id]]));
    // A member whose availability changed asks again for its card in this generation.
    for (const item of items) if (!thumbs[item.asset_id]) requested.delete(`collection:${c.generation}:${item.asset_id}`);
    return { items, total: items.length, thumbs, generation: resetThumbs ? c.generation + 1 : c.generation };
  });
  const selected = state.collection.selected;
  if (selected && !state.collectionView.members[selected]) closeDetail("collection");
  else if (selected && state.collectionView.phase === "all" && !items.some((item) => item.asset_id === selected)) closeDetail("collection");
}
export function setCollectionQuery(query: string) {
  setState((s) => ({ collectionView: { ...s.collectionView, query } }));
}
export function setCollectionMode(mode: string) {
  setState((s) => ({ collectionView: { ...s.collectionView, mode } }));
  if (state.collectionView.phase === "search") void searchCollection();
}
/** Search inside the open collection: owner text first, then the ranked library search limited to members. */
export async function searchCollection(): Promise<void> {
  const view = state.collectionView;
  if (!view.id) return;
  if (!view.query.trim()) return clearCollectionSearch();
  const generation = ++collectionGeneration;
  setState((s) => ({ collectionView: { ...s.collectionView, phase: "search", busy: true, loading: true, error: null } }));
  try {
    const result = await api().collection_search(view.id, { query: view.query, mode: view.mode });
    if (generation !== collectionGeneration) return;
    if (result.status === "faulty") throw Error(result.reason);
    setState((s) => ({ collectionView: { ...s.collectionView, search: result.search } }));
    showCollection(result, result.items, false);
  } catch (error) {
    if (generation === collectionGeneration) setState((s) => ({ collectionView: { ...s.collectionView, loading: false, error: (error as Error).message } }));
  } finally {
    if (generation === collectionGeneration) setState((s) => ({ collectionView: { ...s.collectionView, busy: false } }));
  }
}
export function clearCollectionSearch(): Promise<void> {
  setState((s) => ({ collectionView: { ...s.collectionView, query: "", phase: "all", search: null } }));
  return loadCollection();
}

async function collectionAction(action: string, id: string | null, options: Json = {}) {
  const result = await api().collection_action(action, id, options);
  if (result.status === "faulty") throw Error(result.reason);
  return result;
}
/** Views that show collections reload after any change; the open one keeps its search. */
async function refreshCollections() {
  const page = route().page;
  await Promise.all([
    page === "collections" || state.collections.loaded ? loadCollections() : null,
    page === "collection" && state.collectionView.id ? loadCollection() : null,
  ]);
}
const collectionToast = (id: string, title: string, body: string, tone: Tone = "success") =>
  pushToast({ tone, title, body, actions: route().page === "collection" && route().key === id ? [] : [{ label: "Open collection", run: () => openCollection(id) }] });

export async function createCollection(name: string, description: string, assetIds: string[] = [], sourceKey: string | null = null) {
  const result = await collectionAction("create", null, { name, description, asset_ids: assetIds, source_key: sourceKey });
  collectionToast(result.collection_id, assetIds.length ? `Added to “${result.name}”` : `Created “${result.name}”`,
    assetIds.length ? "New collection created with this asset." : "Right-click any asset card to add it to this collection.");
  await refreshCollections();
  return result;
}
export async function updateCollection(id: string, patch: { name?: string; description?: string }) {
  const result = await collectionAction("update", id, patch);
  await refreshCollections();
  return result;
}
export function confirmDeleteCollection(summary: Json) {
  askConfirm({
    title: `Delete “${summary.name}”?`,
    body: `This deletes the collection with its labels and notes${summary.asset_count ? ` for ${plural(summary.asset_count, "asset", "assets")}` : ""}. The assets themselves, their files and their tags are not affected.`,
    confirmLabel: "Delete collection",
    run: async () => {
      const id = summary.collection_id;
      await collectionAction("delete", id);
      if (route().page === "collection" && route().key === id) navigate({ page: "collections" });
      pushToast({ tone: "info", title: `Deleted “${summary.name}”`, body: "The assets remain in the library." });
      await loadCollections();
    },
  });
}
export async function addToCollection(collection: Json, grid: GridId, item: Json) {
  try {
    const result = await collectionAction("add", collection.collection_id, { asset_ids: [item.asset_id], source_key: sourceKeyFor(grid, item) });
    collectionToast(collection.collection_id, `Added to “${result.name}”`, result.added ? `${item.name} is now in this collection.` : `${item.name} was already in this collection.`);
    await refreshCollections();
  } catch (error) {
    pushToast({ tone: "fault", title: "Could not add to the collection", body: (error as Error).message });
  }
}
/** Home cards come from the library; source-browser cards and source-only members name their source. */
function sourceKeyFor(grid: GridId, item: Json) {
  if (grid === "source") return state.source.key;
  if (grid === "collection" && !item.in_library) return item.source_key;
  return null;
}
export async function removeFromCollection(id: string, assetIds: string[]) {
  try {
    const result = await collectionAction("remove", id, { asset_ids: assetIds });
    const removed: Json[] = result.removed;
    pushToast({
      tone: "info", title: `Removed ${plural(removed.length, "asset", "assets")}`,
      body: `From “${result.name}”. Undo brings them back with their labels and notes.`,
      actions: removed.length ? [{ label: "Undo", run: () => void restoreToCollection(id, removed) }] : [],
    });
    await refreshCollections();
  } catch (error) {
    pushToast({ tone: "fault", title: "Could not remove from the collection", body: (error as Error).message });
  }
}
async function restoreToCollection(id: string, removed: Json[]) {
  try {
    const result = await collectionAction("restore", id, { removed });
    pushToast({ tone: "success", title: `Restored ${plural(result.restored, "asset", "assets")}`, body: "Labels and notes are back." });
    await refreshCollections();
  } catch (error) {
    pushToast({ tone: "fault", title: "Could not undo", body: (error as Error).message });
  }
}
/** Label and notes belong to this collection only; the saved values replace the card's. */
export async function setCollectionItem(id: string, assetId: string, patch: { label?: string; notes?: string }) {
  const result = await collectionAction("set_item", id, { asset_id: assetId, ...patch });
  const update = (item: Json) => (item.asset_id === assetId ? { ...item, label: result.label, notes: result.notes } : item);
  patchGrid("collection", (c) => ({ items: c.items.map(update) }));
  setState((s) => ({ collectionView: { ...s.collectionView, members: { ...s.collectionView.members, [assetId]: update(s.collectionView.members[assetId] || {}) } } }));
  return result;
}

/* --------------------------- collection covers ---------------------------- */

const covers = new Map<string, Promise<Thumb>>();
const coverQueue: (() => void)[] = [];
let coverWorkers = 0;
function nextCover() {
  while (coverWorkers < 3 && coverQueue.length) {
    coverWorkers++;
    coverQueue.shift()!();
  }
}
/** Card thumbnails for the Collections tab, cached per asset; at most three requests at a time. */
export function coverThumb(entry: Json): Promise<Thumb> {
  if (entry.availability === "unavailable") return Promise.resolve({ placeholder: "Unavailable", reason: entry.reason });
  const key = entry.asset_id + (entry.in_library ? "" : ":" + entry.source_key);
  if (!covers.has(key))
    covers.set(key, new Promise<Thumb>((resolve) => {
      coverQueue.push(async () => {
        try {
          const source = entry.in_library ? libraryApi(api()) : sourceApi(api(), entry.source_key);
          const result = await source.thumbnail(entry.asset_id, null);
          resolve(result.image ? { image: result.image, pixelArt: Boolean(result.payload?.pixel_art_candidate) } : { placeholder: "No preview", reason: result.payload?.preview?.reason || result.reason });
        } catch (error) {
          resolve({ placeholder: "No preview", reason: (error as Error).message });
        } finally {
          coverWorkers--;
          nextCover();
          syncPreviews();
        }
      });
      nextCover();
      syncPreviews();
    }));
  return covers.get(key)!;
}

/* ----------------------- selection (batch removal) ------------------------ */

/** Like forwarding messages: the first card is ticked, more can be added before removing them together. */
export function startSelection(assetId: string | null = null) {
  setState({ selection: { active: true, ids: assetId ? [assetId] : [], anchor: assetId }, menu: null });
}
export function toggleSelected(assetId: string, range = false) {
  const { ids, anchor } = state.selection;
  const order = state.collection.items.map((item) => item.asset_id);
  if (range && anchor && order.includes(anchor)) {
    const [a, b] = [order.indexOf(anchor), order.indexOf(assetId)].sort((x, y) => x - y);
    setState({ selection: { active: true, ids: [...new Set([...ids, ...order.slice(a, b + 1)])], anchor: assetId } });
    return;
  }
  setState({ selection: { active: true, ids: ids.includes(assetId) ? ids.filter((id) => id !== assetId) : [...ids, assetId], anchor: assetId } });
}
export function selectAllShown() {
  setState((s) => ({ selection: { ...s.selection, active: true, ids: s.collection.items.map((item) => item.asset_id) } }));
}
export function cancelSelection() {
  setState({ selection: { active: false, ids: [], anchor: null } });
}
export async function removeSelected() {
  const ids = state.selection.ids, id = state.collectionView.id;
  if (!ids.length || !id) return;
  cancelSelection();
  await removeFromCollection(id, ids);
}

/* ------------------------ menus, dialogs and tags ------------------------- */

let menuId = 0;
export function openAssetMenu(grid: GridId, item: Json, x: number, y: number, returnFocus: HTMLElement | null = null, keyboard = false) {
  setState({ menu: { id: ++menuId, kind: "asset", grid, item, x, y, returnFocus, keyboard } });
}
export function openCollectionMenu(summary: Json, x: number, y: number, returnFocus: HTMLElement | null = null, keyboard = false) {
  setState({ menu: { id: ++menuId, kind: "collection", item: summary, x, y, returnFocus, keyboard } });
}
export function openExportMenu(collectionId: string, x: number, y: number, returnFocus: HTMLElement | null = null, keyboard = false) {
  setState({ menu: { id: ++menuId, kind: "export", item: { collection_id: collectionId }, x, y, returnFocus, keyboard } });
}
export function closeMenu() {
  if (state.menu) setState({ menu: null });
}
/** Every deletion asks first; the confirm button is red and nothing happens until it is pressed. */
export function askConfirm(request: ConfirmRequest) {
  setState({ confirm: request, menu: null });
}
export function closeConfirm() {
  setState({ confirm: null });
}
export function confirmRemoveSource(source: Json) {
  askConfirm({
    title: `Remove “${source.name}”?`,
    body: "Assetarium stops listing this source and its assets. Its files and processing results stay on disk; adding the folder again brings them back.",
    confirmLabel: "Remove source",
    run: () => sourceAction("remove", source.key),
  });
}
/** Recheck failures from the file check (decision 0020), then confirm before anything is retried. */
export async function recheckFailures(source: Json) {
  try {
    const found = await api().recheck_failures(source.key);
    if (found.status === "faulty") throw Error(found.reason);
    const still = found.still_failing ? ` ${found.still_failing.toLocaleString()} still fail it and stay recorded.` : "";
    if (!found.retry) {
      askConfirm({ tone: "neutral", title: "Nothing to retry", confirmLabel: "",
        body: `No recorded failure in “${source.name}” came from a file problem that is resolved now.${still} Other failures stay recorded with their reasons in the Importing failures report.` });
      return;
    }
    const count = found.retry.toLocaleString();
    askConfirm({
      tone: "neutral",
      title: `Retry ${count} ${found.retry === 1 ? "asset" : "assets"}?`,
      body: `${count} ${found.retry === 1 ? "asset" : "assets"} in “${source.name}” failed only because a file ${found.retry === 1 ? "it is" : "they are"} not rendered from had a problem (for example ${found.examples.slice(0, 3).join(", ")}). ${found.retry === 1 ? "It" : "They"} can be processed now.${still} Retrying marks them pending; nothing runs until you click Make previews. Other recorded failures stay as they are.`,
      confirmLabel: `Retry ${count} ${found.retry === 1 ? "asset" : "assets"}`,
      run: async () => {
        const result = await api().retry_failures(source.key, found.preview_id);
        if (result.status !== "faulty") {
          setState({ sourcesMessage: result.reason || "" });
          await loadSources();
        }
        return result;
      },
    });
  } catch (error) {
    pushToast({ tone: "fault", title: "Recheck failed", body: (error as Error).message });
  }
}
export function openCreateCollection(request: CreateRequest = { assetIds: [], sourceKey: null }) {
  setState({ create: request, menu: null });
}
export function closeCreateCollection() {
  setState({ create: null });
}
export function assetMenuSource(grid: GridId, item: Json) {
  return sourceKeyFor(grid, item);
}

export async function loadKnownTags() {
  try {
    const result = await api().asset_tags(null);
    if (result.status !== "faulty") setState({ knownTags: result.known });
  } catch {
    // Suggestions are optional; editing tags still works without them.
  }
}
export async function assetTags(assetId: string): Promise<string[]> {
  const result = await api().asset_tags(assetId);
  if (result.status === "faulty") throw Error(result.reason);
  setState({ knownTags: result.known });
  return result.tags;
}
export async function saveAssetTags(assetId: string, tags: string[]): Promise<string[]> {
  const result = await api().set_asset_tags(assetId, tags);
  if (result.status === "faulty") throw Error(result.reason);
  const saved: string[] = result.tags[assetId];
  patchGrid("collection", (c) => ({ items: c.items.map((item) => (item.asset_id === assetId ? { ...item, tags: saved } : item)) }));
  void loadKnownTags();
  return saved;
}

/* --------------------------------- exports -------------------------------- */

const EXPORT_NAMES: Record<string, string> = { json: "JSON", png: "Sample image", md: "Markdown", pdf: "PDF" };
/** Writes where the owner chooses (or a scripted target under data/exports). PDFs print the report in this window. */
export async function exportCollection(id: string, kind: "json" | "png" | "md" | "pdf", target: string | null = null) {
  let result: Json;
  try {
    result = await api().collection_export(id, kind, target);
    if (result.status === "print") {
      let root = document.getElementById("print-root");
      if (!root) {
        root = document.createElement("div");
        root.id = "print-root";
        document.body.append(root);
      }
      root.innerHTML = result.html;
      await Promise.all([...root.querySelectorAll("img")].map((image) => image.decode().catch(() => undefined)));
      try {
        result = await api().collection_print(result.token);
      } finally {
        root.replaceChildren();
      }
    }
    if (result.status === "faulty") throw Error(result.reason);
  } catch (error) {
    pushToast({ tone: "fault", title: `${EXPORT_NAMES[kind]} export failed`, body: (error as Error).message });
    return { status: "faulty", reason: (error as Error).message };
  }
  if (result.status === "exported") {
    const path = result.path as string;
    pushToast({ tone: "success", title: `${EXPORT_NAMES[kind]} exported`, body: path, actions: [{ label: "Copy path", run: () => void copyText(path, "Export path copied.") }] });
  }
  return result;
}

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

const tokens = { library: null as string | null, sources: null as string | null, collections: null as string | null, agent: null as string | null };
let checking = false;
const workerMessages: Record<string, string> = {
  loading_libraries: "Searching the library… Preparing the search runtime; the window remains available.",
  loading_model: "Searching the library… Loading the search model (first search only); the window remains available.",
};
async function watchChanges() {
  const first = await api().changes();
  if (first.status !== "faulty") {
    Object.assign(tokens, { library: first.library, sources: first.sources, collections: first.collections, agent: first.agent });
    setState({ worker: first.worker });
  }
  // One cheap stat-only poll; library and source data reload only when their token changes.
  setInterval(async () => {
    if (checking) return;
    checking = true;
    try {
      const next = await api().changes();
      if (next.status === "faulty") return;
      if (next.worker !== state.worker) setState({ worker: next.worker });
      const sourcesChanged = next.sources !== tokens.sources;
      const libraryChanged = next.library !== tokens.library;
      if (state.search.busy && workerMessages[next.worker]) patchSearch({ status: workerMessages[next.worker] });
      const collectionsChanged = next.collections !== tokens.collections;
      const agentChanged = next.agent !== tokens.agent;
      Object.assign(tokens, { library: next.library, sources: next.sources, collections: next.collections, agent: next.agent });
      // Agent setup steps, proposals and connections appear live while the panel is open.
      if (agentChanged && state.setup.open && state.setup.agentMode) void loadAgentSetup();
      if (libraryChanged) await refreshContext();
      // Agent edits (and this window's own saves) reach the collection views here.
      if (collectionsChanged || (libraryChanged && route().page === "collection")) {
        void loadKnownTags();
        await refreshCollections();
      }
      // Running operations also report worker liveness, which is not a file change.
      if (sourcesChanged || state.sources.some((source) => operationActive(source.operation))) await loadSources();
      // The tree and the shown folder follow scans and processing; the rail's folder dot follows the tree.
      if (sourcesChanged) {
        await loadLibraryTree();
        const s = state.sourcesView;
        if (route().page === "sources" && s.key && !state.source.loading) void refreshFolder();
      }
      if (route().page === "settings" && (sourcesChanged || operationActive(state.render.values?.operation))) void loadRenderSettings();
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
    patchGrid("library", { version: context.generation });
    renderCoverage(context);
    await loadSources();
    void loadLibraryTree();
    void watchChanges();
    // Setup opens by itself only on a genuinely fresh install (setup_core.first_run).
    void loadSetupState().then((info) => info.auto_open && openSetup()).catch(() => undefined);
    if (context.managed_sources) await sourceAction("scan");
  } catch (error) {
    setState({ startupError: (error as Error).message, ready: true });
  }
}
