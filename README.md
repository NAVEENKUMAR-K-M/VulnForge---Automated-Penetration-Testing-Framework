# VulnForge 🛡️

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![React](https://img.shields.io/badge/react-18-blue.svg)
![FastAPI](https://img.shields.io/badge/fastapi-0.109+-green.svg)

VulnForge is a next-generation Automated Penetration Testing and Reconnaissance framework. It seamlessly orchestrates industry-standard security tools (Nmap, Nuclei, Gowitness) into a unified, asynchronous pipeline, delivering a beautiful React Dashboard for vulnerability management, automated PDF reporting, and real-time asset tracking.

---

## 🚀 Key Features

- **Automated Reconnaissance Engine**: Dynamically orchestrates tools like Nmap, Nuclei, FFUF, and WhatWeb.
- **Intelligent Data Deduplication**: Merges structured JSONB metadata from multiple tools natively in PostgreSQL.
- **Sleek React Dashboard**: A bleeding-edge UI powered by Tailwind CSS v4 and glassmorphism design.
- **Multi-Format Reporting Engine**: Instantly generate professional HTML, Markdown, PDF, and JSON executive summaries.
- **Role-Based Access Control**: Secure, isolated multi-tenant Workspaces managed by JWT authentication.

---

## 📸 Screenshots

![VulnForge Dashboard](/absolute/path/to/Dashboard.png)
*(Note: Replace with actual screenshots when hosting on GitHub)*

---

## ⚡ Quickstart

Get VulnForge running in under a minute using Docker!

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/VulnForge.git
cd VulnForge

# 2. Configure environment variables
cp .env.example .env

# 3. Launch the development stack
docker-compose up --build
```
Navigate to **http://localhost:5173** to access the Dashboard!

---

## 📚 Project Documentation

We have comprehensive documentation available in the `docs/` directory:

- 📖 **[Installation Guide](docs/INSTALLATION.md)** - Bare metal and Docker setups.
- 🏗️ **[Architecture Overview](docs/ARCHITECTURE.md)** - System design, DB schemas, and Plugin Engine.
- 🔌 **[API Documentation](docs/API.md)** - JWT Auth, Swagger UI, and Endpoints.
- 🛠️ **[Developer & Contribution Guide](docs/DEVELOPMENT.md)** - How to build custom Recon Plugins.
- 🚀 **[Deployment & Troubleshooting](docs/DEPLOYMENT.md)** - Securing production Nginx deployments.

---

## 🤝 Contributing
Please read our [Developer Guide](docs/DEVELOPMENT.md) before submitting Pull Requests. We welcome all contributions—whether it's writing a new Plugin, fixing UI bugs, or expanding the documentation!

## 📜 License
This project is licensed under the MIT License - see the LICENSE file for details.
