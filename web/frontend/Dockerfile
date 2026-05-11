FROM node:22-alpine AS deps
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./
RUN pnpm install --frozen-lockfile --config.dangerouslyAllowAllBuilds=true

FROM node:22-alpine AS builder
WORKDIR /app
RUN corepack enable
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG AUTH_URL=https://staging.thinkadaptive.ai
ARG NEXT_PUBLIC_APP_URL=https://staging.thinkadaptive.ai
ARG NEXTAUTH_URL=https://staging.thinkadaptive.ai
ARG AUTH_ISSUER_URL=https://auth.thinkadaptive.ai/api/auth
ARG BACKEND_URL=http://web:8000
ARG AUTH_PROVIDER_ID=socialai-studio-auth
ARG AUTH_PROVIDER_NAME="SocialAI Studio Auth"
ARG AUTH_CLIENT_ID=build-placeholder
ARG AUTH_CLIENT_SECRET=build-placeholder
ARG AUTH_SECRET=build-placeholder
ENV AUTH_URL=$AUTH_URL
ENV NEXT_PUBLIC_APP_URL=$NEXT_PUBLIC_APP_URL
ENV NEXTAUTH_URL=$NEXTAUTH_URL
ENV AUTH_ISSUER_URL=$AUTH_ISSUER_URL
ENV BACKEND_URL=$BACKEND_URL
ENV AUTH_PROVIDER_ID=$AUTH_PROVIDER_ID
ENV AUTH_PROVIDER_NAME=$AUTH_PROVIDER_NAME
ENV AUTH_CLIENT_ID=$AUTH_CLIENT_ID
ENV AUTH_CLIENT_SECRET=$AUTH_CLIENT_SECRET
ENV AUTH_SECRET=$AUTH_SECRET
RUN pnpm build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV HOSTNAME=0.0.0.0
ENV PORT=3000
RUN corepack enable
COPY --from=builder /app ./
EXPOSE 3000
CMD ["pnpm", "start"]
