"use client";

import { useSession } from "next-auth/react";
import SignInOverlay from "./SignInOverlay";

interface AuthGuardProps {
    children: React.ReactNode;
}

export default function AuthGuard({ children }: AuthGuardProps) {
    const { data: session, status } = useSession();

    if (status === "loading") {
        // Show loading state or nothing while checking auth
        return <>{children}</>;
    }

    if (!session) {
        // Show the main content with the signin overlay on top
        return (
            <>
                {children}
                <SignInOverlay />
            </>
        );
    }

    // User is authenticated, show normal content
    return <>{children}</>;
}
