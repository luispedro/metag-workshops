# Sourced when a pixi environment of this project is activated (pixi.toml,
# [activation] scripts): the database paths that the workshop commands use
# ($SINGLEM_METAPACKAGE_PATH, $CHECKM2DB, $GUNC_DB, $EGGNOG_DATA_DIR,
# $GTDBTK_DATA_PATH).
#
# - $METAG_WS_DB set: the databases downloaded there by
#   setup/download_databases.sh
# - otherwise, /opt/metag-ws/db if it exists (the workshop machine)
# - otherwise, the databases installed on aqua (used for the precomputed
#   results)
if [ -n "${METAG_WS_DB:-}" ] || [ -d /opt/metag-ws/db ]; then
    _metag_ws_db="${METAG_WS_DB:-/opt/metag-ws/db}"
    export SINGLEM_METAPACKAGE_PATH="$_metag_ws_db/singlem/S6.5.0.GTDB_r232.metapackage_20260319.smpkg.zb/payload_directory"
    export CHECKM2DB="$_metag_ws_db/checkm2/uniref100.KO.1.dmnd"
    export GUNC_DB="$_metag_ws_db/gunc/gunc_db_progenomes2.1.dmnd"
    export EGGNOG_DATA_DIR="$_metag_ws_db/eggnog/5.0.2"
    export GTDBTK_DATA_PATH="$_metag_ws_db/gtdbtk/release232"
    unset _metag_ws_db
else
    export SINGLEM_METAPACKAGE_PATH=/work/microbiome/db/singlem/S6.5.0.GTDB_r232.metapackage_20260319.smpkg.zb/payload_directory
    export CHECKM2DB=/work/microbiome/db/CheckM2_database/uniref100.KO.1.dmnd
    export GUNC_DB=/work/microbiome/db/gunc/1.0.1/gunc_db_2.0.4.dmnd
    export EGGNOG_DATA_DIR=/work/microbiome/db/eggnog-mapper/2.1.12
    export GTDBTK_DATA_PATH=/work/microbiome/db/gtdb/gtdb_release232/auxillary_files/gtdbtk_package/full_package/release232
fi
