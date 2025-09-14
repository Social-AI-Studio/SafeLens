"use server";

import { headers, cookies } from "next/headers";

function isValidUrl(u: string): boolean {
    try {
        const url = new URL(u);
        return url.protocol === "https:" || url.protocol === "http:";
    } catch {
        return false;
    }
}

export type RegisterOidcAppInput = {
    client_name: string;
    redirect_uris: string[];
    token_endpoint_auth_method?: "none" | "client_secret_basic" | "client_secret_post";
    scope?: string; // e.g., "openid email profile"
    metadata?: Record<string, any>;
};

export type RegisterOidcAppResult =
    | { ok: true; client_id: string; client_secret?: string; raw: any }
    | { ok: false; message: string; issues?: string[] };

/**
 * Server action to register a new OIDC client via the Better Auth OIDC provider
 * dynamic client registration endpoint (RFC 7591).
 *
 * This action must be called from a trusted/admin context. You should guard
 * the UI that invokes this action using your own session/role checks.
 */
export async function registerOidcApplication(
    input: RegisterOidcAppInput,
): Promise<RegisterOidcAppResult> {
    const issues: string[] = [];
    if (!input.client_name || input.client_name.trim().length < 2) {
        issues.push("client_name is required and must be at least 2 chars");
    }
    if (!Array.isArray(input.redirect_uris) || input.redirect_uris.length === 0) {
        issues.push("At least one redirect URI is required");
    }
    const badUris = (input.redirect_uris || []).filter((u) => !isValidUrl(u));
    if (badUris.length > 0) {
        issues.push(`Invalid redirect URIs: ${badUris.join(", ")}`);
    }
    if (issues.length > 0) {
        return { ok: false, message: "Validation failed", issues };
    }

    const hdrs = await headers();
    const serverEnvBase = (process.env.AUTH_BASE_URL || "").replace(/\/$/, "");
    if (!serverEnvBase) {
        return {
            ok: false,
            message:
                "Server misconfiguration: AUTH_BASE_URL is required for registration.",
        };
    }
    const baseURL = serverEnvBase;
    const endpoint = new URL("/api/auth/oauth2/register", baseURL).toString();

    const cookieStore = await cookies();
    const cookieHeader = cookieStore
        .getAll()
        .map((c) => `${c.name}=${encodeURIComponent(c.value)}`)
        .join("; ");

    const origin = new URL(baseURL).origin;
    const userAgent = hdrs.get("user-agent") || undefined;

    const payload: any = {
        client_name: input.client_name,
        redirect_uris: input.redirect_uris,
    };
    if (input.token_endpoint_auth_method) {
        payload.token_endpoint_auth_method = input.token_endpoint_auth_method;
    }
    if (input.scope) payload.scope = input.scope;
    if (input.metadata) payload.metadata = input.metadata;

    let res: Response;
    try {
        res = await fetch(endpoint, {
            method: "POST",
            headers: {
                "content-type": "application/json",
                ...(cookieHeader ? { Cookie: cookieHeader } : {}),
                ...(origin ? { Origin: origin } : {}),
                ...(userAgent ? { "User-Agent": userAgent } : {}),
            },
            body: JSON.stringify(payload),
            cache: "no-store",
        });
    } catch (e: any) {
        return {
            ok: false,
            message: `Network error calling registration endpoint (${endpoint}): ${e?.message || e}`,
        };
    }

    if (!res.ok) {
        let detail: any = undefined;
        try {
            detail = await res.json();
        } catch {
            // ignore
        }
        return {
            ok: false,
            message: `Registration failed (${res.status})`,
            issues:
                detail?.errors || detail?.message
                    ? [String(detail.message)]
                    : undefined,
        };
    }

    const data = await res.json();
    return {
        ok: true,
        client_id: String(data.client_id),
        client_secret: data.client_secret ? String(data.client_secret) : undefined,
        raw: data,
    };
}
