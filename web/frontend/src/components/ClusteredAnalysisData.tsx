"use client";

import { useEffect, useRef, type CSSProperties } from "react";
import { Badge } from "@/components/ui/badge";
import type { ClusteredHarmfulContent } from "@/utils/clustering";

interface ClusteredAnalysisDataProps {
    clusteredData: ClusteredHarmfulContent[];
    onSeekToTimestamp: (timestamp: number) => void;
    onHeightChange?: (px: number) => void;
    onBoxMetricsChange?: (metrics: { height: number; top: number }) => void;
    analysisModel?: string;
}

function ConfidenceIndicator({ confidence, animate = false }: { confidence: number; animate?: boolean }) {
    const percent = Math.round(confidence * 100);
    const getColor = () => {
        if (percent >= 90) return "bg-red-500";
        if (percent >= 70) return "bg-orange-500";
        return "bg-yellow-500";
    };
    
    return (
        <div className="flex items-center gap-2">
            <div className="w-12 h-1.5 bg-muted rounded-full overflow-hidden">
                <div 
                    className={`h-full ${getColor()} rounded-full ${animate ? "animate-fill-bar" : ""}`}
                    style={{ 
                        width: `${percent}%`,
                        "--fill-width": `${percent}%`,
                    } as CSSProperties}
                />
            </div>
            <span className="text-sm font-medium text-muted-foreground tabular-nums">
                {percent}%
            </span>
        </div>
    );
}

// Icon components for category types
function AudioIcon({ className }: { className?: string }) {
    return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.536 8.464a5 5 0 010 7.072M18.364 5.636a9 9 0 010 12.728M12 6v12m0 0l-4-4m4 4l4-4" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M11 5L6 9H2v6h4l5 4V5z" />
        </svg>
    );
}

function VisualIcon({ className }: { className?: string }) {
    return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
        </svg>
    );
}

function TextIcon({ className }: { className?: string }) {
    return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
        </svg>
    );
}

// Determine icon based on category keywords
function getCategoryIcon(category: string) {
    const lower = category.toLowerCase();
    
    // Audio-related keywords
    if (lower.includes("profanity") || lower.includes("vulgar") || lower.includes("speech") || 
        lower.includes("audio") || lower.includes("language")) {
        return <AudioIcon className="w-3 h-3" />;
    }
    
    // Visual-related keywords
    if (lower.includes("visual") || lower.includes("nudity") || lower.includes("violence") || 
        lower.includes("graphic") || lower.includes("image") || lower.includes("gesture")) {
        return <VisualIcon className="w-3 h-3" />;
    }
    
    // Text/content-related (default for harassment, threats, etc.)
    return <TextIcon className="w-3 h-3" />;
}

function CategoryPill({ category }: { category: string }) {
    return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium bg-muted/80 text-muted-foreground rounded max-w-[180px]">
            {getCategoryIcon(category)}
            <span className="truncate">{category}</span>
        </span>
    );
}

export default function ClusteredAnalysisData({
    clusteredData,
    onSeekToTimestamp,
    onHeightChange,
    onBoxMetricsChange,
    analysisModel,
}: ClusteredAnalysisDataProps) {
    const wrapperRef = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
        if (!wrapperRef.current) return;
        const el = wrapperRef.current;
        const compute = () => {
            const rect = el.getBoundingClientRect();
            const wrapperHeight = rect.height;
            const wrapperTop = rect.top + (window.scrollY || window.pageYOffset);

            if (wrapperHeight > 0) {
                onHeightChange?.(wrapperHeight);
                onBoxMetricsChange?.({ height: wrapperHeight, top: wrapperTop });
            }
        };
        compute();
        const ro = new ResizeObserver(() => compute());
        ro.observe(el);
        window.addEventListener("resize", compute);
        return () => {
            ro.disconnect();
            window.removeEventListener("resize", compute);
        };
    }, [onHeightChange, onBoxMetricsChange, clusteredData]);

    const formatTime = (seconds: number) => {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
    };

    if (clusteredData.length === 0) {
        return null;
    }

    return (
        <div ref={wrapperRef} className="flex flex-col h-full overflow-x-hidden">
            {/* Sticky header */}
            <div className="sticky top-0 z-10 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80 pb-3">
                <div className="flex items-center justify-between pt-1">
                    <div className="flex items-center gap-2">
                        <h4 className="font-medium text-foreground text-lg">Flagged Segments</h4>
                        <Badge variant="secondary" className="text-xs font-normal">
                            {clusteredData.length} cluster{clusteredData.length !== 1 ? "s" : ""}
                        </Badge>
                    </div>
                    {analysisModel && (
                        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                            <span>Analyzed by</span>
                            <Badge variant="secondary" className="text-xs font-medium">
                                {analysisModel}
                            </Badge>
                        </div>
                    )}
                </div>
            </div>
            
            <div className="space-y-3">
                    {clusteredData.map((cluster, index) => {
                        const isActualCluster = cluster.eventCount > 1;
                        const highestConfidenceEvent = cluster.events.reduce(
                            (prev, current) =>
                                prev.confidence > current.confidence ? prev : current,
                        );

                        return (
                            <div
                                key={cluster.id}
                                className="group relative bg-card border border-border rounded-lg overflow-hidden hover:border-border/80 transition-colors"
                            >
                                {/* Left accent bar - color based on max confidence */}
                                <div 
                                    className={`absolute left-0 top-0 bottom-0 w-1 ${
                                        cluster.maxConfidence >= 0.9 
                                            ? "bg-red-500" 
                                            : cluster.maxConfidence >= 0.7 
                                                ? "bg-orange-500" 
                                                : "bg-yellow-500"
                                    }`}
                                />
                                
                                <div className="pl-4 pr-4 py-3">
                                    {/* Header row */}
                                    <div className="flex items-start justify-between gap-4">
                                        <div className="flex-1 min-w-0">
                                            {/* Timestamp pill */}
                                            <button
                                                onClick={() => {
                                                    onSeekToTimestamp(cluster.navigationTimestamp ?? cluster.startTime);
                                                }}
                                                className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-muted/60 hover:bg-muted rounded-md transition-colors group/btn"
                                            >
                                                <svg 
                                                    className="w-3.5 h-3.5 text-muted-foreground group-hover/btn:text-foreground transition-colors" 
                                                    fill="none" 
                                                    viewBox="0 0 24 24" 
                                                    stroke="currentColor"
                                                >
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                                </svg>
                                                <span className="font-mono text-sm font-medium text-foreground">
                                                    {formatTime(cluster.startTime)}
                                                </span>
                                                <span className="text-muted-foreground text-sm">–</span>
                                                <span className="font-mono text-sm font-medium text-foreground">
                                                    {formatTime(cluster.endTime)}
                                                </span>
                                            </button>
                                            
                                            {/* Meta info */}
                                            <div className="flex items-center gap-3 mt-2 text-sm text-muted-foreground">
                                                <span>{cluster.eventCount} event{cluster.eventCount !== 1 ? "s" : ""}</span>
                                                <span className="w-1 h-1 rounded-full bg-muted-foreground/40" />
                                                <span>{Math.round(cluster.duration)}s</span>
                                            </div>
                                        </div>
                                        
                                        {/* Confidence indicator with animation */}
                                        <div className="flex flex-col items-end gap-1">
                                            <ConfidenceIndicator confidence={cluster.maxConfidence} animate />
                                            {isActualCluster && (
                                                <span className="text-xs text-muted-foreground">
                                                    avg {Math.round(cluster.avgConfidence * 100)}%
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                    
                                    {/* Category tags with icons */}
                                    {cluster.categories.length > 0 && (
                                        <div className="flex flex-wrap gap-1.5 mt-3">
                                            {cluster.categories.slice(0, 4).map((category, idx) => (
                                                <CategoryPill key={idx} category={category} />
                                            ))}
                                            {cluster.categories.length > 4 && (
                                                <span className="inline-flex px-2 py-0.5 text-xs text-muted-foreground">
                                                    +{cluster.categories.length - 4} more
                                                </span>
                                            )}
                                        </div>
                                    )}

                                    {/* Expandable details */}
                                    {isActualCluster && (
                                        <details className="mt-3">
                                            <summary className="cursor-pointer text-sm text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1.5">
                                                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                                </svg>
                                                View {cluster.eventCount} individual segments
                                            </summary>
                                            <div className="mt-2 space-y-1.5 pl-2 border-l border-border/60">
                                                {cluster.events.map((event, eventIndex) => (
                                                    <button
                                                        key={eventIndex}
                                                        onClick={() => {
                                                            onSeekToTimestamp(event.startTime);
                                                        }}
                                                        className="w-full flex items-center justify-between gap-2 px-2 py-1.5 rounded hover:bg-muted/50 transition-colors text-left"
                                                    >
                                                        <div className="flex items-center gap-2 min-w-0">
                                                            <span className="font-mono text-xs text-muted-foreground">
                                                                {formatTime(event.startTime)}
                                                            </span>
                                                            <span className="text-xs text-muted-foreground/60">•</span>
                                                            <span className="text-xs text-muted-foreground truncate">
                                                                {event.type}
                                                            </span>
                                                        </div>
                                                        <ConfidenceIndicator confidence={event.confidence} />
                                                    </button>
                                                ))}
                                            </div>
                                        </details>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
        </div>
    );
}
