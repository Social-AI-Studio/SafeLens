import {
    pgTable,
    text,
    timestamp,
    boolean,
    integer,
    pgEnum,
    primaryKey,
    uniqueIndex,
} from "drizzle-orm/pg-core";
import { relations } from "drizzle-orm";
import { createId } from "@paralleldrive/cuid2";

/**
 * --------------------------------------------------------------------------
 * CUSTOM ENUMS
 * --------------------------------------------------------------------------
 */
export const roleEnum = pgEnum("role", ["USER", "ADMIN"]);

/**
 * --------------------------------------------------------------------------
 * CORE TABLES
 * These definitions follow the library's generated schema to ensure
 * compatibility, with our 'role' customization added to the users table.
 * --------------------------------------------------------------------------
 */

export const users = pgTable("user", {
    id: text("id")
        .primaryKey()
        .$defaultFn(() => createId()),
    name: text("name"),
    email: text("email").notNull().unique(),
    emailVerified: boolean("email_verified").notNull().default(false),
    image: text("image"),
    createdAt: timestamp("created_at").notNull().defaultNow(),
    updatedAt: timestamp("updated_at").notNull().defaultNow(),
    role: roleEnum("role").notNull().default("USER"),
});

export const sessions = pgTable("session", {
    id: text("id")
        .primaryKey()
        .$defaultFn(() => createId()),
    expiresAt: timestamp("expires_at").notNull(),
    token: text("token").notNull().unique(),
    createdAt: timestamp("created_at").notNull().defaultNow(),
    updatedAt: timestamp("updated_at").notNull().defaultNow(),
    ipAddress: text("ip_address"),
    userAgent: text("user_agent"),
    userId: text("user_id")
        .notNull()
        .references(() => users.id, { onDelete: "cascade" }),
});

export const accounts = pgTable(
    "account",
    {
        id: text("id")
            .primaryKey()
            .$defaultFn(() => createId()),
        accountId: text("account_id").notNull(),
        providerId: text("provider_id").notNull(),
        userId: text("user_id")
            .notNull()
            .references(() => users.id, { onDelete: "cascade" }),
        accessToken: text("access_token"),
        refreshToken: text("refresh_token"),
        idToken: text("id_token"),
        accessTokenExpiresAt: timestamp("access_token_expires_at"),
        refreshTokenExpiresAt: timestamp("refresh_token_expires_at"),
        scope: text("scope"),
        password: text("password"),
        createdAt: timestamp("created_at").notNull().defaultNow(),
        updatedAt: timestamp("updated_at").notNull().defaultNow(),
    },
    (table) => [
        uniqueIndex("account_provider_idx").on(table.providerId, table.accountId),
    ],
);

export const verificationTokens = pgTable("verification", {
    id: text("id")
        .primaryKey()
        .$defaultFn(() => createId()),
    identifier: text("identifier").notNull(),
    value: text("value").notNull(),
    expiresAt: timestamp("expires_at").notNull(),
    createdAt: timestamp("created_at").notNull().defaultNow(),
    updatedAt: timestamp("updated_at").notNull().defaultNow(),
});

/**
 * --------------------------------------------------------------------------
 * JWT PLUGIN TABLE
 * This table is required by the `jwt` plugin to store the public/private
 * key pairs used for secure, asymmetric signing of ID tokens.
 * --------------------------------------------------------------------------
 */

export const jwks = pgTable("jwks", {
    id: text("id")
        .primaryKey()
        .$defaultFn(() => createId()),
    publicKey: text("public_key").notNull(),
    privateKey: text("private_key").notNull(),
    createdAt: timestamp("created_at").notNull().defaultNow(),
});

/**
 * --------------------------------------------------------------------------
 * OIDC PROVIDER TABLES
 * --------------------------------------------------------------------------
 */

export const oauthApplications = pgTable("oauth_application", {
    id: text("id")
        .primaryKey()
        .$defaultFn(() => createId()),
    name: text("name"),
    icon: text("icon"),
    metadata: text("metadata"),
    clientId: text("client_id").notNull().unique(),
    clientSecret: text("client_secret").notNull(),
    redirectURLs: text("redirect_u_r_ls"),
    type: text("type"),
    disabled: boolean("disabled").notNull().default(false),
    userId: text("user_id"),
    createdAt: timestamp("created_at").notNull().defaultNow(),
    updatedAt: timestamp("updated_at").notNull().defaultNow(),
});

export const oauthAccessTokens = pgTable("oauth_access_token", {
    id: text("id")
        .primaryKey()
        .$defaultFn(() => createId()),
    accessToken: text("access_token").notNull().unique(),
    refreshToken: text("refresh_token").unique(),
    accessTokenExpiresAt: timestamp("access_token_expires_at").notNull(),
    refreshTokenExpiresAt: timestamp("refresh_token_expires_at"),
    clientId: text("client_id")
        .notNull()
        .references(() => oauthApplications.clientId, { onDelete: "cascade" }),
    userId: text("user_id")
        .notNull()
        .references(() => users.id, { onDelete: "cascade" }),
    scopes: text("scopes"),
    createdAt: timestamp("created_at").notNull().defaultNow(),
    updatedAt: timestamp("updated_at").notNull().defaultNow(),
});

export const oauthConsents = pgTable("oauth_consent", {
    id: text("id")
        .primaryKey()
        .$defaultFn(() => createId()),
    userId: text("user_id")
        .notNull()
        .references(() => users.id, { onDelete: "cascade" }),
    clientId: text("client_id")
        .notNull()
        .references(() => oauthApplications.clientId, { onDelete: "cascade" }),
    scopes: text("scopes"),
    createdAt: timestamp("created_at").notNull().defaultNow(),
    updatedAt: timestamp("updated_at").notNull().defaultNow(),
    consentGiven: boolean("consent_given"),
});

/**
 * --------------------------------------------------------------------------
 * RELATIONS
 * --------------------------------------------------------------------------
 */

export const usersRelations = relations(users, ({ many }) => ({
    accounts: many(accounts),
    sessions: many(sessions),
    oauthAccessTokens: many(oauthAccessTokens),
    oauthConsents: many(oauthConsents),
}));

export const sessionsRelations = relations(sessions, ({ one }) => ({
    user: one(users, { fields: [sessions.userId], references: [users.id] }),
}));

export const accountsRelations = relations(accounts, ({ one }) => ({
    user: one(users, { fields: [accounts.userId], references: [users.id] }),
}));

export const oauthApplicationsRelations = relations(oauthApplications, ({ many }) => ({
    accessTokens: many(oauthAccessTokens),
    consents: many(oauthConsents),
}));

export const oauthAccessTokensRelations = relations(oauthAccessTokens, ({ one }) => ({
    user: one(users, { fields: [oauthAccessTokens.userId], references: [users.id] }),
    application: one(oauthApplications, {
        fields: [oauthAccessTokens.clientId],
        references: [oauthApplications.clientId],
    }),
}));

export const oauthConsentsRelations = relations(oauthConsents, ({ one }) => ({
    user: one(users, { fields: [oauthConsents.userId], references: [users.id] }),
    application: one(oauthApplications, {
        fields: [oauthConsents.clientId],
        references: [oauthApplications.clientId],
    }),
}));
