"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { videoFileSchema, videoUrlSchema } from "@/lib/validation";
import ModelSelector from "@/components/ModelSelector";

interface VideoUploadProps {
    onVideoSelectAction: (file: File) => void;
    onVideoUrlAction: (url: string) => void;
    onModelChange?: (model: string) => void;
    selectedModel?: string;
    isUploading?: boolean;
    uploadProgress?: number;
}

export default function VideoUpload({
    onVideoSelectAction,
    onVideoUrlAction,
    onModelChange,
    selectedModel,
    isUploading = false,
    uploadProgress = 0,
}: VideoUploadProps) {
    const [urlError, setUrlError] = useState<string>("");
    const [fileError, setFileError] = useState<string>("");

    const {
        register,
        handleSubmit,
        formState: { errors },
        reset,
    } = useForm({
        resolver: zodResolver(videoUrlSchema),
    });

    const onDrop = useCallback(
        (acceptedFiles: File[], rejectedFiles: any[]) => {
            setFileError("");

            if (rejectedFiles.length > 0) {
                const rejection = rejectedFiles[0];
                if (rejection.errors) {
                    setFileError(rejection.errors[0].message || "Invalid file");
                }
                return;
            }

            if (acceptedFiles.length > 0) {
                const file = acceptedFiles[0];

                // Validate with zod schema
                const result = videoFileSchema.safeParse({ file });
                if (!result.success) {
                    setFileError(
                        result.error.issues[0]?.message || "File validation failed",
                    );
                    return;
                }

                onVideoSelectAction(file);
            }
        },
        [onVideoSelectAction],
    );

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        accept: {
            "video/*": [".mp4", ".mov", ".avi", ".wmv", ".flv", ".webm", ".mkv"],
        },
        maxFiles: 1,
        disabled: isUploading,
        maxSize: 500 * 1024 * 1024, // 500MB
    });

    const onUrlSubmit = (data: { url: string }) => {
        setUrlError("");
        onVideoUrlAction(data.url);
        reset();
    };

    if (isUploading) {
        return (
            <Card className="w-full">
                <CardContent className="p-6">
                    <div className="text-center space-y-4">
                        <div className="text-lg font-medium">Uploading video...</div>
                        <Progress value={uploadProgress} className="w-full" />
                        <div className="text-sm text-muted-foreground">
                            {uploadProgress}% complete
                        </div>
                    </div>
                </CardContent>
            </Card>
        );
    }

    return (
        <Card className="w-full">
            <CardContent className="p-6 space-y-4 py-0">
                {/* Header with Model Selector */}
                <div className="flex justify-between items-center pb-2">
                    <h2 className="text-lg font-medium">Video Analysis</h2>
                    <ModelSelector
                        value={selectedModel}
                        onModelChange={onModelChange}
                    />
                </div>

                {/* Upload Area */}
                <div
                    {...getRootProps()}
                    className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
                        isDragActive
                            ? "border-primary bg-primary/5"
                            : fileError
                              ? "border-destructive bg-destructive/5"
                              : "border-border hover:border-primary/50"
                    }`}
                >
                    <input {...getInputProps()} />
                    <div className="space-y-2">
                        <div className="text-lg font-medium">
                            {isDragActive
                                ? "Drop the video here"
                                : "Upload a video file"}
                        </div>
                        <div className="text-sm text-muted-foreground">
                            Drag and drop a video file here, or click to select
                        </div>
                        <div className="text-xs text-muted-foreground">
                            Supports: MP4, MOV, AVI, WMV, FLV, WebM, MKV (Max 500MB)
                        </div>
                        {fileError && (
                            <div className="text-sm text-destructive mt-2">
                                {fileError}
                            </div>
                        )}
                    </div>
                </div>

                {/* OR Divider */}
                <div className="flex items-center gap-4">
                    <div className="flex-1 h-px bg-border" />
                    <span className="text-sm text-muted-foreground">OR</span>
                    <div className="flex-1 h-px bg-border" />
                </div>

                {/* URL Input */}
                <form onSubmit={handleSubmit(onUrlSubmit)} className="space-y-2">
                    <Label htmlFor="video-url">Video URL</Label>
                    <div className="flex gap-2 py-4">
                        <div className="flex-1">
                            <Input
                                id="video-url"
                                placeholder="https://example.com/video.mp4"
                                {...register("url")}
                                className={errors.url ? "border-destructive" : ""}
                            />
                            {errors.url && (
                                <div className="text-sm text-destructive mt-1">
                                    {errors.url.message}
                                </div>
                            )}
                        </div>
                        <Button type="submit">Load</Button>
                    </div>
                </form>
            </CardContent>
        </Card>
    );
}
