"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Skeleton } from "@/components/ui/skeleton";
import VideoUpload from "@/components/VideoUpload";
import UserVideos from "@/components/UserVideos";
import { useSession } from "next-auth/react";

export default function Home() {
    const [isUploading, setIsUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState(0);
    const [isNavigating, setIsNavigating] = useState(false);
    const [selectedModel, setSelectedModel] = useState("SafeLens/llama-3-8b");
    const router = useRouter();

    const { status } = useSession();

    if (status === "loading") {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <Skeleton className="w-1/2 h-1/2" />
            </div>
        );
    }

    const handleVideoSelect = async (file: File) => {
        setIsUploading(true);
        setUploadProgress(0);

        try {
            const formData = new FormData();
            formData.append("file", file);
            formData.append("analysis_model", selectedModel);

            const xhr = new XMLHttpRequest();

            xhr.upload.addEventListener("progress", (event) => {
                if (event.lengthComputable) {
                    const percentComplete = Math.round(
                        (event.loaded / event.total) * 100,
                    );
                    setUploadProgress(percentComplete);
                }
            });

            xhr.addEventListener("load", () => {
                setIsUploading(false);
                if (xhr.status === 200) {
                    const response = JSON.parse(xhr.responseText);
                    if (response.video_id) {
                        setIsNavigating(true);
                        router.push(`/${response.video_id}`);
                    } else {
                        console.error(
                            "Upload failed:",
                            response.detail ||
                                response.error ||
                                "Invalid response format",
                        );
                        setUploadProgress(0);
                    }
                } else {
                    console.error("Upload error:", xhr.statusText);
                    setUploadProgress(0);
                }
            });

            xhr.addEventListener("error", () => {
                console.error("Upload failed");
                setIsUploading(false);
                setUploadProgress(0);
            });

            xhr.open("POST", "/api/upload");
            xhr.send(formData);
        } catch (error) {
            console.error("Upload error:", error);
            setIsUploading(false);
            setUploadProgress(0);
        }
    };

    const handleVideoUrl = async (url: string) => {
        setIsUploading(true);
        setUploadProgress(0);

        try {
            const response = await fetch("/api/upload/url", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    url,
                    analysis_model: selectedModel,
                }),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || "Download failed");
            }

            const data = await response.json();
            const videoId = data.video_id;

            // Poll for download status with better progress tracking
            const pollDownloadStatus = async () => {
                try {
                    const statusResponse = await fetch(
                        `/api/download/${videoId}/status`,
                    );
                    if (statusResponse.ok) {
                        const statusData = await statusResponse.json();

                        console.log(
                            `Download Status: ${statusData.download_status}, Analysis Status: ${statusData.analysis_status}`,
                        );

                        // Update progress based on status
                        if (statusData.download_status === "pending") {
                            setUploadProgress(10); // Just started
                            setTimeout(pollDownloadStatus, 2000);
                        } else if (statusData.download_status === "downloading") {
                            setUploadProgress(30); // Downloading
                            setTimeout(pollDownloadStatus, 2000);
                        } else if (statusData.download_status === "completed") {
                            // Download complete - navigate to video page immediately
                            setUploadProgress(100); // Download done
                            setIsUploading(false);
                            setIsNavigating(true);
                            router.push(`/${videoId}`);
                        } else if (statusData.download_status === "failed") {
                            throw new Error(
                                statusData.download_error || "Download failed",
                            );
                        }
                    } else {
                        throw new Error("Failed to check download status");
                    }
                } catch (error) {
                    console.error("Status polling error:", error);
                    throw error;
                }
            };

            // Start polling after initial delay
            setTimeout(pollDownloadStatus, 1000);
        } catch (error) {
            console.error("URL upload error:", error);
            setIsUploading(false);
            setUploadProgress(0);
            // Show error to user
            alert(`Upload failed.`);
        }
    };

    return (
        <main className="container mx-auto px-4 py-8 relative">
            <div className="max-w-6xl mx-auto space-y-12">
                <div>
                    <div className="text-center mb-8">
                        <h2 className="text-3xl font-bold mb-4">
                            Upload Video for Analysis
                        </h2>
                        <p className="text-muted-foreground">
                            Upload your video to detect harmful content using AI-powered
                            analysis
                        </p>
                    </div>

                    <VideoUpload
                        onVideoSelectAction={handleVideoSelect}
                        onVideoUrlAction={handleVideoUrl}
                        onModelChange={setSelectedModel}
                        selectedModel={selectedModel}
                        isUploading={isUploading}
                        uploadProgress={uploadProgress}
                    />
                </div>

                <UserVideos />
            </div>

            {isNavigating && (
                <div className="absolute inset-0 bg-background/80 backdrop-blur-sm z-50 overflow-auto">
                    <div className="container mx-auto px-4 py-8">
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                            {/* Left Column - Video Section */}
                            <div className="lg:col-span-2 space-y-6">
                                {/* Header */}
                                <div className="flex items-center justify-between">
                                    <Skeleton className="h-8 w-48" />
                                    <Skeleton className="h-10 w-36" />
                                </div>

                                {/* Video Player */}
                                <div className="space-y-4">
                                    <Skeleton className="w-full h-[500px] rounded-lg" />
                                    <div className="space-y-2">
                                        <Skeleton className="h-4 w-full" />
                                        <Skeleton className="h-4 w-3/4" />
                                        <Skeleton className="h-4 w-1/2" />
                                    </div>
                                </div>

                                {/* Timestamp Display */}
                                <div className="space-y-3">
                                    <Skeleton className="h-6 w-32" />
                                    <div className="flex gap-2">
                                        <Skeleton className="h-8 w-20" />
                                        <Skeleton className="h-8 w-20" />
                                        <Skeleton className="h-8 w-20" />
                                    </div>
                                </div>
                            </div>

                            {/* Right Column - Analysis Sidebar */}
                            <div className="lg:col-span-1 space-y-6">
                                {/* Summary Card */}
                                <div className="space-y-4">
                                    <Skeleton className="h-6 w-24" />
                                    <Skeleton className="h-20 w-full rounded-lg" />
                                    <div className="flex gap-2">
                                        <Skeleton className="h-6 w-16 rounded-full" />
                                        <Skeleton className="h-6 w-16 rounded-full" />
                                    </div>
                                </div>

                                {/* Transcription Card */}
                                <div className="space-y-4">
                                    <Skeleton className="h-6 w-32" />
                                    <div className="space-y-2">
                                        <Skeleton className="h-4 w-full" />
                                        <Skeleton className="h-4 w-full" />
                                        <Skeleton className="h-4 w-5/6" />
                                        <Skeleton className="h-4 w-3/4" />
                                        <Skeleton className="h-4 w-4/5" />
                                    </div>
                                </div>

                                {/* Additional Loading Indicators */}
                                <div className="space-y-3">
                                    <Skeleton className="h-6 w-40" />
                                    <Skeleton className="h-24 w-full rounded-lg" />
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </main>
    );
}
