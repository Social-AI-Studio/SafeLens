import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";

export async function POST(
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
            `${process.env.BACKEND_URL!}/api/analyze/${videoId}`,
            {
                method: "POST",
                headers: {
                    "user-id": session.user.id,
                },
            },
        );

        if (!backendResponse.ok) {
            const errorData = await backendResponse.json();
            return NextResponse.json(
                { error: errorData.detail || "Failed to trigger analysis" },
                { status: backendResponse.status },
            );
        }

        const result = await backendResponse.json();

        return NextResponse.json(result);
    } catch (error) {
        console.error("Trigger analysis error:", error);
        return NextResponse.json(
            { error: "Failed to trigger analysis" },
            { status: 500 },
        );
    }
}
