import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { auth } from "@/lib/auth";

export default auth((req) => {
    const isAuthenticated = !!req.auth;
    const isAuthPage = req.nextUrl.pathname.startsWith("/api/auth");

    if (isAuthPage) {
        return NextResponse.next();
    }

    return NextResponse.next();
});

export const config = {
    matcher: ["/", "/:videoId*", "/account/:page*"],
};
