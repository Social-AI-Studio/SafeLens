"use client";

import { useEffect, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import SyncedLyrics from "@/components/SyncedLyrics";
import type { TranscriptionWord } from "@/types/analysis";
import { useClampedScrollHeight } from "@/hooks/useClampedScrollHeight";

interface AnalysisResultsProps {
    summary?: string;
    transcription?: string;
    transcriptionWords?: TranscriptionWord[];
    isLoading?: boolean;
}

export default function AnalysisResults({
    summary,
    transcription,
    transcriptionWords,
    isLoading = false,
}: AnalysisResultsProps) {
    // Ensure we have valid data
    const validSummary = summary || "No summary available";
    const validTranscription = transcription || "No transcription available";

    // Summary scroll area clamped like ClusteredAnalysis
    // TOTAL_REM budget for the right column (Summary + Transcription)
    // h-86 = 86 * 0.25rem = 21.5rem
    const TOTAL_REM = 21.5;
    // Clamp Summary's scrollable region to this rem height (matches prior max-h-26)
    const SUMMARY_SCROLL_REM = 6.5;
    const summaryContentRef = useRef<HTMLDivElement | null>(null);
    const [summaryContainerHeightPx, summaryMaxHeightCss] = useClampedScrollHeight(
        summaryContentRef,
        SUMMARY_SCROLL_REM,
        [validSummary, isLoading],
    );

    // Calculate a fallback transcription height for the loading state so that
    // summary + transcription heights add up to TOTAL_REM.
    const rootFontSize =
        typeof window !== "undefined"
            ? parseFloat(getComputedStyle(document.documentElement).fontSize) || 16
            : 16;
    const SUMMARY_MAX_REM = SUMMARY_SCROLL_REM; // for fallback
    const totalPx = TOTAL_REM * rootFontSize;
    const summaryPx = summaryContainerHeightPx ?? SUMMARY_MAX_REM * rootFontSize;
    const computedTranscriptionHeightPx = Math.max(0, totalPx - summaryPx);
    const lineBlockPx = rootFontSize + 8; // 1rem skeleton line height + ~8px gap
    const estimatedLines = Math.max(
        6,
        Math.floor(Math.max(0, computedTranscriptionHeightPx - 8) / lineBlockPx),
    );
    const skeletonWidths = [
        "100%",
        "95%",
        "90%",
        "85%",
        "92%",
        "88%",
        "80%",
        "73%",
        "100%",
        "67%",
    ];

    return (
        <div className="space-y-4">
            <Card>
                <CardHeader>
                    <CardTitle>Summary</CardTitle>
                </CardHeader>
                <CardContent>
                    {/* ClusteredAnalysis pattern: rounded + overflow-hidden wrapper; clamped ScrollArea height */}
                    <div className="w-full rounded-md overflow-hidden">
                        <ScrollArea
                            className="w-full"
                            style={{
                                height: summaryContainerHeightPx ?? "auto",
                                maxHeight: summaryMaxHeightCss,
                            }}
                        >
                            <div ref={summaryContentRef} className="pr-4">
                                {isLoading ? (
                                    <div className="space-y-2 py-1">
                                        <Skeleton className="h-4 w-full" />
                                        <Skeleton className="h-4 w-3/4" />
                                        <Skeleton className="h-4 w-1/2" />
                                    </div>
                                ) : (
                                    <div className="text-base leading-relaxed break-words whitespace-pre-wrap">
                                        {validSummary}
                                    </div>
                                )}
                            </div>
                        </ScrollArea>
                    </div>
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Transcription</CardTitle>
                </CardHeader>
                <CardContent>
                    {/* Maintain total height budget: summary height + transcription height = TOTAL_REM */}
                    <div
                        style={{ height: computedTranscriptionHeightPx }}
                        className="w-full"
                    >
                        {isLoading ? (
                            <div className="space-y-2">
                                {Array.from({ length: estimatedLines }).map((_, i) => (
                                    <Skeleton
                                        key={i}
                                        className="h-4"
                                        style={{
                                            width: skeletonWidths[
                                                i % skeletonWidths.length
                                            ],
                                        }}
                                    />
                                ))}
                            </div>
                        ) : (
                            // Conditional rendering: SyncedLyrics when word data available, static fallback otherwise
                            <>
                                {transcriptionWords &&
                                transcriptionWords.length >= 3 ? (
                                    <SyncedLyrics
                                        words={transcriptionWords}
                                        config={{
                                            containerHeightClass: "h-full",
                                            autoScrollBehavior: "smooth",
                                            highlightMode: "progressive",
                                            leadMs: 120,
                                            overlayTransitionMs: 100,
                                            gapThresholdSec: 0.6,
                                            maxWordsPerLine: 14,
                                        }}
                                    />
                                ) : (
                                    <ScrollArea className="h-full w-full">
                                        <div className="text-lg leading-relaxed">
                                            {validTranscription ? (
                                                validTranscription
                                                    .split("\n")
                                                    .map((line, index) => (
                                                        <div
                                                            key={index}
                                                            className="mb-2"
                                                        >
                                                            {line}
                                                        </div>
                                                    ))
                                            ) : (
                                                <div className="text-muted-foreground italic">
                                                    Video transcription will appear here
                                                    once processing is complete.
                                                </div>
                                            )}
                                        </div>
                                    </ScrollArea>
                                )}
                            </>
                        )}
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
