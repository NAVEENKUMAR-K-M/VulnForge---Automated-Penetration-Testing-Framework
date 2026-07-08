# Deployment & Troubleshooting Guide

This guide covers deploying VulnForge to a production environment securely and resolving common infrastructure issues.

## 1. Production Deployment

We strongly recommend using the provided `docker-compose.prod.yml` configuration for production. This architecture utilizes a multi-stage Docker build to discard development dependencies and serve the frontend via an ultra-fast Nginx container.

### Step-by-Step Deployment
1. **Clone the Codebase** on your production server.
2. **Configure `.env`**:
   - `SECRET_KEY`: Must be a long, randomly generated string. Do not use the default!
   - `POSTGRES_PASSWORD`: Change this to a secure password.
   - `ALLOWED_ORIGINS`: Set this to `["https://your-production-domain.com"]` to secure the backend against Cross-Origin Resource Sharing (CORS) attacks.
3. **Build and Launch**:
   ```bash
   docker-compose -f docker-compose.prod.yml up --build -d
   ```
4. **SSL/TLS**: The Nginx container exposes port `80`. We recommend placing VulnForge behind a secondary reverse proxy (like Cloudflare, AWS ALB, or an external Traefik/Nginx instance) to terminate HTTPS connections and manage SSL certificates.

## 2. Security Best Practices
- **Network Isolation**: Notice that in `docker-compose.prod.yml`, the `db`, `redis`, and `api` services do not expose ports to the host machine. They are isolated on an internal bridge network. Do not map `5432` to the host in production!
- **Default Passwords**: Never deploy with the default PostgreSQL or Redis passwords found in the `.env.example`.

---

## 3. Troubleshooting

### Issue: "Missing wkhtmltopdf" or Report Generation Fails
**Symptom**: Clicking "Generate PDF" throws a 500 error or the report service crashes.
**Fix**: Ensure `wkhtmltopdf` is installed natively inside the container or on your host OS. The multi-stage `backend/Dockerfile` handles this automatically, but if you are running Bare Metal on Windows/macOS, you must install the binary manually.

### Issue: CORS Errors on Login
**Symptom**: The browser console shows `Access-Control-Allow-Origin` errors.
**Fix**: Check your backend `.env` file. The `ALLOWED_ORIGINS` JSON array must exactly match the protocol and domain you are using to access the frontend (e.g., `["http://localhost", "https://vulnforge.mydomain.com"]`).

### Issue: PostgreSQL Connection Refused in Docker
**Symptom**: The backend container crashes in an endless restart loop with `ConnectionRefusedError: [Errno 111]`.
**Fix**: Sometimes the backend boots faster than PostgreSQL initializes its data volume. `docker-compose` handles this with `depends_on`, but if it persists, restart the backend container manually: `docker-compose restart api`.

### Issue: Frontend Changes Not Showing
**Symptom**: You edited a React file, but the browser doesn't update.
**Fix**: If you are using the Production Dockerfile, changes require a complete container rebuild because the code is statically compiled and baked into the image. Run `docker-compose -f docker-compose.prod.yml build` again. For instant hot-reloading, use the Development compose file instead!
