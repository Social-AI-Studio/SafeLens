"use client";

import { useEffect, useRef } from "react";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { EVENT_PANEL_REM } from "@/components/ui/constants";
import { useClampedScrollHeight } from "@/hooks/useClampedScrollHeight";
import type { ClusteredHarmfulContent } from "@/utils/clustering";
import type { HarmfulContent } from "@/types/analysis";

// Simpler approach: use a slightly smaller max height than Event Details so the
// visible bottom edge (wrapper) aligns. Tune this rem delta during visual QA.
const CLUSTER_OVERHEAD_REM = 4.14; // header + padding + border + spacing
const CLUSTER_SCROLL_REM = Math.max(8, EVENT_PANEL_REM - CLUSTER_OVERHEAD_REM);

interface ClusteredAnalysisDataProps {
    clusteredData: ClusteredHarmfulContent[];
    onSeekToTimestamp: (timestamp: number) => void;
    onEventSelect: (event: HarmfulContent) => void;
    onHeightChange?: (px: number) => void;
    onBoxMetricsChange?: (metrics: { height: number; top: number }) => void;
}

export default function ClusteredAnalysisData({
    clusteredData,
    onSeekToTimestamp,
    onEventSelect,
    onHeightChange,
    onBoxMetricsChange,
}: ClusteredAnalysisDataProps) {
    const contentRef = useRef<HTMLDivElement | null>(null);
    const wrapperRef = useRef<HTMLDivElement | null>(null);
    // Clamp ClusteredAnalysis ScrollArea to a slightly smaller max than Event Details
    const [containerHeight, maxHeightCss] = useClampedScrollHeight(
        contentRef,
        CLUSTER_SCROLL_REM,
        [clusteredData],
    );
    // Notify parent with the actual rendered container height (for alignment)
    useEffect(() => {
        if (!wrapperRef.current) return;
        const el = wrapperRef.current;
        const compute = () => {
            const rect = el.getBoundingClientRect();
            const wrapperHeight = rect.height;
            const wrapperTop = rect.top + (window.scrollY || window.pageYOffset);

            // Notify parent with wrapper metrics
            if (wrapperHeight > 0) {
                onHeightChange?.(wrapperHeight);
                onBoxMetricsChange?.({ height: wrapperHeight, top: wrapperTop });
            }

            // No dynamic alignment — parent gets wrapper metrics for optional use
        };
        compute();
        const ro = new ResizeObserver(() => compute());
        ro.observe(el);
        window.addEventListener("resize", compute);
        window.addEventListener("scroll", compute, { passive: true });
        return () => {
            ro.disconnect();
            window.removeEventListener("resize", compute);
            window.removeEventListener("scroll", compute);
        };
    }, [onHeightChange, onBoxMetricsChange, clusteredData, containerHeight]);
    const formatTime = (seconds: number) => {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
    };

    if (clusteredData.length === 0) {
        return null;
    }

    return (
        <div
            ref={wrapperRef}
            className="bg-destructive/10 border border-destructive/20 p-4 rounded-lg overflow-hidden"
        >
            <h4 className="font-medium text-destructive mb-2">Harmful Segments</h4>
            <ScrollArea
                className="w-full"
                style={{ height: containerHeight ?? "auto", maxHeight: maxHeightCss }}
            >
                <div ref={contentRef} className="space-y-3 pr-4">
                    {clusteredData.map((cluster) => {
                        const isActualCluster = cluster.eventCount > 1;
                        return (
                            <div
                                key={cluster.id}
                                className="bg-background p-3 rounded border"
                            >
                                <div className="flex items-center justify-between">
                                    <div className="flex flex-col justify-center">
                                        <span
                                            className="text-blue-600 hover:text-blue-800 cursor-pointer underline font-medium text-xl"
                                            onClick={() => {
                                                onSeekToTimestamp(
                                                    cluster.navigationTimestamp,
                                                );
                                                // Find the highest confidence event for selection
                                                const highestConfidenceEvent =
                                                    cluster.events.reduce(
                                                        (prev, current) =>
                                                            prev.confidence >
                                                            current.confidence
                                                                ? prev
                                                                : current,
                                                    );
                                                onEventSelect(highestConfidenceEvent);
                                            }}
                                        >
                                            {formatTime(cluster.startTime)} –{" "}
                                            {formatTime(cluster.endTime)}
                                        </span>
                                        <div className="flex items-center gap-2 mt-1 text-base text-muted-foreground">
                                            <span>
                                                {cluster.eventCount} event
                                                {cluster.eventCount > 1 ? "s" : ""}
                                            </span>
                                            <span>•</span>
                                            <span>
                                                {Math.round(cluster.duration)}s duration
                                            </span>
                                            {cluster.categories.length > 1 && (
                                                <>
                                                    <span>•</span>
                                                    <span>
                                                        {cluster.categories.length}{" "}
                                                        categories
                                                    </span>
                                                </>
                                            )}
                                        </div>
                                    </div>
                                    <div className="flex flex-col items-end gap-1">
                                        <Badge
                                            variant="destructive"
                                            className="text-base"
                                        >
                                            {Math.round(cluster.maxConfidence * 100)}%
                                            max
                                        </Badge>
                                        {cluster.eventCount > 1 && (
                                            <Badge
                                                variant="outline"
                                                className="text-base"
                                            >
                                                {Math.round(
                                                    cluster.avgConfidence * 100,
                                                )}
                                                % avg
                                            </Badge>
                                        )}
                                    </div>
                                </div>

                                {/* Expandable details for all clusters */}
                                <details className="mt-2">
                                    <summary className="cursor-pointer text-base text-muted-foreground hover:text-foreground">
                                        {isActualCluster
                                            ? "Show individual segments"
                                            : "Show segment details"}
                                    </summary>
                                    <div className="mt-2 space-y-1 pl-4 border-l-2 border-muted">
                                        {cluster.events.map((event, eventIndex) => (
                                            <div
                                                key={eventIndex}
                                                className="text-base flex items-center justify-between"
                                            >
                                                <span
                                                    className="text-blue-500 hover:text-blue-700 cursor-pointer"
                                                    onClick={() => {
                                                        onSeekToTimestamp(
                                                            event.startTime,
                                                        ); // or use midpoint: (event.startTime + event.endTime) / 2
                                                        onEventSelect(event);
                                                    }}
                                                    title={`${formatTime(event.startTime)}–${formatTime(event.endTime)} • ${Math.max(1, Math.round(event.endTime - event.startTime))}s`}
                                                >
                                                    {formatTime(event.startTime)} –{" "}
                                                    {formatTime(event.endTime)} •{" "}
                                                    {Math.max(
                                                        1,
                                                        Math.round(
                                                            event.endTime -
                                                                event.startTime,
                                                        ),
                                                    )}
                                                    s • {event.type}
                                                </span>
                                                <Badge
                                                    variant="outline"
                                                    className="text-sm px-1 py-0"
                                                >
                                                    {Math.round(event.confidence * 100)}
                                                    %
                                                </Badge>
                                            </div>
                                        ))}
                                    </div>
                                </details>
                            </div>
                        );
                    })}
                </div>
            </ScrollArea>
        </div>
    );
}
