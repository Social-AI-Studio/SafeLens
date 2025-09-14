import type { TranscriptionWord, TranscriptionLine } from "@/types/analysis";

export interface SyncedLyricsConfig {
    gapThresholdSec?: number; // default 0.6
    maxWordsPerLine?: number; // default 14
    punctuationBreak?: RegExp; // default /[.!?]/
    autoScrollBehavior?: "smooth" | "instant"; // default 'smooth'
    containerHeightClass?: string; // default 'h-60'
    highlightMode?: "progressive" | "word"; // default 'progressive'
    leadMs?: number; // default 0 (allow advancing highlight slightly)
    overlayTransitionMs?: number; // default 100 (transition for progressive overlay width)
}

/**
 * Segments words into lines based on gaps, punctuation, and max words per line
 */
export function segmentWordsIntoLines(
    words: TranscriptionWord[],
    config: SyncedLyricsConfig = {},
): TranscriptionLine[] {
    const {
        gapThresholdSec = 0.6,
        maxWordsPerLine = 14,
        punctuationBreak = /[.!?]/,
    } = config;

    if (!words || words.length === 0) {
        return [];
    }

    const lines: TranscriptionLine[] = [];
    let currentLine: TranscriptionWord[] = [];

    for (let i = 0; i < words.length; i++) {
        const word = words[i];
        const prevWord = currentLine[currentLine.length - 1];

        const shouldBreak =
            currentLine.length >= maxWordsPerLine ||
            (prevWord && word.start - prevWord.start > gapThresholdSec) ||
            (prevWord && punctuationBreak.test(prevWord.word));

        if (shouldBreak && currentLine.length > 0) {
            const lineStart = currentLine[0].start;
            let lineEnd: number;

            if (i < words.length) {
                lineEnd = words[i].start;
            } else {
                lineEnd = currentLine[currentLine.length - 1].start + 0.6;
            }

            const lineText = currentLine.map((w) => w.word).join(" ");

            lines.push({
                start: lineStart,
                end: lineEnd,
                words: [...currentLine],
                text: lineText,
            });

            currentLine = [];
        }

        currentLine.push(word);
    }

    // Handle final line
    if (currentLine.length > 0) {
        const lineStart = currentLine[0].start;
        const lineEnd = currentLine[currentLine.length - 1].start + 0.6;
        const lineText = currentLine.map((w) => w.word).join(" ");

        lines.push({
            start: lineStart,
            end: lineEnd,
            words: currentLine,
            text: lineText,
        });
    }

    return lines;
}

/**
 * Binary search to find the index of the word/line at a given timestamp
 * Returns the index of the last element where element.start <= currentTime
 */
export function binarySearchWordIndex(starts: number[], currentTime: number): number {
    if (!starts || starts.length === 0) return 0;

    let left = 0;
    let right = starts.length - 1;
    let result = 0;

    while (left <= right) {
        const mid = Math.floor((left + right) / 2);
        if (starts[mid] <= currentTime) {
            result = mid;
            left = mid + 1;
        } else {
            right = mid - 1;
        }
    }

    return result;
}

/**
 * Compute progressive word highlighting progress within a line
 * Returns the active word index and fraction (0-1) for progressive fill
 */
export function computeWordProgress(
    line: TranscriptionLine,
    currentTime: number,
): { wordIndex: number; fraction: number } {
    if (currentTime < line.start) {
        return { wordIndex: 0, fraction: 0 };
    }

    if (currentTime >= line.end) {
        return { wordIndex: line.words.length - 1, fraction: 1 };
    }

    const wordStarts = line.words.map((w) => w.start);
    const wordIndex = binarySearchWordIndex(wordStarts, currentTime);

    const currentWord = line.words[wordIndex];
    const nextWord = line.words[wordIndex + 1];

    // Calculate word end time
    let wordEnd: number;
    if (nextWord) {
        wordEnd = nextWord.start;
    } else {
        wordEnd = line.end;
    }

    // Guard against zero-length intervals with small epsilon
    const duration = wordEnd - currentWord.start;
    const epsilon = 1e-3;
    const safeDuration = Math.max(duration, epsilon);

    // Calculate fraction within the current word
    const elapsed = currentTime - currentWord.start;
    const fraction = Math.min(1, Math.max(0, elapsed / safeDuration));

    return { wordIndex, fraction };
}

/**
 * Precompute arrays for efficient binary search during playback
 * This optimization avoids creating arrays during timeupdate events
 */
export function precomputeSearchArrays(lines: TranscriptionLine[]) {
    return {
        lineStarts: lines.map((l) => l.start),
        wordStartsByLine: lines.map((line) => line.words.map((w) => w.start)),
    };
}

/**
 * Find the active line index based on current time
 * Uses binary search on precomputed line starts for O(log n) performance
 */
export function findActiveLineIndex(lineStarts: number[], currentTime: number): number {
    return binarySearchWordIndex(lineStarts, currentTime);
}

/**
 * Find the active word index within a specific line
 * Uses binary search on precomputed word starts for O(log n) performance
 */
export function findActiveWordIndex(wordStarts: number[], currentTime: number): number {
    return binarySearchWordIndex(wordStarts, currentTime);
}
