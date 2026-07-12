# sshm

Seletor rápido de máquinas SSH pelo terminal, com busca fuzzy em tempo real
(estilo fzf). Escrito em Python usando só a biblioteca padrão — sem
dependências para instalar.

```
sshm — digite para buscar | ↑↓ navega | Enter conecta | Esc sai
 > prod
  prod-web1     deploy@10.0.1.10:22
  prod-db1      admin@10.0.1.20
```

## Instalação (Linux)

```bash
git clone <url-do-seu-repo> sshm
cd sshm
./install.sh
```

O instalador:
- verifica se você tem `python3` (3.6+), o módulo `curses` e o cliente `ssh`;
- copia o script para `~/.local/bin/sshm` e dá permissão de execução;
- cria `~/.config/sshm/machines.json` (se ainda não existir);
- adiciona `~/.local/bin` ao seu `PATH`, detectando automaticamente
  **bash**, **zsh** ou **fish** e editando o arquivo de config certo em
  cada caso (`.bashrc`, `.zshrc` ou `~/.config/fish/config.fish` com
  `fish_add_path`).

Rodar `./install.sh` de novo no futuro atualiza a instalação sem apagar suas
máquinas cadastradas.

### Desinstalar

```bash
./uninstall.sh
```

## Uso

```bash
sshm              # abre o menu interativo de busca e conexão
sshm add          # cadastra uma nova máquina
sshm import ARQUIVO.csv [--update]   # importa máquinas em lote via CSV
sshm list         # lista todas as máquinas (ssh config + custom)
sshm remove NOME  # remove uma máquina custom
sshm edit         # abre o machines.json no seu editor ($EDITOR)
```

No menu interativo:
- Digite para filtrar por nome, host, usuário, tag ou nota.
- `↑` / `↓` navegam pela lista filtrada.
- `Enter` conecta via `ssh` na máquina selecionada.
- `Esc` ou `Ctrl+C` sai sem conectar.

## De onde vêm as máquinas

O `sshm` combina automaticamente duas fontes:

1. **`~/.ssh/config`** — todo `Host` nomeado (sem `*`/`?`) já aparece na
   lista, sem precisar cadastrar de novo. Ele lê `HostName`, `User` e `Port`,
   e delega a conexão pro `ssh` (então `IdentityFile`, `ProxyJump`, etc. do
   seu config são respeitados normalmente).
2. **`~/.config/sshm/machines.json`** — máquinas cadastradas por você via
   `sshm add`, com campos extras como `tags`, `note` e `key` (chave `.pem`)
   para facilitar a busca e a conexão.

Se um nome existir nos dois lugares, a versão do `machines.json` tem
prioridade.

### Exemplo de machines.json

```json
[
  {
    "name": "aws-ec2-1",
    "host": "54.10.20.30",
    "user": "ec2-user",
    "port": "22",
    "key": "~/.ssh/keys/aws-prod.pem",
    "tags": ["aws", "ec2"],
    "note": "Servidor AWS"
  }
]
```

> ⚠️ Esse arquivo fica em `~/.config/sshm/machines.json`, fora do repositório
> git, e o `.gitignore` já bloqueia qualquer `machines.json` que acabe
> aparecendo dentro do projeto — assim você não corre o risco de commitar
> IP/usuário/caminho de chave da sua empresa.

## Importação em lote via CSV

Se você já tem suas máquinas numa planilha (ou consegue exportar de algum
inventário interno), pode importar tudo de uma vez:

```bash
sshm import maquinas.csv
```

Formato esperado (veja `examples/machines.example.csv`):

```csv
name,host,user,port,key,tags,note
prod-web1,10.0.1.10,deploy,22,,prod;web,Servidor web principal
prod-db1,10.0.1.20,admin,,,prod;db,
aws-ec2-1,54.10.20.30,ec2-user,,~/.ssh/keys/aws-prod.pem,aws;ec2,Servidor AWS
```

Regras:
- Colunas `host` e `user`, `port`, `key`, `tags`, `note` são todas opcionais,
  **exceto `name` e `host`**, que são obrigatórias — linhas sem elas são
  ignoradas (com aviso) e não interrompem o resto da importação.
- Múltiplas tags no mesmo campo: separe com `;` ou `|` (ex: `prod;web`).
- Por padrão, se uma máquina do CSV já existir (mesmo `name`), ela é
  **ignorada** para não sobrescrever algo que você editou manualmente.
  Use `--update` (ou `-u`) para sobrescrever:
  ```bash
  sshm import maquinas.csv --update
  ```
- No fim, o comando mostra um resumo: quantas foram adicionadas, atualizadas,
  ignoradas por já existir e quantas deram erro.

## Chave PEM (identity file)

- **Máquina no `~/.ssh/config`**: não precisa fazer nada, o `ssh` já lê o
  `IdentityFile` de lá.
- **Máquina custom**: `sshm add` pergunta o caminho da chave e monta o
  comando com `-i` automaticamente (equivalente a
  `ssh -i ~/.ssh/keys/chave.pem usuario@host`). Aceita `~` no caminho.

## Estrutura do projeto

```
sshm/
├── sshm.py                       # script principal
├── install.sh                    # instalador Linux
├── uninstall.sh                  # desinstalador
├── examples/machines.example.json
├── LICENSE
└── README.md
```

## Ideias de evolução

- Suporte a `ProxyJump` / bastion explícito no `machines.json`.
- Copiar `scp`/`rsync` rápido para a máquina selecionada.
- Histórico de "últimas máquinas acessadas" no topo da lista.
- Integração com um inventário central da empresa.
