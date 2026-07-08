# API Documentation

VulnForge features a fully documented RESTful API built on FastAPI. The entire specification is automatically generated according to the OpenAPI 3 standard.

## 1. Interactive Documentation (Swagger UI)

When the backend server is running, you can access the live, interactive API documentation directly in your browser:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

These interfaces allow you to execute API requests directly from your browser, making it incredibly easy to test endpoints without writing scripts.

## 2. OpenAPI Specification (`openapi.json`)

The raw JSON specification is available at `backend/openapi.json`. You can import this file into tools like:
- **Postman**
- **Insomnia**
- Frontend SDK generators (e.g., `openapi-typescript-codegen`)

## 3. Authentication

The VulnForge API is secured using JWT (JSON Web Tokens). Most endpoints require an `Authorization` header.

### Generating a Token
To obtain an access token, send a POST request with your credentials:
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email": "your_email@example.com", "password": "your_password"}'
```
*Response:*
```json
{
  "access_token": "eyJhbGciOiJIUz...",
  "refresh_token": "eyJhbGciOiJIUz...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Accessing Protected Endpoints
Use the returned `access_token` in the `Authorization` header:
```bash
curl -X GET http://localhost:8000/api/v1/workspaces \
     -H "Authorization: Bearer eyJhbGciOiJIUz..."
```

## 4. Error Handling
The API follows standard HTTP status codes:
- **200/201**: Success / Created
- **400**: Bad Request (Invalid parameters)
- **401**: Unauthorized (Missing or expired JWT)
- **403**: Forbidden (Insufficient Workspace permissions - e.g., only Owners can delete)
- **404**: Not Found
- **422**: Unprocessable Entity (Pydantic validation failure)
- **500**: Internal Server Error

Detailed JSON error messages are returned in the response body.
