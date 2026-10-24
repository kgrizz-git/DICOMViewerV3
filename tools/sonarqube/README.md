# Local SonarQube Community Build

**Last updated:** 2026-10-24

This directory holds the **local** SonarQube analysis settings for DICOM Viewer V3
([`sonar-project.properties`](sonar-project.properties)). Analysis is submitted
with [`scripts/run_local_sonarqube.py`](../../scripts/run_local_sonarqube.py).
Setup overview: [`dev-docs/DEVELOPER_SETUP.md`](../../dev-docs/DEVELOPER_SETUP.md).

The SonarQube **server** itself is shared machine infrastructure. It is not part
of this application's runtime and is not scoped to a single git repo.

## Current server on this machine

One Community Build serves every local project. As of 2026-10-24 it is the
Compose stack in MyPySkinDose, not a container started from this repo:

| | |
|--|--|
| Compose file | `~/MyCode/MyPySkinDose/compose.sonarqube.yaml` |
| Compose project | `sonarqube-local` |
| App container | `sonarqube-local` |
| Image pin | `sonarqube:26.9.0.129388-community` (digest pinned in that file) |
| Database | Postgres 17 (`sonarqube-local-db-1`), volume `sonarqube-local_postgresql_data` |
| URL | `http://127.0.0.1:9000` |
| Runtime | Colima (Docker). The container restart policy is `unless-stopped`. |

Upgrade and backup steps for that stack live in
`~/MyCode/MyPySkinDose/dev-docs/SONARQUBE_LOCAL.md`. Postgres is what makes an
in-place server upgrade possible. Do not start a second Sonar container on
port 9000.

Stopped containers named `sonarqube` and `dicom-viewer-sonarqube` are the older
embedded-H2 installs described below. Leave them stopped. Starting one of them
instead of `sonarqube-local` talks to a different database, so the current
tokens look invalid even though nothing was deleted.

Users, tokens, projects, and analysis history for the live server are in
`sonarqube-local_postgresql_data`. Recreating the `sonarqube-local` container
while that volume stays attached keeps them. A new empty Postgres volume, or
`docker volume rm` / `docker volume prune` of that volume, does not.

## eMudhra / emSign trust store (October 2026)

SonarQube Community Build through 26.10.0.133078, including the pinned
26.9.0.129388 image, still trusts compromised eMudhra (emSign) certificate
roots. There is no patched Community Build image yet. Bumping
`sonarqube:community` does not clear this. SonarQube Cloud's own trust stores
were already updated; that does not update this local server.

The Docker workaround mounts a cleaned Java `cacerts` read-only and sets
`SONAR_WEB_JAVAADDITIONALOPTS` and `SONAR_CE_JAVAADDITIONALOPTS` on the
**existing** `sonarqube` service, then recreates that container. Official
steps: [eMudhra certificate authority compromise](https://docs.sonarsource.com/sonarqube-community-build/server-update-and-maintenance/release-notes/emudhra-certificate-authority-compromise).

That workaround does not replace a volume, does not run a database migration,
and does not rotate the admin password or analysis tokens. The JVM property
`javax.net.ssl.trustStorePassword` is the Java trust-store password
(`changeit` on the image's `cacerts`), not the Sonar admin password. Expect a
short restart. If the mounted file is missing or unreadable, Java silently
keeps the image trust store: the server still starts, and the workaround has
not applied. Outbound HTTPS from the server to a host whose certificate chains
to those roots will start failing, which is the point of removing them. This
local server is not configured for GitHub, LDAP, email, or webhooks.

Scanner JRE provisioning is a separate client setting
(`SONAR_SCANNER_SKIP_JRE_PROVISIONING=true` until Sonar ships cleaned scanner
runtimes). It does not touch the server database. The SonarQube CLI (`sonar`,
not `sonar-scanner`) and a self-hosted SonarQube MCP server are not part of
this stack. The Cursor SonarQube for IDE extension is a client update only.

Notes from the 2026-10-24 check, including what is and is not installed, are
in `~/MyCode/empty-landing-dir/sonarqube-local/NOTES.md`.

## Container vs volume (short)

| Concept | What it is | Survives reboot? | Survives `docker rm`? |
|---------|------------|------------------|------------------------|
| **Container** | The running SonarQube process + its config (ports, restart policy, which volumes are attached) | Only if Colima (or Docker Desktop) is running **and** the container has `--restart unless-stopped` (or you start it again) | No — removing the container does not delete named volumes |
| **Volume** | Durable disk. On the live stack, accounts and projects are in `sonarqube-local_postgresql_data`. `sonarqube-local_sonarqube_data` is mounted at `/opt/sonarqube/data` and is not that database. Older H2 containers kept the database inside `/opt/sonarqube/data`. | Yes (Colima / Docker disk) | **Named** volumes: yes, until you `docker volume rm` / `prune`. **Anonymous** volumes: stay on disk but become easy to lose / prune once no container references them |

**Rule of thumb:** tokens and the admin password live in the **database volume**, not in the container name. Recreating a container with a **new empty** database looks like a “password reset” and invalidates tokens.

## Naming

- **Container name:** the live app container is `sonarqube-local` (Compose project `sonarqube-local`). One server serves many coding projects. Do not start another server named after this repo.
- **Volume names:** these are **server** volumes (shared DB for all projects analyzed on that instance), not per-git-repo volumes. The live names are `sonarqube-local_postgresql_data`, `sonarqube-local_sonarqube_data`, `sonarqube-local_sonarqube_extensions`, and `sonarqube-local_sonarqube_logs`. Older names such as `dicom-viewer-sonarqube-data` belong to the stopped H2 containers.
- **Project identity** in Sonar is `sonar.projectKey` (this repo: `dicom-viewer-v3`) plus each checkout’s ignored `.env` `SONAR_TOKEN`.

## Multi-project usage

One instance at `http://127.0.0.1:9000` (or `http://localhost:9000`) can hold many projects. Each repo configures:

- its own project key / `sonar-project.properties`
- its own `SONAR_TOKEN` in that repo’s ignored `.env`

This repository’s runner rejects non-loopback `SONAR_HOST_URL` values so the local token is not sent off-machine.

## Historical H2 setup (do not start this beside the live server)

The commands below describe the older embedded-H2 layout. They are not how
the current server is created. Running them against a new volume creates a
second database and a new `admin` / `admin` login. Existing `SONAR_TOKEN`
values keep working only against the database that issued them.

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

The current runtime is Colima, started separately from Docker Desktop. A
container with `--restart unless-stopped` comes back when the Colima VM is
running.

Bind the published port to loopback only (do not publish on all host
interfaces) so the UI and API stay on this machine.

The live definition is `~/MyCode/MyPySkinDose/compose.sonarqube.yaml`. Do not
treat that file as application infrastructure for this repo, and do not add a
second compose project that publishes port 9000.

## Why tokens / admin password looked “reset”

Typical failure mode on this machine:

1. An older container named `sonarqube` stored users/tokens in **anonymous** Docker volumes.
2. A newer container (`dicom-viewer-sonarqube`) was created with **new named** volumes, so Sonar initialized a **fresh** database (`admin` / `admin`).
3. `.env` still held a token issued against the **old** database → API auth failed.
4. After reboot, `RestartPolicy=no` left the container stopped until started manually.

Named volumes already persist across reboots; the wipe was from attaching a different (empty) data volume, not from reboot itself.

## Restore existing users and tokens (historical H2 only)

These steps apply to the stopped embedded-H2 containers. They are not the
recovery path for `sonarqube-local`. Starting `sonarqube` while
`sonarqube-local` is up fails on port 9000. Stopping the live server and
starting an old container points the UI at a different database.

If the old container that still mounts the good data volume exists, **prefer restoring it** over minting new credentials only when you intentionally want that older database.

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
docker logs sonarqube-local --tail 50
docker restart sonarqube-local
docker inspect sonarqube-local --format '{{json .Mounts}}' | python3 -m json.tool

# From this repo root, with venv active and SONAR_TOKEN in .env:
python scripts/run_local_sonarqube.py --status
python scripts/run_local_sonarqube.py
python scripts/check_local_sonarqube_updates.py
# After analysis: priority findings + automatic JSON archive under tmp/sonarqube-findings/
python scripts/report_local_sonarqube_issues.py \
  --expected-revision "$(git rev-parse HEAD)"
# Optional Markdown copy: add --output tmp/sonar-findings.md
```

If this token is denied access to analysis history (HTTP 403), the reporter
can still archive the accessible issues as a **provisional** snapshot. The
archive separates the unverified local submission revision from the unknown
server revision; it does not claim the server processed that commit. Other
reporting failures still stop the archive.

## Backup

The live database is Postgres. Back it up with the `pg_dump` command in
`~/MyCode/MyPySkinDose/dev-docs/SONARQUBE_LOCAL.md` before an image upgrade.
Archiving `sonarqube-local_sonarqube_data` does not copy users, tokens, or
projects.

The tar command below is only for an older H2 volume named `sonarqube-data`.
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

If an old H2 data volume uses another name, substitute that volume for `sonarqube-data`.

## Troubleshooting

### Token invalid / “unauthorized”

Usually the token was issued for a different database than the one currently serving port 9000. Confirm `sonarqube-local` is the container that is up. Prefer that Postgres volume over **Restore** (the restore steps bring back an older H2 database). Otherwise create a new token under **User → My Account → Security** and update `.env`.

### Not reachable after reboot

1. Confirm Colima is running (`colima status`, then `docker info`).
2. `docker ps -a --filter name=sonar` — start `sonarqube-local` (and its Postgres dependency) with `docker compose -f ~/MyCode/MyPySkinDose/compose.sonarqube.yaml up -d` from a shell that can read that repo's `.env`.
3. Leave the older `sonarqube` and `dicom-viewer-sonarqube` containers stopped.

### Port 9000 already allocated

Only one Sonar container can bind `127.0.0.1:9000`. Stop the other (`docker stop …`) before starting the one you want.

### Orphaned volumes

```bash
docker volume ls --filter dangling=true
# Remove specific volumes only after restore/backup; avoid blind prune while undecided
```
