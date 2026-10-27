// The pywebview js_api bridge (desktop.DesktopBridge). Every method resolves to
// plain JSON; faults arrive as {status: 'faulty', reason}. Payload shapes are
// owned by the backend, so they stay loosely typed here.
/* eslint-disable @typescript-eslint/no-explicit-any */
export type Json = any;

export interface Bridge {
  context(): Promise<Json>;
  sources(): Promise<Json>;
  changes(): Promise<Json>;
  general_settings(): Promise<Json>;
  render_settings(): Promise<Json>;
  save_render_settings(device: string | null, processes: number | null, memoryGib: number | null): Promise<Json>;
  render_test(action: "start" | "cancel"): Promise<Json>;
  save_general_settings(budget: string | number, formats: string[], batch: string | number, descriptionsEnabled?: boolean | null,
    engine?: string | null, server?: { url: string; model: string } | null, searchDevice?: string | null): Promise<Json>;
  setup_state(): Promise<Json>;
  setup_environment(): Promise<Json>;
  setup_blender(): Promise<Json>;
  setup_check_blender(path: string): Promise<Json>;
  setup_cancel_blender(): Promise<Json>;
  setup_storage_use(measure: boolean): Promise<Json>;
  setup_check_server(url: string, model: string): Promise<Json>;
  save_setup(choices: Json): Promise<Json>;
  skip_setup(): Promise<Json>;
  choose_blender_executable(): Promise<Json>;
  agent_setup_state(): Promise<Json>;
  open_agent_setup(): Promise<Json>;
  end_agent_setup(): Promise<Json>;
  decide_setup_proposal(proposalId: string, decision: "apply" | "reject", confirmRerender: boolean): Promise<Json>;
  interface_settings(): Promise<Json>;
  save_interface_settings(appearance: string | null, inspectorWidth: number | null): Promise<Json>;
  importing_failures(): Promise<Json>;
  notification_action(action: string, identifier?: string | null): Promise<Json>;
  source_action(action: string, key?: string | null, directory?: string | null, enabled?: boolean | null): Promise<Json>;
  source_exclusions(key: string, patterns: string[]): Promise<Json>;
  source_export(key: string, suggestionId: string, decision: string): Promise<Json>;
  source_export_undo(key: string, decisionId: string): Promise<Json>;
  source_textures(key: string, folder: string | null, singleCopies: boolean): Promise<Json>;
  source_textures_undo(key: string): Promise<Json>;
  recheck_failures(key: string): Promise<Json>;
  retry_failures(key: string, previewId: string): Promise<Json>;
  choose_source_directory(): Promise<Json>;
  browse(filters: Json, offset: number, pageSize: number): Promise<Json>;
  source_browse(key: string, offset: number, pageSize: number): Promise<Json>;
  search(settings: Json): Promise<Json>;
  copy_text(text: string): Promise<Json>;
  preview_shell(): Promise<Json>;
  [name: string]: (...args: any[]) => Promise<Json>;
}

/** The per-collection subset used by cards, inspection and the 3D preview. */
export interface AssetApi {
  asset(id: string, format: string | null, view: string, version: string | null): Promise<Json>;
  thumbnail(id: string, version: string | null): Promise<Json>;
  image_view(id: string, edge: number | null, version: string | null): Promise<Json>;
  reveal(id: string, format: string | null): Promise<Json>;
  preview_shell(): Promise<Json>;
  preview_prepare(...args: any[]): Promise<Json>;
  preview_file(...args: any[]): Promise<Json>;
  preview_fault(...args: any[]): Promise<Json>;
  preview_release(...args: any[]): Promise<Json>;
}

export function libraryApi(bridge: Bridge): AssetApi {
  return bridge as unknown as AssetApi;
}

export function sourceApi(bridge: Bridge, key: string): AssetApi {
  const api: Record<string, (...args: any[]) => Promise<Json>> = { preview_shell: () => bridge.preview_shell() };
  for (const name of ["asset", "thumbnail", "image_view", "reveal", "preview_prepare", "preview_file", "preview_fault", "preview_release"])
    api[name] = (...args) => bridge["source_" + name](key, ...args);
  return api as unknown as AssetApi;
}

declare global {
  interface Window {
    pywebview?: { api: Bridge };
    LAL_BOOT?: { appearance: string; inspector_width: number };
    LALPreview: {
      mount(container: HTMLElement, item: Json, api: AssetApi): Json;
      dispose(): void;
      pause(): void;
      readonly current: Json;
    };
  }
}
