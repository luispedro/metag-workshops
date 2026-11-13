# Sourced by every jug_hpc worker (the `setup` in jug_hpc.toml): activates the
# pixi environment, which provides jug and the tools.

# In the mqyolo sandbox the default pixi cache (/pkg/...) is read-only, but
# writable through /mnt/weka.
if [ -n "${PIXI_CACHE_DIR:-}" ] && [ ! -w "$PIXI_CACHE_DIR" ] && [ -w "/mnt/weka$PIXI_CACHE_DIR" ]; then
    export PIXI_CACHE_DIR="/mnt/weka$PIXI_CACHE_DIR"
fi
_ws_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
# pixi re-creates the .pixi/envs symlink (detached environments) on every
# activation, so workers starting together race on it: one at a time. As an
# assignment, a failing shell-hook stops the worker (set -e), unlike
# `eval "$(pixi shell-hook)"`.
mkdir -p "$_ws_root/.pixi"
_ws_hook="$(flock "$_ws_root/.pixi/shell-hook.lock" \
    pixi shell-hook --frozen --manifest-path "$_ws_root/pixi.toml")"
eval "$_ws_hook"
unset _ws_root _ws_hook
