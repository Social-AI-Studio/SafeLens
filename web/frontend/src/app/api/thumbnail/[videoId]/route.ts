import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";

export async function GET(
    request: NextRequest,
    { params }: { params: Promise<{ videoId: string }> },
) {
    try {
        const session = await auth();
        const { videoId } = await params;

        console.log(
            `Thumbnail request for video ${videoId} from user ${session?.user?.id}`,
        );

        const backendResponse = await fetch(
            `${process.env.BACKEND_URL!}/api/videos/${videoId}/thumbnail.jpg`,
            {
                method: "GET",
                headers: {
                    ...(session?.user?.id && { "user-id": session.user.id }),
                },
            },
        );

        console.log(
            `Backend response for thumbnail ${videoId}: ${backendResponse.status}`,
        );

        if (!backendResponse.ok) {
            console.log(
                `Backend returned error for thumbnail ${videoId}: ${backendResponse.status}`,
            );
            const errorText = await backendResponse.text();
            console.log(`Backend error text: ${errorText}`);
            return new NextResponse("Failed to fetch thumbnail", {
                status: backendResponse.status,
            });
        }

        const buffer = await backendResponse.arrayBuffer();
        const contentType = backendResponse.headers.get("content-type") || "image/jpeg";

        console.log(
            `Successfully fetched thumbnail for ${videoId}, content type: ${contentType}, size: ${buffer.byteLength} bytes`,
        );

        return new NextResponse(buffer, {
            status: 200,
            headers: {
                "Content-Type": contentType,
            },
        });
    } catch (error) {
        console.error("Fetch thumbnail error:", error);
        return new NextResponse("Failed to fetch thumbnail", { status: 500 });
    }
}
