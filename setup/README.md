# Setting up the workshop machine

One shared machine, one account per participant (PLAN.md, "The AWS
machine"). Everything shared lives under `/opt/metag-ws/` (the defaults of
`metag-ws` and of `activate_databases.sh`), read-only for participants:

| Path | What | Size | From |
|---|---|---|---|
| `/opt/metag-ws/metag-workshops/` | this repository + pixi environments | | GitHub, `pixi install` |
| `/opt/metag-ws/db/` | the databases | ≈ 165 GB | public sources: `pixi run download-dbs` |
| `/opt/metag-ws/data/` | the reads (`sample_R1/R2/ont.fq.gz`) | 1.2 GB | aqua: `data-prep/subsets/9ca3c728/workshop_data/` |
| `/opt/metag-ws/precomputed/` | results of every step, for `results-for` | ≈ 3.6 GB | aqua: `data-prep/precomputed/` |

Plus ≈ 5 GB per participant in their home directory (a full run of their own).

## The databases

`download_databases.sh` (`pixi run download-dbs [DEST [DB...]]`) fetches
pinned versions over HTTPS, checks md5 sums where they are published,
resumes interrupted downloads, and skips what is already installed. The task
runs in its own small pixi environment, `setup`, which has `aria2c`: it
downloads each file over 8 connections, because Zenodo throttles each
connection (≈ 0.3 MB/s each from aqua, against ≈ 4 MB/s from the eggNOG and
GTDB servers).

| DB | Version | Download | Installed | Source |
|---|---|---|---|---|
| `singlem` | metapackage S6.5.0 (GTDB r232), what SingleM 0.21 expects | 2.2 GB | 9.7 GB | [Zenodo 20150069](https://doi.org/10.5281/zenodo.20150069) |
| `checkm2` | DB v3 (recommended for CheckM2 1.1; `CHECKM2_DB_VERSION=2` for the 2021 one) | 1.7 GB | ≈ 3 GB | [Zenodo 14897628](https://doi.org/10.5281/zenodo.14897628) |
| `gunc` | proGenomes 2.1 | 7.2 GB | 13.5 GB | [Zenodo 19631736](https://zenodo.org/records/19631736) |
| `eggnog` | eggNOG 5.0.2 (emapper data) | 12 GB | 51 GB | <https://eggnog5.embl.de/download/emapperdb-5.0.2/> |
| `gtdbtk` | GTDB r232, what GTDB-Tk 2.8 expects | 61 GB | 88 GB | <https://data.gtdb.aau.ecogenomic.org/> |

The script does not use the tools' own downloaders, for two reasons. `singlem
data` takes the newest metapackage in the Zenodo series, which is not
necessarily the one the installed SingleM expects. `download_eggnog_data.py`
uses `eggnogdb.embl.de`, which no longer resolves.

Only step 13 (GTDB-Tk) uses the GTDB-Tk data, and step 13 is results-only:
participants never run it. It is included so that the installation is
complete (e.g., to rerun the precomputed results on the machine).

How the environment finds them: `activate_databases.sh` (an activation
script in `pixi.toml`) sets `$SINGLEM_METAPACKAGE_PATH`, `$CHECKM2DB`,
`$GUNC_DB`, `$EGGNOG_DATA_DIR` and `$GTDBTK_DATA_PATH` from `$METAG_WS_DB`.
If that is not set, it uses `/opt/metag-ws/db` when that exists, and
otherwise the databases installed on aqua.

## Step by step

As a user with sudo on the workshop machine:

```bash
# 1. folders (owned by you while setting up; locked down in step 6)
sudo mkdir -p /opt/metag-ws/{data,precomputed,db}
sudo chown -R $USER /opt/metag-ws

# 2. software
curl -fsSL https://pixi.sh/install.sh | sudo PIXI_BIN_DIR=/usr/local/bin PIXI_NO_PATH_UPDATE=1 bash
cd /opt/metag-ws
git clone https://github.com/luispedro/metag-workshops.git
cd metag-workshops
pixi install --frozen -e default -e eggnog -e gtdbtk -e metabat2 -e setup   # docs is not needed

# 3. databases: about 84 GB to download, so run it in tmux (rerun it if it stops)
tmux new -s dbs
pixi run download-dbs /opt/metag-ws/db
```

Meanwhile, the reads and the precomputed results, which are not public yet
(they are pushed from aqua; replace `WS` with `user@workshop-host`):

```bash
# 4. on aqua, from the repository
rsync -avP data-prep/subsets/9ca3c728/workshop_data/sample_*.fq.gz WS:/opt/metag-ws/data/
rsync -avP \
  --exclude=.done --exclude='04_ASSEMBLY/binary_temp' --exclude='04_ASSEMBLY/[0-3]-*' \
  --exclude='05_POLISH/filtered_*.sam' \
  data-prep/precomputed/ WS:/opt/metag-ws/precomputed/
```

(`-a`, not `-L`: `13_GTDBTK` contains a relative symlink.)

Back on the workshop machine:

```bash
# 5. every login shell gets the environment (and metag-ws)
sudo tee /etc/profile.d/metag-ws.sh <<'EOF'
eval "$(pixi shell-hook --as-is --manifest-path /opt/metag-ws/metag-workshops/pixi.toml)"
export METAG_WS_THREADS=8
EOF

# 6. read-only for everyone else
sudo chown -R root:root /opt/metag-ws
sudo chmod -R a+rX,go-w /opt/metag-ws

# 7. check, as an ordinary user
sudo useradd -m testuser && sudo -iu testuser
for v in SINGLEM_METAPACKAGE_PATH CHECKM2DB GUNC_DB EGGNOG_DATA_DIR GTDBTK_DATA_PATH; do ls -d "${!v}"; done
metag-ws show-cmd 1
metag-ws results-for 12 && ls -l ~/workshop        # *_precomputed symlinks
pixi run -e eggnog emapper.py --version            # the eggnog environment, read-only
metag-ws _run-all -o ~/test-run --skip-results-only -t 16   # ≈ 25 min; also a timing test
```

## Consistency with the precomputed results

The precomputed results were made on aqua with aqua's databases. SingleM,
eggNOG and GTDB-Tk are the same versions as the ones downloaded here. Aqua's
GUNC database (`gunc_db_2.0.4.dmnd`) has the same md5 sum as the downloaded
`gunc_db_progenomes2.1.dmnd`. CheckM2 differs: aqua has the 2021 database
(v1/v2, same sha256), and the download is v3. For the participants' CheckM2
numbers to match the precomputed ones exactly, rebuild the precomputed
results with the downloaded databases (`METAG_WS_DB=...
data-prep/scripts/run_precomputed.sh`), or download with
`CHECKM2_DB_VERSION=2`.
