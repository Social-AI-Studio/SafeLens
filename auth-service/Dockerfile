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
ARG NEXT_PUBLIC_BETTER_AUTH_URL=https://auth.thinkadaptive.ai/api/auth
ARG AUTH_BASE_URL=https://auth.thinkadaptive.ai/api/auth
ARG DATABASE_URL=postgres://socialaistudio:socialaistudio@auth_db:5432/socialai_auth
ARG BETTER_AUTH_SECRET=build-placeholder
ARG GOOGLE_CLIENT_ID=build-placeholder
ARG GOOGLE_CLIENT_SECRET=build-placeholder
ENV NEXT_PUBLIC_BETTER_AUTH_URL=$NEXT_PUBLIC_BETTER_AUTH_URL
ENV AUTH_BASE_URL=$AUTH_BASE_URL
ENV DATABASE_URL=$DATABASE_URL
ENV BETTER_AUTH_SECRET=$BETTER_AUTH_SECRET
ENV GOOGLE_CLIENT_ID=$GOOGLE_CLIENT_ID
ENV GOOGLE_CLIENT_SECRET=$GOOGLE_CLIENT_SECRET
RUN pnpm build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV HOSTNAME=0.0.0.0
ENV PORT=8888
RUN corepack enable
COPY --from=builder /app ./
EXPOSE 8888
CMD ["pnpm", "start", "--", "-p", "8888"]
