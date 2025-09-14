"use client";

import { useEffect, useState, useRef, useMemo, useCallback } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { usePlayer } from "@/context/PlayerContext";
import {
    segmentWordsIntoLines,
    precomputeSearchArrays,
    findActiveLineIndex,
    findActiveWordIndex,
    computeWordProgress,
    type SyncedLyricsConfig,
} from "@/utils/transcription";
import type { TranscriptionWord, TranscriptionLine } from "@/types/analysis";

interface SyncedLyricsProps {
    words: TranscriptionWord[];
    config?: SyncedLyricsConfig;
}

export default function SyncedLyrics({ words, config = {} }: SyncedLyricsProps) {
    const {
        containerHeightClass = "h-60",
        autoScrollBehavior = "smooth",
        highlightMode = "progressive",
        leadMs = 0,
        overlayTransitionMs = 100,
    } = config;

    const { seekTo, subscribeTime } = usePlayer();

    // Memoized line segmentation - only recalculates when words or config change
    const lines = useMemo(() => {
        return segmentWordsIntoLines(words, config);
    }, [words, config]);

    // Memoized search arrays for O(log n) performance during playback
    const { lineStarts, wordStartsByLine } = useMemo(() => {
        return precomputeSearchArrays(lines);
    }, [lines]);

    // Refs for performance - avoid re-renders on time updates
    const currentTimeRef = useRef(0);
    const lastLineIndexRef = useRef(0);
    const lastWordIndexRef = useRef(0);
    // Ref to the actual scrollable viewport of Radix ScrollArea (forwardRef'ed)
    const scrollAreaRef = useRef<HTMLDivElement>(null);

    // React state - only updated when indices actually change
    const [currentLineIndex, setCurrentLineIndex] = useState(0);
    const [currentWordIndex, setCurrentWordIndex] = useState(0);
    const [wordProgress, setWordProgress] = useState(0);

    // Auto-scroll active line into center view - declared before useEffect
    const autoScrollToLine = useCallback(
        (lineIndex: number) => {
            const viewport = scrollAreaRef.current; // Radix viewport element
            if (!viewport) return;

            const line = viewport.querySelector(
                `[data-line-index="${lineIndex}"]`,
            ) as HTMLElement | null;
            if (!line) return;

            // Respect reduced motion preference
            const prefersReducedMotion = window.matchMedia(
                "(prefers-reduced-motion: reduce)",
            ).matches;
            const behavior = prefersReducedMotion
                ? "auto"
                : (autoScrollBehavior as ScrollBehavior);

            // Manually compute center position to constrain scrolling to the viewport only.
            const viewportRect = viewport.getBoundingClientRect();
            const lineRect = line.getBoundingClientRect();

            const currentTop = viewport.scrollTop;
            const lineCenterWithinViewport =
                lineRect.top - viewportRect.top + lineRect.height / 2;
            const targetTop =
                currentTop + lineCenterWithinViewport - viewportRect.height / 2;

            const maxScrollTop = viewport.scrollHeight - viewport.clientHeight;
            const clampedTop = Math.max(0, Math.min(targetTop, maxScrollTop));

            // Use scrollTo on the viewport to avoid scrolling ancestors (page)
            viewport.scrollTo({ top: clampedTop, behavior });
        },
        [autoScrollBehavior],
    );

    // Subscribe to time updates from PlayerContext
    useEffect(() => {
        if (lines.length === 0) return;

        const handleTimeUpdate = (currentTime: number) => {
            // Apply a small lead to line/word detection for better perceived sync
            const effectiveTime = currentTime + (leadMs || 0) / 1000;
            currentTimeRef.current = effectiveTime;

            // Binary search for active line - O(log n)
            const lineIndex = findActiveLineIndex(lineStarts, effectiveTime);

            // Only update state and scroll if line changed
            if (lineIndex !== lastLineIndexRef.current) {
                lastLineIndexRef.current = lineIndex;
                setCurrentLineIndex(lineIndex);
                autoScrollToLine(lineIndex);
            }

            // Handle word-level highlighting within the active line
            if (highlightMode === "progressive" && lines[lineIndex]) {
                const currentLine = lines[lineIndex];

                // Binary search for active word within line - O(log n)
                const wordIndex = findActiveWordIndex(
                    wordStartsByLine[lineIndex],
                    effectiveTime,
                );

                // Only update word state when index changes
                if (wordIndex !== lastWordIndexRef.current) {
                    lastWordIndexRef.current = wordIndex;
                    setCurrentWordIndex(wordIndex);
                }

                // Calculate progressive fill fraction
                const { fraction } = computeWordProgress(currentLine, effectiveTime);
                setWordProgress(fraction);
            }
        };

        // Subscribe to time updates from PlayerContext
        return subscribeTime(handleTimeUpdate);
    }, [
        subscribeTime,
        lines,
        lineStarts,
        wordStartsByLine,
        highlightMode,
        autoScrollToLine,
    ]);

    // Click handlers for seeking
    const handleLineClick = useCallback(
        (line: TranscriptionLine) => {
            seekTo(line.start);
        },
        [seekTo],
    );

    const handleWordClick = useCallback(
        (word: TranscriptionWord, event: React.MouseEvent) => {
            event.stopPropagation(); // Prevent line click from firing
            seekTo(word.start);
        },
        [seekTo],
    );

    // Fallback for insufficient word data
    if (words.length < 3) {
        return (
            <div
                className={`${containerHeightClass} flex items-center justify-center text-muted-foreground italic p-4`}
            >
                Word-level timestamps not available. Synced lyrics require at least 3
                words with timestamps.
            </div>
        );
    }

    return (
        <ScrollArea className={`${containerHeightClass} w-full`} ref={scrollAreaRef}>
            <div className="space-y-3 p-4" role="list" aria-live="polite">
                {lines.map((line, lineIndex) => (
                    <div
                        key={lineIndex}
                        data-line-index={lineIndex}
                        role="listitem"
                        className={`cursor-pointer transition-all duration-200 leading-relaxed ${
                            lineIndex === currentLineIndex
                                ? "text-lg font-semibold opacity-100 text-foreground"
                                : "text-lg opacity-60 hover:opacity-80 text-muted-foreground"
                        }`}
                        onClick={() => handleLineClick(line)}
                        aria-label={`Line ${lineIndex + 1}: ${line.text}`}
                    >
                        <div className="flex flex-wrap gap-1 items-baseline">
                            {line.words.map((word, wordIndex) => {
                                const isActiveWord =
                                    lineIndex === currentLineIndex &&
                                    wordIndex === currentWordIndex;
                                const isPastWord =
                                    lineIndex === currentLineIndex &&
                                    wordIndex < currentWordIndex;

                                return (
                                    <span
                                        key={wordIndex}
                                        className="relative inline-block cursor-pointer hover:underline transition-colors"
                                        onClick={(e) => handleWordClick(word, e)}
                                        aria-label={`Seek to ${word.word} at ${Math.floor(word.start)}s`}
                                        tabIndex={
                                            lineIndex === currentLineIndex ? 0 : -1
                                        }
                                        onKeyDown={(e) => {
                                            if (e.key === "Enter" || e.key === " ") {
                                                e.preventDefault();
                                                handleWordClick(word, e as any);
                                            }
                                        }}
                                    >
                                        {/* Base text layer - always readable by screen readers */}
                                        <span className="relative z-10">
                                            {word.word}
                                        </span>

                                        {/* Progressive highlight overlay - aria-hidden for accessibility */}
                                        {lineIndex === currentLineIndex &&
                                            highlightMode === "progressive" &&
                                            (isPastWord || isActiveWord) && (
                                                <span
                                                    aria-hidden="true"
                                                    className="absolute inset-0 text-primary overflow-hidden z-20"
                                                    style={{
                                                        width: isPastWord
                                                            ? "100%"
                                                            : isActiveWord
                                                              ? `${wordProgress * 100}%`
                                                              : "0%",
                                                        transition:
                                                            overlayTransitionMs &&
                                                            overlayTransitionMs > 0
                                                                ? `width ${overlayTransitionMs}ms linear`
                                                                : "none",
                                                    }}
                                                >
                                                    {word.word}
                                                </span>
                                            )}
                                    </span>
                                );
                            })}
                        </div>
                        {/**
                         * Optional: Show timing info for active line
                         *
                         * {lineIndex === currentLineIndex && (
                         *   <div className="text-xs text-muted-foreground mt-1 opacity-50">
                         *     {Math.floor(line.start)}s - {Math.floor(line.end)}s
                         *   </div>
                         * )}
                         */}
                    </div>
                ))}
            </div>

            {/* Custom styles for enhanced visual feedback */}
            <style jsx>{`
                /* Smooth transitions for word highlighting */
                .word-highlight-overlay {
                    background: linear-gradient(
                        90deg,
                        hsl(var(--primary)) 0%,
                        hsl(var(--primary)) var(--progress, 0%),
                        transparent var(--progress, 0%)
                    );
                }

                /* Enhanced focus states for keyboard navigation */
                [data-line-index] span:focus {
                    outline: 2px solid hsl(var(--ring));
                    outline-offset: 2px;
                    border-radius: 2px;
                }

                /* Active line emphasis */
                [data-line-index].active-line {
                    transform: translateX(4px);
                    border-left: 3px solid hsl(var(--primary));
                    padding-left: 12px;
                }
            `}</style>
        </ScrollArea>
    );
}
