import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";

export async function POST(request: NextRequest) {
    try {
        const session = await auth();

        if (!session?.user) {
            return NextResponse.json(
                { error: "Unauthorized - No valid session" },
                { status: 401 },
            );
        }

        const needsRegistration = session.needsRegistration;
        const registrationData = session.registrationData;

        if (!needsRegistration || !registrationData) {
            return NextResponse.json(
                { error: "No registration required or data not available" },
                { status: 400 },
            );
        }

        const backendUrl = process.env.BACKEND_URL!;
        const response = await fetch(`${backendUrl}/api/auth/register`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(registrationData),
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error(`[api][error] Backend registration failed:`, {
                status: response.status,
                error: errorText,
                userId: session.user.id,
            });

            if (response.status === 409) {
                return NextResponse.json(
                    {
                        error: "Account conflict detected",
                        details:
                            "This email is associated with a different account. Please contact support.",
                    },
                    { status: 409 },
                );
            }

            return NextResponse.json(
                {
                    error: "Registration failed",
                    details:
                        process.env.NODE_ENV === "development" ? errorText : undefined,
                },
                { status: response.status },
            );
        }

        const userData = await response.json();
        const isNewUser = response.status === 201;
        const isExistingUser = response.status === 200;

        if (isNewUser) {
            console.log(`[api][info] New user registered successfully:`, {
                id: userData.id,
                email: userData.email,
            });
        } else if (isExistingUser) {
            console.log(`[api][info] Existing user session updated:`, {
                id: userData.id,
                email: userData.email,
            });
        }

        return NextResponse.json({
            success: true,
            user: userData,
            isNewUser: isNewUser,
            isExistingUser: isExistingUser,
        });
    } catch (error) {
        console.error(`[api][error] Registration error:`, error);

        return NextResponse.json(
            {
                error: "Internal server error during registration",
                details:
                    process.env.NODE_ENV === "development" ? String(error) : undefined,
            },
            { status: 500 },
        );
    }
}
