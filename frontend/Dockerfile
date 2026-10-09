FROM node:22-alpine AS base
RUN corepack enable pnpm

FROM base AS deps
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --prefer-frozen-lockfile

FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# No NEXT_PUBLIC_* build arg on purpose: nothing in src/ reads one any more, and
# baking the domain in is what would force a rebuild per Customer (ADR 010, ADR 045).
ENV API_URL=http://backend:8000
# pnpm re-checks node_modules against package.json before `run`, and wants to
# rebuild the dir when they drift (they do, since @playwright/test landed). Without
# a TTY it refuses and the whole image build dies — CI=true is what it asks for.
ENV CI=true
RUN pnpm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static
COPY --from=builder --chown=node:node /app/public ./public
USER node
EXPOSE 3000
CMD ["node", "server.js"]
