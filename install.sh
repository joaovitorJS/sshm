#!/usr/bin/env bash
#
# install.sh - instala o sshm no seu usuário Linux
#
# Uso:
#   ./install.sh
#
# Pode ser rodado de novo a qualquer momento para atualizar a versão instalada.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${SSHM_INSTALL_DIR:-$HOME/.local/bin}"
CONFIG_DIR="$HOME/.config/sshm"
BIN_NAME="sshm"

info()  { printf '\033[1;36m[sshm]\033[0m %s\n' "$1"; }
warn()  { printf '\033[1;33m[sshm]\033[0m %s\n' "$1"; }
error() { printf '\033[1;31m[sshm]\033[0m %s\n' "$1" >&2; }

# 1. Verifica pré-requisitos -------------------------------------------------

if ! command -v python3 >/dev/null 2>&1; then
    error "python3 não encontrado. Instale com: sudo apt install python3"
    exit 1
fi

PY_VERSION="$(python3 -c 'import sys; print(sys.version_info[0], sys.version_info[1])')"
PY_MAJOR="${PY_VERSION%% *}"
PY_MINOR="${PY_VERSION##* }"
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 6 ]; }; then
    error "É necessário Python 3.6+. Versão encontrada: $(python3 --version)"
    exit 1
fi

if ! python3 -c "import curses" >/dev/null 2>&1; then
    error "O módulo 'curses' do Python não está disponível."
    error "No Debian/Ubuntu: sudo apt install python3-curses (ou reinstale o pacote python3)"
    exit 1
fi

if ! command -v ssh >/dev/null 2>&1; then
    warn "Comando 'ssh' não encontrado no PATH. Instale o cliente OpenSSH: sudo apt install openssh-client"
fi

# 2. Instala o binário --------------------------------------------------------

mkdir -p "$INSTALL_DIR"
cp "$REPO_DIR/sshm.py" "$INSTALL_DIR/$BIN_NAME"
chmod +x "$INSTALL_DIR/$BIN_NAME"
info "Instalado em: $INSTALL_DIR/$BIN_NAME"

# 3. Cria diretório/arquivo de config se não existir --------------------------

mkdir -p "$CONFIG_DIR"
if [ ! -f "$CONFIG_DIR/machines.json" ]; then
    if [ -f "$REPO_DIR/examples/machines.example.json" ]; then
        cp "$REPO_DIR/examples/machines.example.json" "$CONFIG_DIR/machines.json"
        info "Arquivo de exemplo copiado para: $CONFIG_DIR/machines.json"
    else
        echo "[]" > "$CONFIG_DIR/machines.json"
        info "Arquivo de config criado em: $CONFIG_DIR/machines.json"
    fi
else
    info "Config já existe em $CONFIG_DIR/machines.json (mantido como está)"
fi

# 4. Garante que INSTALL_DIR está no PATH -------------------------------------

add_line_once() {
    # add_line_once <arquivo> <linha>
    local file="$1" line="$2"
    if [ -f "$file" ] && grep -Fqs "$line" "$file"; then
        return 0
    fi
    printf '\n# adicionado pelo instalador do sshm\n%s\n' "$line" >> "$file"
    info "Adicionado ao PATH em $file"
}

case ":$PATH:" in
    *":$INSTALL_DIR:"*)
        ;;
    *)
        case "${SHELL:-}" in
            */fish)
                FISH_RC="$HOME/.config/fish/config.fish"
                mkdir -p "$HOME/.config/fish"
                add_line_once "$FISH_RC" "fish_add_path $INSTALL_DIR"
                warn "Abra um novo terminal (ou rode: source $FISH_RC) para usar o comando 'sshm'"
                ;;
            */zsh)
                SHELL_RC="$HOME/.zshrc"
                add_line_once "$SHELL_RC" 'export PATH="$HOME/.local/bin:$PATH"'
                warn "Abra um novo terminal (ou rode: source $SHELL_RC) para usar o comando 'sshm'"
                ;;
            *)
                # bash e demais shells POSIX-compatíveis
                SHELL_RC="$HOME/.bashrc"
                [ -n "${SHELL:-}" ] && [ "${SHELL##*/}" != "bash" ] && SHELL_RC="$HOME/.profile"
                add_line_once "$SHELL_RC" 'export PATH="$HOME/.local/bin:$PATH"'
                warn "Abra um novo terminal (ou rode: source $SHELL_RC) para usar o comando 'sshm'"
                ;;
        esac
        ;;
esac

echo
info "Instalação concluída! Experimente:"
echo "    sshm            # abrir o menu interativo"
echo "    sshm add        # cadastrar uma máquina"
echo "    sshm --help     # ver todos os comandos"

