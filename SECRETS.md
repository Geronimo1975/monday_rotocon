# GitHub Actions Secrets — Weekly Machine Report

Configure under **Settings → Secrets and variables → Actions** for
`Geronimo1975/monday_rotocon`:

| Secret | Value |
|---|---|
| `MONDAY_API_TOKEN` | monday.com personal API token (read scope) |
| `N8N_WEBHOOK_URL` | `https://n8n.rotocon.world/webhook/monday-weekly-report` |
| `N8N_WEBHOOK_TOKEN` | the 64-char hex token set on the `Report Webhook Token` n8n credential |
| `REPORT_RECIPIENT` | `george@rotocon.world` (expand to the team later) |

Schedule: **Mondays at 08:00 Europe/Berlin**, exactly year-round. GitHub cron is
UTC with no DST, so the workflow fires at both `0 6 * * 1` and `0 7 * * 1` (06:00
and 07:00 UTC) and a `gate` job lets only the trigger that is actually 08:00 in
Berlin proceed (06:00 UTC in summer/CEST, 07:00 UTC in winter/CET).
Manual run: Actions → "Weekly Machine Report" → "Run workflow" (always proceeds).
