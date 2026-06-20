import { useEffect, useRef, useState } from "react";

/** Returns a debounced copy of `value` that updates after `delay` ms. */
export function useDebouncedValue<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(id);
  }, [value, delay]);
  return debounced;
}

/** Imperative debounce for callbacks (e.g. map move handlers). */
export function useDebouncedCallback<A extends unknown[]>(
  fn: (...args: A) => void,
  delay = 300,
): (...args: A) => void {
  const timer = useRef<number>();
  const fnRef = useRef(fn);
  fnRef.current = fn;
  useEffect(() => () => window.clearTimeout(timer.current), []);
  return (...args: A) => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => fnRef.current(...args), delay);
  };
}
