# --- Base Stage ---
# Use an official Node.js runtime as a parent image
FROM node:20-alpine AS base

# Set working directory
WORKDIR /app

# Copy package.json and package-lock.json
COPY package.json package-lock.json ./

# --- Dependencies Stage ---
FROM base AS deps
# Install dependencies
RUN npm ci

# --- Development Stage ---
FROM deps AS dev
# Copy the rest of the application code
COPY . .
# Expose port and start the development server
EXPOSE 3000
CMD ["npm", "run", "dev"]


# --- Production Build Stage ---
FROM deps AS builder
# Accept build arguments for Next.js environment variables
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_BASE_PATH
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_BASE_PATH=$NEXT_PUBLIC_BASE_PATH

# Accept build arguments for Keycloak configuration
ARG KEYCLOAK_SERVER_URL
ARG KEYCLOAK_REALM
ARG KEYCLOAK_CLIENT_ID
ARG KEYCLOAK_CLIENT_SECRET
ARG KEYCLOAK_AUDIENCE
ARG NEXTAUTH_SECRET
ARG NEXTAUTH_URL
ARG SUPERVITY_AUTH_DEBUG
ARG NEXT_PUBLIC_KEYCLOAK_URL

# Set environment variables for build time
ENV KEYCLOAK_SERVER_URL=$KEYCLOAK_SERVER_URL
ENV KEYCLOAK_REALM=$KEYCLOAK_REALM
ENV KEYCLOAK_CLIENT_ID=$KEYCLOAK_CLIENT_ID
ENV KEYCLOAK_CLIENT_SECRET=$KEYCLOAK_CLIENT_SECRET
ENV KEYCLOAK_AUDIENCE=$KEYCLOAK_AUDIENCE
ENV NEXTAUTH_SECRET=$NEXTAUTH_SECRET
ENV NEXTAUTH_URL=$NEXTAUTH_URL
ENV SUPERVITY_AUTH_DEBUG=$SUPERVITY_AUTH_DEBUG
ENV NEXT_PUBLIC_KEYCLOAK_URL=$NEXT_PUBLIC_KEYCLOAK_URL

# Copy the rest of the application code
COPY . .
# Build the Next.js app for production
RUN npm run build

# --- Production Stage ---
FROM base AS prod
# Copy the complete built application from builder
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package.json .
COPY --from=builder /app/package-lock.json .
COPY --from=builder /app/next.config.ts .
COPY --from=builder /app/node_modules ./node_modules

# Expose port and start the production server
EXPOSE 3000
CMD ["npm", "start"]
