import { LibraryBig } from "lucide-react";

const PAGES = {
  library: { title: "Library", icon: LibraryBig, body: "Your whole library, organized for browsing, will live here." },
};

/** Reserved destinations; they intentionally offer no actions yet. */
export function Placeholder({ page }: { page: keyof typeof PAGES }) {
  const { title, icon: Icon, body } = PAGES[page];
  return (
    <div id={`${page}-view`} className="flex h-full flex-col overflow-y-auto px-8 pb-10">
      <h1 className="text-[26px] font-semibold text-foreground">{title}</h1>
      <div className="grid flex-1 place-items-center content-center gap-4 pb-[12vh] text-center">
        <span aria-hidden className="grid size-[72px] place-items-center rounded-2xl bg-surface text-muted-foreground"><Icon className="size-7" strokeWidth={1.5} /></span>
        <p className="text-[17px] font-semibold text-foreground">Coming in a later version</p>
        <p className="max-w-[340px] text-[13px] leading-relaxed text-muted-foreground">{body} Search from Home in the meantime.</p>
      </div>
    </div>
  );
}
