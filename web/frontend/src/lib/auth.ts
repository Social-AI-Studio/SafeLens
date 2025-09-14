import NextAuth from "next-auth";
import type { NextAuthConfig, User, Profile, Session } from "next-auth";
import type { JWT } from "next-auth/jwt";
import { env, AUTH_ISSUER_ORIGIN, OIDC_WELL_KNOWN } from "@/env";

const isDev = process.env.NODE_ENV === "development";
const authLogger = {
    debug(message: string, ...rest: any[]) {
        if (isDev) console.log(`[auth][debug] ${message}`, ...rest);
    },
    warn(message: string, ...rest: any[]) {
        if (isDev) console.warn(`[auth][warn] ${message}`, ...rest);
    },
    error(message: string, ...rest: any[]) {
        console.error(`[auth][error] ${message}`, ...rest);
    },
};

// Custom OIDC profile type for our provider
interface CustomOIDCProfile extends Profile {
    sub: string;
    name?: string;
    email?: string;
    profile?: string;
}

// Runtime type guards to avoid unsafe casts
const isOIDCProfile = (p: unknown): p is CustomOIDCProfile =>
    typeof p === "object" && p !== null && typeof (p as any).sub === "string";

const hasStringId = (u: unknown): u is User & { id: string } =>
    typeof (u as any)?.id === "string" && (u as any).id.length > 0;

// Backend OIDC base under NextAuth (points to /api/auth)
const api_base = env.AUTH_ISSUER_URL;
// Provider `iss` claim is the origin
const issuer = AUTH_ISSUER_ORIGIN;

export const authConfig: NextAuthConfig = {
    debug: isDev,
    logger: {
        error(error: Error) {
            authLogger.error(`Unhandled error`, error);
            if ((error as any)?.cause) authLogger.error(`Cause`, (error as any).cause);
        },
        warn(code: string) {
            authLogger.warn(code);
        },
        debug(code: string, metadata?: any) {
            authLogger.debug(code, metadata);
        },
    },
    providers: [
        {
            id: env.AUTH_PROVIDER_ID,
            name: env.AUTH_PROVIDER_NAME,
            type: "oidc",
            clientId: env.AUTH_CLIENT_ID,
            clientSecret: env.AUTH_CLIENT_SECRET,
            client: { id_token_signed_response_alg: "EdDSA" },
            idToken: true,
            checks: ["pkce", "state", "nonce"],
            issuer: issuer,
            // Use OIDC discovery at the provider base path
            wellKnown: OIDC_WELL_KNOWN,
            authorization: {
                url: `${api_base}/oauth2/authorize`,
                params: {
                    scope: "openid profile email",
                    response_type: "code",
                },
            },
            token: `${api_base}/oauth2/token`,
            userinfo: `${api_base}/oauth2/userinfo`,
            jwks_endpoint: `${api_base}/jwks`,
            profile(profile: CustomOIDCProfile): User {
                authLogger.debug(
                    `OIDC profile received for user: ${profile.email?.split("@")[1] || "unknown"}`,
                );

                return {
                    id: profile.sub,
                    name: profile.name,
                    email: profile.email,
                    image: profile.profile,
                };
            },
        },
    ],
    session: {
        strategy: "jwt",
    },
    callbacks: {
        signIn: async ({ user, profile }) => {
            authLogger.debug(
                `Sign-in attempt for user with email domain: ${user.email?.split("@")[1]}`,
            );
            authLogger.debug(`Profile has sub claim: ${!!profile?.sub}`);

            return !!(user.email && profile?.sub);
        },

        jwt: async ({ token, user, trigger, profile, session }) => {
            if (trigger === "signIn") {
                if (!isOIDCProfile(profile) || !hasStringId(user)) {
                    authLogger.warn("Missing profile.sub or user.id; skipping registration data");
                    return token;
                }

                const name = typeof user.name === "string" ? user.name : undefined;
                const email = typeof user.email === "string" ? user.email : undefined;
                const image = typeof user.image === "string" ? user.image : undefined;

                token.needsRegistration = true;
                authLogger.debug(`CUIDv2: ${profile.sub} & session_uuid: ${user.id}`);
                token.registrationData = {
                    id: profile.sub,         // OIDC subject (CUID v2)
                    session_uuid: user.id,   // Auth.js session UUID
                    name,
                    email,
                    image,
                };

                if (email) {
                    authLogger.debug(
                        `User sign-in detected, registration/update deferred for: ${email.split("@")[1]} domain`,
                    );
                }
            }

            if (trigger === "update" && session) {
                token = { ...token, ...session };

                authLogger.debug(`Session updated:`, session);
            }

            if (token.needsRegistration === false) {
                delete token.needsRegistration;
                delete token.registrationData;
            }

            return token;
        },

        session: async ({ session, token }) => {
            if (token.sub && session.user) {
                session.user.id = token.sub;
            }

            session.needsRegistration = token.needsRegistration;
            session.registrationData = token.registrationData;

            return session;
        },
    },
};

export const { handlers, signIn, signOut, auth } = NextAuth(authConfig);
