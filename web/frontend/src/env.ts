import { z } from "zod";

// Validate required server-side environment variables at build/start time
const EnvSchema = z.object({
  AUTH_PROVIDER_ID: z.string().min(1, "AUTH_PROVIDER_ID is required"),
  AUTH_PROVIDER_NAME: z.string().min(1, "AUTH_PROVIDER_NAME is required"),
  AUTH_CLIENT_ID: z.string().min(1, "AUTH_CLIENT_ID is required"),
  AUTH_CLIENT_SECRET: z.string().min(1, "AUTH_CLIENT_SECRET is required"),
  AUTH_ISSUER_URL: z.string().url("AUTH_ISSUER_URL must be a URL"),
  AUTH_SECRET: z.string().min(1, "AUTH_SECRET is required"),
});

export const env = EnvSchema.parse({
  AUTH_PROVIDER_ID: process.env.AUTH_PROVIDER_ID,
  AUTH_PROVIDER_NAME: process.env.AUTH_PROVIDER_NAME,
  AUTH_CLIENT_ID: process.env.AUTH_CLIENT_ID,
  AUTH_CLIENT_SECRET: process.env.AUTH_CLIENT_SECRET,
  AUTH_ISSUER_URL: process.env.AUTH_ISSUER_URL,
  AUTH_SECRET: process.env.AUTH_SECRET,
});

// Derived values used in OIDC configuration
export const AUTH_ISSUER_ORIGIN = new URL(env.AUTH_ISSUER_URL).origin;
export const OIDC_WELL_KNOWN = `${env.AUTH_ISSUER_URL}/.well-known/openid-configuration`;

