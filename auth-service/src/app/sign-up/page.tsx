"use client";

import Image from "next/image";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { authClient } from "@/lib/auth-client";
import { useRouter } from "next/navigation";

export default function LoginPage() {
    const router = useRouter();

    const handleGoogleSignIn = async () => {
        try {
            const result = await authClient.signIn.social({
                provider: "google",
                callbackURL: "/",
            });

            if (result.error) {
                console.error("Sign in error:", result.error);
            } else {
                router.push("/");
            }
        } catch (error) {
            console.error("Sign in failed:", error);
        }
    };

    return (
        <div className="flex items-center justify-center min-h-screen bg-background px-4">
            <div className="w-full max-w-sm -mt-20">
                <div className="text-center mb-6">
                    <div className="flex justify-center mb-6">
                        <Image
                            src="/capybara.svg"
                            alt="SocialAI Studio Logo"
                            width={96}
                            height={96}
                            className="object-contain"
                        />
                    </div>
                    <h1 className="text-xl font-bold text-foreground">Sign up</h1>
                </div>

                <div className="p-8 space-y-6 bg-card rounded-2xl shadow-md border border-border">
                    <Button
                        variant="outline"
                        className="w-full flex items-center justify-center gap-2 py-6 text-base"
                        onClick={handleGoogleSignIn}
                    >
                        <Image
                            src="/google.svg"
                            alt="Google Logo"
                            width={20}
                            height={20}
                            className="object-contain"
                        />
                        Continue with Google
                    </Button>

                    <div className="text-center">
                        <p className="text-sm text-muted-foreground">
                            Already have an account?{" "}
                            <Link
                                href="/sign-in"
                                className="text-blue-600 hover:underline underline-offset-4 dark:text-blue-400"
                            >
                                Sign in
                            </Link>
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
}
