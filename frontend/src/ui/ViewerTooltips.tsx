import { useEffect, useRef, useState } from "react";
import { Tooltip, type TooltipSide } from "@/components/beui/tooltip";
import { focusFromKeyboard, watchModality } from "@/components/beui/tooltip/grace";
import { TOOLTIP_DELAY } from "./primitives";

const ID = "viewer-tooltip";
const SELECTOR = ".model-preview [data-tooltip-text]";

type Tip = { text: string; side: TooltipSide; container: Element | null };

/**
 * The app's tooltip for the plain-JS 3D viewer (`ui/interactive-preview.js`), which can't render React: its controls
 * carry their text in `data-tooltip-text`, and this one controlled tooltip follows hover (after the shared delay) and
 * keyboard focus (at once). In fullscreen the viewer is a modal `<dialog>` in the top layer, so the tooltip renders
 * inside it; anywhere else would be hidden behind it.
 */
export function ViewerTooltips() {
  const anchorRef = useRef<HTMLElement | null>(null);
  const [tip, setTip] = useState<Tip | null>(null);
  const hideRef = useRef(() => {});

  useEffect(() => {
    watchModality();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let keyboard = false;
    const control = (node: EventTarget | null) => (node instanceof Element ? node.closest<HTMLElement>(SELECTOR) : null);
    const read = (element: HTMLElement): Tip => {
      const dialog = element.closest("dialog");
      return {
        text: element.dataset.tooltipText ?? "",
        // The view switcher sits at the bottom of the stage, the corner buttons at the top.
        side: element.closest(".model-views") ? "top" : "bottom",
        container: dialog?.matches(":modal") ? dialog : null,
      };
    };
    const show = (element: HTMLElement) => {
      clearTimeout(timer);
      if (anchorRef.current && anchorRef.current !== element) anchorRef.current.removeAttribute("aria-describedby");
      anchorRef.current = element;
      const next = read(element);
      if (!next.text) return hide();
      element.setAttribute("aria-describedby", ID);
      setTip(next);
    };
    const hide = () => {
      clearTimeout(timer);
      keyboard = false;
      anchorRef.current?.removeAttribute("aria-describedby");
      setTip(null);
    };
    hideRef.current = hide;

    const onOver = (event: PointerEvent) => {
      const element = control(event.target);
      if (!element || event.pointerType === "touch" || element.contains(event.relatedTarget as Node | null)) return;
      clearTimeout(timer);
      // Moving along the toolbar while a label shows switches it at once.
      if (anchorRef.current?.isConnected && anchorRef.current.hasAttribute("aria-describedby")) show(element);
      else timer = setTimeout(() => show(element), TOOLTIP_DELAY);
    };
    const onOut = (event: PointerEvent) => {
      const element = control(event.target);
      if (!element || element.contains(event.relatedTarget as Node | null)) return;
      clearTimeout(timer);
      if (!(keyboard && element === anchorRef.current)) hide();
    };
    // A press dismisses the label; the control's own action is what matters now.
    const onDown = (event: PointerEvent) => {
      if (control(event.target)) hide();
    };
    const onFocusIn = (event: FocusEvent) => {
      const element = control(event.target);
      if (!element || !focusFromKeyboard()) return;
      keyboard = true;
      show(element);
    };
    const onFocusOut = (event: FocusEvent) => {
      const element = control(event.target);
      if (element && element === anchorRef.current && !element.contains(event.relatedTarget as Node | null)) hide();
    };
    document.addEventListener("pointerover", onOver);
    document.addEventListener("pointerout", onOut);
    document.addEventListener("pointerdown", onDown, true);
    document.addEventListener("focusin", onFocusIn);
    document.addEventListener("focusout", onFocusOut);
    return () => {
      clearTimeout(timer);
      document.removeEventListener("pointerover", onOver);
      document.removeEventListener("pointerout", onOut);
      document.removeEventListener("pointerdown", onDown, true);
      document.removeEventListener("focusin", onFocusIn);
      document.removeEventListener("focusout", onFocusOut);
    };
  }, []);

  // The viewer rewrites a label (Fullscreen ↔ Exit fullscreen, a reason that no longer applies) or disposes its
  // controls on a new selection without any pointer or focus event; follow it while the label shows.
  const open = tip !== null;
  useEffect(() => {
    if (!open) return;
    let frame = requestAnimationFrame(function follow() {
      const element = anchorRef.current;
      if (!element?.isConnected || !element.dataset.tooltipText) return hideRef.current();
      const text = element.dataset.tooltipText;
      setTip((current) => (current && current.text !== text ? { ...current, text } : current));
      frame = requestAnimationFrame(follow);
    });
    return () => cancelAnimationFrame(frame);
  }, [open]);

  return (
    <Tooltip
      id={ID}
      open={open}
      onOpenChange={(next) => {
        if (!next) hideRef.current();
      }}
      anchorRef={anchorRef}
      content={tip?.text ?? null}
      side={tip?.side ?? "bottom"}
      container={tip?.container}
    />
  );
}
