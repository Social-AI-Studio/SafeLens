"use client";

import { useEffect, useRef } from "react";
import videojs from "video.js";
import "video.js/dist/video-js.css";

interface HarmfulContentMarker {
    time: number;
    endTime: number;
    confidence: number;
    eventCount?: number;
    categories?: string[];
    navigationTimestamp?: number;
}

interface VideoPlayerProps {
    src?: string;
    harmfulMarkers?: HarmfulContentMarker[];
    onReady?: (player: any) => void;
}

export default function VideoPlayer({
    src,
    harmfulMarkers = [],
    onReady,
}: VideoPlayerProps) {
    const videoRef = useRef<HTMLDivElement>(null);
    const playerRef = useRef<any>(null);

    useEffect(() => {
        if (!playerRef.current && videoRef.current && src) {
            const videoElement = document.createElement("video-js");
            videoElement.classList.add("vjs-big-play-centered");
            videoRef.current.appendChild(videoElement);

            const player = videojs(videoElement, {
                controls: true,
                responsive: false,
                fluid: false,
                fill: false,
                width: "100%",
                height: 500,
                playbackRates: [0.5, 1, 1.25, 1.5, 2],
                preload: "auto",
                sources: [{ src, type: "video/mp4" }],
            });

            playerRef.current = player;

            player.ready(() => {
                onReady?.(player);
                // Use the harmfulMarkers prop instead of hardcoded values
                setTimeout(() => {
                    addMarkersFromProps(player, harmfulMarkers);
                }, 1000);
            });
        } else if (playerRef.current && src) {
            // Update source if player already exists
            playerRef.current.src({ src, type: "video/mp4" });
            // Update markers when source changes
            setTimeout(() => {
                addMarkersFromProps(playerRef.current, harmfulMarkers);
            }, 1000);
        }
    }, [src, onReady, harmfulMarkers]);

    // Function to add markers based on props
    const addMarkersFromProps = (player: any, markers: HarmfulContentMarker[]) => {
        // Wait for player to be fully loaded
        const addMarkersWhenReady = () => {
            const duration = player.duration();
            if (duration && duration > 0) {
                const progressBar = player.el()?.querySelector(".vjs-progress-holder");
                if (progressBar) {
                    // Remove any existing markers first
                    const existingMarkers = progressBar.querySelectorAll(
                        ".custom-harmful-marker",
                    );
                    existingMarkers.forEach((marker: any) => marker.remove());

                    // Add markers for each harmful content range
                    markers.forEach((marker, index) => {
                        const startPercent = (marker.time / duration) * 100;
                        const rawEndPercent = (marker.endTime / duration) * 100;

                        // Clamp endPercent to video duration (handle overflow from +1s buffer)
                        const endPercent = Math.min(rawEndPercent, 100);
                        const width = endPercent - startPercent;

                        // Ensure width is positive and markers start within bounds
                        if (width > 0 && startPercent >= 0 && startPercent <= 100) {
                            const rangeElement = document.createElement("div");
                            const isCluster = (marker.eventCount || 1) > 1;
                            rangeElement.className = `custom-harmful-marker ${isCluster ? "cluster-marker" : "single-marker"}`;

                            rangeElement.style.cssText = `
                position: absolute;
                left: ${startPercent}%;
                width: ${width}%;
                height: 100%;
                background-color: #ef4444;
                opacity: 0.8;
                z-index: 10;
                pointer-events: auto;
                cursor: pointer;
                border-radius: 2px;
                border: 1px solid #dc2626;
                box-shadow: 0 1px 3px rgba(0,0,0,0.2);
                transition: opacity 0.2s ease;
              `;

                            // Enhanced tooltip for clusters
                            const formatTime = (seconds: number) => {
                                const mins = Math.floor(seconds / 60);
                                const secs = Math.floor(seconds % 60);
                                return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
                            };

                            if (isCluster) {
                                const categoriesText =
                                    marker.categories?.join(", ") || "harmful content";
                                rangeElement.title = `⚠️ Cluster: ${formatTime(marker.time)} – ${formatTime(marker.endTime)} | ${marker.eventCount} events | ${Math.round(marker.confidence * 100)}% max confidence | ${categoriesText}`;
                            } else {
                                rangeElement.title = `⚠️ Harmful content from ${formatTime(marker.time)} to ${formatTime(marker.endTime)} (${Math.round(marker.confidence * 100)}% confidence)`;
                            }

                            // Add hover effect
                            rangeElement.addEventListener("mouseenter", () => {
                                rangeElement.style.opacity = "1";
                            });
                            rangeElement.addEventListener("mouseleave", () => {
                                rangeElement.style.opacity = "0.8";
                            });

                            // Note: Cluster badges removed for cleaner timeline appearance

                            // Add click handler to seek to highest confidence event in cluster
                            rangeElement.addEventListener("click", () => {
                                const seekTime =
                                    marker.navigationTimestamp || marker.time;
                                player.currentTime(seekTime);
                            });

                            progressBar.appendChild(rangeElement);
                        }
                    });
                } else {
                    console.warn("Progress bar not found, retrying...");
                    // Retry after a short delay
                    setTimeout(addMarkersWhenReady, 500);
                }
            } else {
                console.warn("Video duration not available, retrying...");
                // Retry after a short delay
                setTimeout(addMarkersWhenReady, 500);
            }
        };

        // Try to add markers with multiple attempts
        setTimeout(addMarkersWhenReady, 1500);
    };

    useEffect(() => {
        const player = playerRef.current;

        return () => {
            if (player && !player.isDisposed()) {
                player.dispose();
                playerRef.current = null;
            }
        };
    }, []);

    return (
        <div className="w-full">
            <div ref={videoRef} className="video-player-container" />
            <style jsx global>{`
                .video-player-container .video-js {
                    width: 100%;
                    height: 500px !important;
                    max-height: 500px !important;
                    min-height: 400px;
                }

                .video-player-container .video-js .vjs-tech {
                    width: 100% !important;
                    height: 100% !important;
                    object-fit: contain;
                }

                .video-js .vjs-marker {
                    background-color: #ef4444 !important;
                    opacity: 0.8 !important;
                    transition: opacity 0.2s;
                    border-radius: 3px !important;
                }

                .video-js .vjs-marker:hover {
                    opacity: 1 !important;
                }

                .vjs-tip {
                    background: rgba(0, 0, 0, 0.9) !important;
                    color: white !important;
                    font-size: 12px !important;
                    padding: 6px 10px !important;
                    border-radius: 4px !important;
                    border: 1px solid #ef4444 !important;
                }

                .custom-harmful-marker:hover {
                    opacity: 1 !important;
                }

                .cluster-marker {
                    border: 2px solid #dc2626 !important;
                    box-shadow: 0 2px 4px rgba(220, 38, 38, 0.3) !important;
                }

                .cluster-marker:hover {
                    background-color: #dc2626 !important;
                    box-shadow: 0 4px 8px rgba(220, 38, 38, 0.4) !important;
                }

                .single-marker {
                    border: 1px solid #dc2626 !important;
                }
            `}</style>
        </div>
    );
}
