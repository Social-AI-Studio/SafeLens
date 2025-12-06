import { signIn, signOut } from "next-auth/react";

export class AuthError extends Error {
    constructor(
        message: string,
        public status: number,
    ) {
        super(message);
        this.name = "AuthError";
    }
}

export async function authFetch(
    input: RequestInfo | URL,
    init?: RequestInit,
): Promise<Response> {
    const response = await fetch(input, init);

    if (response.status === 401) {
        try {
            await signIn("socialai-studio-auth", { redirect: false });
            const retryResponse = await fetch(input, init);
            if (retryResponse.status === 401) {
                await signOut({ callbackUrl: "/", redirect: true });
                throw new AuthError("Session expired. Please sign in again.", 401);
            }
            return retryResponse;
        } catch (error) {
            if (error instanceof AuthError) throw error;
            await signOut({ callbackUrl: "/", redirect: true });
            throw new AuthError("Session expired. Please sign in again.", 401);
        }
    }

    return response;
}
