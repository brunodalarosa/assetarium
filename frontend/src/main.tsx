import "./styles.css";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import * as store from "./app/store";

// Automation surface for the real-WebView2 verification scripts (scripts/verify-*.py):
// they read state and call the same actions as the UI instead of reaching into React.
Object.defineProperty(window, "lal", {
  value: Object.freeze({ ...store, get state() { return store.getState(); } }),
});

createRoot(document.getElementById("root")!).render(<App />);

const begin = () => {
  if (typeof window.pywebview?.api?.context === "function" && !store.getState().api) void store.start(window.pywebview.api);
};
window.addEventListener("pywebviewready", begin);
begin();
