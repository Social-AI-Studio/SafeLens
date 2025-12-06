import { NextRequest, NextResponse } from "next/server";

export async function GET(
    request: NextRequest,
    { params }: { params: Promise<{ videoId: string }> },
) {
    try {
        const { videoId } = await params;
        const backendUrl = `${process.env.BACKEND_URL!}/api/videos/${videoId}/video.mp4`;

        // Forward Range header if present for proper seeking/duration
        const headers: HeadersInit = {};
        const rangeHeader = request.headers.get("Range");
        if (rangeHeader) {
            headers["Range"] = rangeHeader;
        }

        const backendResponse = await fetch(backendUrl, { 
            headers,
            // Disable Next.js caching to ensure fresh metadata
            cache: "no-store",
        });

        if (!backendResponse.ok && backendResponse.status !== 206) {
            return NextResponse.json({ error: "Video not found" }, { status: 404 });
        }

        // Forward important headers from backend
        const responseHeaders = new Headers();
        responseHeaders.set("Content-Type", "video/mp4");
        responseHeaders.set("Accept-Ranges", "bytes");
        // Prevent caching issues with video metadata
        responseHeaders.set("Cache-Control", "no-cache");

        const contentLength = backendResponse.headers.get("Content-Length");
        if (contentLength) {
            responseHeaders.set("Content-Length", contentLength);
        }

        const contentRange = backendResponse.headers.get("Content-Range");
        if (contentRange) {
            responseHeaders.set("Content-Range", contentRange);
        }

        // Stream the response body
        return new NextResponse(backendResponse.body, {
            status: backendResponse.status,
            headers: responseHeaders,
        });
    } catch (error) {
        console.error("Error serving video:", error);
        return NextResponse.json({ error: "Failed to serve video" }, { status: 500 });
    }
}

// Handle HEAD requests for video metadata (duration detection)
export async function HEAD(
    request: NextRequest,
    { params }: { params: Promise<{ videoId: string }> },
) {
    try {
        const { videoId } = await params;
        const backendUrl = `${process.env.BACKEND_URL!}/api/videos/${videoId}/video.mp4`;

        // Make a HEAD request to get metadata without downloading the file
        const backendResponse = await fetch(backendUrl, { 
            method: "HEAD",
            cache: "no-store",
        });

        if (!backendResponse.ok) {
            return new NextResponse(null, { status: 404 });
        }

        const responseHeaders = new Headers();
        responseHeaders.set("Content-Type", "video/mp4");
        responseHeaders.set("Accept-Ranges", "bytes");
        responseHeaders.set("Cache-Control", "no-cache");

        const contentLength = backendResponse.headers.get("Content-Length");
        if (contentLength) {
            responseHeaders.set("Content-Length", contentLength);
        }

        return new NextResponse(null, {
            status: 200,
            headers: responseHeaders,
        });
    } catch (error) {
        console.error("Error getting video metadata:", error);
        return new NextResponse(null, { status: 500 });
    }
}
