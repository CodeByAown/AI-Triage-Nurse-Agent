# Neural Hub AI Triage Nurse - Developer's Local Run Guide

Welcome! This guide explains how to set up, launch, and troubleshoot the **Neural Hub AI Triage Nurse** system on your local Windows machine. 

This guide is designed for developers of all experience levels, including those with minimal DevOps background.

---

## 1. Prerequisites

Before starting, ensure you have the following installed on your system:

- **Python**: Version 3.12 or 3.13 (recommended). Download from [python.org](https://www.python.org/downloads/).
- **Node.js**: Version 20 or higher. Download from [nodejs.org](https://nodejs.org/).
- **Git**: Installed and available in your command line.

---

## 2. Setting Up the Environment

Open your terminal (e.g., PowerShell or Command Prompt) and navigate to the project directory:

```powershell
cd "C:\Ai Agents\AI Triage Nurse Agent"
```

### A. Backend Setup
1. Move to the `backend/` directory:
   ```powershell
   cd backend
   ```
2. Create a virtual environment to isolate the project's dependencies:
   ```powershell
   python -m venv venv
   ```
3. Activate the virtual environment:
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```
   *(If you get a script execution policy error, run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process` first, then run the activation script.)*
4. Install all python packages:
   ```powershell
   pip install -r requirements.txt
   ```
5. Return to the root folder:
   ```powershell
   cd ..
   ```

### B. Frontend Setup
1. Move to the `frontend/` directory:
   ```powershell
   cd frontend
   ```
2. Install the Next.js dependencies:
   ```powershell
   npm install
   ```
3. Return to the root folder:
   ```powershell
   cd ..
   ```

---

## 3. Environment Variables Configuration

The project utilizes environment configuration files at the root level and inside the frontend subdirectory.

### Backend Configurations (Root `.env` File)
The main configuration file is located at the root of the project: `C:\Ai Agents\AI Triage Nurse Agent\.env`. 
Ensure the following variables are set:
- `OPENAI_API_KEY`: Paste your OpenAI API key here (`sk-proj-...`). This is required for Maya to chat.
- `DATABASE_URL`: Set by default to the Supabase connection string.
- `DATABASE_URL_SYNC`: Set by default to the sync Supabase connection string for migrations.
- `SECRET_KEY`: Set to a secure, random string (already generated).

### Frontend Configurations (`frontend/.env.local`)
Create a new file named `.env.local` inside the `frontend/` directory if it does not already exist, and add:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME="Neural Hub"
NEXT_PUBLIC_APP_URL=http://localhost:3000
```
*(If missing, the frontend defaults to `http://localhost:8000` for the backend connection, which is appropriate for local runs).*

---

## 4. Database Setup & Migrations

The database is hosted on Supabase (PostgreSQL) and has been configured for you. Since the database structures are managed by **Alembic**, you should run migrations to ensure your local schema is up to date:

1. Navigate to the `backend/` folder and activate the virtual environment if you haven't already.
2. Run the Alembic migration command:
   ```powershell
   alembic upgrade head
   ```
   *Expected Output:* If the schema is already current, this command will complete immediately with no output. If there are new migrations, they will print out step-by-step.

---

## 5. Startup Commands

To run the application, you need to open **two separate terminal windows**:

### Terminal 1: Backend API
1. Navigate to the backend folder:
   ```powershell
   cd "C:\Ai Agents\AI Triage Nurse Agent\backend"
   ```
2. Activate the virtual environment:
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```
3. Start the FastAPI server using Uvicorn:
   ```powershell
   uvicorn app.main:app --reload --port 8000
   ```
   *Expected Output:*
   ```text
   INFO:     Started server process [PID]
   INFO:     Waiting for application startup.
   INFO:     Application startup complete.
   INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
   ```

### Terminal 2: Frontend App
1. Open a new terminal window.
2. Navigate to the frontend folder:
   ```powershell
   cd "C:\Ai Agents\AI Triage Nurse Agent\frontend"
   ```
3. Start the Next.js development server:
   ```powershell
   npm run dev
   ```
   *Expected Output:*
   ```text
   ▲ Next.js 15.1.3
   - Local:        http://localhost:3000
   ```

---

## 6. Accessing the Application

Open your browser and navigate to:
- **Main App**: [http://localhost:3000](http://localhost:3000)
- **API Swagger Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **API Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

## 7. Troubleshooting & Orphaned Processes

### A. How to Kill Stuck Background Processes (Orphaned Servers)
If you close VS Code or your terminal window, the application servers (Node.js and Uvicorn/Python) can sometimes keep running in the background. If you try to restart them, you will see a `Port already in use` error.

To solve this, run this command in **PowerShell** to force-terminate any processes holding ports `3000` or `8000`:

```powershell
Get-NetTCPConnection -LocalPort 3000, 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force }
```

### B. Common Errors & Fixes

#### 1. "Port 8000 is already in use" or "Port 3000 is already in use"
- **Cause**: An old server process was left running in the background.
- **Fix**: Run the PowerShell kill script listed in **Section A** above.

#### 2. "Pydantic ValidationError" on startup
- **Cause**: The backend was started from the wrong folder or is missing the `.env` configuration file.
- **Fix**: Ensure you run `uvicorn` from within the `backend/` directory, and that `C:\Ai Agents\AI Triage Nurse Agent\.env` is filled out correctly.

#### 3. OpenAI API key errors or Maya won't respond
- **Cause**: Your `OPENAI_API_KEY` is invalid, expired, or missing from `.env`.
- **Fix**: Check the console log of the backend (Terminal 1) for error messages. Double-check that `OPENAI_API_KEY` is set inside `.env` at the root folder.
