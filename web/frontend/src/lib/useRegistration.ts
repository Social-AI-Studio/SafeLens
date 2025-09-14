import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";

interface RegistrationResult {
    success: boolean;
    user?: any;
    isNewUser?: boolean;
    isExistingUser?: boolean;
    error?: string;
}

export function useRegistration() {
    const { data: session, update } = useSession();
    const [registrationStatus, setRegistrationStatus] = useState<
        "idle" | "registering" | "completed" | "error"
    >("idle");
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const needsRegistration = session?.needsRegistration;

        if (session && needsRegistration && registrationStatus === "idle") {
            handleRegistration();
        }
    }, [session, registrationStatus]);

    const handleRegistration = async () => {
        if (registrationStatus === "registering") return; // Prevent double submission

        setRegistrationStatus("registering");
        setError(null);

        try {
            const response = await fetch("/api/user/register", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
            });

            const result: RegistrationResult = await response.json();

            if (!response.ok || !result.success) {
                throw new Error(result.error || "Registration failed");
            }

            if (result.isNewUser) {
                console.log(`[registration] New user registered successfully:`, {
                    userId: result.user?.id,
                });
            } else if (result.isExistingUser) {
                console.log(`[registration] Existing user session updated:`, {
                    userId: result.user?.id,
                });
            }

            // Clear the registration flags from the JWT token
            await update({
                needsRegistration: false,
            });

            setRegistrationStatus("completed");

            // Auto-hide after 2 seconds for existing users, or wait for user interaction for new users
            if (result.isExistingUser) {
                setTimeout(() => {
                    setRegistrationStatus("idle");
                }, 2000);
            }
        } catch (err) {
            const errorMessage =
                err instanceof Error ? err.message : "Unknown registration error";
            console.error(`[registration] Registration failed:`, errorMessage);
            setError(errorMessage);
            setRegistrationStatus("error");
        }
    };

    const retryRegistration = () => {
        if (registrationStatus === "error") {
            setRegistrationStatus("idle");
        }
    };

    const hideRegistration = () => {
        setRegistrationStatus("idle");
    };

    return {
        registrationStatus,
        error,
        retryRegistration,
        hideRegistration,
        needsRegistration: session?.needsRegistration ?? false,
    };
}
