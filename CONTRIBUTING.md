# Contributing to Fantasy Points System

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to this project.

---

## Table of Contents

- [Development Setup](#development-setup)
- [Branching Strategy](#branching-strategy)
- [Code Style](#code-style)
- [Commit Messages](#commit-messages)
- [Pull Request Process](#pull-request-process)
- [Architecture Overview](#architecture-overview)

---

## Development Setup

### 1. Fork and clone

```bash
git clone https://github.com/<your-fork>/fantasy-points-system.git
cd fantasy-points-system
```

### 2. Create a virtual environment

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r backend/requirements.txt
```

### 3. Install frontend dependencies

```bash
cd frontend && npm install && cd ..
```

### 4. Set up credentials

Place your Google service account JSON at `credentials/google_service_account.json`. This file is gitignored and must never be committed.

### 5. Start development servers

```bash
# Terminal 1 — Backend
uvicorn backend.main:app --host 127.0.0.1 --port 8080 --reload

# Terminal 2 — Frontend
cd frontend && npm run dev
```

---

## Branching Strategy

We follow **GitHub Flow**:

| Branch          | Purpose                                        |
| --------------- | ---------------------------------------------- |
| `main`          | Production-ready code. Protected branch.       |
| `feature/*`     | New features (e.g. `feature/add-odi-scoring`)  |
| `fix/*`         | Bug fixes (e.g. `fix/name-resolution-edge`)    |
| `docs/*`        | Documentation changes                          |
| `refactor/*`    | Code restructuring without behavior change     |

1. Create a branch from `main`
2. Make your changes with clear, focused commits
3. Open a Pull Request against `main`
4. Address review feedback
5. Squash-merge when approved

---

## Code Style

### Python (Backend)

- **Formatter**: Follow PEP 8. Use `black` for formatting, `ruff` for linting.
- **Type hints**: Use type annotations on all public functions.
- **Imports**: Standard library → third-party → local. Use absolute imports (`from backend.logger import get_logger`).
- **Logging**: Always use `from backend.logger import get_logger; logger = get_logger(__name__)`. Never use `print()` for debugging.
- **Docstrings**: Use triple-quoted docstrings for all public classes and functions.

### TypeScript (Frontend)

- **Formatter**: Follows project Prettier/ESLint config.
- **Types**: No `any` types. Define interfaces in `types/index.ts`.
- **Components**: Functional components with TypeScript props interfaces.

### General

- No hard-coded secrets or credentials in code.
- Configuration goes in `backend/config.py` or environment variables.
- Keep functions small and focused. Prefer composition over inheritance.

---

## Commit Messages

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>(<scope>): <short summary>

<optional body>
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `ci`

**Examples**:
```
feat(scraper): add support for ODI scorecards
fix(engine): correct duck penalty for bowlers
docs(readme): update installation instructions
ci(github): add Python lint workflow
```

---

## Pull Request Process

1. **Before opening a PR**:
   - Ensure the backend starts without errors
   - Ensure the frontend compiles without errors
   - Run `python test_api.py all` with a valid scorecard URL
   - Update documentation if you changed behavior

2. **PR title**: Use conventional commit format (e.g. `feat(scraper): add ODI support`)

3. **PR description**: Include:
   - What changed and why
   - How to test
   - Screenshots for UI changes

4. **Review**: At least one approval required before merge

5. **Merge**: Squash-merge to keep `main` history clean

---

## Architecture Overview

```
Request Flow:
  Frontend → API Routes → Match Service → Scraper / Engine / Sheet Service
                                              ↓             ↓
                                        ESPN Cricinfo   Google Sheets
```

**Key design principles**:
- **Wrappers**: All external dependencies (Selenium, BeautifulSoup, gspread) are wrapped. This makes testing and swapping implementations easy.
- **Pure functions**: The points calculator is stateless — given metadata, it produces points deterministically.
- **Orchestration**: `MatchService` ties everything together and persists intermediate JSON at each step for debuggability and replayability.
- **Human-in-the-loop**: The frontend forces explicit approval at each step, preventing accidental data corruption.

---

## Adding a New Scoring Format

1. Create a new calculator in `backend/engine/` (e.g. `odi_calculator.py`)
2. Add the new schemas to `backend/models/schemas.py`
3. Wire it into `MatchService` with a format parameter
4. Add corresponding UI step if needed
5. Update tests and documentation
