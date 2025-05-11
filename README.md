# NovaGuard AI

## Cấu trúc Thư mục và Database Schema

```
novaguard-ai/
├── novaguard-ui/                     # Frontend React App
│   ├── public/
│   ├── src/
│   │   ├── assets/
│   │   ├── components/               # UI Components (Buttons, Inputs, Cards, etc.)
│   │   │   ├── auth/
│   │   │   ├── project/
│   │   │   └── pr/
│   │   ├── constants/                # Constants, Enums
│   │   ├── contexts/                 # React Contexts (e.g., AuthContext)
│   │   ├── features/                 # Feature-specific modules/slices (Redux/Zustand)
│   │   │   ├── auth/
│   │   │   ├── projects/
│   │   │   └── pullRequests/
│   │   ├── hooks/                    # Custom React Hooks
│   │   ├── layouts/                  # Layout components (e.g., MainLayout, AuthLayout)
│   │   ├── pages/                    # Page components
│   │   │   ├── AuthPage.tsx
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── ProjectDetailPage.tsx
│   │   │   ├── PRReviewPage.tsx
│   │   │   ├── AddProjectPage.tsx
│   │   │   └── ProjectSettingsPage.tsx
│   │   ├── services/                 # API service calls (e.g., authService.ts, projectService.ts)
│   │   ├── store/                    # State management (Redux, Zustand)
│   │   ├── types/                    # TypeScript type definitions
│   │   ├── utils/                    # Utility functions
│   │   ├── App.tsx
│   │   ├── index.tsx
│   │   └── vite-env.d.ts             # Or react-app-env.d.ts for CRA
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts                # Or other bundler config
│
├── novaguard-backend/                # Backend Services (Monorepo or separate repos)
│   ├── services/
│   │   ├── auth_service/
│   │   │   ├── app/
│   │   │   │   ├── api/              # API Endpoints/Routers
│   │   │   │   │   └── v1/
│   │   │   │   │       └── auth_routes.py
│   │   │   │   ├── core/             # Core logic, config
│   │   │   │   │   └── config.py
│   │   │   │   ├── crud/             # CRUD operations for database
│   │   │   │   │   └── crud_user.py
│   │   │   │   ├── db/               # Database session, base model
│   │   │   │   │   ├── base.py
│   │   │   │   │   └── session.py
│   │   │   │   ├── models/           # SQLAlchemy models
│   │   │   │   │   └── user_model.py
│   │   │   │   ├── schemas/          # Pydantic schemas
│   │   │   │   │   └── user_schema.py
│   │   │   │   ├── services/         # Business logic services (e.g., github_oauth_service.py)
│   │   │   │   └── main.py           # FastAPI app instance
│   │   │   ├── tests/
│   │   │   ├── Dockerfile
│   │   │   └── requirements.txt
│   │   │
│   │   ├── project_service/
│   │   │   ├── app/
│   │   │   │   ├── api/
│   │   │   │   │   └── v1/
│   │   │   │   │       └── project_routes.py
│   │   │   │   ├── core/
│   │   │   │   │   └── config.py
│   │   │   │   ├── crud/
│   │   │   │   │   └── crud_project.py
│   │   │   │   ├── db/
│   │   │   │   ├── models/
│   │   │   │   │   └── project_model.py
│   │   │   │   ├── schemas/
│   │   │   │   │   └── project_schema.py
│   │   │   │   ├── services/         # e.g., github_integration_service.py
│   │   │   │   └── main.py
│   │   │   ├── tests/
│   │   │   ├── Dockerfile
│   │   │   └── requirements.txt
│   │   │
│   │   ├── webhook_service/
│   │   │   ├── app/
│   │   │   │   ├── api/
│   │   │   │   │   └── v1/
│   │   │   │   │       └── webhook_routes.py
│   │   │   │   ├── core/
│   │   │   │   │   └── config.py
│   │   │   │   ├── schemas/          # Pydantic schemas for webhook payloads
│   │   │   │   ├── services/         # e.g., task_publisher_service.py (to Kafka/RabbitMQ)
│   │   │   │   └── main.py
│   │   │   ├── tests/
│   │   │   ├── Dockerfile
│   │   │   └── requirements.txt
│   │   │
│   │   └── analysis_worker/          # This is a worker, not a web service
│   │       ├── app/
│   │       │   ├── core/
│   │       │   │   └── config.py
│   │       │   ├── db/               # For saving analysis results
│   │       │   ├── models/           # PRAnalysisRequest, AnalysisFinding
│   │       │   ├── crud/
│   │       │   ├── analysis_orchestrator/ # Logic for orchestrating analysis steps
│   │       │   │   ├── context_builder.py # Create/Enrich DynamicProjectContext
│   │       │   │   ├── agents/            # Simplified agents for MVP1
│   │       │   │   │   └── deep_logic_bug_hunter_mvp1.py
│   │       │   │   └── orchestrator.py
│   │       │   ├── llm_wrapper/
│   │       │   │   └── ollama_client.py
│   │       │   ├── services/         # e.g., github_data_fetcher.py
│   │       │   └── worker.py         # Main worker logic (consumes from queue)
│   │       ├── tests/
│   │       ├── Dockerfile
│   │       └── requirements.txt
│   │
│   ├── common/                       # Shared Python code (e.g., Pydantic models, DB base, utils)
│   │   ├── db_base/
│   │   ├── models_shared/
│   │   └── schemas_shared/
│   │
│   └── requirements.txt              # Common requirements or manage via individual services
│
├── docs/
│   ├── api/                          # OpenAPI specs
│   │   └── openapi.yaml
│   ├── architecture.md
│   └── setup_guide.md
│
├── scripts/                          # Helper scripts (e.g., DB migration, initial setup)
│   └── initial_db_setup.sql
│
├── .env.example                      # Example environment variables
├── docker-compose.yml
└── README.md
```