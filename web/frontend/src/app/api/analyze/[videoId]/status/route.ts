import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";

export async function GET(
    request: NextRequest,
    { params }: { params: Promise<{ videoId: string }> },
) {
    try {
        const session = await auth();

        if (!session?.user?.id) {
            return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
        }

        const { videoId } = await params;

        const backendResponse = await fetch(
            `${process.env.BACKEND_URL!}/api/analyze/${videoId}/status`,
            {
                method: "GET",
                headers: {
                    "user-id": session.user.id,
                },
            },
        );

        if (!backendResponse.ok) {
            const errorData = await backendResponse.json();
            return NextResponse.json(
                { error: errorData.detail || "Failed to fetch analysis status" },
                { status: backendResponse.status },
            );
        }

        const status = await backendResponse.json();

        return NextResponse.json(status);
    } catch (error) {
        console.error("Fetch analysis status error:", error);
        return NextResponse.json(
            { error: "Failed to fetch analysis status" },
            { status: 500 },
        );
    }
}
