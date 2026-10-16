# 🔮 Palmistry & Tarot Intelligence Platform

An AI-powered platform that combines palmistry and tarot-based insights to provide personalized spiritual guidance.

## 📌 Project Overview

The **Palmistry & Tarot Intelligence Platform** integrates a web-based interface with a FastAPI backend and database services. It provides a foundation for palm analysis, tarot readings, user management, consultation workflows, and personalized guidance.

The project includes a Dockerized backend and multiple frontend pages for interacting with the platform.

## ✨ Key Features

- **Palmistry Analysis** — Backend endpoints and services for palm image analysis and interpretation.
- **Tarot Readings** — Tarot reading workflows supported by a tarot card catalog.
- **Personalized Guidance** — Services for synthesizing insights and generating recommendations.
- **User Authentication** — Authentication and user management endpoints.
- **Consultation Management** — Consultation hub, notes, and spiritual consultant workflows.
- **Reader Dashboard and Reports** — Frontend pages for tarot readers, dashboards, and reports.
- **REST API** — FastAPI endpoints with interactive Swagger documentation.
- **Containerized Backend** — Docker and Docker Compose configuration for the backend and supporting services.

## 🛠️ Tech Stack

| Component | Technologies |
|---|---|
| Backend | Python, FastAPI, Uvicorn |
| API validation | Pydantic |
| Relational database | PostgreSQL |
| Document database | MongoDB |
| Cache / data store | Redis |
| ORM | SQLAlchemy |
| Image processing | OpenCV, MediaPipe, Pillow |
| Frontend | HTML, CSS, JavaScript |
| Containerization | Docker, Docker Compose |
| Testing | Pytest |

## 📂 Project Structure

```text
palmistry-tarot-platform/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       └── endpoints/
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── main.py
│   ├── datasets/
│   │   └── metadata/
│   │       └── tarot_catalog.json
│   ├── tests/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .gitignore
├── frontend/
│   ├── assets/
│   ├── public/
│   │   └── images/
│   │       └── active_deck/
│   ├── index.html
│   ├── dashboard.html
│   ├── admin.html
│   ├── consultant.html
│   ├── consultation_hub.html
│   ├── history.html
│   ├── tarot.html
│   ├── tarot_reader.html
│   ├── tarot_reader_reports.html
│   └── report.html
├── .env.example
├── .gitignore
├── docker-compose.yml
└── README.md
```

## ⚙️ Prerequisites

Install the following before running the project:

- [Git](https://git-scm.com/)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- A modern web browser

Docker Desktop should be running before starting the containers.

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/springboardmentor1210a/Spiritual-Guidance-Intelligence-Platform.git
cd Spiritual-Guidance-Intelligence-Platform
git checkout Jyotiprakash
```

Alternatively, clone your personal fork and check out the `Jyotiprakash` branch.

### 2. Configure environment variables

Create a root `.env` file using `.env.example` as a reference.

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Open `.env` and configure the required values for your local environment. Use valid database credentials and a secure secret key.

**Security:** Never commit `.env`, API keys, database passwords, or other secrets to GitHub. Keep `.env.example` limited to placeholder values.

### 3. Build and start the services

From the project root, run:

```bash
docker compose up -d --build
```

This builds the backend image and starts the services defined in `docker-compose.yml`.

### 4. Verify the containers

```bash
docker compose ps
```

Check backend logs if necessary:

```bash
docker compose logs --tail=100 backend
```

To stop the services:

```bash
docker compose down
```

This stops the containers without removing named database volumes.

## 🔗 API Endpoints

When the backend is running locally on port `8000`, use the following URLs:

| Resource | URL |
|---|---|
| Health check | http://localhost:8000/health |
| API root | http://localhost:8000/ |
| Swagger UI | http://localhost:8000/docs |
| OpenAPI schema | http://localhost:8000/openapi.json |

The health endpoint can be tested with:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

A successful health check should return an operational status.

Use Swagger UI to inspect the available endpoints and test API requests.

## 🗄️ Database Services

The Docker Compose configuration includes the following services:

| Service | Default local port |
|---|---:|
| FastAPI backend | 8000 |
| PostgreSQL | 5432 |
| MongoDB | 27017 |
| Redis | 6379 |

Configure connection strings and credentials through the environment variables expected by the application and Compose configuration.

Do not expose database ports or development credentials publicly in a production deployment.

## 🖥️ Frontend

The frontend consists of HTML pages and associated assets, including tarot card images and a hand diagram.

The available pages include:

- Main interface
- Dashboard
- Palmistry and tarot-related pages
- Tarot reader dashboard and reports
- Consultation hub
- Consultant interface
- Administration interface
- Reading history and report pages

The frontend is maintained separately from the Dockerized backend. Configure the frontend's API URLs to point to the running backend when testing the integration.

## 🧪 Testing

The backend contains a `tests/` directory with Pytest test modules.

To run the test suite, use an environment with the backend dependencies installed:

```bash
cd backend
python -m pip install -r requirements.txt
python -m pytest
```

Tests that require databases, authentication configuration, or other services may need the corresponding environment variables and services configured first.

## 🔒 Security Notes

- Keep `.env` files out of version control.
- Use strong, unique secrets and passwords.
- Avoid exposing database services to untrusted networks.
- Validate and authenticate requests to protected API endpoints.
- Review environment configuration before deploying outside a local development environment.

## 🛣️ Future Improvements

Potential areas for further development include:

- Expanding automated API and integration tests.
- Improving frontend-backend integration.
- Adding comprehensive setup and API usage examples.
- Strengthening deployment configuration and monitoring.
- Improving documentation for palmistry and tarot analysis workflows.

## 👨‍💻 Development

This project is maintained in the `Jyotiprakash` branch of the Spiritual Guidance Intelligence Platform repository.

Contributions and suggestions are welcome through the repository's agreed development workflow.

## ⚠️ Disclaimer

Palmistry and tarot interpretations are intended for entertainment, reflection, and personal guidance. They should not be treated as scientifically validated predictions or as substitutes for professional medical, financial, legal, or mental health advice.
