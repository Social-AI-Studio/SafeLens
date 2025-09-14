import { NextRequest, NextResponse } from "next/server";

export async function GET(
    request: NextRequest,
    { params }: { params: Promise<{ videoId: string }> },
) {
    try {
        const { videoId } = await params;

        const backendResponse = await fetch(
            `${process.env.BACKEND_URL!}/api/videos/${videoId}/video.mp4`,
        );

        if (!backendResponse.ok) {
            return NextResponse.json({ error: "Video not found" }, { status: 404 });
        }

        // Get the video stream from backend
        const videoBlob = await backendResponse.blob();

        return new NextResponse(videoBlob, {
            headers: {
                "Content-Type": "video/mp4",
                "Accept-Ranges": "bytes",
            },
        });
    } catch (error) {
        console.error("Error serving video:", error);
        return NextResponse.json({ error: "Failed to serve video" }, { status: 500 });
    }
}
