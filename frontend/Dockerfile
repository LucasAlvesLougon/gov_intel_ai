FROM node:24.17.0-alpine@sha256:156b55f92e98ccd5ef49578a8cea0df4679826564bad1c9d4ef04462b9f0ded6
ENV NEXT_TELEMETRY_DISABLED=1
ARG NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
WORKDIR /app
COPY package.json package-lock.json .npmrc ./
RUN npm ci --ignore-scripts
COPY . .
RUN test -n "$NEXT_PUBLIC_API_BASE_URL" && npm run build \
    && mkdir -p /app/node_modules/.vite \
    && chown node:node /app /app/next-env.d.ts \
    && chown -R node:node /app/.next /app/node_modules/.vite
USER node
EXPOSE 3000
CMD ["npm", "start"]
