# Quick Access — your ops cheat-sheet (example)

This is a safe template. Copy this folder to `data/` (which is git-ignored) and
replace the placeholders with your real commands, hosts, and credentials —
nothing in `data/` is ever committed.

Keep facts on **labeled lines** and commands in code blocks; that's what makes
them easy for the model to look up.

---

## Credentials & passwords

- **Postgres password:** `<your-postgres-password>` (user `postgres`)
- **MySQL password:** `<your-mysql-password>` (user `root`)
- **Service X API key:** `<your-api-key>`

## Key hosts

- **Jumpbox:** `ubuntu@10.0.0.5` (key `~/keys/jumpbox.pem`)
- **Staging URL:** `https://staging.example.com`

---

## Databases

### Postgres
Password: `<your-postgres-password>`
```bash
psql -U postgres
```

---

## Example service

### Restart it
```bash
sudo systemctl restart my-service
```
