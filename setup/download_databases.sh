#!/usr/bin/env bash
# Downloads the databases of the workshop from their public sources into DEST
# (setup/README.md), in the layout that setup/activate_databases.sh expects:
#
#   DEST/singlem/S6.5.0.GTDB_r232.metapackage_20260319.smpkg.zb/   9.7 GB  steps 3, 11
#   DEST/checkm2/uniref100.KO.1.dmnd                         about 3 GB  steps 8, 14.2
#   DEST/gunc/gunc_db_progenomes2.1.dmnd                      13.5 GB  step 9
#   DEST/eggnog/5.0.2/                                          51 GB  step 13
#   DEST/gtdbtk/release232/                                     88 GB  step 10
#
# Usage: setup/download_databases.sh [DEST [DB...]]
#   DEST  default: $METAG_WS_DB, or /opt/metag-ws/db
#   DB    any of: singlem checkm2 gunc eggnog gtdbtk (default: all of them)
# or, through pixi: pixi run download-dbs [DEST [DB...]]
#
# The versions are pinned (the ones the installed tools expect), not "the
# latest". CHECKM2_DB_VERSION=2 gets the 2021 CheckM2 database instead of v3.
# Rerunning is safe: finished databases are skipped and interrupted downloads
# resume. With aria2c (in the pixi environment `setup`), each file is
# downloaded over 8 connections (much faster from Zenodo); otherwise with
# curl. Downloads (about 84 GB, 61 GB of them GTDB-Tk) go to DEST/.download/
# and each is removed once unpacked: in total about 165 GB, plus 61 GB while
# GTDB-Tk is unpacked.
set -euo pipefail

DEST="${1:-${METAG_WS_DB:-/opt/metag-ws/db}}"
shift || true
ALL=(singlem checkm2 gunc eggnog gtdbtk)
DBS=("$@")
[ ${#DBS[@]} -gt 0 ] || DBS=("${ALL[@]}")
for db in "${DBS[@]}"; do
    case " ${ALL[*]} " in
        *" $db "*) ;;
        *) echo "Unknown database '$db' (known: ${ALL[*]})" >&2; exit 1 ;;
    esac
done

SINGLEM_URL=https://zenodo.org/records/20150069/files/S6.5.0.GTDB_r232.metapackage_20260319.smpkg.zb.tar.gz
SINGLEM_MD5=580f9ae9ae6a0972f15665c7397c6369
SINGLEM_NAME=S6.5.0.GTDB_r232.metapackage_20260319.smpkg.zb
case "${CHECKM2_DB_VERSION:-3}" in
    3) CHECKM2_URL=https://zenodo.org/records/14897628/files/checkm2_database.tar.gz
       CHECKM2_MD5=07c10655620843b517d0df0c160d911f ;;
    2) CHECKM2_URL=https://zenodo.org/records/5571251/files/checkm2_database.tar.gz
       CHECKM2_MD5=f35c40f58efaf112d29fc187a88af6f5 ;;
    *) echo "CHECKM2_DB_VERSION must be 2 or 3" >&2; exit 1 ;;
esac
# the md5 sums are those in gunc 1.1.1 (gunc/gunc_database.py)
GUNC_URL=https://zenodo.org/records/19631736/files/gunc_db_progenomes2.1.dmnd.gz
GUNC_GZ_MD5=bc93a855e0760aad5c4e5f2d0e26da46
GUNC_MD5=447c9330056b02f29f30fe81fe4af4eb
# download_eggnog_data.py (eggnog-mapper 2.1.15) uses http://eggnogdb.embl.de,
# which no longer resolves; the same files are served here (no md5 sums
# published: gzip's own check is all there is)
EGGNOG_URL=https://eggnog5.embl.de/download/emapperdb-5.0.2
# as in GTDB-Tk 2.8's download-db.sh (no md5 sum published)
GTDBTK_URL=https://data.gtdb.aau.ecogenomic.org/releases/release232/232.0/auxillary_files/gtdbtk_package/full_package/gtdbtk_r232_data.tar.gz

mkdir -p "$DEST"
DEST="$(cd "$DEST" && pwd)"
DL="$DEST/.download"
mkdir -p "$DL"

if command -v pigz > /dev/null; then
    GUNZIP=(pigz -dc -p "$(( $(nproc) > 8 ? 8 : $(nproc) ))")
else
    GUNZIP=(gzip -dc)
fi

log() { echo "[$(date +%H:%M:%S)] $*"; }

# fetch URL FILE [MD5]: download (resuming a partial download) and check
fetch() {
    local url=$1 out="$DL/$2" md5=${3:-}
    if [ -e "$out.ok" ]; then
        log "already downloaded: $2"
        return
    fi
    log "downloading $url"
    if command -v aria2c > /dev/null; then
        # Zenodo throttles each connection (≈ 0.3 MB/s from aqua): 8 at once
        aria2c -x 8 -s 8 -k 10M -c --max-tries=10 --retry-wait=30 \
            --summary-interval=60 --console-log-level=warn \
            ${CURL_CA_BUNDLE:+--ca-certificate="$CURL_CA_BUNDLE"} \
            -d "$DL" -o "$2" "$url"
    else
        curl -fL --retry 10 --retry-delay 30 --retry-all-errors -C - --progress-bar -o "$out" "$url"
    fi
    if [ -n "$md5" ]; then
        log "checking md5 of $2"
        if [ "$(md5sum < "$out" | cut -d' ' -f1)" != "$md5" ]; then
            echo "md5 of $out does not match (expected $md5): delete it and rerun" >&2
            exit 1
        fi
    fi
    touch "$out.ok"
}

# todo TARGET: true if TARGET (the final file or directory) is not there yet
todo() {
    if [ -e "$1" ]; then
        log "already installed: $1"
        return 1
    fi
}

finish() { rm -f "$DL/$1" "$DL/$1.ok"; }

get_singlem() {
    local target="$DEST/singlem/$SINGLEM_NAME"
    todo "$target" || return 0
    fetch "$SINGLEM_URL" singlem.tar.gz "$SINGLEM_MD5"
    log "unpacking SingleM metapackage"
    rm -rf "$DEST/singlem/.tmp" && mkdir -p "$DEST/singlem/.tmp"
    "${GUNZIP[@]}" "$DL/singlem.tar.gz" | tar xf - -C "$DEST/singlem/.tmp"
    mv "$DEST/singlem/.tmp/$SINGLEM_NAME" "$target"
    rm -rf "$DEST/singlem/.tmp"
    finish singlem.tar.gz
}

get_checkm2() {
    local target="$DEST/checkm2/uniref100.KO.1.dmnd"
    todo "$target" || return 0
    fetch "$CHECKM2_URL" checkm2.tar.gz "$CHECKM2_MD5"
    log "unpacking CheckM2 database"
    rm -rf "$DEST/checkm2/.tmp" && mkdir -p "$DEST/checkm2/.tmp"
    "${GUNZIP[@]}" "$DL/checkm2.tar.gz" | tar xf - -C "$DEST/checkm2/.tmp"
    echo "CheckM2 database v${CHECKM2_DB_VERSION:-3} ($CHECKM2_URL)" > "$DEST/checkm2/VERSION"
    mv "$DEST/checkm2/.tmp/CheckM2_database/uniref100.KO.1.dmnd" "$target"
    rm -rf "$DEST/checkm2/.tmp"
    finish checkm2.tar.gz
}

get_gunc() {
    local target="$DEST/gunc/gunc_db_progenomes2.1.dmnd"
    todo "$target" || return 0
    fetch "$GUNC_URL" gunc.dmnd.gz "$GUNC_GZ_MD5"
    log "unpacking GUNC database"
    mkdir -p "$DEST/gunc"
    "${GUNZIP[@]}" "$DL/gunc.dmnd.gz" > "$target.tmp"
    log "checking md5 of the GUNC database"
    if [ "$(md5sum < "$target.tmp" | cut -d' ' -f1)" != "$GUNC_MD5" ]; then
        echo "md5 of $target.tmp does not match (expected $GUNC_MD5)" >&2
        exit 1
    fi
    mv "$target.tmp" "$target"
    finish gunc.dmnd.gz
}

get_eggnog() {
    local dir="$DEST/eggnog/5.0.2"
    mkdir -p "$dir"
    local f
    for f in eggnog.db eggnog_proteins.dmnd; do
        todo "$dir/$f" || continue
        fetch "$EGGNOG_URL/$f.gz" "$f.gz"
        log "unpacking $f"
        "${GUNZIP[@]}" "$DL/$f.gz" > "$dir/$f.tmp"
        mv "$dir/$f.tmp" "$dir/$f"
        finish "$f.gz"
    done
    if todo "$dir/eggnog.taxa.db"; then
        fetch "$EGGNOG_URL/eggnog.taxa.tar.gz" eggnog.taxa.tar.gz
        rm -rf "$dir/.tmp" && mkdir -p "$dir/.tmp"
        "${GUNZIP[@]}" "$DL/eggnog.taxa.tar.gz" | tar xf - -C "$dir/.tmp"
        mv "$dir/.tmp/eggnog.taxa.db.traverse.pkl" "$dir/"
        mv "$dir/.tmp/eggnog.taxa.db" "$dir/"
        rm -rf "$dir/.tmp"
        finish eggnog.taxa.tar.gz
    fi
}

get_gtdbtk() {
    local target="$DEST/gtdbtk/release232"
    todo "$target" || return 0
    fetch "$GTDBTK_URL" gtdbtk.tar.gz
    log "unpacking GTDB-Tk data (88 GB)"
    rm -rf "$DEST/gtdbtk/.tmp" && mkdir -p "$DEST/gtdbtk/.tmp"
    "${GUNZIP[@]}" "$DL/gtdbtk.tar.gz" | tar xf - -C "$DEST/gtdbtk/.tmp"
    mv "$DEST/gtdbtk/.tmp/release232" "$target"
    rm -rf "$DEST/gtdbtk/.tmp"
    finish gtdbtk.tar.gz
}

log "installing into $DEST: ${DBS[*]}"
df -h "$DEST" | tail -1
for db in "${DBS[@]}"; do
    "get_$db"
done
rmdir "$DL" 2> /dev/null || true
chmod -R a+rX "$DEST"
log "done. The workshop environment uses these databases if METAG_WS_DB=$DEST"
log "(or nothing, if DEST is /opt/metag-ws/db): see setup/activate_databases.sh"
