import { betterAuth } from "better-auth";
import { oidcProvider, jwt } from "better-auth/plugins";
import { drizzleAdapter } from "better-auth/adapters/drizzle";
import { db } from "@/db";
import * as schema from "@/db/schema";

export const auth = betterAuth({
    disabledPaths: ["/token"],  // OIDC Compliance
    database: drizzleAdapter(db, {
        provider: "pg",
        schema: {
            ...schema,
            user: schema.users,
            account: schema.accounts,
            session: schema.sessions,
            verification: schema.verificationTokens,
            oauthApplication: schema.oauthApplications,
            oauthAccessToken: schema.oauthAccessTokens,
            oauthConsent: schema.oauthConsents,
        },
    }),
    socialProviders: {
        google: {
            clientId: process.env.GOOGLE_CLIENT_ID as string,
            clientSecret: process.env.GOOGLE_CLIENT_SECRET as string,
        },
    },
    plugins: [
        jwt({
            jwks: { keyPairConfig: { alg: "EdDSA", crv: "Ed25519" } },
            jwt: {
                // Emit tokens with origin-only issuer/audience to satisfy clients that expect no path
                issuer: new URL(process.env.AUTH_BASE_URL as string).origin,
                audience: new URL(process.env.AUTH_BASE_URL as string).origin,
            },
            disableSettingJwtHeader: true,
        }),
        oidcProvider({
            useJWTPlugin: true,
            loginPage: "/sign-in",
            trustedClients: [
                {
                    clientId: "256801d076d678f34cef8513e887f878",  // harmful-moderation
                    clientSecret: "9d76be99b2af553a3dcb2c5f6693684d0c6e3f1dbd6a7babe301a4eff9e8b598",
                    name: "Harmful Moderation",
                    type: "web",
                    redirectUrls: ["https://staging.thinkadaptive.ai/api/auth/callback/socialai-studio-auth"],
                    disabled: false,
                    skipConsent: true,
                    metadata: { external: true }
                },
                // {
                //   clientId: "",
                //   clientSecret: "",
                //   name: "",
                //   type: "web",
                //   redirectUrls: ["https://yourdomain.com/api/auth/callback/socialai-studio-auth"],  // The value of 'socialai-studio-auth' must match with AUTH_PROVIDER_ID under web/frontend/.env
                //   disabled: false,
                //   skipConsent: true,
                //   metadata: { external: true }
                // },
            ],
            metadata: {
                // Discovery issuer should match the JWT issuer (origin only)
                issuer: new URL(process.env.AUTH_BASE_URL as string).origin,
            },
        }),
    ],
    baseURL: process.env.AUTH_BASE_URL,
});
