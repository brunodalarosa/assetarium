import { Checkbox } from "@/components/beui/checkbox";

// Formats Assetarium uses (decision 0026): one toggle each; assets only in formats that are off are hidden everywhere.
export const MODEL_FORMATS: [string, string, string][] = [
  ["fbx", "FBX", "Rigs and animation; common in Unity and Unreal."],
  ["gltf", "glTF / GLB", "Open format with PBR materials, rigs and animation."],
  ["obj", "OBJ", "Simple static meshes without skeletons or animation."],
];
export const IMAGE_FORMATS: [string, string][] = [
  ["png", "PNG"], ["jpeg", "JPEG (.jpg)"], ["svg", "SVG"], ["webp", "WebP"], ["tga", "TGA"], ["tiff", "TIFF (.tif)"],
  ["bmp", "BMP"], ["gif", "GIF"], ["avif", "AVIF"],
];
export const FORMATS_HELP = "Assets whose files are only in formats you turn off are hidden: from the Library, search and your agent. Turning a format back on brings them back with their results; nothing is deleted or scanned again.";

/** A set of format checkboxes that keeps the list's order. ``onChange`` gets an update of the current list, so quick
 *  clicks in a row never undo each other. */
export function FormatToggles({ id, options, value, onChange, disabled, columns }: {
  id: string; options: [string, string, string?][]; value: string[]; onChange: (update: (current: string[]) => string[]) => void;
  disabled?: boolean; columns?: boolean;
}) {
  return (
    <fieldset id={id} disabled={disabled} className={columns ? "grid gap-3" : "flex flex-wrap gap-x-8 gap-y-3"}>
      {options.map(([format, label, note]) => (
        <Checkbox key={format} id={`${id}-${format}`} label={label} description={note} disabled={disabled} checked={value.includes(format)}
          onCheckedChange={(checked) => onChange((current) => checked ? options.map(([f]) => f).filter((f) => f === format || current.includes(f)) : current.filter((f) => f !== format))} />
      ))}
    </fieldset>
  );
}

export function ImageFormatsNote() {
  return <p className="text-[12px] text-muted-foreground">These cover images that are assets on their own. Textures used by 3D models are always read, whatever you choose here.</p>;
}
