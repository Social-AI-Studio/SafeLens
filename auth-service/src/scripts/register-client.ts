import "dotenv/config"; // Load .env first
import { randomBytes } from "crypto";
import { db } from "@/db";
import { oauthApplications } from "@/db/schema";
import { eq } from "drizzle-orm";

/*
Production-ready OIDC client registration script

Usage (no file edits needed):

  pnpm run register-client -- \
    --name "My App" \
    --redirect "https://app.example.com/api/auth/callback/socialai-studio-auth" \
    --type web

Or via env vars:

  CLIENT_NAME="My App" \
  REDIRECT_URIS="https://app.example.com/api/auth/callback/socialai-studio-auth,https://app.example.com/alt" \
  CLIENT_TYPE=web \
  pnpm run register-client

Notes
- Redirect URIs must be exact (scheme/host/path). Comma-separated for multiple.
- This writes directly to the oauth_application table (bypasses admin UI).
- After creation, set these in your consuming app:
    AUTH_CLIENT_ID, AUTH_CLIENT_SECRET, AUTH_ISSUER_URL
*/

type Args = {
    name?: string;
    redirect?: string[]; // allow multiple
    type?: string; // e.g., web
    clientId?: string;
    clientSecret?: string;
    force?: boolean;
};

function parseArgs(argv: string[]): Args {
    const args: Args = { redirect: [] };
    for (let i = 0; i < argv.length; i++) {
        const a = argv[i];
        if (a === "--name") args.name = argv[++i];
        else if (a === "--redirect") args.redirect!.push(argv[++i]);
        else if (a === "--type") args.type = argv[++i];
        else if (a === "--client-id") args.clientId = argv[++i];
        else if (a === "--client-secret") args.clientSecret = argv[++i];
        else if (a === "--force") args.force = true;
    }

    // Merge env vars
    if (!args.name && process.env.CLIENT_NAME) args.name = process.env.CLIENT_NAME;
    const envUris = (process.env.REDIRECT_URIS || "")
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
    if (envUris.length > 0) args.redirect = [...(args.redirect || []), ...envUris];
    if (!args.type && process.env.CLIENT_TYPE) args.type = process.env.CLIENT_TYPE;
    if (!args.clientId && process.env.CLIENT_ID) args.clientId = process.env.CLIENT_ID;
    if (!args.clientSecret && process.env.CLIENT_SECRET)
        args.clientSecret = process.env.CLIENT_SECRET;

    return args;
}

function isValidRedirect(uri: string): boolean {
    try {
        const u = new URL(uri);
        return (
            u.protocol === "https:" ||
            u.hostname === "localhost" ||
            u.hostname === "127.0.0.1"
        );
    } catch {
        return false;
    }
}

async function register() {
    const args = parseArgs(process.argv.slice(2));

    // Validate required inputs
    if (!args.name || !(args.redirect && args.redirect.length)) {
        console.error(
            `\nUsage: pnpm run register-client -- --name "My App" --redirect "https://app.example.com/api/auth/callback/..." [--type web]`,
        );
        console.error(
            `Or set env: CLIENT_NAME, REDIRECT_URIS (comma-separated), CLIENT_TYPE`,
        );
        process.exit(1);
    }

    // Normalize redirects to comma-separated string for storage
    const invalid = args.redirect.filter((r) => !isValidRedirect(r));
    if (invalid.length) {
        console.error(`Invalid redirect URIs: ${invalid.join(", ")}`);
        process.exit(1);
    }
    const redirectString = args.redirect.join(",");

    // Guard: existing app with same name (avoid accidental duplicates)
    try {
        const existing = await db
            .select({ id: oauthApplications.id })
            .from(oauthApplications)
            .where(eq(oauthApplications.name, args.name));
        if (existing.length && !args.force) {
            console.error(
                `\nAn application named "${args.name}" already exists. Use --force to create another with the same name.`,
            );
            process.exit(1);
        }
    } catch (e) {
        // continue; select guard is best-effort
    }

    // Credentials (generate if not supplied)
    const clientId = args.clientId || randomBytes(16).toString("hex");
    const clientSecret = args.clientSecret || randomBytes(32).toString("hex");

    console.log(`\nRegistering client: ${args.name}`);
    console.log(`Redirect URIs:`);
    args.redirect.forEach((u) => console.log(` - ${u}`));

    try {
        await db.insert(oauthApplications).values({
            name: args.name,
            redirectURLs: redirectString,
            type: args.type || "web",
            clientId,
            clientSecret,
            disabled: false,
        });

        console.log("\n✅ Client registered successfully");
        console.log("-----------------------------------------");
        console.log("Store these in your client application's env:");
        console.log(`AUTH_CLIENT_ID="${clientId}"`);
        console.log(`AUTH_CLIENT_SECRET="${clientSecret}"`);
        console.log("-----------------------------------------");
        console.log(
            "If you want to skip consent, add this client to the trustedClients array in src/lib/auth.ts.",
        );
    } catch (error: any) {
        console.error("\n❌ Failed to register client.");
        console.error("Error:", error?.message || error);
        process.exit(1);
    }
}

register();
