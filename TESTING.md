# TESTING AND DEMO SCRIPT

This file provides an exact demo flow for diploma defense.

## 1. Environment Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Configure .env:
- APP_ADMIN_USERS=admin,rapoz
- OPENAI_API_KEY can stay empty for MVP demo

3. Run app:

```bash
streamlit run app.py
```

4. Run automated checks:

```bash
run_smoke_test.bat
python -m pytest -q
```

## 2. Demo Accounts

Create accounts through UI registration before defense, for example:
- Citizen: citizen_demo / Demo123
- Officer: admin / Demo123

Important:
- Officer username must be listed in APP_ADMIN_USERS.
- Password policy in UI: minimum 6 characters.

## 3. Citizen Flow (Semi-digital)

1. Login as citizen_demo.
2. Open Dashboard and explain service split:
- Semi-digital MUP services
- Fully digital tourism services
3. Go to Podnesi zahtjev.
4. Choose MUP (polu-digitalno) and service Pasoš.
5. Show required documents, fee, and physical-presence note.
6. Upload one or two sample files and submit.
7. Go to Moji zahtjevi and verify:
- Status is Podnesen
- Request is visible
- Citizen can add comment to officer
- Audit trail exists

## 4. Citizen Flow (Fully digital tourism)

1. Still as citizen_demo, open Podnesi zahtjev.
2. Choose Turizam (potpuno digitalno) and Registracija nekretnine.
3. Fill property fields:
- Naziv objekta
- Adresa
- Opština
- Kapacitet
- Broj soba
4. Upload documents and submit.
5. Explain that full process is designed online (no physical arrival in core flow).

## 5. Officer/Admin Flow

1. Logout and login as admin.
2. Open Admin/Officer panel.
3. Dashboard tab:
- Show totals and active queue overview.
4. Aktivni zahtjevi tab:
- Open one request
- Add comment visible to user
- Change status to U obradi
- Change status to Čeka korisnika with message
5. Arhiva tab:
- After final statuses, show completed/rejected entries.

## 6. End-to-End Status Transition Demo

Recommended path for one request:
- draft -> submitted (automatic on citizen submit)
- submitted -> under_review (officer)
- under_review -> pending_user (officer asks for correction)
- pending_user -> submitted (citizen resubmits via new action/comment)
- submitted -> under_review -> approved -> completed

## 7. What to Verify Before Defense

- App starts with no errors.
- Registration/login works.
- Citizen cannot access officer panel.
- Officer panel is visible only to configured usernames.
- Document uploads persist under documents/<request_id>/.
- Comments are exchanged between citizen and officer.
- Audit trail is visible in citizen request details.
- Semi-digital requests show physical-presence warning.
- Tourism requests show fully-digital path message.

## 8. Known MVP Limits

- No real e-signature integration.
- No external payment gateway integration.
- Officer role is username-based from APP_ADMIN_USERS.
- Legacy helper modules remain in repo but are out of main UX flow.

## 9. Automated Validation Suite

- `run_smoke_test.bat`
	- End-to-end smoke of auth + municipality validation + DMS submit flow + audit log.
	- Cleans up generated smoke data automatically.

- `python -m pytest -q`
	- Regression checks for auth/session helpers and workflow authorization guards.
