import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";

export async function POST(request: NextRequest) {
    try {
        const session = await auth();

        if (!session?.user?.id) {
            return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
        }

        const formData = await request.formData();
        const file = formData.get("file") as File;
        const analysisModel = formData.get("analysis_model") as string;

        if (!file) {
            return NextResponse.json(
                { error: "No video file provided" },
                { status: 400 },
            );
        }

        if (!analysisModel) {
            return NextResponse.json(
                { error: "No analysis model provided" },
                { status: 400 },
            );
        }

        // Validate file type
        const allowedTypes = [
            "video/mp4",
            "video/mov",
            "video/avi",
            "video/wmv",
            "video/webm",
            "video/mkv",
        ];
        if (!allowedTypes.includes(file.type)) {
            return NextResponse.json(
                { error: "Invalid file type. Please upload a video file." },
                { status: 400 },
            );
        }

        // Validate file size (max 500MB to match backend)
        const maxSize = 500 * 1024 * 1024; // 500MB
        if (file.size > maxSize) {
            return NextResponse.json(
                { error: "File size too large. Maximum size is 500MB." },
                { status: 400 },
            );
        }

        // Forward upload to backend
        const backendFormData = new FormData();
        backendFormData.append("file", file);
        backendFormData.append("analysis_model", analysisModel);

        const backendResponse = await fetch(`${process.env.BACKEND_URL!}/api/upload`, {
            method: "POST",
            body: backendFormData,
            headers: {
                "user-id": session.user.id,
            },
        });

        if (!backendResponse.ok) {
            const errorData = await backendResponse.json();
            return NextResponse.json(
                { error: errorData.detail || "Failed to upload to backend" },
                { status: backendResponse.status },
            );
        }

        const result = await backendResponse.json();

        return NextResponse.json({
            success: true,
            video_id: result.video_id,
            message: result.message,
            filename: result.filename,
            size: file.size,
            type: file.type,
        });
    } catch (error) {
        console.error("Upload error:", error);
        return NextResponse.json({ error: "Failed to upload video" }, { status: 500 });
    }
}
