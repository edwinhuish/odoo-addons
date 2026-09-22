# Odoo 扩展开发环境搭建总结

> **这份文档写给谁**：第一次接手本仓库、或要在一台新机器上把环境搭起来的团队成员。
> 它讲的是「环境是怎么搭的、为什么这么选、踩过哪些坑」，日常怎么用看 [`DEV_WORKFLOW.md`](DEV_WORKFLOW.md)。
>
> 环境版本：Odoo 19.0（官方镜像 `odoo:19.0`，构建于 2026-09-08）+ PostgreSQL 16 + Python 3.12
> 文档整理时间：2026-09-16（同日的实测结果见 `DEV_WORKFLOW.md` 第 10 节）

---

## 0. 一页速览

| 项目 | 内容 |
|---|---|
| 启动环境 | `task up` → <http://localhost:8069> |
| 网页登录 | `admin` / `admin`（Odoo 建库默认值，我们不干预） |
| 数据库账号 | `odoo` / `odoo` |
| 数据库管理页密码 | `admin`（`odoo.conf` 的 `admin_passwd`，只管建库 / 删库 / 备份） |
| 命令入口 | 仓库根 `Taskfile.yml`（`task --list` 看全部），VS Code 任务面板与之一一对应 |
| 环境实现 | `.dev/`：`compose.yml` + `docker/`（镜像与入口脚本）+ `scripts/`（辅助脚本） |
| 数据位置 | `.dev/data/`（`postgres` = 数据库，`odoo` = filestore）；`task reset` 一键清空 |
| 编辑器 | **不连容器**：VS Code 直接开本机仓库 |

```bash
task up                 # 起环境（首次自动建库 + 装模块 + 演示数据）
task logs               # 跟日志（Odoo 日志走 stdout）
task update -- product_packing      # 升级模块（-u）
task test -- product_image          # 跑测试
task init -- --fresh    # 把 dev 库删掉重建（含演示数据）
task reset              # 连 filestore 一起清空，回到最干净
```

---

## 1. 目标与背景

### 1.1 背景

本仓库是**一堆 Odoo 19 扩展模块**（addons），仓库根目录本身就是 `addons_path` 的一段。模块不能独立运行，
必须有 Odoo + PostgreSQL + 一套数据才能跑起来；而扩展开发的大量时间花在「读 Odoo 核心源码 → 改自己的
`_inherit` / patch → 刷新页面验证」这个循环上。

### 1.2 目标（可验收）

1. **一条命令起环境**，重建镜像/容器后**不需要手工装模块或改配置**；
2. **改代码即时生效**：改 `.py` 自动重启、改 XML/QWeb 刷页面即可；
3. **调试体验在本机**：编辑器、LSP、git、pre-commit 都跑在宿主机（不连远程容器）；
4. **数据可持久、可重置、可拉现场**：能从服务器拉回一份含附件的数据库来复现问题；
5. **与服务器对齐**：Odoo 版本 = 服务器版本（镜像 tag 对齐），依赖 = 服务器补过的包；
6. **可复用**：新人 clone 下来 `task up` 就能开始写代码。

### 1.3 明确不做

- 不做生产部署（生产走 `task deploy` 的 rsync + 服务器侧升级步骤）；
- 不追求「宿主机零依赖」（前提是本机有 Docker）；
- 不支持 Windows（脚本按 Linux/macOS + bash 写）。

---

## 2. 技术方案与架构选型

### 2.1 三个候选方案

| | A：Dev Container（自建镜像 + 容器内开发） | **B：本机编辑 + compose 跑服务（采用）** | C：官方镜像 + 极简 devcontainer |
|---|---|---|---|
| 复杂度 | 高：Dockerfile、postCreate 脚本、uid 对齐、挂载占位、devcontainer.json | **低：一个 compose + 几个脚本** | 中低 |
| 编辑 / LSP | 远端容器（有网络往返） | **本机，零延迟** | 远端容器 |
| 热重载 | ✅ | ✅ | ✅ |
| 踩坑面 | 多（本次几乎每个坑都出自这里） | **少：只剩容器自身的问题** | 少，但仍要远端扩展 |

### 2.2 为什么选 B

扩展开发 **90% 的时间在写 Python / XML**，而这几件事在宿主机上最快：Pylance 索引、`grep`、`git`、
pre-commit。方案 A 的绝大部分复杂度，都来自「要在容器里开发」这个前提：uid 对齐、依赖装在可写层、
root 属主文件、绑定源占位文件……**不连容器，这些问题一个都不存在**。

同时，容器只承担它擅长的事：跑一个**版本固定**的 Odoo + PostgreSQL，并且把数据库和附件放在宿主机目录里。

### 2.3 付出的代价（诚实列出）

- 失去「宿主机零依赖」——需要本机有 docker + compose；
- 不是「环境完全一致」——容器内没有你惯用的 shell 工具链（要什么 `task bash` 进去装）；
- Odoo 日志走 `task logs`（stdout），宿主机上没有日志文件。

### 2.4 方案演进：A 阶段的坑就是最好的经验

最初的方案 A（自建镜像 + VS Code Dev Container）能跑通，但过程里踩了一长串与业务无关的坑，
最后决定降级成 B。这些坑记录下来，避免以后再走回头路：

| A 阶段的坑 | 根因 | 现在的状态 |
|---|---|---|
| 容器起不来：`initdb: invalid locale settings` | 给 db 设了 `zh_CN.UTF-8`，但 `postgres:16` 镜像里没这个 locale | 改成 `C.UTF-8`（B 阶段沿用） |
| Odoo 起不来：`invalid literal for int()` | `odoo.conf` 写了行尾注释，configparser 把 `1  # 注释` 整段当值 | 只写整行注释（B 阶段沿用） |
| `pip install` 的包「没装上」 | VS Code 终端是登录 shell，`/etc/profile` 把 `PATH` 重置回系统 Python，venv 不生效 | B 阶段没有 venv，问题消失 |
| 重建容器后依赖全丢 | 依赖装在容器**可写层**，`compose` 重建容器就回到镜像状态 | 依赖写进 `Dockerfile`，不再需要后置安装 |
| 仓库里出现 root 属主的 `__pycache__` | 容器以 root 跑 | 容器进程身份 = `PUID:PGID`（= 宿主机用户），且编辑器在容器外 |
| 绑定挂载目录缺失 / PGDATA 非空 | Docker 用 root 建绑定源；PGDATA 必须空目录，放 `.gitkeep` 会让 `initdb` 拒绝 | B 阶段用 `task up` 先建目录，`data/postgres` 不放占位文件 |
| 「降权后要执行谁」写成了中转变量 | 两个镜像的官方 entrypoint 路径不同，用变量传容易漏 | 官方 entrypoint 直接写进镜像 `ENTRYPOINT`（见 3.3） |
| `Dockerfile.db` 被当成数据库文件 | `.db` 后缀引发编辑器/工具误判 | 改名 `Dockerfile.pg`（现在用的名字） |

---

## 3. 架构与关键配置

### 3.1 组件与数据流

```text
宿主机（编辑器 / 终端 / 任务）
   │  task up / logs / update / test ...
   ▼
docker compose（.dev/compose.yml）
   ├── odoo19     官方 odoo:19.0 + watchdog / debugpy / 中文字体
   └── odoo19-db  postgres:16（共用同一个降权入口脚本）
        │
        ├─ 绑定挂载：仓库 ──→ /mnt/extra-addons     （改代码即时生效）
        ├─ 绑定挂载：.dev/odoo.conf ──→ /etc/odoo/odoo.conf（只读）
        └─ 绑定挂载：.dev/data/{odoo,postgres}      （运行时可持久化数据）
```

**没有任何具名 volume**（`docker volume ls` 里看不到本项目）：所有需要保留的东西都是宿主机上的普通目录，
随时可以查看、备份、删除。

### 3.2 目录结构

```text
.dev/
|-- compose.yml          # 服务编排（唯一的环境入口）
|-- odoo.conf            # 容器内 Odoo 配置（挂到 /etc/odoo/odoo.conf）
|-- init.yaml            # task init 的安装配置（YAML：modules / addons / langs）
|-- .gitignore           # 本目录的不入库规则（data/、backups/、.env、.cache/）
|-- docker/              # 镜像与容器内入口（构建上下文就是这个子目录）
|   |-- Dockerfile.odoo      # 官方 odoo:19.0 + watchdog / debugpy / fonts-noto-cjk
|   |-- Dockerfile.pg        # 官方 postgres:16 + 共用入口脚本
|   `-- run-as.sh            # 两个镜像共用：按 PUID/PGID 调属主 → 降权 → 执行命令
|-- scripts/             # Taskfile 各任务调用的脚本
|   |-- init-db.sh           # 开发库初始化 / 补齐（init.yaml 的 modules + addons + 语言 + 演示数据）
|   |-- db-sync.sh           # 拉服务器现场数据（含 filestore）/ 备份 / 复制库
|   |-- i18n-reload.sh       # 强制刷新已有译文
|   |-- deploy.sh            # rsync 发布到服务器
|   |-- check_repo.py        # 仓库自检（也用于 pre-commit；含 TODO.md 结构检查）
|   `-- todo_status.py       # 待办池看板：跑 TODO.md 条目自带的「检测：」条件
|-- data/                # 运行时数据（不入库）
`-- backups/             # db-sync.sh 产出的备份 zip（不入库）
```

### 3.3 身份模型：容器 root 起，进程降权到宿主机用户

容器必须**以 root 启动**（否则改不了数据目录属主、切不了身份），但真正跑 Odoo / PostgreSQL 的进程
必须是 `PUID:PGID`（默认 `1000:1000` = 宿主机当前用户），否则容器写进挂载目录的文件会变成 root 属主。

「降权」和「官方入口」是**两段**，直接写进镜像的 `ENTRYPOINT`，不需要任何中转变量：

| 服务 | `ENTRYPOINT`（镜像） | `command`（compose） | 实际执行的命令 |
|---|---|---|---|
| odoo | `run-as.sh` + `/entrypoint.sh` | `odoo --dev=all -d dev` | `run-as.sh /entrypoint.sh odoo --dev=all -d dev` |
| db | `run-as.sh` + `/usr/local/bin/docker-entrypoint.sh` | `postgres -c max_connections=100 …` | `run-as.sh /usr/local/bin/docker-entrypoint.sh postgres -c …` |

`run-as.sh` 只做三件事：**腾位置**（目标 uid 被别的账号占用就把占用者挪走）→ **对齐用户**（建 / 改 `USER`
的 uid:gid）→ **调属主 + 降权**（`CHOWN_SRC` 里的目录归 `PUID:PGID`，然后 `setpriv` 切身份、原样执行命令）。

> 为什么 db 必须保留官方 entrypoint：`initdb`、建用户建库这些事只有它做。odoo 那边保留它则是为了
> 启动前 `wait-for-psql`；它注入 `--db_*` 参数的条件是「配置文件里没写」，我们的 `odoo.conf` 写了，所以它
> 实际只负责等库就绪。

### 3.4 关键配置逐条解释

| 配置 | 值 | 为什么 |
|---|---|---|
| `workers` | `0` | 多进程模式下不挂文件监听，`--dev=all` 的热重载会失效 |
| `max_cron_threads` | `1` | 设 1 才会跑定时任务；不想被 cron 打扰就设 0 |
| `http_interface` | `0.0.0.0` | 绑 `127.0.0.1` 宿主机就访问不到 |
| `db_host/db_port/db_user/db_password` | `db` / `5432` / `odoo` / `odoo` | 写在配置里，官方 entrypoint 就不会再往命令行注入 `--db_*` |
| `ODOO_RC` | `/etc/odoo/odoo.conf` | Odoo 的 CLI 只看 `argv[0]`：`odoo -c conf db dump …` 会被当成 server 命令报错；走环境变量后所有子命令都写成 `odoo db dump …` |
| `admin_passwd` | `admin` | 数据库管理页密码，**不是**网页登录密码 |
| db 的 `LANG/LC_ALL` | `C.UTF-8` | `postgres:16` 只有 `C` / `C.UTF-8` / `en_US.utf8`，写 `zh_CN.UTF-8` 会让 `initdb` 直接失败（中文照样能存能查） |
| db 的 `fsync=off` 等 | `-c` 启动参数 | 本地开发：牺牲崩溃安全换导入速度 |
| `PUID` / `PGID` | `${PUID:-1000}` | 容器内进程身份；宿主机 uid 不是 1000 就在 `.dev/.env` 里覆盖 |
| `CHOWN_SRC` | odoo：`/var/lib/odoo`；db：`/var/lib/postgresql/data` | 要调属主的**绑定源目录本身**；属主已对就跳过（避免每次启动递归 chown 整个 filestore / PGDATA） |
| 构建上下文 | `.dev/docker/` | 只含三个小文件；若设成 `.dev/`，每次 `rebuild` 都要把 77MB 的 `data/` 打包发给守护进程 |
| `--dev=all` | 命令行传 | Odoo 把它标了 `file_exportable=False`，写不进配置文件 |

---

## 4. 实施步骤

### 4.1 一次性准备

```bash
# 装 go-task（单文件二进制，不需要 sudo）
GOBIN="$HOME/.local/bin" go install github.com/go-task/task/v3/cmd/task@latest
export PATH="$HOME/.local/bin:$PATH"        # 建议写进 ~/.bashrc

# 确认 docker 可用（当前用户在 docker 组里）
docker info >/dev/null && echo OK
```

> 仓库与 Odoo 源码**不需要**同级关系：Odoo 源码就在镜像里（见第 6 节「查核心源码」）。

### 4.2 首次启动

```bash
task up
```

这一条命令做了四件事（幂等，重复跑没有副作用）：

1. 起 `db` 服务；
2. `init-db.sh`：库不存在就建库，然后装 `base` + `.dev/init.yaml` 里 `modules` 的模块
   （Odoo 官方 / 第三方，默认 `sale_management` / `purchase` / `stock`）+ `addons` 的本仓库扩展
   （留空 = 自动发现全部）+ 演示数据（`--with-demo`）；
3. 装语言：`.dev/init.yaml` 里 `langs`（默认 `en_US, zh_CN`）缺哪个装哪个（走
   `base.language.install`，译文一并灌进库，首次装中文要几分钟）；
4. 起 `odoo` 服务；
5. 打印登录地址与账号。

首次会拉取 `odoo:19.0` 镜像（镜像较大：落盘约 3GB，本机镜像 `odoo-addons-dev-odoo` 约 3.1GB），
之后建库 + 装模块 + 演示数据也需要几分钟 —— 这段时间不要以为卡死了，`task logs` 能看到进度。

### 4.3 验收（判断环境是否真的可用）

```bash
task ps                                     # 两个容器 Up，db 是 healthy
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8069   # 303（跳登录页）
```

浏览器打开 <http://localhost:8069> → 用 `admin` / `admin` 登录，能看到 Sales / Purchase / Inventory
三个应用，以及本仓库的 9 个模块；产品、客户列表里有演示数据。

### 4.4 日常开发

```bash
task logs                          # 跟日志
task update -- product_packing     # 改了模型字段 / manifest / 静态资源 → 升级模块
task test -- product_image         # 跑测试（先重建 test 库）
task debug                         # 启动并挂调试端口 5678，然后 VS Code 按 F5
task bash / shell / psql           # 进容器 / Odoo shell / 连数据库
task check                         # 提交前自检（也挂在 pre-commit 上）
```

热重载的覆盖范围（细节见 `DEV_WORKFLOW.md` 第 3 节）：改 `.py` 自动原地重启；改视图 XML / QWeb 刷页面即可；
**新增静态资源或改 manifest 必须 `-u`**。

### 4.5 复现现场问题 / 发布

```bash
SSH_HOST=odoo@server REMOTE_DB=prod task pull     # 拉回含 filestore 的备份
task db-sync -- duplicate dev dev_clean           # 折腾前留个干净副本
DEPLOY_HOST=odoo@server task deploy               # 本地验收通过后发布
```

---

## 5. 问题与解决方案（踩坑清单）

### 5.1 数据库

| 现象 | 根因 | 解决 |
|---|---|---|
| `initdb: error: invalid locale settings` | `postgres:16` 里没有 `zh_CN.UTF-8` | `LANG/LC_ALL` 改 `C.UTF-8` |
| 页面 500，日志 `relation "ir_module_module" does not exist` | 用 `odoo -d <库>` 只会建**空库**，不装任何模块 | `init-db.sh` 负责建库并装模块；`task init` 手工补 |
| 演示数据装不上（`product_template = 0`） | **Odoo 19 起 CLI 默认不装演示数据**（`--without-demo` 只是保留的取反别名） | 安装时显式传 `--with-demo` |
| 已装好的库想补演示数据，补不进去 | 演示数据只在「模块安装那一刻」灌入，事后无法追加 | 只能 `task init -- --fresh` 删库重建 |
| `PGDATA` 初始化失败 | `data/postgres` 放了 `.gitkeep` 占位文件，`initdb` 要求目录为空 | 该目录不放占位文件（缺失时 Docker 建成 root 也无妨，db 容器接管属主） |

### 5.2 容器与权限

| 现象 | 根因 | 解决 |
|---|---|---|
| 容器写不进挂载目录 | 目录属主不是 `PUID:PGID` | `run-as.sh` 启动时纠正；宿主机 uid 不是 1000 就在 `.dev/.env` 设 `PUID/PGID` |
| 每次启动都在递归 chown（大库很慢） | 无条件 `chown -R` | 属主已对就跳过；**判断目标必须是绑定源目录本身**（写上一级镜像层目录会次次判不等） |
| 宿主机 `rm -rf` 删不掉数据目录 | 本机 `rm` 有「批量删除保护」（>500 文件直接拒绝），且属主可能不是当前用户 | 走一次性容器删（`task reset` / `task odoo-src-clean` 都是这个套路） |
| `.dev/data` 里出现 root 属主的文件 | 早期容器以 root 跑 | 现在进程身份是 `PUID:PGID`；`task bash` 也显式带 `-u $(id -u):$(id -g)` |

### 5.3 Odoo 行为

| 现象 | 根因 | 解决 |
|---|---|---|
| `int() 报 invalid literal` | `odoo.conf` 写了行尾注释，configparser 把 `1  # 注释` 整段当值 | 说明只写整行注释（该文件自己的坑） |
| `odoo -c conf db dump …` 报 `unrecognized parameters` | Odoo 的 CLI 分发只看 `argv[0]` | 配置走 `ODOO_RC` 环境变量，子命令写成 `odoo db dump …` |
| 改了密码却登不上 / 以为 `admin_passwd` 是登录密码 | `admin_passwd` 只管数据库管理页；网页登录 `admin/admin` 是建库时写进 `res_users` 的默认值 | 两者分清：登录密码在 `/web/reset_password` 或 `odoo shell` 里改 |
| 单步进不去核心代码 / 断点不生效 | 容器路径与本地路径对不上 | `launch.json` 的 `pathMappings`（仓库 + `task odoo-src` 导出的核心源码） |
| 改了静态资源没生效 | manifest 的 `assets` 变更需要升级模块 | `task update -- <模块>` |

### 5.4 工具链

| 现象 | 根因 | 解决 |
|---|---|---|
| `task update product_image` 报 `Task "product_image" does not exist` | task 把裸参数当任务名 | 带参数必须用 `--`：`task update -- product_image` |
| `task restart db` 报同样的错 | 同上 | `task restart -- db` |
| `docker compose config --images odoo` 返回了两行 | 这个位置的「服务名」参数会被忽略 | 从 `config --format json` 的工程名推导镜像名（`task odoo-src` 用到） |
| 每次 `rebuild` 都很慢 | 构建上下文含 `data/`（77MB） | 构建上下文设成 `.dev/docker/` |
| VS Code 索引卡顿 | 导出的核心源码有 1.7 万个文件 | `files/search/watcherExclude` 排除 `.dev/.cache` |

---

## 6. 最佳实践与注意事项

### 6.1 命令与脚本

- **命令只在 `Taskfile.yml`**：不要在文档里散落 `docker compose …` 长命令；脚本放 `.dev/scripts/`，
  由任务调用。这样「文档 → 命令 → 实现」三条链路始终一致，改一处即可。
- 脚本一律用**绝对路径 / 显式路径推导**（`HERE=$(cd "$(dirname "$0")" && pwd)`），不要依赖调用者所在目录。
- 幂等优先：`task up` / `task init` 可以随便重复跑。

### 6.2 数据与权限

- 数据放宿主机目录（`data/`、`backups/`），**不入库**；重置用 `task reset`，不要手工删。
- 绑定源目录必须属于**当前用户**：`task up` 用当前用户先建目录，容器再对齐属主。
- 容器内的进程身份与宿主机用户一致，所以不会在仓库里留下 root 属主文件。

### 6.3 版本与依赖

- 镜像 tag = 服务器版本（当前 `odoo:19.0`）。**改 tag 后要做三件事**：`task rebuild`、重跑 `task odoo-src`
  刷新核心源码副本、`task init` 让库跟着升级。
- 服务器额外补过的 pip 包，写进 `.dev/docker/Dockerfile.odoo`，不要 `pip install` 完就算
  （容器重建就丢）。

### 6.4 核心源码怎么查（重要）

Odoo 源码**就在镜像里**，不要另外 clone 一份（避免版本对不上、也省掉 1.4GB 下载）：

```bash
docker exec odoo19 grep -rn "def _compute_display_name" /usr/lib/python3/dist-packages/odoo/orm/
task bash          # 进容器里看：/usr/lib/python3/dist-packages/{odoo,addons}
task odoo-src      # 想在编辑器里跳转/打断点，就导出核心 .py 到 .dev/.cache/odoo-src
```

### 6.5 模块开发约定（摘要）

- 不修改 Odoo 核心源码，一律 `_inherit` 或 patch；继承视图用 `t-inherit` + extension；
- 模块源语言是**英文**，中文只出现在 `i18n/zh_CN.po` 的 `msgstr` 里；
- 提交前跑 `task check`（已挂 pre-commit）：po 重复 msgid、manifest 与 `shortdesc` 一致性、XML 合法性、JS 语法。

---

## 7. 后续优化方向

| 方向 | 收益 | 备注 |
|---|---|---|
| `task doctor`：一键自检（docker 可用、端口占用、属主、模块是否齐全、lang 是否 `C.UTF-8`） | 新人排障时间从「翻文档」变成「跑一条命令」 | 把第 5 节的坑变成检查项 |
| CI（GitHub Actions）里跑 `task check` + `task test`，复用同一份 compose | 提交即验证，不依赖本地环境 | 需要一套无 GUI 的最小 compose |
| 首次启动耗时统计 + 进度提示（装模块可能几分钟） | 新人不至于以为卡死 | 可选 |
| `task reset` 后自动 `task init`（少一步） | 少记一条命令 | 注意别顺手把 dev 库删了 |
| 把 `.dev/.cache/odoo-src` 换成「attach 容器」零拷贝方案 | 省 161MB 磁盘 | 前提是团队接受在容器里读核心源码 |
| 多版本并行（`git worktree` + `.dev/.env`）包装成脚本 | 同时维护两条分支的环境 | 机制已具备，只是没包装 |

---

## 8. 附：命令速查

| 目的 | 命令 |
|---|---|
| 起 / 停 / 重启 | `task up` / `task down` / `task restart -- odoo` |
| 重建镜像（改了 `docker/Dockerfile*`） | `task rebuild` |
| 清空重来（库 + filestore） | `task reset && task up` |
| 只重建库（保留 filestore） | `task init -- --fresh` |
| 升级 / 安装模块 | `task update -- <模块...>` / `task install -- <模块...>` |
| 跑测试 | `task test -- <模块> [--test-tags=...]` |
| 调试 | `task debug` → VS Code F5 |
| 进容器 / Odoo shell / psql | `task bash` / `task shell` / `task psql` |
| 任意 odoo 子命令 | `task odoo -- db dump dev /tmp/x.zip` |
| 拉服务器数据 / 备份 / 复制库 | `task pull` / `task db-sync -- dump` / `task db-sync -- duplicate dev dev_clean` |
| 刷新译文 | `task i18n -- zh_CN <模块...>` |
| 导出核心源码 / 删掉副本 | `task odoo-src` / `task odoo-src-clean` |
| 仓库自检 / 发布 | `task check` / `DEPLOY_HOST=... task deploy` |
