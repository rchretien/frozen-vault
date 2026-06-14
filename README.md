# Fridge App Workspace

This repository is now structured as a workspace that can host multiple apps.

## Current apps

- `apps/api`: FastAPI backend for the fridge inventory application

## Backend development

Serve the backend app directly from the workspace root:

```sh
uv run poe api --dev
```

Run backend tests:

```sh
uv run poe test
```

Run backend linting:

```sh
uv run poe lint
```

If you want to target the backend project explicitly, use:

```sh
uv run --directory apps/api poe lint
```

## Containers

Start the backend container from the workspace root:

```sh
docker compose up app
```

## Raspberry Pi LAN Deployment

The production deployment is intended to run inside the local network only. It uses Nginx as the
reverse proxy, the FastAPI app container, and Supabase PostgreSQL as the persistent database.

Create `.env-prod` from `.env-prod.example` on the Raspberry Pi and fill in the Supabase database
connection values. Do not commit `.env-prod`.

Run database migrations for the configured environment:

```sh
uv run poe migrate
```

Run production migrations through the app container:

```sh
uv run poe migrate-prod
```

Pull the production image and start the production stack. The API container runs migrations on
startup through its production command.

```sh
./scripts/pi-deploy.sh
```

Run a quick post-deploy check for the HTTPS proxy, static assets, and mixed-content URLs:

```sh
./scripts/pi-check.sh
```

The production stack serves the app through Nginx at `/fridge-app`. Keep the Raspberry Pi behind
your router firewall and do not configure public port forwarding if the app should remain private.

Tailscale is optional. It is a private WireGuard-based VPN that lets your own devices reach the Pi
securely from outside your home network without exposing the app to the public internet.

## Notes

Within the Dev Container this is equivalent to:

```sh
poe api
```
- The backend Python package name remains `fridge_app_backend`.
- No frontend app has been added yet; the workspace is only prepared for it.
- Backend-specific setup, including PostgreSQL and Alembic instructions, lives in `apps/api/README.md`.
