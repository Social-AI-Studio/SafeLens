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
                issuer: process.env.AUTH_BASE_URL,
                audience: process.env.AUTH_BASE_URL,
            },
            disableSettingJwtHeader: true,
        }),
        oidcProvider({
            useJWTPlugin: true,
            loginPage: "/sign-in",
            trustedClients: [
                // {
                //   clientId: "",
                //   clientSecret: "",
                //   name: "",
                //   type: "web",
                //   redirectURLs: ["https://yourdomain.com/api/auth/callback/socialai-studio-auth"],  // The value of 'socialai-studio-auth' must match with AUTH_PROVIDER_ID under web/frontend/.env
                //   disabled: false,
                //   skipConsent: true,
                //   metadata: { external: true }
                // },
            ],
            metadata: {
                issuer: process.env.AUTH_BASE_URL,
            },
        }),
    ],
    baseURL: process.env.AUTH_BASE_URL,
});
