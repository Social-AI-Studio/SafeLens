"use client";

import { useState, useMemo, useEffect } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Slider } from "@/components/ui/slider";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import type { HarmfulContent, TranscriptionWord, TranscriptionLine } from "@/types/analysis";
import SyncedLyrics from "@/components/SyncedLyrics";
import { usePlayer } from "@/context/PlayerContext";
import { segmentWordsIntoLines } from "@/utils/transcription";

interface InspectorPanelProps {
    harmfulEvents: HarmfulContent[];
    transcriptionWords?: TranscriptionWord[];
    transcriptionFull?: string;
}

// Heuristic function to generate Radar Data
function getModalityScores(event: HarmfulContent | undefined) {
    if (!event) return { visual: 10, audio: 10, text: 10 };

    let visual = 30;
    let audio = 30;
    let text = 30;

    const desc = (event.description || "").toLowerCase();
    const cats = (event.categories || []).map(c => c.toLowerCase()).join(" ");

    // Heuristics
    if (cats.includes("visual") || desc.includes("scene") || desc.includes("gesture") || desc.includes("text on screen")) {
        visual += 50;
    }
    if (cats.includes("profanity") || cats.includes("slur") || desc.includes("shout") || desc.includes("scream") || desc.includes("said")) {
        audio += 50;
        text += 40;
    }
    if (cats.includes("threat") || desc.includes("confrontation")) {
        visual += 30;
        audio += 40;
    }

    // Normalize to max 95
    return {
        visual: Math.min(95, visual),
        audio: Math.min(95, audio),
        text: Math.min(95, text)
    };
}

// Simple SVG Radar Chart Component
function RadarChart({ scores }: { scores: { visual: number, audio: number, text: number } }) {
    const center = { x: 100, y: 105 };
    const maxDist = 80;

    const p1 = { x: center.x, y: center.y - (maxDist * scores.visual / 100) };
    const p2 = {
        x: center.x - (maxDist * Math.cos(Math.PI / 6) * scores.audio / 100),
        y: center.y + (maxDist * Math.sin(Math.PI / 6) * scores.audio / 100)
    };
    const p3 = {
        x: center.x + (maxDist * Math.cos(Math.PI / 6) * scores.text / 100),
        y: center.y + (maxDist * Math.sin(Math.PI / 6) * scores.text / 100)
    };

    const points = `${p1.x},${p1.y} ${p2.x},${p2.y} ${p3.x},${p3.y}`;

    return (
        <div className="relative w-full h-48 flex items-center justify-center">
            <svg width="200" height="180" viewBox="0 0 200 180" className="overflow-visible">
                <polygon points="100,25 30,145 170,145" fill="none" stroke="#e2e8f0" strokeWidth="1" />
                <polygon points="100,65 53,145 147,145" fill="none" stroke="#e2e8f0" strokeWidth="1" />
                <line x1="100" y1="105" x2="100" y2="25" stroke="#cbd5e1" strokeWidth="1" strokeDasharray="4 2" />
                <line x1="100" y1="105" x2="30" y2="145" stroke="#cbd5e1" strokeWidth="1" strokeDasharray="4 2" />
                <line x1="100" y1="105" x2="170" y2="145" stroke="#cbd5e1" strokeWidth="1" strokeDasharray="4 2" />
                <polygon points={points} fill="rgba(239, 68, 68, 0.2)" stroke="#ef4444" strokeWidth="2" />
                <circle cx={p1.x} cy={p1.y} r="3" fill="#ef4444" />
                <circle cx={p2.x} cy={p2.y} r="3" fill="#ef4444" />
                <circle cx={p3.x} cy={p3.y} r="3" fill="#ef4444" />
                <text x="100" y="15" textAnchor="middle" className="text-[10px] font-bold fill-slate-500 uppercase tracking-wider">Visual</text>
                <text x="20" y="160" textAnchor="middle" className="text-[10px] font-bold fill-slate-500 uppercase tracking-wider">Audio</text>
                <text x="180" y="160" textAnchor="middle" className="text-[10px] font-bold fill-slate-500 uppercase tracking-wider">Text</text>
            </svg>
        </div>
    );
}

export default function InspectorPanel({
    harmfulEvents,
    transcriptionWords,
    transcriptionFull,
}: InspectorPanelProps) {
    const { subscribeTime } = usePlayer();
    const [currentTimestamp, setCurrentTimestamp] = useState(0);
    const [confidenceThreshold, setConfidenceThreshold] = useState(80);

    // Subscribe to time updates from Context
    useEffect(() => {
        return subscribeTime((t) => setCurrentTimestamp(t));
    }, [subscribeTime]);

    // Find active event based on timestamp and threshold
    const activeEvent = useMemo(() => {
        return harmfulEvents.find(
            (e) =>
                currentTimestamp >= e.startTime &&
                currentTimestamp <= e.endTime &&
                e.confidence * 100 >= confidenceThreshold
        );
    }, [currentTimestamp, harmfulEvents, confidenceThreshold]);

    const scores = useMemo(() => getModalityScores(activeEvent), [activeEvent]);

    // Segment words into lines for live context display
    const transcriptLines = useMemo(() => {
        if (!transcriptionWords || transcriptionWords.length < 3) return [];
        return segmentWordsIntoLines(transcriptionWords, {});
    }, [transcriptionWords]);

    // Find the current line index based on timestamp
    const currentLineIndex = useMemo(() => {
        if (!transcriptLines.length) return -1;
        for (let i = transcriptLines.length - 1; i >= 0; i--) {
            if (transcriptLines[i].start <= currentTimestamp) {
                return i;
            }
        }
        return 0;
    }, [transcriptLines, currentTimestamp]);

    // Get prev, current, and next lines for the 3-line display
    const contextLines = useMemo(() => {
        if (currentLineIndex < 0 || !transcriptLines.length) return { prev: null, current: null, next: null };
        return {
            prev: currentLineIndex > 0 ? transcriptLines[currentLineIndex - 1] : null,
            current: transcriptLines[currentLineIndex] || null,
            next: currentLineIndex < transcriptLines.length - 1 ? transcriptLines[currentLineIndex + 1] : null,
        };
    }, [transcriptLines, currentLineIndex]);

    // Find the currently spoken word within the current line
    const currentWordIndex = useMemo(() => {
        const currentLine = contextLines.current;
        if (!currentLine) return -1;
        const words = currentLine.words;
        for (let i = words.length - 1; i >= 0; i--) {
            if (words[i].start <= currentTimestamp) {
                return i;
            }
        }
        return 0;
    }, [contextLines, currentTimestamp]);

    return (
        <div className="h-full flex flex-col space-y-4">
            {/* Header: Confidence Slider */}
            <div className="flex flex-col space-y-3 px-1 shrink-0">
                <div className="flex justify-between items-center">
                    <span className="text-sm font-bold text-muted-foreground uppercase tracking-wider">
                        Confidence Filter
                    </span>
                    <Badge variant="outline" className="font-mono text-sm px-2 py-1">
                        {confidenceThreshold}%
                    </Badge>
                </div>
                <Slider
                    defaultValue={[confidenceThreshold]}
                    max={100}
                    step={1}
                    onValueChange={(vals) => setConfidenceThreshold(vals[0])}
                    className="py-1"
                />
            </div>

            {/* Tabs */}
            <Tabs defaultValue="analysis" className="flex-1 flex flex-col overflow-hidden">
                <TabsList className="grid w-full grid-cols-2 shrink-0">
                    <TabsTrigger value="analysis">Analysis</TabsTrigger>
                    <TabsTrigger value="transcript">Transcript</TabsTrigger>
                </TabsList>

                {/* TAB A: Analysis */}
                <TabsContent value="analysis" className="flex-1 overflow-y-auto min-h-0 text-lg">
                    <Card className="border-0 shadow-none bg-transparent">
                        {activeEvent ? (
                            <div className="space-y-6">
                                {/* Verdict Header */}
                                <div className="flex items-center justify-between border-b pb-4">
                                    <span className="text-lg font-bold text-destructive leading-tight">High Risk</span>
                                    <Badge variant="destructive" className="text-sm px-3 py-1.5 font-mono">
                                        {Math.round(activeEvent.confidence * 100)}%
                                    </Badge>
                                </div>

                                {/* Radar Chart */}
                                <div className="bg-slate-50/50 rounded-lg border border-slate-100 p-4">
                                    <RadarChart scores={scores} />
                                </div>

                                {/* Category Badges */}
                                <div className="flex flex-wrap gap-2 justify-center">
                                    {(activeEvent.categories || []).map((cat) => (
                                        <Badge key={cat} variant="outline" className="border-red-200 text-red-700 bg-red-50 text-sm px-3 py-1">
                                            {cat}
                                        </Badge>
                                    ))}
                                </div>

                                {/* Reasoning */}
                                <div className="space-y-2">
                                    <div className="flex items-center gap-2">
                                        <div className="w-1 h-4 bg-muted-foreground/30 rounded-full" />
                                        <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                                            Model Reasoning
                                        </h4>
                                    </div>
                                    <p className="text-base text-foreground/80 leading-relaxed pl-3 border-l-2 border-muted">
                                        {activeEvent.description}
                                    </p>
                                </div>

                                {/* Live Context - 3 line display */}
                                {contextLines.current && (
                                    <div className="space-y-2">
                                        <div className="flex items-center gap-2">
                                            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                                            <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                                                Live Context
                                            </h4>
                                        </div>
                                        <div className="bg-muted/30 rounded-lg border overflow-hidden">
                                            {/* Previous line */}
                                            {contextLines.prev && (
                                                <div className="px-3 py-2 text-sm text-muted-foreground/50 border-b border-muted/50">
                                                    {contextLines.prev.text}
                                                </div>
                                            )}

                                            {/* Current line with word highlighting */}
                                            <div className="px-3 py-3 bg-background/50">
                                                <p className="text-sm leading-relaxed">
                                                    {contextLines.current.words.map((w, idx) => (
                                                        <span
                                                            key={idx}
                                                            className={`transition-colors duration-150 ${idx === currentWordIndex
                                                                ? "text-foreground font-semibold bg-yellow-200/60 dark:bg-yellow-500/30 px-0.5 rounded"
                                                                : idx < currentWordIndex
                                                                    ? "text-foreground/80"
                                                                    : "text-foreground/50"
                                                                }`}
                                                        >
                                                            {w.word}{idx < contextLines.current!.words.length - 1 ? " " : ""}
                                                        </span>
                                                    ))}
                                                </p>
                                            </div>

                                            {/* Next line */}
                                            {contextLines.next && (
                                                <div className="px-3 py-2 text-sm text-muted-foreground/50 border-t border-muted/50">
                                                    {contextLines.next.text}
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="flex flex-col items-center justify-center flex-1 text-center space-y-4 text-muted-foreground pb-20 text-lg">
                                <span className="text-4xl opacity-50">🛡️</span>
                                <div className="space-y-1">
                                    <h3 className="font-semibold text-xl">No Harmful Content</h3>
                                    <p className="text-base max-w-[240px] mx-auto opacity-70">
                                        Content at this timestamp is considered safe.
                                    </p>
                                </div>
                            </div>
                        )}
                    </Card>
                </TabsContent>

                {/* TAB B: Transcript */}
                <TabsContent value="transcript" className="flex-1 overflow-hidden mt-4 bg-slate-50 rounded-md border relative text-lg">
                    {transcriptionWords && transcriptionWords.length > 0 ? (
                        <div className="absolute inset-0">
                            <SyncedLyrics
                                words={transcriptionWords}
                                config={{ containerHeightClass: "h-full" }}
                            />
                        </div>
                    ) : (
                        <div className="p-4 text-base text-muted-foreground">
                            {transcriptionFull || "No transcription available."}
                        </div>
                    )}
                </TabsContent>
            </Tabs>
        </div>
    );
}
