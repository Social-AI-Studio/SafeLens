"use client";

import React from "react";
import { useFormStatus } from "react-dom";
import { registerOidcApplicationAction } from "./actions";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function SubmitButton() {
    const { pending } = useFormStatus();
    return (
        <Button type="submit" disabled={pending}>
            {pending ? "Registering..." : "Register"}
        </Button>
    );
}

type FormState = {
    ok: boolean | null;
    message?: string;
    issues?: string[];
    client_id?: string;
    client_secret?: string;
};

export default function NewAppPage() {
    const initialState: FormState = { ok: null };
    const [state, formAction] = React.useActionState(
        registerOidcApplicationAction as any,
        initialState,
    );
    const [copiedId, setCopiedId] = React.useState(false);
    const [copiedSecret, setCopiedSecret] = React.useState(false);
    const formRef = React.useRef<HTMLFormElement>(null);

    async function copy(text?: string) {
        if (!text) return;
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch {
            return false;
        }
    }

    return (
        <div className="px-4 md:px-6">
            <Card className="max-w-3xl mx-auto">
                <CardHeader className="border-b [.border-b]:pb-4">
                    <CardTitle className="text-xl md:text-2xl">
                        Register New OIDC Application
                    </CardTitle>
                </CardHeader>
                <CardContent className="py-2">
                    {state.ok && (
                        <div className="mb-6 p-4 rounded-md bg-green-50 border text-sm">
                            <div className="font-medium mb-1">
                                Client registered successfully.
                            </div>
                            <div className="mt-2 flex items-start gap-2">
                                <div className="flex-1">
                                    <div className="text-xs uppercase text-gray-500">
                                        client_id
                                    </div>
                                    <div className="font-mono break-all select-all">
                                        {state.client_id}
                                    </div>
                                </div>
                                <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={async () => {
                                        const ok = await copy(state.client_id);
                                        setCopiedId(Boolean(ok));
                                        setTimeout(() => setCopiedId(false), 1500);
                                    }}
                                >
                                    {copiedId ? "Copied" : "Copy"}
                                </Button>
                            </div>

                            {state.client_secret && (
                                <div className="mt-2 flex items-start gap-2">
                                    <div className="flex-1">
                                        <div className="text-xs uppercase text-gray-500">
                                            client_secret
                                        </div>
                                        <div className="font-mono break-all select-all">
                                            {state.client_secret}
                                        </div>
                                    </div>
                                    <Button
                                        type="button"
                                        variant="outline"
                                        size="sm"
                                        onClick={async () => {
                                            const ok = await copy(state.client_secret);
                                            setCopiedSecret(Boolean(ok));
                                            setTimeout(
                                                () => setCopiedSecret(false),
                                                1500,
                                            );
                                        }}
                                    >
                                        {copiedSecret ? "Copied" : "Copy"}
                                    </Button>
                                </div>
                            )}
                            <div className="mt-2 text-yellow-700">
                                Copy and store these securely. The secret will not be
                                shown again.
                            </div>
                            <div className="mt-3 flex gap-2">
                                <Button variant="outline" asChild>
                                    <Link href="/admin/apps">Go to applications</Link>
                                </Button>
                                <Button
                                    type="button"
                                    variant="secondary"
                                    onClick={() => window.location.reload()}
                                >
                                    Register another
                                </Button>
                            </div>
                        </div>
                    )}

                    {state.ok === false && (
                        <div className="mb-6 p-4 rounded-md bg-red-50 border text-sm">
                            <div className="font-medium mb-1">
                                Failed to register client
                            </div>
                            <div>{state.message}</div>
                            {state.issues && state.issues.length > 0 && (
                                <ul className="list-disc ml-5 mt-2">
                                    {state.issues.map((i, idx) => (
                                        <li key={idx}>{i}</li>
                                    ))}
                                </ul>
                            )}
                        </div>
                    )}

                    <form action={formAction} className="space-y-4" ref={formRef}>
                        <div>
                            <label className="block text-sm font-medium">
                                Application Name
                            </label>
                            <input
                                name="client_name"
                                className="mt-1 w-full border rounded-md p-2"
                                placeholder="My App"
                                required
                                disabled={Boolean(state.ok)}
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium">
                                Redirect URIs
                            </label>
                            <textarea
                                name="redirect_uris"
                                className="mt-1 w-full border rounded-md p-2 h-28"
                                placeholder="https://app.example.com/api/auth/callback"
                                required
                                disabled={Boolean(state.ok)}
                            />
                            <p className="text-xs text-muted-foreground mt-1">
                                One per line or comma-separated. Must be exact.
                            </p>
                        </div>

                        <div>
                            <label className="block text-sm font-medium">
                                Token Endpoint Auth Method
                            </label>
                            <select
                                name="token_endpoint_auth_method"
                                className="mt-1 w-full border rounded-md p-2"
                                defaultValue="client_secret_basic"
                                disabled={Boolean(state.ok)}
                            >
                                <option value="client_secret_basic">
                                    client_secret_basic
                                </option>
                                <option value="client_secret_post">
                                    client_secret_post
                                </option>
                                <option value="none">none (public client)</option>
                            </select>
                        </div>

                        <div>
                            <label className="block text-sm font-medium">Scopes</label>
                            <input
                                name="scope"
                                className="mt-1 w-full border rounded-md p-2"
                                defaultValue="openid email profile"
                                disabled={Boolean(state.ok)}
                            />
                        </div>

                        <div className="flex items-center gap-6">
                            <label className="inline-flex items-center gap-2 text-sm">
                                <input
                                    type="checkbox"
                                    name="first_party"
                                    disabled={Boolean(state.ok)}
                                />
                                First-party
                            </label>
                            <label className="inline-flex items-center gap-2 text-sm">
                                <input
                                    type="checkbox"
                                    name="skip_consent"
                                    disabled={Boolean(state.ok)}
                                />
                                Skip consent
                            </label>
                        </div>

                        {state.ok ? (
                            <Button
                                type="button"
                                onClick={() => window.location.reload()}
                            >
                                Register another
                            </Button>
                        ) : (
                            <SubmitButton />
                        )}
                    </form>

                    <div className="mt-6 p-3 bg-yellow-50 border border-yellow-200 rounded-md text-sm">
                        After registration, you will see the <strong>client_id</strong>{" "}
                        and <strong>client_secret</strong> once. Store them securely in
                        the client app configuration.
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
