"use client";

import Image from "next/image";
import { signIn } from "next-auth/react";
import { Button } from "@/components/ui/button";

export default function SignInOverlay() {
    const handleSignIn = async () => {
        // Try to bypass the signin page by going directly to the provider
        await signIn("socialai-studio-auth", {});
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 backdrop-blur-sm">
            <div className="w-full max-w-md p-8 space-y-6 bg-white/95 backdrop-blur-md rounded-2xl shadow-xl border border-white/20">
                <div className="flex justify-center">
                    <Image
                        src="/capybara.svg"
                        alt="SocialAI Studio Auth Logo"
                        width={120}
                        height={120}
                        className="object-contain"
                        priority
                    />
                </div>

                <div className="text-center">
                    <h2 className="text-xl font-semibold text-gray-900 mb-2">
                        Welcome
                    </h2>
                    <p className="text-gray-600 text-sm">Please sign in to continue</p>
                </div>

                <Button
                    size="lg"
                    className="w-full py-3 text-base font-medium"
                    onClick={handleSignIn}
                >
                    Sign in with SocialAI Studio
                </Button>
            </div>
        </div>
    );
}
