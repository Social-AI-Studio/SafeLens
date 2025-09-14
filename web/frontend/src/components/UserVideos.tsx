"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { format } from "date-fns";
import { useRouter } from "next/navigation";
import Image from "next/image";

interface Video {
    video_id: string;
    original_filename: string;
    file_size: number;
    uploaded_at: string;
    analysis_status: string;
    duration?: number;
    thumbnail_url?: string;
    safety_rating?: string; // 'Safe' | 'Caution' | 'Unsafe' (optional)
    harmful_events_count?: number; // number of harmful events (optional)
}

export default function UserVideos() {
    const [videos, setVideos] = useState<Video[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const router = useRouter();
    const { data: session, status } = useSession();
    const user = session?.user;

    useEffect(() => {
        if (status === "authenticated" && user?.id) {
            fetchUserVideos();
        }
    }, [user?.id, status]);

    const fetchUserVideos = async () => {
        try {
            const response = await fetch("/api/user/videos");

            if (!response.ok) {
                throw new Error("Failed to fetch videos");
            }

            const data = await response.json();
            setVideos(data);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load videos");
        } finally {
            setLoading(false);
        }
    };

    const formatFileSize = (bytes: number) => {
        if (bytes === 0) return "0 Bytes";
        const k = 1024;
        const sizes = ["Bytes", "KB", "MB", "GB"];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
    };

    const formatDuration = (seconds?: number) => {
        if (!seconds) return "";
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;
        return `${minutes}:${remainingSeconds.toString().padStart(2, "0")}`;
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case "completed":
                return "bg-green-500/10 text-green-500 border-green-500/20";
            case "processing":
                return "bg-blue-500/10 text-blue-500 border-blue-500/20";
            case "failed":
                return "bg-red-500/10 text-red-500 border-red-500/20";
            default:
                return "bg-gray-500/10 text-gray-500 border-gray-500/20";
        }
    };

    if (loading || status === "loading") {
        return (
            <div className="space-y-4">
                <Skeleton className="h-8 w-48" />
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {[1, 2, 3].map((i) => (
                        <Card key={i}>
                            <div className="aspect-video bg-gray-100 rounded-t-lg">
                                <Skeleton className="w-full h-full" />
                            </div>
                            <CardContent className="p-4">
                                <Skeleton className="h-4 w-full mb-2" />
                                <Skeleton className="h-4 w-3/4 mb-2" />
                                <Skeleton className="h-4 w-1/2" />
                            </CardContent>
                        </Card>
                    ))}
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <Card className="w-full">
                <CardContent className="p-6">
                    <p className="text-destructive">{error}</p>
                </CardContent>
            </Card>
        );
    }

    if (videos.length === 0) {
        return (
            <Card className="w-full">
                <CardContent className="p-6 text-center">
                    <p className="text-muted-foreground">
                        No videos uploaded yet. Upload your first video to get started!
                    </p>
                </CardContent>
            </Card>
        );
    }

    return (
        <div className="space-y-6">
            <h3 className="text-2xl font-bold">Your Videos</h3>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {videos.map((video) => (
                    <Card
                        key={video.video_id}
                        className="cursor-pointer hover:shadow-lg transition-shadow overflow-hidden"
                        onClick={() => router.push(`/${video.video_id}`)}
                    >
                        <div className="aspect-video bg-gray-100 relative">
                            <Image
                                src={`/api/thumbnail/${video.video_id}`}
                                alt={video.original_filename}
                                fill
                                className="object-cover"
                                onError={(e) => {
                                    // Fallback to placeholder if thumbnail fails to load
                                    (e.target as HTMLImageElement).src =
                                        "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='100'%3E%3Crect width='100' height='100' fill='%23f3f4f6'/%3E%3Ctext x='50' y='50' text-anchor='middle' dy='.3em' font-size='12' fill='%236b7280'%3EVideo%3C/text%3E%3C/svg%3E";
                                }}
                            />
                        </div>
                        <CardHeader className="pb-3">
                            <CardTitle className="text-sm font-medium truncate">
                                {video.original_filename}
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-2 pt-0">
                            <div className="flex items-center justify-between text-sm">
                                <span className="text-muted-foreground">
                                    {formatFileSize(video.file_size)}
                                </span>
                                {video.duration && (
                                    <span className="text-muted-foreground">
                                        {formatDuration(video.duration)}
                                    </span>
                                )}
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-xs text-muted-foreground">
                                    {format(new Date(video.uploaded_at), "MMM d, yyyy")}
                                </span>
                                <div className="flex items-center gap-2">
                                    {/* Analysis status */}
                                    <Badge
                                        className={getStatusColor(
                                            video.analysis_status,
                                        )}
                                    >
                                        {video.analysis_status}
                                    </Badge>
                                    {/* Harmful badge when applicable */}
                                    {(video.safety_rating || "").toLowerCase() ===
                                        "unsafe" && (
                                        <Badge variant="destructive">Harmful</Badge>
                                    )}
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                ))}
            </div>
        </div>
    );
}
