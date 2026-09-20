# Kampala Community Health Clinic Management System

This project contains a full-stack healthcare patient management system with:

- React + Vite frontend
- Django + Python backend
- role-based access for patients, doctors, receptionists, and clinic managers
- appointments, patient records, staff handoff, and billing foundations

## Project structure

- `frontend/` - React frontend
- `backend/` - Django backend API

## Quick start

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Features

- AI-assisted patient intake and triage (kept isolated until clinical workflows are approved)
- patient chat interface
- appointment booking flow
- doctor/reception escalation workflow
- invoice and billing workflow
- secure Django API layer
- modular architecture for future healthcare features

## Notes

This MVP provides the working foundation for a patient management system and AI first-contact workflow.
