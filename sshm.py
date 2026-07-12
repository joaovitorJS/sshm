#!/usr/bin/env python3
"""
sshm - Seletor interativo de máquinas SSH
Uso:
    sshm                    # abre o menu interativo (buscar + selecionar + conectar)
    sshm add                # cadastra uma nova máquina no arquivo custom
    sshm import ARQUIVO.csv # importa máquinas em lote a partir de um CSV
    sshm list               # lista todas as máquinas (ssh config + custom)
    sshm remove NOME        # remove uma máquina do arquivo custom
    sshm edit                # abre o arquivo custom no seu editor ($EDITOR)
"""

import csv
import curses
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "sshm"
CUSTOM_FILE = CONFIG_DIR / "machines.json"
SSH_CONFIG_FILE = Path.home() / ".ssh" / "config"


# --------------------------------------------------------------------------
# Modelo de dados
# --------------------------------------------------------------------------

class Machine:
    __slots__ = ("name", "host", "user", "port", "key", "tags", "note", "source")

    def __init__(self, name, host="", user="", port="", key="", tags=None, note="", source="custom"):
        self.name = name
        self.host = host
        self.user = user
        self.port = port
        self.key = key
        self.tags = tags or []
        self.note = note
        self.source = source  # "ssh_config" ou "custom"

    def ssh_target(self):
        """Como conectar: se veio do ~/.ssh/config, usa o alias direto (ssh já lê IdentityFile de lá)."""
        if self.source == "ssh_config":
            return [self.name]
        target = f"{self.user}@{self.host}" if self.user else self.host
        args = []
        if self.key:
            args += ["-i", os.path.expanduser(self.key)]
        if self.port:
            args += ["-p", str(self.port)]
        args.append(target)
        return args

    def searchable(self):
        return " ".join([self.name, self.host, self.user, self.note, " ".join(self.tags)]).lower()

    def display_right(self):
        parts = []
        if self.user or self.host:
            dest = f"{self.user}@{self.host}" if self.user else self.host
            if self.port:
                dest += f":{self.port}"
            if self.key:
                dest += f"  [key:{Path(self.key).name}]"
            parts.append(dest)
        if self.tags:
            parts.append("#" + " #".join(self.tags))
        return "  ".join(parts)


# --------------------------------------------------------------------------
# Carregamento
# --------------------------------------------------------------------------

def ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CUSTOM_FILE.exists():
        CUSTOM_FILE.write_text("[]\n", encoding="utf-8")


def parse_ssh_config():
    """Extrai hosts nomeados (sem wildcard) do ~/.ssh/config."""
    machines = []
    if not SSH_CONFIG_FILE.exists():
        return machines

    current_names = []
    fields = {}

    def flush():
        for name in current_names:
            m = Machine(
                name=name,
                host=fields.get("hostname", ""),
                user=fields.get("user", ""),
                port=fields.get("port", ""),
                note="~/.ssh/config",
                source="ssh_config",
            )
            machines.append(m)

    with open(SSH_CONFIG_FILE, encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = re.split(r"\s+", line, maxsplit=1)
            if len(parts) != 2:
                continue
            key, value = parts[0].lower(), parts[1].strip()
            if key == "host":
                flush()
                current_names = [v for v in value.split() if "*" not in v and "?" not in v]
                fields = {}
            elif key in ("hostname", "user", "port"):
                fields[key] = value
        flush()

    return machines


def load_custom():
    ensure_config_dir()
    try:
        data = json.loads(CUSTOM_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = []
    machines = []
    for item in data:
        machines.append(Machine(
            name=item.get("name", ""),
            host=item.get("host", ""),
            user=item.get("user", ""),
            port=item.get("port", ""),
            key=item.get("key", ""),
            tags=item.get("tags", []),
            note=item.get("note", ""),
            source="custom",
        ))
    return machines


def save_custom(machines):
    data = [
        {
            "name": m.name, "host": m.host, "user": m.user,
            "port": m.port, "key": m.key, "tags": m.tags, "note": m.note,
        }
        for m in machines if m.source == "custom"
    ]
    CUSTOM_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_all():
    """custom tem prioridade sobre ssh_config quando o nome colide."""
    ssh_machines = {m.name: m for m in parse_ssh_config()}
    custom_machines = {m.name: m for m in load_custom()}
    ssh_machines.update(custom_machines)
    return sorted(ssh_machines.values(), key=lambda m: m.name.lower())


# --------------------------------------------------------------------------
# Fuzzy match simples (subsequência com pontuação por proximidade)
# --------------------------------------------------------------------------

def fuzzy_score(query, text):
    query = query.lower()
    if not query:
        return 0
    ti = 0
    score = 0
    consecutive = 0
    for qc in query:
        idx = text.find(qc, ti)
        if idx == -1:
            return None  # não bate
        gap = idx - ti
        consecutive = consecutive + 1 if gap == 0 else 1
        score += 10 - min(gap, 8) + consecutive
        ti = idx + 1
    return score


def filter_machines(machines, query):
    if not query:
        return machines
    scored = []
    for m in machines:
        s = fuzzy_score(query, m.searchable())
        if s is not None:
            scored.append((s, m))
    scored.sort(key=lambda t: -t[0])
    return [m for _, m in scored]


# --------------------------------------------------------------------------
# Interface (curses)
# --------------------------------------------------------------------------

def run_ui(stdscr, machines):
    curses.curs_set(1)
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_CYAN, -1)   # selecionado
    curses.init_pair(2, curses.COLOR_YELLOW, -1)  # tags/host
    curses.init_pair(3, curses.COLOR_GREEN, -1)   # header

    query = ""
    selected = 0
    stdscr.keypad(True)

    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()

        header = " sshm — digite para buscar | ↑↓ navega | Enter conecta | Esc sai "
        stdscr.addnstr(0, 0, header.ljust(w), w, curses.color_pair(3) | curses.A_BOLD)

        prompt = f" > {query}"
        stdscr.addnstr(1, 0, prompt, w)

        filtered = filter_machines(machines, query)
        if selected >= len(filtered):
            selected = max(0, len(filtered) - 1)

        list_start = 3
        max_rows = h - list_start - 1
        if not filtered:
            stdscr.addnstr(list_start, 2, "(nenhuma máquina encontrada)", w - 2)
        else:
            for i, m in enumerate(filtered[:max_rows]):
                y = list_start + i
                left = f"{m.name}"
                right = m.display_right()
                line = f" {left:<24} {right}"
                attr = curses.color_pair(1) | curses.A_REVERSE if i == selected else curses.A_NORMAL
                stdscr.addnstr(y, 0, line.ljust(w), w, attr)

        stdscr.move(1, min(len(prompt), w - 1))
        stdscr.refresh()

        try:
            ch = stdscr.get_wch()
        except curses.error:
            continue

        if ch in ("\x1b",):  # Esc
            return None
        elif ch in ("\n", "\r", curses.KEY_ENTER):
            if filtered:
                return filtered[selected]
        elif ch == curses.KEY_UP:
            selected = max(0, selected - 1)
        elif ch == curses.KEY_DOWN:
            selected = min(max(0, len(filtered) - 1), selected + 1)
        elif ch in ("\x7f", "\b", curses.KEY_BACKSPACE):
            query = query[:-1]
            selected = 0
        elif ch == "\x03":  # Ctrl-C
            return None
        elif isinstance(ch, str) and ch.isprintable():
            query += ch
            selected = 0


def interactive_select():
    machines = load_all()
    if not machines:
        print("Nenhuma máquina cadastrada ainda. Use 'sshm add' para adicionar uma.")
        return None
    return curses.wrapper(run_ui, machines)


# --------------------------------------------------------------------------
# Comandos
# --------------------------------------------------------------------------

def cmd_default():
    machine = interactive_select()
    if machine is None:
        return
    args = machine.ssh_target()
    print(f"\nConectando em {machine.name}...\n")
    os.execvp("ssh", ["ssh"] + args)


def cmd_list():
    machines = load_all()
    if not machines:
        print("Nenhuma máquina cadastrada.")
        return
    for m in machines:
        tag = "[ssh_config]" if m.source == "ssh_config" else "[custom]"
        print(f"{m.name:<20} {m.display_right():<40} {tag}")


def cmd_add():
    ensure_config_dir()
    custom = load_custom()
    print("Cadastrar nova máquina (deixe em branco para pular um campo)")
    name = input("Nome (apelido único): ").strip()
    if not name:
        print("Nome é obrigatório. Abortado.")
        return
    if any(m.name == name for m in custom):
        print(f"Já existe uma máquina custom chamada '{name}'.")
        return
    host = input("Host/IP: ").strip()
    user = input("Usuário: ").strip()
    port = input("Porta (Enter = padrão 22): ").strip()
    key = input("Caminho da chave .pem (Enter = nenhuma, usa senha/agent): ").strip()
    tags = input("Tags (separadas por vírgula, ex: prod,cliente-x): ").strip()
    note = input("Nota/descrição: ").strip()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    custom.append(Machine(name=name, host=host, user=user, port=port, key=key, tags=tag_list, note=note))
    save_custom(custom)
    print(f"Máquina '{name}' adicionada.")


def cmd_import(csv_path, update=False):
    path = Path(csv_path).expanduser()
    if not path.exists():
        print(f"Arquivo não encontrado: {path}")
        sys.exit(1)

    ensure_config_dir()
    custom = load_custom()
    by_name = {m.name: m for m in custom}

    added, updated, skipped, errors = 0, 0, 0, 0

    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            print("CSV vazio ou sem cabeçalho. Colunas esperadas: name,host,user,port,key,tags,note")
            sys.exit(1)

        # normaliza nomes de coluna (case-insensitive, espaços nas pontas)
        normalized_fields = {fn: fn.strip().lower() for fn in reader.fieldnames}
        known = {"name", "host", "user", "port", "key", "tags", "note"}
        unknown = set(normalized_fields.values()) - known
        if unknown:
            print(f"Aviso: colunas desconhecidas ignoradas: {', '.join(sorted(unknown))}")

        for row_num, raw_row in enumerate(reader, start=2):  # linha 1 é o cabeçalho
            row = {normalized_fields[k]: (v or "").strip() for k, v in raw_row.items() if k in normalized_fields}

            name = row.get("name", "")
            host = row.get("host", "")
            if not name:
                print(f"Linha {row_num}: sem 'name', ignorada.")
                errors += 1
                continue
            if not host:
                print(f"Linha {row_num} ('{name}'): sem 'host', ignorada.")
                errors += 1
                continue

            tags_raw = row.get("tags", "")
            tag_list = [t.strip() for t in re.split(r"[;|]", tags_raw) if t.strip()]

            machine = Machine(
                name=name,
                host=host,
                user=row.get("user", ""),
                port=row.get("port", ""),
                key=row.get("key", ""),
                tags=tag_list,
                note=row.get("note", ""),
            )

            if name in by_name:
                if update:
                    by_name[name] = machine
                    updated += 1
                else:
                    print(f"Linha {row_num}: '{name}' já existe, ignorada (use --update para sobrescrever).")
                    skipped += 1
            else:
                by_name[name] = machine
                added += 1

    save_custom(list(by_name.values()))

    print()
    print(f"Importação concluída: {added} adicionada(s), {updated} atualizada(s), "
          f"{skipped} ignorada(s) por já existir, {errors} com erro.")


def cmd_remove(name):
    custom = load_custom()
    new_custom = [m for m in custom if m.name != name]
    if len(new_custom) == len(custom):
        print(f"Nenhuma máquina custom chamada '{name}' encontrada.")
        return
    save_custom(new_custom)
    print(f"Máquina '{name}' removida.")


def cmd_edit():
    ensure_config_dir()
    editor = os.environ.get("EDITOR", "nano")
    if not shutil.which(editor):
        editor = "nano" if shutil.which("nano") else "vi"
    subprocess.run([editor, str(CUSTOM_FILE)])


def main():
    args = sys.argv[1:]
    if not args:
        cmd_default()
    elif args[0] == "list":
        cmd_list()
    elif args[0] == "add":
        cmd_add()
    elif args[0] == "import":
        if len(args) < 2:
            print("Uso: sshm import ARQUIVO.csv [--update]")
            sys.exit(1)
        csv_path = args[1]
        update = "--update" in args[2:] or "-u" in args[2:]
        cmd_import(csv_path, update=update)
    elif args[0] == "remove":
        if len(args) < 2:
            print("Uso: sshm remove NOME")
            sys.exit(1)
        cmd_remove(args[1])
    elif args[0] == "edit":
        cmd_edit()
    elif args[0] in ("-h", "--help", "help"):
        print(__doc__)
    else:
        print(f"Comando desconhecido: {args[0]}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
