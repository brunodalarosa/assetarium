// 2D images: native-size/zoom viewing on selectable backgrounds; the pixels are the source's own.
import { Maximize, Minus, Plus } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import type { AssetApi } from "../app/api";
import { setState, useApp } from "../app/store";
import { Checkbox } from "@/components/beui/checkbox";
import { IconButton, SelectField } from "./primitives";

const BACKGROUNDS: [string, string][] = [["checker", "Checkerboard"], ["light", "Light"], ["dark", "Dark"], ["gray", "Mid gray"]];
const ZOOMS = [0.125, 0.25, 0.5, 1, 2, 3, 4, 6, 8, 12, 16, 24, 32];

export function ImageViewer({ assetId, name, image, api, version, native, pixelArt, vector }: {
  assetId: string;
  name: string;
  image: string | null;
  api: AssetApi;
  version: string | null;
  native: [number | null, number | null];
  pixelArt: boolean;
  vector: boolean;
}) {
  const background = useApp((s) => s.imageBackground);
  const [zoom, setZoom] = useState<number | "fit">("fit");
  const [smooth, setSmooth] = useState(!pixelArt);
  const [src, setSrc] = useState(image);
  const [note, setNote] = useState(vector ? "Rendered from the SVG source." : "Original source pixels.");
  const stage = useRef<HTMLDivElement>(null);
  const request = useRef(0);
  const [width, height] = native;

  const load = useCallback(async (edge: number | null) => {
    const token = ++request.current;
    let result;
    try {
      result = await api.image_view(assetId, edge, version);
    } catch (error) {
      result = { status: "faulty", reason: (error as Error).message };
    }
    if (token !== request.current) return;
    if (result.status === "image") {
      setSrc(result.image);
      setNote(result.note + (result.size ? ` · showing ${result.size[0]} × ${result.size[1]} px` : ""));
    } else setNote((result.reason || "Full-resolution image unavailable.") + " The preview above is reduced.");
  }, [api, assetId, version]);

  useEffect(() => {
    setSrc(image);
    void load(vector ? 1024 : null);
    return () => {
      request.current++;
    };
  }, [image, load, vector]);

  // Re-render an SVG at the requested on-screen size after zooming settles.
  useEffect(() => {
    if (!vector || zoom === "fit" || !width || !height) return;
    const timer = setTimeout(() => void load(Math.min(2048, Math.max(16, Math.round(Math.max(width, height) * zoom * (devicePixelRatio || 1))))), 250);
    return () => clearTimeout(timer);
  }, [vector, zoom, width, height, load]);

  const effective = () => {
    const el = stage.current;
    return zoom === "fit" ? (width && height && el?.clientWidth ? Math.min(el.clientWidth / width, el.clientHeight / height) : 1) : zoom;
  };
  const step = (direction: 1 | -1) => {
    const current = effective();
    const next = direction > 0 ? ZOOMS.find((z) => z > current * 1.001) : [...ZOOMS].reverse().find((z) => z < current * 0.999);
    if (next) setZoom(next);
  };
  const style = zoom === "fit" || !width || !height ? undefined : { width: width * zoom, height: height * zoom };
  return (
    <div className="image-viewer grid gap-3">
      <div
        ref={stage}
        tabIndex={0}
        aria-label={`${name} image. Plus and minus zoom, 0 fits, 1 shows native size.`}
        onKeyDown={(event) => {
          if (event.key === "+" || event.key === "=") { event.preventDefault(); step(1); }
          else if (event.key === "-") { event.preventDefault(); step(-1); }
          else if (event.key === "0") setZoom("fit");
          else if (event.key === "1") setZoom(1);
        }}
        className={cn("image-stage scroll-thin", `bg-${background}`, zoom === "fit" && "fit")}
      >
        {src && <img src={"data:image/png;base64," + src} alt={name + " — 2D image"} draggable={false} style={style} className={cn(!smooth && "pixelated")} />}
      </div>
      <div className="image-toolbar flex flex-wrap items-end gap-2">
        <div className="flex items-center gap-1 rounded-full border border-border p-1">
          <button type="button" onClick={() => setZoom("fit")} aria-label="Fit image to panel" title="Fit image to panel" className="h-8 rounded-full px-3 text-[12px] hover:bg-surface-2"><Maximize className="inline size-3.5" aria-hidden /> Fit</button>
          <button type="button" onClick={() => setZoom(1)} aria-label="Native size (100%)" title="Native size (100%)" className="h-8 rounded-full px-3 text-[12px] hover:bg-surface-2">1:1</button>
          <IconButton label="Zoom out" onClick={() => step(-1)} className="size-8 rounded-full"><Minus className="size-3.5" /></IconButton>
          <span className="image-zoom min-w-12 text-center text-[12px] tabular-nums" aria-live="polite">{zoom === "fit" ? "Fit" : Math.round(zoom * 100) + "%"}</span>
          <IconButton label="Zoom in" onClick={() => step(1)} className="size-8 rounded-full"><Plus className="size-3.5" /></IconButton>
        </div>
        <SelectField id="image-background" label="Background" value={background} onChange={(value) => setState({ imageBackground: value })} options={BACKGROUNDS} className="image-background w-40" />
        <Checkbox className="image-pixelated mb-3 text-[12px]" label="Hard pixel edges" checked={!smooth} onCheckedChange={(checked) => setSmooth(!checked)} />
      </div>
      <p className="image-note text-[12px] leading-relaxed text-muted-foreground">{note}</p>
    </div>
  );
}
