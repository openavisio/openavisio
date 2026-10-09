# Breach response runbook

Procedures for responding to a personal data breach under GDPR Articles 33 and 34. Health data breaches are high-risk by default — follow all steps.

---

## What counts as a breach

A personal data breach is any accidental or unlawful destruction, loss, alteration, unauthorised disclosure of, or access to personal data. Examples:

- Unauthorised access to the database or storage files
- Patient data visible to a user who should not have access
- Accidental deletion of patient records
- Loss or theft of a server containing patient data
- Exposure of `app_secret` or `DOCUMENT_ENCRYPTION_KEY`
- A software bug that leaks one patient's data to another user's session

---

## Step 1 — Contain

As soon as a breach is suspected, limit further exposure.

```bash
# Take the backend offline if actively exploited
ssh root@YOUR_SERVER_IP
cd /opt/openavisio && docker compose stop backend celery-worker celery-beat frontend
```

If the breach involves compromised credentials:
```bash
# Rotate APP_SECRET (invalidates all sessions)
# Rotate DOCUMENT_ENCRYPTION_KEY (run rotate_deks first — see docs/security.md)
nano /opt/openavisio/.env
cd /opt/openavisio && docker compose up -d --build backend celery-worker celery-beat
```

---

## Step 2 — Assess scope

Determine what happened, when, and who is affected.

```bash
# Check audit log for suspicious actions
docker exec openavisio-postgres-1 psql -U openavisio vaultdb \
  -c "SELECT timestamp, user_name, entity_type, action FROM audit_log ORDER BY timestamp DESC LIMIT 100;"

# Check backend logs for unauthorised requests
docker logs openavisio-backend-1 --since 72h 2>&1 | grep -E "40[13]|error|exception" | head -50

# Check celery worker logs
docker logs openavisio-celery-worker-1 --since 72h 2>&1 | grep -E "error|exception" | head -50
```

Document answers to:
- When did the breach start and end?
- How many patients / users are affected?
- What categories of data were exposed? (health data, credentials, access records)
- What caused the breach?

---

## Step 3 — Notify the supervisory authority (Art. 33) — within 72 hours

Notification to the supervisory authority is mandatory within **72 hours** of becoming aware of the breach, unless the breach is unlikely to result in a risk to individuals.

**LfDI Baden-Württemberg**
Online notification: https://www.baden-wuerttemberg.datenschutz.de/meldung-einer-datenpanne/
Postal: Der Landesbeauftragte für den Datenschutz und die Informationsfreiheit, Lautenschlagerstraße 20, 70173 Stuttgart
Phone: +49 711 61 55 41-0

Required information for the notification (Art. 33(3)):
1. Nature of the breach (what happened)
2. Categories and approximate number of data subjects affected
3. Categories and approximate number of personal data records concerned
4. Name and contact details of the data protection contact
5. Likely consequences of the breach
6. Measures taken or proposed to address the breach

If full information is not yet available within 72 hours, submit what you have and supplement later.

---

## Step 4 — Notify affected data subjects (Art. 34)

Required when the breach **is likely to result in a high risk** to the rights and freedoms of individuals. Health data breaches are high-risk by default.

Notification must be made **without undue delay** and must include:
- Description of the breach in plain language
- Name and contact details of the data protection contact
- Likely consequences
- Measures taken or proposed

Notification channel: email to affected Users via `services/email.py`, or direct contact if email is unavailable.

---

## Step 5 — Remediate

Fix the root cause before bringing services back online. Common remediation steps:

| Root cause | Remediation |
|---|---|
| Compromised `app_secret` | Rotate in `.env`, rebuild backend (all sessions invalidated) |
| Compromised `DOCUMENT_ENCRYPTION_KEY` | Run `rotate_deks.py` with new key, update `.env`, rebuild |
| SQL injection / access control bug | Patch code, deploy, check audit log for scope |
| Misconfigured firewall / exposed port | Close port, audit network rules |
| Insider access | Revoke user account, check audit log |

---

## Step 6 — Document

Maintain a written record of the incident (Art. 33(5)) including:

- Date and time the breach was discovered
- Date and time the breach occurred (if known)
- Description of what happened
- Data affected: categories, approximate count
- Likely consequences
- Actions taken and timeline
- Supervisory authority notification (date, reference number)
- Data subject notification (if applicable)

Store the incident record securely. Keep for a minimum of 3 years.

---

## Contact

Data protection contact for this deployment: **[FILL IN — name, email, phone]**
