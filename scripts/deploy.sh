#!/usr/bin/env bash
# Run on the server: bash scripts/deploy.sh
# Deploy only TurboAbr; never stop, recreate, or prune other Compose projects.
set -Eeuo pipefail

main() {
    if [[ $EUID -ne 0 ]]; then
        exec sudo bash "${BASH_SOURCE[0]}" "$@"
    fi

    local app_dir=/opt/turboabr
    local project=turboabr
    local backup_dir=/var/backups/turboabr
    local previous_commit backup_file container

    cd "$app_dir"
    [[ "$(pwd -P)" == "$app_dir" ]] || {
        echo "Deployment must run from $app_dir." >&2
        exit 1
    }

    command -v git >/dev/null
    command -v docker >/dev/null
    command -v flock >/dev/null
    docker compose version >/dev/null
    docker info >/dev/null

    exec 9> /run/lock/turboabr-deploy.lock
    flock -n 9 || {
        echo 'Another TurboAbr deployment is already running.' >&2
        exit 1
    }

    [[ -f .env ]] || { echo "Missing $app_dir/.env" >&2; exit 1; }
    [[ "$(git branch --show-current)" == main ]] || {
        echo 'Deployment requires the main branch.' >&2
        exit 1
    }
    local dirty_status dirty_path
    dirty_status="$(git status --porcelain --untracked-files=no)"
    if [[ -n "$dirty_status" ]]; then
        while IFS= read -r dirty_path; do
            dirty_path="${dirty_path:3}"
            [[ "$dirty_path" == 'docker-compose.yml' ]] || {
                echo 'Tracked files other than docker-compose.yml have local changes:' >&2
                echo "$dirty_status" >&2
                echo 'Commit or resolve them before deploying.' >&2
                exit 1
            }
        done <<< "$dirty_status"
        echo 'Keeping the server-local docker-compose.yml changes.'
    fi

    local -a compose=(
        docker compose
        --project-name "$project"
        --project-directory "$app_dir"
        -f "$app_dir/docker-compose.yml"
    )

    # Refuse to reuse the project name if its bot belongs to another checkout.
    while IFS= read -r container; do
        [[ -n "$container" ]] || continue
        [[ "$(docker inspect --format '{{ index .Config.Labels "com.docker.compose.project.working_dir" }}' "$container")" == "$app_dir" ]] || {
            echo "Compose project '$project' belongs to another checkout." >&2
            exit 1
        }
    done < <(docker ps -aq \
        --filter "label=com.docker.compose.project=$project" \
        --filter label=com.docker.compose.service=bot)

    previous_commit="$(git rev-parse HEAD)"
    echo "[1/7] Checking origin/main..."
    git fetch origin main
    git merge-base --is-ancestor HEAD origin/main || {
        echo 'Server history has diverged from origin/main; deployment aborted.' >&2
        exit 1
    }

    echo "[2/7] Creating a validated PostgreSQL backup..."
    [[ -n "$("${compose[@]}" ps --status running -q postgres)" ]] || {
        echo 'PostgreSQL is not running; refusing to deploy without a backup.' >&2
        exit 1
    }
    install -d -m 700 "$backup_dir"
    backup_file="$backup_dir/pre-deploy-$(date -u +%Y%m%dT%H%M%SZ)-${previous_commit:0:12}.sql.gz"
    "${compose[@]}" exec -T postgres sh -ec \
        'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' | gzip > "$backup_file"
    test -s "$backup_file"
    gzip -t "$backup_file"
    chmod 600 "$backup_file"

    trap 'echo "Deployment failed at line $LINENO. Previous commit: '"$previous_commit"'. Backup: '"$backup_file"'" >&2' ERR

    echo "[3/7] Updating to origin/main (fast-forward only)..."
    git merge --ff-only origin/main

    echo "[4/7] Building the bot image..."
    "${compose[@]}" build --pull bot

    echo "[5/7] Applying database migrations..."
    "${compose[@]}" run --rm --no-deps bot alembic upgrade head

    echo "[6/7] Recreating only the bot container..."
    "${compose[@]}" up -d --no-deps --force-recreate bot

    echo "[7/7] Verifying startup and immediate traffic sync..."
    sleep 12
    container="$("${compose[@]}" ps -q bot)"
    [[ -n "$container" ]] || { echo 'Bot container was not created.' >&2; exit 1; }
    [[ "$(docker inspect --format '{{.State.Running}} {{.RestartCount}}' "$container")" == 'true 0' ]] || {
        "${compose[@]}" logs --tail=100 bot
        echo 'Bot failed its startup check.' >&2
        exit 1
    }

    "${compose[@]}" ps bot
    "${compose[@]}" logs --tail=100 bot
    echo "Deployment complete: $(git rev-parse --short HEAD)"
    echo "Database backup: $backup_file"
    echo 'The scheduler starts traffic synchronization immediately after bot startup.'
}

# Parse the whole function before this script updates itself from Git.
main "$@"
