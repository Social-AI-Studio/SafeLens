"use client";

import { useEffect, useRef, useCallback, useState, useMemo } from "react";
import {
    MediaPlayer,
    MediaProvider,
    useMediaState,
    useMediaRemote,
    type MediaPlayerInstance,
} from "@vidstack/react";
import "@vidstack/react/player/styles/base.css";
import { usePlayer } from "@/context/PlayerContext";

// Simple inline SVG icons
const PlayIcon = () => (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6">
        <path d="M8 5v14l11-7z" />
    </svg>
);

const PauseIcon = () => (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6">
        <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
    </svg>
);

const MuteIcon = () => (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
        <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z" />
    </svg>
);

const VolumeHighIcon = () => (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
        <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z" />
    </svg>
);

const FullscreenIcon = () => (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
        <path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z" />
    </svg>
);

const FullscreenExitIcon = () => (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
        <path d="M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z" />
    </svg>
);

interface HarmfulSegment {
    time: number;
    endTime: number;
    confidence: number;
    eventCount?: number;
    categories?: string[];
    navigationTimestamp?: number;
}

interface VidstackPlayerProps {
    src?: string;
    harmfulSegments?: HarmfulSegment[];
    onReady?: (player: MediaPlayerInstance) => void;
}

const GAP_PX = 3;

function formatTime(seconds: number): string {
    if (!seconds || !isFinite(seconds)) return "00:00";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
}

function getSegmentColor(confidence: number): string {
    if (confidence >= 0.9) return "bg-red-500";
    if (confidence >= 0.7) return "bg-orange-500";
    return "bg-yellow-500";
}

interface SegmentedTimelineProps {
    segments: HarmfulSegment[];
}

function SegmentedTimeline({ segments }: SegmentedTimelineProps) {
    const duration = useMediaState("duration");
    const currentTime = useMediaState("currentTime");
    const remote = useMediaRemote();
    const containerRef = useRef<HTMLDivElement>(null);
    const [hoveredSegment, setHoveredSegment] = useState<HarmfulSegment | null>(null);
    const [hoverX, setHoverX] = useState(0);

    // Build chapters from segments
    const chapters = useMemo(() => {
        if (!duration || duration <= 0) return [];

        const sorted = [...segments].sort((a, b) => a.time - b.time);
        const result: Array<{
            start: number;
            end: number;
            isHarmful: boolean;
            segment?: HarmfulSegment;
        }> = [];

        // Threshold for tiny gaps (in seconds) - gaps smaller than this get absorbed
        const GAP_THRESHOLD = 2;

        let cursor = 0;

        for (let i = 0; i < sorted.length; i++) {
            const seg = sorted[i];
            
            // Only add safe section if gap is significant
            if (seg.time > cursor + GAP_THRESHOLD) {
                result.push({ start: cursor, end: seg.time, isHarmful: false });
                cursor = seg.time;
            }
            
            // Start harmful segment from cursor if gap was tiny
            const actualStart = seg.time <= cursor + GAP_THRESHOLD ? cursor : seg.time;
            result.push({ start: actualStart, end: seg.endTime, isHarmful: true, segment: seg });
            cursor = Math.max(cursor, seg.endTime);
        }

        // Always add trailing safe section if there's any remaining duration
        // (unlike internal gaps, the end section should always be visible)
        if (cursor < duration) {
            result.push({ start: cursor, end: duration, isHarmful: false });
        }

        return result;
    }, [duration, segments]);

    const handleClick = useCallback(
        (e: React.MouseEvent) => {
            if (!containerRef.current || !duration || duration <= 0) return;

            const rect = containerRef.current.getBoundingClientRect();
            const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
            const percent = x / rect.width;
            const seekTime = percent * duration;
            remote.seek(seekTime);
        },
        [duration, remote]
    );

    const handleMouseMove = useCallback(
        (e: React.MouseEvent) => {
            if (!containerRef.current || !duration || duration <= 0) return;

            const rect = containerRef.current.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const percent = x / rect.width;
            const hoverTime = percent * duration;
            setHoverX(e.clientX);

            // Find if hovering over a harmful segment
            for (const chapter of chapters) {
                if (hoverTime >= chapter.start && hoverTime <= chapter.end && chapter.isHarmful && chapter.segment) {
                    setHoveredSegment(chapter.segment);
                    return;
                }
            }
            setHoveredSegment(null);
        },
        [duration, chapters]
    );

    // Calculate progress percentage
    const progressPercent = duration && duration > 0 ? (currentTime / duration) * 100 : 0;

    if (!duration || duration <= 0) {
        return <div className="w-full h-2 bg-white/20 rounded-full" />;
    }

    // If no harmful segments, show simple progress bar
    if (segments.length === 0) {
        return (
            <div className="relative w-full group/timeline">
                <div
                    ref={containerRef}
                    className="relative w-full h-1.5 bg-white/30 rounded-full cursor-pointer overflow-hidden transition-all duration-150 group-hover/timeline:h-3"
                    onClick={handleClick}
                >
                    <div
                        className="absolute left-0 top-0 h-full bg-white/80 rounded-full"
                        style={{ width: `${progressPercent}%` }}
                    />
                </div>
            </div>
        );
    }

    return (
        <div className="relative w-full group/timeline">
            <div
                ref={containerRef}
                className="relative w-full h-1.5 flex cursor-pointer transition-all duration-150 group-hover/timeline:h-3"
                onClick={handleClick}
                onMouseMove={handleMouseMove}
                onMouseLeave={() => setHoveredSegment(null)}
                style={{ gap: `${GAP_PX}px` }}
            >
                {chapters.map((chapter, idx) => {
                    const widthPercent = ((chapter.end - chapter.start) / duration) * 100;
                    
                    // Calculate fill percentage for this specific chapter
                    let fillPercent = 0;
                    if (currentTime >= chapter.end) {
                        fillPercent = 100; // Fully played
                    } else if (currentTime > chapter.start) {
                        fillPercent = ((currentTime - chapter.start) / (chapter.end - chapter.start)) * 100;
                    }

                    return (
                        <div
                            key={idx}
                            className={`relative h-full rounded-sm transition-colors flex-shrink-0 overflow-hidden ${
                                chapter.isHarmful
                                    ? getSegmentColor(chapter.segment!.confidence)
                                    : "bg-white/30"
                            }`}
                            style={{ 
                                width: `calc(${widthPercent}% - ${(GAP_PX * (chapters.length - 1) * widthPercent) / 100}px)`,
                            }}
                        >
                            {/* Per-chapter progress fill */}
                            {fillPercent > 0 && (
                                <div 
                                    className="absolute left-0 top-0 h-full bg-white/40 pointer-events-none"
                                    style={{ width: `${fillPercent}%` }}
                                />
                            )}
                        </div>
                    );
                })}

                {/* Scrubber - always visible */}
                <div
                    className="absolute top-1/2 w-3 h-3 bg-white rounded-full shadow-md pointer-events-none z-10"
                    style={{ 
                        left: `${progressPercent}%`, 
                        transform: "translateX(-50%) translateY(-50%)" 
                    }}
                />
            </div>

            {/* Hover tooltip */}
            {hoveredSegment && (
                <div
                    className="fixed z-50 px-3 py-2 bg-black/90 border border-white/20 rounded-lg shadow-xl text-sm pointer-events-none"
                    style={{
                        left: hoverX,
                        top: containerRef.current ? containerRef.current.getBoundingClientRect().top - 60 : 0,
                        transform: "translateX(-50%)",
                    }}
                >
                    <div className="font-medium text-white">
                        {formatTime(hoveredSegment.time)} – {formatTime(hoveredSegment.endTime)}
                    </div>
                    <div className="flex items-center gap-2 mt-1 text-white/70 text-xs">
                        <span className={`w-2 h-2 rounded-full ${getSegmentColor(hoveredSegment.confidence)}`} />
                        <span>{Math.round(hoveredSegment.confidence * 100)}% confidence</span>
                        {hoveredSegment.eventCount && hoveredSegment.eventCount > 1 && (
                            <span>• {hoveredSegment.eventCount} events</span>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}

function PlayerControls({ segments }: { segments: HarmfulSegment[] }) {
    const isPaused = useMediaState("paused");
    const currentTime = useMediaState("currentTime");
    const duration = useMediaState("duration");
    const muted = useMediaState("muted");
    const fullscreen = useMediaState("fullscreen");
    const remote = useMediaRemote();

    const handleVideoClick = useCallback(() => {
        if (isPaused) {
            remote.play();
        } else {
            remote.pause();
        }
    }, [isPaused, remote]);

    return (
        <>
            {/* Click overlay for play/pause */}
            <div 
                className="absolute inset-0 cursor-pointer" 
                onClick={handleVideoClick}
                style={{ bottom: "80px" }} // Leave space for controls
            />
            
            <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 via-black/40 to-transparent px-4 pb-3 pt-12 opacity-0 group-hover:opacity-100 transition-opacity">
            {/* Timeline */}
            <div className="mb-3">
                <SegmentedTimeline segments={segments} />
            </div>

            {/* Controls row */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    {/* Play/Pause */}
                    <button
                        onClick={() => (isPaused ? remote.play() : remote.pause())}
                        className="w-10 h-10 flex items-center justify-center text-white hover:text-white/80 transition-colors"
                    >
                        {isPaused ? <PlayIcon /> : <PauseIcon />}
                    </button>

                    {/* Volume */}
                    <button
                        onClick={() => remote.toggleMuted()}
                        className="w-10 h-10 flex items-center justify-center text-white hover:text-white/80 transition-colors"
                    >
                        {muted ? <MuteIcon /> : <VolumeHighIcon />}
                    </button>

                    {/* Time display */}
                    <span className="text-white text-sm font-mono">
                        {formatTime(currentTime)} / {formatTime(duration)}
                    </span>
                </div>

                <div className="flex items-center gap-3">
                    {/* Fullscreen */}
                    <button
                        onClick={() => remote.toggleFullscreen()}
                        className="w-10 h-10 flex items-center justify-center text-white hover:text-white/80 transition-colors"
                    >
                        {fullscreen ? <FullscreenExitIcon /> : <FullscreenIcon />}
                    </button>
                </div>
            </div>
        </div>
        </>
    );
}

export default function VidstackPlayer({
    src,
    harmfulSegments = [],
    onReady,
}: VidstackPlayerProps) {
    const playerRef = useRef<MediaPlayerInstance>(null);
    const { setPlayer, fanOutTime, fanOutDuration } = usePlayer();

    useEffect(() => {
        if (playerRef.current) {
            setPlayer(playerRef.current);
            onReady?.(playerRef.current);
        }
        return () => setPlayer(null);
    }, [setPlayer, onReady]);

    if (!src) {
        return (
            <div className="w-full h-full bg-black flex items-center justify-center text-white/50">
                No video source
            </div>
        );
    }

    return (
        <>
            <style jsx global>{`
                [data-media-player] {
                    background: black !important;
                }
                [data-media-provider] {
                    background: transparent !important;
                }
            `}</style>
            <MediaPlayer
                ref={playerRef}
                src={src}
                crossOrigin
                playsInline
                className="w-full h-full !bg-black relative group"
                onTimeUpdate={() => {
                    if (playerRef.current) {
                        fanOutTime(playerRef.current.currentTime);
                    }
                }}
                onDurationChange={() => {
                    if (playerRef.current) {
                        fanOutDuration(playerRef.current.duration);
                    }
                }}
            >
                <MediaProvider className="w-full h-full [&>video]:w-full [&>video]:h-full [&>video]:object-contain" />
                <PlayerControls segments={harmfulSegments} />
            </MediaPlayer>
        </>
    );
}
