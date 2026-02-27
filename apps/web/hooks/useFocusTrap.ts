"use client";

import { useCallback, useEffect, useRef } from "react";

/**
 * Manages focus trapping, save/restore, and Escape-to-close for modal dialogs.
 *
 * @param isOpen - Whether the dialog is currently open
 * @param onClose - Callback invoked when user presses Escape
 * @param options.initialFocus - CSS selector for element to focus on open; if omitted, focuses the container
 */
export function useFocusTrap<T extends HTMLElement = HTMLElement>(
  isOpen: boolean,
  onClose: () => void,
  options?: { initialFocus?: string },
) {
  const ref = useRef<T>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  // Save focus on open, restore on close
  useEffect(() => {
    if (isOpen) {
      previousFocusRef.current = document.activeElement as HTMLElement;
      requestAnimationFrame(() => {
        if (options?.initialFocus && ref.current) {
          ref.current.querySelector<HTMLElement>(options.initialFocus)?.focus();
        } else {
          ref.current?.focus();
        }
      });
    } else if (previousFocusRef.current) {
      previousFocusRef.current.focus();
      previousFocusRef.current = null;
    }
  }, [isOpen, options?.initialFocus]);

  // Escape key
  useEffect(() => {
    if (!isOpen) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [isOpen, onClose]);

  // Tab wrapping
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key !== "Tab" || !ref.current) return;
    const focusable = ref.current.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }, []);

  return { ref, handleKeyDown };
}
