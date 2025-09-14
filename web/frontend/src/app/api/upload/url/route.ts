import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";

export async function POST(request: NextRequest) {
    try {
        const session = await auth();

        if (!session?.user?.id) {
            return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
        }

        const body = await request.json();
        const { url, analysis_model } = body;

        if (!url) {
            return NextResponse.json({ error: "URL is required" }, { status: 400 });
        }

        try {
            new URL(url);
        } catch {
            return NextResponse.json({ error: "Invalid URL format" }, { status: 400 });
        }

        const backendResponse = await fetch(
            `${process.env.BACKEND_URL!}/api/upload/url`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "user-id": session.user.id,
                },
                body: JSON.stringify({
                    url,
                    analysis_model: analysis_model || "SafeLens/llama-3-8b",
                }),
            },
        );

        if (!backendResponse.ok) {
            const errorData = await backendResponse.json().catch(() => ({}));
            return NextResponse.json(
                {
                    error: errorData.detail || "Download failed",
                    status: backendResponse.status,
                },
                { status: backendResponse.status },
            );
        }

        const data = await backendResponse.json();
        return NextResponse.json(data);
    } catch (error) {
        console.error("URL upload error:", error);
        return NextResponse.json({ error: "Internal server error" }, { status: 500 });
    }
}
