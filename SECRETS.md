# GitHub Actions Secrets — Weekly Machine Report

Configure under **Settings → Secrets and variables → Actions** for
`Geronimo1975/monday_rotocon`:

| Secret | Value |
|---|---|
| `MONDAY_API_TOKEN` | monday.com personal API token (read scope) |
| `N8N_WEBHOOK_URL` | `https://n8n.rotocon.world/webhook/monday-weekly-report` |
| `N8N_WEBHOOK_TOKEN` | the 64-char hex token set on the `Report Webhook Token` n8n credential |
| `REPORT_RECIPIENT` | `george@rotocon.world` (expand to the team later) |

Schedule: `cron: "0 5 * * 1"` (Mondays, ~07:00 Europe/Bucharest).
Manual run: Actions → "Weekly Machine Report" → "Run workflow".
