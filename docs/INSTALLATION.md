# Installation Guide

Welcome to VulnForge! This guide covers how to set up the platform on your local machine using Docker (Recommended) or Bare Metal (for Developers).

## Prerequisites

Regardless of your installation method, you must have the following installed:
- [Git](https://git-scm.com/)

If using **Docker** (Recommended):
- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

If using **Bare Metal**:
- Python 3.11+
- Node.js 20+
- PostgreSQL 15+
- Redis 7+
- `wkhtmltopdf` (Required for PDF report generation)
- `nmap` (Required for Port Scanning plugins)

---

## Method 1: Docker Compose (Recommended)

This is the fastest way to get VulnForge up and running.

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/VulnForge.git
cd VulnForge
```

### 2. Configure Environment Variables
Copy the example environment file and customize it if needed (especially `SECRET_KEY` and `POSTGRES_PASSWORD`).
```bash
cp .env.example .env
```

### 3. Launch the Stack
For **Development** (hot-reloading enabled, ports exposed to localhost):
```bash
docker-compose up --build
```

For **Production** (Nginx proxy, isolated networks, static frontend):
```bash
docker-compose -f docker-compose.prod.yml up --build -d
```

### 4. Access the Application
Once the containers are running, navigate to:
- **Frontend**: http://localhost (or http://localhost:5173 for Dev)
- **API Docs (Swagger)**: http://localhost:8000/docs
- **Default Login**: You will need to create the first user by clicking "Sign Up" on the login screen.

---

## Method 2: Bare Metal (Developer Setup)

If you are contributing to the core logic, you may want to run the services natively.

### 1. Database Setup
Ensure PostgreSQL and Redis are running locally. Create a database named `vulnforge` and a user `vulnforge_user`. Update your `.env` file to point to `localhost`.

### 2. Backend Setup
Navigate to the backend directory and install the Python dependencies.
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```
Install OS-level binaries:
- Ubuntu/Debian: `sudo apt install nmap wkhtmltopdf`
- macOS: `brew install nmap wkhtmltopdf`

Start the FastAPI server:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend Setup
Open a new terminal, navigate to the frontend directory, and install dependencies.
```bash
cd frontend
npm install
```
Start the Vite development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:5173`.
