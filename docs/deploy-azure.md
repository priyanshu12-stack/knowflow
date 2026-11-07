# Deploying KnowFlow to Azure for Students (no credit card)

[Azure for Students](https://azure.microsoft.com/en-in/free/students) gives full-time students
USD 100 of credit for 12 months, renewable yearly, with **no credit card**. You verify with your
college email. When the credit runs out the subscription is disabled, not charged.

The models still run on the server through Ollama, so ADR-007 (no paid inference) holds.

## What gets created

| Resource | Setting | Cost (Central India, Nov 2026 list prices) |
|---|---|---|
| VM `knowflow-vm` | `Standard_B4as_v2`: 4 vCPU, 16 GB RAM, Ubuntu 24.04 | $0.098/hour **only while running** |
| OS disk | 32 GB Standard SSD | $2.64/month, always |
| Public IP `knowflow-ip` | Standard, with DNS name | $0.005/hour, **deleted on `stop`** |
| Firewall `knowflow-nsg` | 80/443 open; 22 only from your current IP | free |
| Auto-shutdown | every night at 23:30 IST | free |

**Start/stop model:** stopping deallocates the VM and releases the IP, so a stopped server costs
only the disk. That's about $32 a year, which leaves roughly 650 running hours of the $100.

Student subscriptions only allow these regions: Central India, South Central India, Indonesia
Central, Malaysia West and Korea Central. They're limited to 6 vCPUs, and VMs can't be pinned to
an availability zone (regional VMs work).

## How it runs on the server

- PostgreSQL 16 + pgvector in Docker (`infra/docker-compose.yml`, bound to loopback)
- Ollama as a system service with `qwen3:4b` and `nomic-embed-text:v1.5`
- `knowflow-api`, `knowflow-worker` and `knowflow-web` as systemd services on 127.0.0.1
- Caddy on 80/443 with automatic HTTPS (Let's Encrypt) and a password gate

Everything starts on boot, so `start` is all you need before a demo.

## Commands (Windows PowerShell, from the repo root)

```powershell
az login                                          # once per computer
./deploy/azure/knowflow-azure.ps1 create          # one time, 15-25 min
./deploy/azure/knowflow-azure.ps1 set-password    # prompts for username + password (12+ chars)

./deploy/azure/knowflow-azure.ps1 start           # before a demo; prints the link
./deploy/azure/knowflow-azure.ps1 stop            # after the demo
./deploy/azure/knowflow-azure.ps1 status
./deploy/azure/knowflow-azure.ps1 update          # after pushing new code to main
./deploy/azure/knowflow-azure.ps1 logs            # last service log lines
./deploy/azure/knowflow-azure.ps1 ssh
```

The link is always `https://knowflow-priyanshu.centralindia.cloudapp.azure.com`. Change it with
the `KNOWFLOW_AZ_DNS` environment variable before `create`.

### Before an interview
1. `./deploy/azure/knowflow-azure.ps1 start` about 10 minutes ahead.
2. Open the link, log in, and ask one question to warm the model up.
3. After the interview: `./deploy/azure/knowflow-azure.ps1 stop`.

If you forget to stop it, the nightly auto-shutdown stops the VM at 23:30 IST. The IP is still
attached then (about $0.12/day) until you next run `stop` or `start`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Browser says the site can't be reached right after `start` | Wait 1–2 minutes for boot. Then try `logs`. |
| Certificate warning | Caddy is still getting the certificate. Wait a minute and reload. |
| `ssh` times out | Your home IP changed. Every script command re-allows your current IP, so just run it again. |
| `create` fails with `SkuNotAvailable` | Set `$env:KNOWFLOW_AZ_SIZE='Standard_B4s_v2'` (or `Standard_B4ps_v2`, ARM) and run `create` again. |
| Credit check | https://www.microsoftazuresponsorships.com/balance |
