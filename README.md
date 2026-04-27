# Digitalization of MUP Services Through a DMS

This project is a diploma MVP that demonstrates how Montenegro-style administrative services can be digitalized through a Document Management System (DMS).

The app is intentionally focused on credible public-service workflows, not extra showcase features.

## MVP Scope

### 1) Semi-digital services (MUP)
- Lična karta
- Pasoš
- Vozačka dozvola

Supported flow:
- User registration and login
- Required documents and fee information
- Online request submission with document uploads
- Request status tracking
- Officer-user comments
- Explicit note that physical presence is still required for biometrics or pickup

### 2) Fully digital services (Tourism)
- Tourism property registration
- Tourism license
- Adaptation permit

Supported flow:
- Full online submission
- Upload ownership/ID documents
- Property data capture
- Officer-user communication
- Digital approval/rejection without mandatory physical arrival in system flow

## Main Modules

- app.py
  - Streamlit entrypoint
  - Authentication shell
  - Navigation for citizen, officer, workflow and FAQ
- pages/dms_requests.py
  - Citizen flows: submit request and my requests
  - Semi-digital vs fully-digital UX split
  - Uploads, comments, audit timeline visibility
- pages/admin_panel.py
  - Officer/admin panel
  - Queue handling, comments, status transitions, archive
- dms_core/models.py
  - Core request and workflow entities
  - Document metadata, timestamps, status history, comments
- dms_core/manager.py
  - Request workflow engine
  - Transition validation, audit events, document persistence
- dms_core/init_dms.py
  - DMS schema/template bootstrap from JSON rules
- database/database.py
  - User/auth persistence and helper queries

## Security and Hygiene

- Secrets moved to environment variable usage.
- .env is ignored by git.
- .env.example defines required/optional variables.
- Exposed key has been removed from local config and replaced by placeholders.
- Uploaded files are ignored from git (documents/*, except .gitkeep).

## Removed / De-emphasized Features

- Word .docx download is removed from the main flow to keep the diploma narrative focused on DMS process quality.
- Legacy mixed chatbot/search/map sections are not part of the MVP navigation.

## Run Instructions

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Configure environment variables:
- Copy .env.example to .env
- Set APP_ADMIN_USERS (comma-separated usernames for officer/admin access)
- OPENAI_API_KEY is optional and only needed for external AI integrations

3. Start app:

```bash
streamlit run app.py
```

4. Open browser:
- http://localhost:8501

This repository now runs as a Streamlit MVP only.

## Data and Bootstrapping

On startup the app automatically:
- Initializes user/auth database tables
- Creates DMS schema in instance/dms.db
- Loads service templates from:
  - database/mup_rules.json
  - requirements_data/turizam_requirements.json

## Current MVP Capabilities Checklist

- Login/registration
- Citizen dashboard
- Submit request
- My requests
- Officer/admin panel
- Controlled status transitions
- Officer-user comments
- Request audit trail visibility
- Municipality validation in key submission paths
- FAQ/help assistant from DMS templates

## Notes

This repository still contains legacy files from earlier iterations (analytics, chatbot variants, Word generator). They are intentionally outside the main MVP user flow.

The Help/FAQ section now works as a hybrid AI chatbot: it uses OpenAI when `OPENAI_API_KEY` is configured, and otherwise falls back to the local DMS FAQ engine.
