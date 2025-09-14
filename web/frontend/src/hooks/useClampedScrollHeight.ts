"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Observe the rendered height of a content element and clamp a scroll container's
 * height to the smaller of the content height and a max height (in rem).
 *
 * Returns a tuple of [containerHeightPx | null, maxHeightCss]. Use as:
 *   const [height, maxCss] = useClampedScrollHeight(ref, 24, [deps])
 *   <ScrollArea style={{ height: height ?? 'auto', maxHeight: maxCss }} />
 */
export function useClampedScrollHeight(
    contentRef: React.RefObject<HTMLElement | null>,
    maxRem: number,
    deps: React.DependencyList = [],
    overrideMaxPx?: number | null,
): [number | null, string] {
    const [height, setHeight] = useState<number | null>(null);
    const observedRef = useRef<HTMLElement | null>(null);

    useEffect(() => {
        if (typeof window === "undefined") return;

        const compute = () => {
            const rootFontSize =
                parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
            const maxPx = overrideMaxPx ?? maxRem * rootFontSize;
            const contentPx = contentRef.current?.getBoundingClientRect().height || 0;
            const target = Math.min(contentPx, maxPx);
            setHeight(target);
        };

        compute();

        const ro = new ResizeObserver(() => compute());
        // Re-observe if ref.current changes
        if (observedRef.current && observedRef.current !== contentRef.current) {
            ro.unobserve(observedRef.current);
        }
        if (contentRef.current) {
            ro.observe(contentRef.current);
            observedRef.current = contentRef.current;
        }

        window.addEventListener("resize", compute);
        return () => {
            ro.disconnect();
            window.removeEventListener("resize", compute);
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [contentRef, maxRem, overrideMaxPx, ...deps]);

    return [height, `${maxRem}rem`];
}
