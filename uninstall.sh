#!/usr/bin/env bash
#
# uninstall.sh - remove o sshm do sistema
#
set -euo pipefail

INSTALL_DIR="${SSHM_INSTALL_DIR:-$HOME/.local/bin}"
CONFIG_DIR="$HOME/.config/sshm"
BIN_NAME="sshm"

info()  { printf '\033[1;36m[sshm]\033[0m %s\n' "$1"; }

if [ -f "$INSTALL_DIR/$BIN_NAME" ]; then
    rm -f "$INSTALL_DIR/$BIN_NAME"
    info "Binário removido de $INSTALL_DIR/$BIN_NAME"
else
    info "Binário não encontrado em $INSTALL_DIR/$BIN_NAME (nada a fazer)"
fi

if [ -d "$CONFIG_DIR" ]; then
    read -r -p "Remover também as máquinas cadastradas em $CONFIG_DIR? [y/N] " resp
    case "$resp" in
        [yY]*)
            rm -rf "$CONFIG_DIR"
            info "Config removida: $CONFIG_DIR"
            ;;
        *)
            info "Config mantida em $CONFIG_DIR"
            ;;
    esac
fi

info "Desinstalação concluída."
