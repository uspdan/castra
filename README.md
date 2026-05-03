# Siege Range

A self-hosted Capture The Flag training platform for security operations teams. Practice red team and blue team skills through hands-on challenges running in isolated Docker containers.

## Features

- **12 Built-in Challenges** spanning web exploitation, cryptography, forensics, privilege escalation, and detection engineering
- **Real-time Scoreboard** with live WebSocket updates as operators capture flags
- **Dynamic Scoring** with first blood bonuses, streak multipliers, and cross-training rewards
- **MITRE ATT&CK Mapping** for every challenge with team coverage tracking
- **Isolated Challenge Containers** with read-only filesystems, dropped capabilities, and resource limits
- **Competition Mode** for time-boxed CTF events with dedicated scoreboards
- **Writeup System** where operators share and rate solutions
- **PDF Reports** for individual operator and team performance reviews
- **WireGuard VPN** for network-level challenge access
- **Webhook Notifications** to Slack and Microsoft Teams

## System Requirements

| Resource | Minimum |
|----------|---------|
| CPU | 4 cores |
| RAM | 16 GB |
| Disk | 50 GB SSD |
| Docker | 24+ with Compose v2 |

## Quick Start

```bash
# 1. Clone the repository
git clone <repo-url> && cd seige-range

# 2. Create environment file
cp .env.example .env

# 3. Start all services
docker compose up -d

# 4. Wait for services to initialize
sleep 30

# 5. Seed challenges
python scripts/seed_challenges.py
```

Access the dashboard at **http://localhost:3000**

Default admin: `admin@siege.local` / `Admin123!@#` (change in `.env`)

## Architecture

```
                     :3000
                       |
                    [nginx]
                    /     \
                   /       \
           [dashboard]   [api] ---- [redis]
             (Vite)    (FastAPI) --- [db] (PostgreSQL)
                                \
                            [orchestrator] (DinD)
                                |
                        [challenge containers]
                                |
                             [vpn]
                          (WireGuard)
```

| Network | Type | Purpose |
|---------|------|---------|
| siege-frontend | bridge | Connects nginx ↔ dashboard ↔ API |
| siege-backend | internal | Connects API ↔ DB ↔ Redis ↔ orchestrator |
| siege-challenges | internal | Connects orchestrator ↔ containers ↔ VPN |

See the **Deploy** page in the dashboard for full documentation on host isolation, VPN setup, and production configuration.

## License

MIT
