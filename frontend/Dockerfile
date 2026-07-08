# ==========================================
# Base Stage
# ==========================================
FROM node:20-alpine as base

WORKDIR /app

# Copy package management files
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm install

# ==========================================
# Development Stage
# ==========================================
FROM base as development

# Copy all project files (though volume mount typically overrides this)
COPY . .

# Expose Vite's default port
EXPOSE 5173

# Run Vite dev server bound to all network interfaces
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

# ==========================================
# Build Stage
# ==========================================
FROM base as builder

# Copy all source code
COPY . .

# Build the production static assets
# Ensure Vite knows it's production
ENV NODE_ENV=production
RUN npm run build

# ==========================================
# Production Stage
# ==========================================
FROM nginx:alpine as production

# Remove default Nginx HTML files
RUN rm -rf /usr/share/nginx/html/*

# Copy the statically built files from the builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy our custom Nginx configuration (handles React Router fallback and /api proxy)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80 for web traffic
EXPOSE 80

# Run Nginx in the foreground
CMD ["nginx", "-g", "daemon off;"]
