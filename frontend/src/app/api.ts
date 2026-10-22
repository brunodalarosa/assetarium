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
  save_general_settings(budget: string | number, formats: string[], batch: string | number): Promise<Json>;
  interface_settings(): Promise<Json>;
  save_interface_settings(appearance: string | null, inspectorWidth: number | null): Promise<Json>;
  importing_failures(): Promise<Json>;
  notification_action(action: string, identifier?: string | null): Promise<Json>;
  source_action(action: string, key?: string | null, directory?: string | null, enabled?: boolean | null): Promise<Json>;
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
  for (const name of ["asset", "thumbnail", "image_view", "preview_prepare", "preview_file", "preview_fault", "preview_release"])
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
