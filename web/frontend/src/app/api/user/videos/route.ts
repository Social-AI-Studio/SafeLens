import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";

export async function GET(request: NextRequest) {
    try {
        const session = await auth();

        if (!session?.user?.id) {
            return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
        }

        const backendResponse = await fetch(
            `${process.env.BACKEND_URL!}/api/user/videos`,
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
                { error: errorData.detail || "Failed to fetch user videos" },
                { status: backendResponse.status },
            );
        }

        const videos = await backendResponse.json();

        return NextResponse.json(videos);
    } catch (error) {
        console.error("Fetch user videos error:", error);
        return NextResponse.json(
            { error: "Failed to fetch user videos" },
            { status: 500 },
        );
    }
}
