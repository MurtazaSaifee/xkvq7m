/** True when the user has asked the system to reduce motion. Charts turn their animation off then. */
export function prefersReducedMotion(): boolean {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
}
