FROM node:22-alpine AS deps
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./
RUN pnpm install --frozen-lockfile

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
ENV AUTH_URL=$AUTH_URL
ENV NEXT_PUBLIC_APP_URL=$NEXT_PUBLIC_APP_URL
ENV NEXTAUTH_URL=$NEXTAUTH_URL
ENV AUTH_ISSUER_URL=$AUTH_ISSUER_URL
ENV BACKEND_URL=$BACKEND_URL
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
