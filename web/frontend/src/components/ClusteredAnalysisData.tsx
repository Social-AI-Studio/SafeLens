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

function ConfidenceIndicator({ confidence }: { confidence: number; animate?: boolean }) {
    const percent = Math.round(confidence * 100);
    
    // Define styles based on severity
    let styles = {
        bg: "bg-yellow-50",
        text: "text-yellow-700",
        border: "border-yellow-200",
    };
    
    if (percent >= 90) {
        styles = {
            bg: "bg-red-50",
            text: "text-red-700",
            border: "border-red-200",
        };
    } else if (percent >= 70) {
        styles = {
            bg: "bg-orange-50",
            text: "text-orange-700",
            border: "border-orange-200",
        };
    }
    
    return (
        <div className={`flex flex-col items-center justify-center px-4 py-2 rounded-xl border-2 ${styles.bg} ${styles.border} ${styles.text}`}>
            <span className="text-[10px] font-bold uppercase tracking-widest opacity-70 leading-none mb-1">Score</span>
            <span className="text-3xl font-bold tabular-nums leading-none">
                {percent}%
            </span>
        </div>
    );
}

// Icon components for category types - Increased size
function AudioIcon({ className }: { className?: string }) {
    return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.536 8.464a5 5 0 010 7.072M18.364 5.636a9 9 0 010 12.728M12 6v12m0 0l-4-4m4 4l4-4" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M11 5L6 9H2v6h4l5 4V5z" />
        </svg>
    );
}

function VisualIcon({ className }: { className?: string }) {
    return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
        </svg>
    );
}

function TextIcon({ className }: { className?: string }) {
    return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
        </svg>
    );
}

// Determine icon based on category keywords
function getCategoryIcon(category: string) {
    const lower = category.toLowerCase();
    const iconClass = "w-4 h-4"; // Increased from w-3 h-3
    
    // Audio-related keywords
    if (lower.includes("profanity") || lower.includes("vulgar") || lower.includes("speech") || 
        lower.includes("audio") || lower.includes("language")) {
        return <AudioIcon className={iconClass} />;
    }
    
    // Visual-related keywords
    if (lower.includes("visual") || lower.includes("nudity") || lower.includes("violence") || 
        lower.includes("graphic") || lower.includes("image") || lower.includes("gesture")) {
        return <VisualIcon className={iconClass} />;
    }
    
    // Text/content-related (default for harassment, threats, etc.)
    return <TextIcon className={iconClass} />;
}

function CategoryPill({ category }: { category: string }) {
    return (
        <span className="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-semibold bg-secondary text-secondary-foreground rounded-md shadow-sm border border-border/50">
            {getCategoryIcon(category)}
            <span>{category}</span>
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
            <div className="sticky top-0 z-10 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80 pb-4 pt-2">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <h4 className="font-bold text-foreground text-xl">Flagged Segments</h4>
                        <Badge variant="secondary" className="text-sm font-semibold px-2.5 py-0.5">
                            {clusteredData.length} cluster{clusteredData.length !== 1 ? "s" : ""}
                        </Badge>
                    </div>
                    {analysisModel && (
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <span>Analyzed by</span>
                            <Badge variant="outline" className="text-sm font-semibold border-border">
                                {analysisModel}
                            </Badge>
                        </div>
                    )}
                </div>
            </div>
            
            <div className="space-y-4">
                    {clusteredData.map((cluster, index) => {
                        const isActualCluster = cluster.eventCount > 1;

                        return (
                            <div
                                key={cluster.id}
                                className="group relative bg-card border border-border shadow-sm rounded-xl overflow-hidden hover:border-border/80 hover:shadow-md transition-all"
                            >
                                {/* Left accent bar - thickened for visibility */}
                                <div 
                                    className={`absolute left-0 top-0 bottom-0 w-3 ${
                                        cluster.maxConfidence >= 0.9 
                                            ? "bg-red-500" 
                                            : cluster.maxConfidence >= 0.7 
                                                ? "bg-orange-500" 
                                                : "bg-yellow-500"
                                    }`}
                                />
                                
                                <div className="pl-6 pr-5 py-4">
                                    {/* Header row */}
                                    <div className="flex items-start justify-between gap-6">
                                        <div className="flex-1 min-w-0">
                                            {/* Timestamp & Meta */}
                                            <div className="flex flex-wrap items-center gap-4 mb-3">
                                                <button
                                                    onClick={() => {
                                                        onSeekToTimestamp(cluster.navigationTimestamp ?? cluster.startTime);
                                                    }}
                                                    className="inline-flex items-center gap-2 px-3 py-1.5 bg-secondary/50 hover:bg-secondary rounded-lg transition-colors group/btn"
                                                >
                                                    <svg 
                                                        className="w-5 h-5 text-secondary-foreground/70 group-hover/btn:text-foreground transition-colors" 
                                                        fill="none" 
                                                        viewBox="0 0 24 24" 
                                                        stroke="currentColor"
                                                    >
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                                    </svg>
                                                    <span className="font-mono text-xl font-bold text-foreground">
                                                        {formatTime(cluster.startTime)}
                                                    </span>
                                                    <span className="text-muted-foreground font-bold">–</span>
                                                    <span className="font-mono text-xl font-bold text-foreground">
                                                        {formatTime(cluster.endTime)}
                                                    </span>
                                                </button>

                                                <div className="flex items-center gap-3 text-base font-medium text-muted-foreground">
                                                    <span>{cluster.eventCount} event{cluster.eventCount !== 1 ? "s" : ""}</span>
                                                    <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/40" />
                                                    <span>{Math.round(cluster.duration)}s</span>
                                                </div>
                                            </div>

                                            {/* Category tags */}
                                            {cluster.categories.length > 0 && (
                                                <div className="flex flex-wrap gap-2 mt-1">
                                                    {cluster.categories.slice(0, 5).map((category, idx) => (
                                                        <CategoryPill key={idx} category={category} />
                                                    ))}
                                                    {cluster.categories.length > 5 && (
                                                        <span className="inline-flex items-center px-3 py-1 text-sm font-medium text-muted-foreground bg-muted/50 rounded-md">
                                                            +{cluster.categories.length - 5} more
                                                        </span>
                                                    )}
                                                </div>
                                            )}
                                        </div>
                                        
                                        {/* Confidence indicator - Big & Bold */}
                                        <div className="flex flex-col items-end gap-1 shrink-0">
                                            <ConfidenceIndicator confidence={cluster.maxConfidence} animate />
                                        </div>
                                    </div>
                                    
                                    {/* Expandable details - subtle but accessible */}
                                    {isActualCluster && (
                                        <details className="mt-4">
                                            <summary className="cursor-pointer text-sm font-medium text-muted-foreground/80 hover:text-foreground transition-colors flex items-center gap-2 select-none">
                                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                                </svg>
                                                Show individual segments
                                            </summary>
                                            <div className="mt-3 space-y-2 pl-4 border-l-2 border-border/40">
                                                {cluster.events.map((event, eventIndex) => (
                                                    <button
                                                        key={eventIndex}
                                                        onClick={() => {
                                                            onSeekToTimestamp(event.startTime);
                                                        }}
                                                        className="w-full flex items-center justify-between gap-4 px-3 py-2 rounded-md hover:bg-muted/50 transition-colors text-left group/item"
                                                    >
                                                        <div className="flex items-center gap-3 min-w-0">
                                                            <span className="font-mono text-sm font-medium text-muted-foreground group-hover/item:text-foreground transition-colors">
                                                                {formatTime(event.startTime)}
                                                            </span>
                                                            <span className="text-sm font-medium text-foreground/80 truncate">
                                                                {event.type}
                                                            </span>
                                                        </div>
                                                        <span className="text-sm font-bold text-muted-foreground/70 tabular-nums">
                                                            {Math.round(event.confidence * 100)}%
                                                        </span>
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