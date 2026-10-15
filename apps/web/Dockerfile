# ArchitectureScope web app (Next.js) — the container Cloud Run runs.
#
#   gcloud run deploy archscope-web --source apps/web ...
#
# The API's address is read at build time from apps/web/.env.production
# (API_URL=https://archscope-api-….run.app) — create it first; see the
# deployment guide. Hosts that pass environment variables as build
# arguments (Render) can set API_URL there instead; it wins over the file.

FROM node:24-alpine AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
ARG API_URL=""
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN if [ -n "$API_URL" ]; then printf 'API_URL=%s\n' "$API_URL" > .env.production; fi
RUN test -f .env.production && grep -q '^API_URL=https://' .env.production \
    || (echo "Missing API_URL=https://... (the API's public address): set the API_URL build argument or create apps/web/.env.production. See the deployment guide." && exit 1)
# An empty build argument would otherwise hide the value in .env.production.
RUN if [ -z "$API_URL" ]; then unset API_URL; fi && npm run build

FROM node:24-alpine
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=8080 \
    HOSTNAME=0.0.0.0
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
EXPOSE 8080
CMD ["node", "server.js"]
