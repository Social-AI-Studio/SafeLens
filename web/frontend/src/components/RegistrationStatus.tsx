"use client";

import { useRegistration } from "@/lib/useRegistration";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Loader2, CheckCircle, AlertCircle, RefreshCw } from "lucide-react";

export function RegistrationStatus() {
    const {
        registrationStatus,
        error,
        retryRegistration,
        hideRegistration,
        needsRegistration,
    } = useRegistration();

    // Don't show anything if registration isn't needed or if status is idle
    if (!needsRegistration || registrationStatus === "idle") {
        return null;
    }

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <Card className="w-full max-w-md mx-4">
                <CardHeader className="text-center">
                    <div className="flex justify-center mb-4">
                        {registrationStatus === "registering" && (
                            <Loader2 className="h-12 w-12 animate-spin text-blue-500" />
                        )}
                        {registrationStatus === "completed" && (
                            <CheckCircle className="h-12 w-12 text-green-500" />
                        )}
                        {registrationStatus === "error" && (
                            <AlertCircle className="h-12 w-12 text-red-500" />
                        )}
                    </div>

                    <CardTitle>
                        {registrationStatus === "registering" &&
                            "Preparing your session..."}
                        {registrationStatus === "completed" &&
                            "Welcome to Harmful Moderation!"}
                        {registrationStatus === "error" && "Setup Failed"}
                    </CardTitle>

                    <CardDescription>
                        {registrationStatus === "registering" &&
                            "Please wait while we set up your session. This will only take a moment."}
                        {registrationStatus === "completed" &&
                            "Your session is ready. You can now access all features."}
                        {registrationStatus === "error" &&
                            "There was an issue setting up your session. Please try again."}
                    </CardDescription>
                </CardHeader>

                {(registrationStatus === "error" ||
                    registrationStatus === "completed") && (
                    <CardContent className="text-center">
                        {registrationStatus === "error" && (
                            <>
                                {error && (
                                    <p className="text-sm text-red-600 mb-4 p-2 bg-red-50 rounded">
                                        {error}
                                    </p>
                                )}
                                <Button onClick={retryRegistration} className="w-full">
                                    <RefreshCw className="h-4 w-4 mr-2" />
                                    Try Again
                                </Button>
                            </>
                        )}

                        {registrationStatus === "completed" && (
                            <Button onClick={hideRegistration} className="w-full">
                                Continue to Dashboard
                            </Button>
                        )}
                    </CardContent>
                )}
            </Card>
        </div>
    );
}
