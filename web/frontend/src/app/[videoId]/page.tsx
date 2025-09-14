"use client";

import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import VideoPlayer from "@/components/VideoPlayer";
import AnalysisResults from "@/components/AnalysisResults";
import ClusteredAnalysisData from "@/components/ClusteredAnalysisData";
import EventExplanation from "@/components/EventExplanation";
import { clusterHarmfulEvents, createSingleEventCluster } from "@/utils/clustering";
import type { ClusteringConfig, ClusteredHarmfulContent } from "@/utils/clustering";
import type { AnalysisData, HarmfulContent, TranscriptionWord } from "@/types/analysis";
import { PlayerProvider, usePlayer } from "@/context/PlayerContext";

function parseToSeconds(hms: string): number {
    if (!hms || typeof hms !== "string") return 0;
    const parts = hms.split(":");
    try {
        if (parts.length === 3) {
            const h = parseInt(parts[0], 10),
                m = parseInt(parts[1], 10),
                s = parseFloat(parts[2]);
            return h * 3600 + m * 60 + s;
        } else if (parts.length === 2) {
            const m = parseInt(parts[0], 10),
                s = parseFloat(parts[1]);
            return m * 60 + s;
        }
        return parseFloat(parts[0]);
    } catch {
        return 0;
    }
}

function VideoAnalysisContent() {
    const params = useParams();
    const router = useRouter();
    const { data: session, status } = useSession();
    const { setPlayer } = usePlayer();
    const videoId = useMemo(() => {
        return Array.isArray(params.videoId)
            ? params.videoId[0]
            : (params.videoId as string);
    }, [params.videoId]);

    const videoSrc = useMemo(() => {
        return videoId ? `/api/videos/${videoId}/video.mp4` : "";
    }, [videoId]);
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [analysisData, setAnalysisData] = useState<AnalysisData | null>(null);
    const [videoPlayer, setVideoPlayer] = useState<any>(null);
    const [selectedEvent, setSelectedEvent] = useState<HarmfulContent | null>(null);
    const [clusterPanelHeight, setClusterPanelHeight] = useState<number | null>(null);
    const [clusterBoxMetrics, setClusterBoxMetrics] = useState<{
        height: number;
        top: number;
    } | null>(null);
    const eventBoxRef = useRef<HTMLDivElement | null>(null);
    const [eventTop, setEventTop] = useState<number | null>(null);
    const [eventHeight, setEventHeight] = useState<number | null>(null);

    const hasStartedAnalysisRef = useRef(false);

    const [clusteringConfig, setClusteringConfig] = useState<ClusteringConfig>({
        gapThreshold: 2.5,
        clusterAcrossCategories: true,
        minimumConfidence: 0.1,
    });

    // Format time in xx:xx format
    const formatTime = (seconds: number) => {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
    };

    const handlePlayerReady = useCallback(
        (player: any) => {
            setVideoPlayer(player);
            setPlayer(player);
        },
        [setPlayer],
    );

    const seekToTimestamp = (timestamp: number) => {
        if (videoPlayer) {
            videoPlayer.currentTime(timestamp);
            if (videoPlayer.paused()) {
                // Optionally start playing
                // videoPlayer.play();
            }
        }
    };

    const transformBackendData = useCallback((backendData: any): AnalysisData => {
        if (!backendData || typeof backendData !== "object") {
            return {
                summary: "Error: Invalid data received from backend",
                transcription: "No transcription available",
                harmfulContent: [],
            };
        }

        const safetyReport = backendData.safety_report || {};
        const harmfulEvents = safetyReport.harmful_events || [];
        const transcriptionData = safetyReport.transcription || {};

        const videoMetadata = safetyReport.video_metadata || {};
        const analysisModel =
            safetyReport.model_used || videoMetadata.analysis_model || "Unknown";

        const harmfulContent: HarmfulContent[] = harmfulEvents.map((event: any) => {
            if (event && "segment_start" in event) {
                const start = parseToSeconds(event.segment_start);
                const end = parseToSeconds(event.segment_end);
                const data = event.analysis_data || {};
                const confidence =
                    (typeof data.confidence === "number" ? data.confidence : 0) / 100;
                const categories = Array.isArray(data.categories)
                    ? data.categories
                    : [];
                const description =
                    data.explanation || "Harmful content detected through AI analysis";
                const method = Array.isArray(event.analysis_performed)
                    ? event.analysis_performed.join(", ")
                    : "analysis";
                const evidence = event.audio_evidence || "";

                return {
                    startTime: start,
                    endTime: end,
                    confidence,
                    type: categories.length ? categories.join(", ") : "harmful content",
                    description,
                    evidence,
                    source: "multimodal",
                    detectionMethod: method,
                    categories,
                    rawData: event,
                } as HarmfulContent;
            }

            return {
                startTime: event.timestamp || 0,
                endTime: (event.timestamp || 0) + 1,
                confidence: (event.confidence_score || 0) / 100,
                type: Array.isArray(event.categories)
                    ? event.categories.join(", ")
                    : event.categories || "harmful content",
                description:
                    event.description ||
                    event.explanation ||
                    event.details ||
                    "Harmful content detected through AI analysis",
                evidence: event.evidence || event.reasoning || event.context || "",
                source: event.detection_source || event.source || "vision",
                detectionMethod:
                    event.detection_method || event.method || "Multi-modal AI analysis",
                categories: Array.isArray(event.categories)
                    ? event.categories
                    : [event.categories || "harmful content"],
                rawData: event,
            } as HarmfulContent;
        });

        let summary = "Analysis completed successfully.";
        if (videoMetadata.summary) summary = videoMetadata.summary;
        else if (safetyReport.harmful_events_summary)
            summary = safetyReport.harmful_events_summary;
        else if (safetyReport.detailed_evidence)
            summary = safetyReport.detailed_evidence;

        let transcription = "Transcription not available.";
        if (transcriptionData.full_text) transcription = transcriptionData.full_text;
        else if (backendData.full_transcript)
            transcription = backendData.full_transcript;

        let transcriptionWords: TranscriptionWord[] | undefined;
        if (transcriptionData.word_timestamps) {
            try {
                transcriptionWords = (transcriptionData.word_timestamps as any[])
                    .filter(
                        (it) =>
                            Array.isArray(it) &&
                            it.length >= 2 &&
                            typeof it[1] === "number",
                    )
                    .map((it) => ({ word: String(it[0]).trim(), start: Number(it[1]) }))
                    .sort((a, b) => a.start - b.start);
            } catch (e) {
                console.warn("Failed to parse word_timestamps:", e);
                transcriptionWords = undefined;
            }
        }

        return {
            summary,
            transcription,
            harmfulContent,
            analysisModel,
            transcriptionWords,
        } as AnalysisData;
    }, []);

    const checkVideoStatus = useCallback(async (videoId: string) => {
        const statusResponse = await fetch(`/api/analyze/${videoId}/status`);
        if (!statusResponse.ok) throw new Error("Failed to check status");
        return statusResponse.json();
    }, []);

    const fetchResults = useCallback(
        async (videoId: string) => {
            const resultsResponse = await fetch(`/api/analyze/${videoId}/results`);
            if (!resultsResponse.ok) throw new Error("Failed to fetch results");

            const resultsData = await resultsResponse.json();
            const analysisData = transformBackendData(resultsData);
            setAnalysisData(analysisData);
            setIsAnalyzing(false);
        },
        [transformBackendData],
    );

    const pollForAnalysis = useCallback(
        async (videoId: string) => {
            const maxAttempts = 120; // 10 minutes with 5-second intervals
            let attempts = 0;

            const poll = async (): Promise<void> => {
                try {
                    const statusData = await checkVideoStatus(videoId);

                    if (statusData.status === "completed") {
                        await fetchResults(videoId);
                        return;
                    }

                    if (statusData.status === "failed") {
                        setIsAnalyzing(false);
                        return;
                    }

                    // Continue polling
                    attempts++;
                    if (attempts < maxAttempts) {
                        await new Promise((resolve) => setTimeout(resolve, 10000));
                        await poll();
                    } else {
                        setIsAnalyzing(false); // Timeout
                    }
                } catch (error) {
                    console.error("Polling error:", error);
                    setIsAnalyzing(false);
                }
            };

            poll();
        },
        [checkVideoStatus, fetchResults],
    );

    const startAnalysis = useCallback(
        async (videoId: string) => {
            setIsAnalyzing(true);
            setAnalysisData(null);

            try {
                if (status === "loading" || !session?.user?.id) {
                    setIsAnalyzing(false);
                    return;
                }

                const statusData = await checkVideoStatus(videoId);

                switch (statusData.status) {
                    case "completed":
                        await fetchResults(videoId);
                        return;

                    case "processing":
                        await pollForAnalysis(videoId);
                        return;

                    default: // 'pending' or other states
                        const triggerResponse = await fetch(`/api/analyze/${videoId}`, {
                            method: "POST",
                        });
                        if (!triggerResponse.ok)
                            throw new Error("Failed to trigger analysis");

                        const triggerResult = await triggerResponse.json();
                        if (triggerResult.status === "analysis_triggered") {
                            await pollForAnalysis(videoId);
                        } else {
                            throw new Error("Analysis failed to start");
                        }
                }
            } catch (error) {
                console.error("Analysis error:", error);
                setIsAnalyzing(false);
            }
        },
        [checkVideoStatus, fetchResults, pollForAnalysis],
    );

    useEffect(() => {
        if (
            videoId &&
            status === "authenticated" &&
            !analysisData &&
            !isAnalyzing &&
            !hasStartedAnalysisRef.current
        ) {
            checkVideoStatus(videoId)
                .then((statusData) => {
                    if (statusData.status === "completed") {
                        fetchResults(videoId);
                    }
                })
                .catch((error) => {
                    console.error("Error checking video status on refresh:", error);
                });
        }
    }, [videoId, status, analysisData, isAnalyzing, checkVideoStatus, fetchResults]);

    useEffect(() => {
        if (videoId && status === "authenticated" && !hasStartedAnalysisRef.current) {
            hasStartedAnalysisRef.current = true;
            startAnalysis(videoId);
        }
    }, [videoId, status, startAnalysis]);

    const currentClusteredData = useMemo(() => {
        if (!analysisData?.harmfulContent) return [];

        return clusterHarmfulEvents(analysisData.harmfulContent, clusteringConfig);
    }, [analysisData?.harmfulContent, clusteringConfig]);

    const harmfulMarkers = useMemo(() => {
        return currentClusteredData.map((content) => ({
            time: content.startTime,
            endTime: content.endTime,
            confidence: content.confidence,
            eventCount: content.eventCount,
            categories: content.categories,
            navigationTimestamp: content.navigationTimestamp,
        }));
    }, [currentClusteredData]);

    useEffect(() => {
        if (!currentClusteredData.length) {
            setClusterPanelHeight(null);
            setClusterBoxMetrics(null);
        }
    }, [currentClusteredData.length]);

    // Observe EventExplanation card position and height
    useEffect(() => {
        const el = eventBoxRef.current;
        if (!el) return;
        const compute = () => {
            const rect = el.getBoundingClientRect();
            setEventTop(rect.top + (window.scrollY || window.pageYOffset));
            setEventHeight(rect.height);
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
    }, []);

    // Compute height to align bottoms: cluster.height - (eventTop - cluster.top)
    const matchedHeightPx = useMemo(() => {
        if (!clusterBoxMetrics || eventTop == null)
            return clusterPanelHeight ?? undefined;
        const delta = eventTop - clusterBoxMetrics.top;
        const h = clusterBoxMetrics.height - delta;
        return Math.max(0, Math.min(clusterBoxMetrics.height, h));
    }, [clusterBoxMetrics, eventTop, clusterPanelHeight]);

    if (!videoId) {
        return <div>Loading...</div>;
    }

    return (
        <div className="container mx-auto px-4 py-8">
            <main className="container mx-auto px-4 py-8">
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    {/* Left Column - Video Section */}
                    <div className="lg:col-span-2 space-y-6">
                        <div className="space-y-4">
                            <div className="flex justify-between items-center">
                                <div className="flex items-center gap-3">
                                    <h2 className="text-lg font-semibold">
                                        Video Analysis
                                    </h2>
                                    {analysisData?.analysisModel && (
                                        <Badge variant="secondary" className="text-xs">
                                            {analysisData.analysisModel}
                                        </Badge>
                                    )}
                                </div>
                                <Button
                                    variant="outline"
                                    onClick={() => router.push("/")}
                                >
                                    Upload New Video
                                </Button>
                            </div>

                            <VideoPlayer
                                src={videoSrc}
                                harmfulMarkers={harmfulMarkers}
                                onReady={handlePlayerReady}
                            />

                            <ClusteredAnalysisData
                                clusteredData={currentClusteredData}
                                onSeekToTimestamp={seekToTimestamp}
                                onEventSelect={setSelectedEvent}
                                onHeightChange={setClusterPanelHeight}
                                onBoxMetricsChange={setClusterBoxMetrics}
                            />
                        </div>
                    </div>

                    {/* Right Column - Analysis Results (Summary Only) */}
                    <div className="lg:col-span-1 space-y-4">
                        <AnalysisResults
                            summary={analysisData?.summary}
                            transcription={analysisData?.transcription}
                            transcriptionWords={analysisData?.transcriptionWords}
                            isLoading={isAnalyzing || !analysisData}
                        />
                        {currentClusteredData.length > 0 && (
                            <div ref={eventBoxRef}>
                                <EventExplanation
                                    selectedEvent={selectedEvent}
                                    matchedMaxPx={matchedHeightPx}
                                />
                            </div>
                        )}
                    </div>
                </div>
            </main>
        </div>
    );
}

export default function VideoAnalysisPage() {
    return (
        <PlayerProvider>
            <VideoAnalysisContent />
        </PlayerProvider>
    );
}
