# Local SonarQube Community Build

**Last updated:** 2026-08-07

This directory holds the **local** SonarQube analysis settings for DICOM Viewer V3
([`sonar-project.properties`](sonar-project.properties)). Analysis is submitted
with [`scripts/run_local_sonarqube.py`](../../scripts/run_local_sonarqube.py).
Setup overview: [`dev-docs/DEVELOPER_SETUP.md`](../../dev-docs/DEVELOPER_SETUP.md).

The SonarQube **server** itself is shared machine infrastructure. It is not part
of this application's runtime and is not scoped to a single git repo.

## Container vs volume (short)

| Concept | What it is | Survives reboot? | Survives `docker rm`? |
|---------|------------|------------------|------------------------|
| **Container** | The running SonarQube process + its config (ports, restart policy, which volumes are attached) | Only if Docker Desktop is running **and** the container has `--restart unless-stopped` (or you start it again) | No — removing the container does not delete named volumes |
| **Volume** | Durable disk data mounted into the container. For Sonar, `/opt/sonarqube/data` holds the H2 DB, users, tokens, projects, and analyses | Yes (Docker Desktop disk) | **Named** volumes: yes, until you `docker volume rm` / `prune`. **Anonymous** volumes: stay on disk but become easy to lose / prune once no container references them |

**Rule of thumb:** tokens and the admin password live in the **data volume**, not in the container name. Recreating a container with a **new empty** data volume looks like a “password reset” and invalidates tokens.

## Naming

- **Container name:** use a **generic** name such as `sonarqube`. One server serves many coding projects. Do not name the container after this repo.
- **Volume names:** these are **server** volumes (shared DB for all projects analyzed on that instance), not per-git-repo volumes. Prefer generic names (`sonarqube-data`, `sonarqube-extensions`) when creating new volumes. Existing names like `dicom-viewer-sonarqube-data` are fine to keep if they already hold the database you want — they are historical labels, not a requirement that each app repo own a Sonar server.
- **Project identity** in Sonar is `sonar.projectKey` (this repo: `dicom-viewer-v3`) plus each checkout’s ignored `.env` `SONAR_TOKEN`.

## Multi-project usage

One instance at `http://127.0.0.1:9000` (or `http://localhost:9000`) can hold many projects. Each repo configures:

- its own project key / `sonar-project.properties`
- its own `SONAR_TOKEN` in that repo’s ignored `.env`

This repository’s runner rejects non-loopback `SONAR_HOST_URL` values so the local token is not sent off-machine.

## Recommended durable setup

```bash
docker volume create sonarqube-data
docker volume create sonarqube-extensions
docker volume create sonarqube-logs

docker run -d \
  --name sonarqube \
  --restart unless-stopped \
  -p 127.0.0.1:9000:9000 \
  -v sonarqube-data:/opt/sonarqube/data \
  -v sonarqube-extensions:/opt/sonarqube/extensions \
  -v sonarqube-logs:/opt/sonarqube/logs \
  sonarqube:community
```

Also enable **Docker Desktop → Settings → General → Start Docker Desktop when you sign in** so `unless-stopped` containers can come back after a Mac reboot.

Bind the published port to loopback only (do not publish on all host
interfaces) so the UI and API stay on this machine.

Optional compose file may live **outside** any project repo (for example `~/sonarqube/docker-compose.yml`) so multiple checkouts share one definition. Do not treat compose as required application infrastructure for this repo.

## Why tokens / admin password looked “reset”

Typical failure mode on this machine:

1. An older container named `sonarqube` stored users/tokens in **anonymous** Docker volumes.
2. A newer container (`dicom-viewer-sonarqube`) was created with **new named** volumes, so Sonar initialized a **fresh** database (`admin` / `admin`).
3. `.env` still held a token issued against the **old** database → API auth failed.
4. After reboot, `RestartPolicy=no` left the container stopped until started manually.

Named volumes already persist across reboots; the wipe was from attaching a different (empty) data volume, not from reboot itself.

## Restore existing users and tokens (preferred)

If the old container that still mounts the good data volume exists, **prefer restoring it** over minting new credentials.

Inspect:

```bash
docker ps -a --filter name=sonar --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
docker inspect sonarqube --format '{{range .Mounts}}{{.Destination}} <- {{.Name}}{{"\n"}}{{end}}'
docker inspect dicom-viewer-sonarqube --format '{{range .Mounts}}{{.Destination}} <- {{.Name}}{{"\n"}}{{end}}'
```

Restore path (when the exited container `sonarqube` still has the anonymous `/opt/sonarqube/data` volume with the real DB):

```bash
# Free port 9000
docker stop dicom-viewer-sonarqube

# Bring back the container that still mounts the old data volume
docker update --restart unless-stopped sonarqube
docker start sonarqube

# Wait until UP (often 30–60s)
curl -s http://127.0.0.1:9000/api/system/status

# Confirm UI login with the *previous* admin password and that existing SONAR_TOKEN works:
#   python scripts/run_local_sonarqube.py --status
#   python scripts/run_local_sonarqube.py
```

After a successful analysis with the restored DB:

- Leave `dicom-viewer-sonarqube` stopped, or remove only that **container** (`docker rm dicom-viewer-sonarqube`) once you no longer need its empty named volumes.
- Do **not** run `docker volume prune` until you are sure you will never need the restored anonymous data volume (or you have copied it into a named volume — see below).

### Optional: copy restored data into named volumes

Anonymous volumes work but are easy to prune by mistake. After restore succeeds, copy into named volumes and recreate a generic container:

```bash
OLD_DATA=$(docker inspect sonarqube --format '{{range .Mounts}}{{if eq .Destination "/opt/sonarqube/data"}}{{.Name}}{{end}}{{end}}')
OLD_EXT=$(docker inspect sonarqube --format '{{range .Mounts}}{{if eq .Destination "/opt/sonarqube/extensions"}}{{.Name}}{{end}}{{end}}')

# Stop the live container before copying so the H2 DB is not written mid-copy.
docker stop sonarqube

docker volume create sonarqube-data
docker volume create sonarqube-extensions
docker volume create sonarqube-logs

docker run --rm \
  -v "${OLD_DATA}:/from:ro" \
  -v sonarqube-data:/to \
  alpine sh -c 'cd /from && cp -a . /to/'

docker run --rm \
  -v "${OLD_EXT}:/from:ro" \
  -v sonarqube-extensions:/to \
  alpine sh -c 'cd /from && cp -a . /to/'

docker rm sonarqube

docker run -d \
  --name sonarqube \
  --restart unless-stopped \
  -p 127.0.0.1:9000:9000 \
  -v sonarqube-data:/opt/sonarqube/data \
  -v sonarqube-extensions:/opt/sonarqube/extensions \
  -v sonarqube-logs:/opt/sonarqube/logs \
  sonarqube:community
```

Keeping historically named volumes such as `dicom-viewer-sonarqube-data` as the mount target is also fine if that volume already contains the DB you want; rename is cosmetic.

## Fresh start (acceptable fallback)

If the old data volume is gone or you prefer a clean server:

1. Stop/remove conflicting containers on port 9000.
2. Run the **Recommended durable setup** above (generic container + named volumes).
3. Open `http://127.0.0.1:9000`, change `admin` / `admin`, create a new analysis token.
4. Set `SONAR_TOKEN` in this repo’s ignored `.env`.
5. `python scripts/run_local_sonarqube.py`

## Useful commands

```bash
curl -s http://127.0.0.1:9000/api/system/status
docker ps -a --filter name=sonar
docker logs sonarqube --tail 50
docker restart sonarqube
docker inspect sonarqube --format '{{json .Mounts}}' | python3 -m json.tool

# From this repo root, with venv active and SONAR_TOKEN in .env:
python scripts/run_local_sonarqube.py --status
python scripts/run_local_sonarqube.py
python scripts/check_local_sonarqube_updates.py
```

## Backup

Prefer a backup directory outside any project checkout. Restrict directory
permissions before writing archives (for example `umask 077` or
`chmod 700 ~/sonarqube/backups`):

```bash
mkdir -p ~/sonarqube/backups
chmod 700 ~/sonarqube/backups
docker run --rm \
  -v sonarqube-data:/data:ro \
  -v "$HOME/sonarqube/backups":/backup \
  alpine tar czf "/backup/sonarqube-data-$(date +%Y%m%d).tar.gz" -C /data .
```

If your live data volume still uses another name, substitute that volume for `sonarqube-data`.

## Troubleshooting

### Token invalid / “unauthorized”

Usually the token was issued for a different data volume than the one currently mounted. Prefer **Restore** above; otherwise create a new token under **User → My Account → Security** and update `.env`.

### Not reachable after reboot

1. Confirm Docker Desktop is running (`docker info`).
2. `docker ps -a --filter name=sonar` — start the container that mounts the good data volume.
3. Set `--restart unless-stopped` and enable Docker Desktop on login.

### Port 9000 already allocated

Only one Sonar container can bind `127.0.0.1:9000`. Stop the other (`docker stop …`) before starting the one you want.

### Orphaned volumes

```bash
docker volume ls --filter dangling=true
# Remove specific volumes only after restore/backup; avoid blind prune while undecided
```
