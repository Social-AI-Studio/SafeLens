"use server";

import { registerOidcApplication } from "../actions";

type RegisterOidcAppFormState = {
    ok: boolean | null;
    message?: string;
    issues?: string[];
    client_id?: string;
    client_secret?: string;
};

export async function registerOidcApplicationAction(
    _prevState: RegisterOidcAppFormState,
    formData: FormData,
): Promise<RegisterOidcAppFormState> {
    const name = String(formData.get("client_name") || "").trim();
    const redirectUrisRaw = String(formData.get("redirect_uris") || "").trim();
    const method = String(
        formData.get("token_endpoint_auth_method") || "client_secret_basic",
    );
    const scope = String(formData.get("scope") || "openid email profile");

    const redirect_uris = redirectUrisRaw
        .split(/\n|\r|,/)
        .map((s) => s.trim())
        .filter(Boolean);

    const res = await registerOidcApplication({
        client_name: name,
        redirect_uris,
        token_endpoint_auth_method: method as any,
        scope,
        metadata: {
            firstParty: formData.get("first_party") === "on",
            skipConsent: formData.get("skip_consent") === "on",
        },
    });

    if (!res.ok) {
        return {
            ok: false,
            message: res.message,
            issues: res.issues,
        };
    }

    return {
        ok: true,
        client_id: res.client_id,
        client_secret: res.client_secret,
    };
}
