# Helpers for fault scripts. Usage: source "$FAULTS_DIR/lib.sh"
# The working directory is the target app's repo.

LINA="Lina Haddad <lina@shopline.example>"
TOMAS="Tomas Keller <tomas@shopline.example>"
PRIYA="Priya Nair <priya@shopline.example>"

# commit_as "<Name <email>>" "<message>" : commit all current changes, dated now (UTC)
commit_as() {
    local when name email
    when="$(date -u +%Y-%m-%dT%H:%M:%S+00:00)"
    name="${1%% <*}"
    email="${1##*<}"
    email="${email%>}"
    git add -A
    GIT_AUTHOR_DATE="$when" GIT_COMMITTER_DATE="$when" \
        git -c user.name="$name" -c user.email="$email" commit -q -m "$2"
}

# mark_culprit : remember the current commit as the culprit for ground truth
mark_culprit() {
    git rev-parse --short HEAD > "$WORK/culprit_commit"
}

# deploy [--migrate] <service>... : build the current commit and restart services
deploy() {
    bash ./deploy.sh "$@"
}

# psql_db "<sql>" : run SQL directly against the shop database
psql_db() {
    MSYS_NO_PATHCONV=1 docker compose exec -T db psql -q -U shopline -d shopline -v ON_ERROR_STOP=1 -c "$1"
}
