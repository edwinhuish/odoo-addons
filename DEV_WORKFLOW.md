# 本地开发工作流（`.dev/`）

> 本文是**日常操作手册**（怎么跑、怎么调、怎么拉数据）。
> 环境是怎么搭起来的、方案为什么这么选、踩过哪些坑 → 见 [`DEV_ENV_SETUP.md`](DEV_ENV_SETUP.md)。

给外贸 SOHO 自研 addons 的一套**轻量**开发环境：Odoo 19 + PostgreSQL 跑在容器里，
**编辑器和调试都在宿主机**——不连远程容器，改完即生效。

```bash
task                                  # 列出所有命令
task up                               # 启动 → http://localhost:8069（首次自动建库装 base）
task logs                             # 跟日志
task update -- product_image          # 升级模块（注意参数前要加 --）
task down                             # 停止（数据保留）
```

仓库根目录的 **`Taskfile.yml` 是唯一命令入口**（[go-task](https://taskfile.dev)）：
`up / down / update / test / pull / check / deploy ...`，VS Code 任务面板（`Ctrl+Shift+B`）与它一一对应。

装一次 `task`（单文件二进制，不需要 sudo）：

```bash
# 有 go 的话（推荐）
GOBIN="$HOME/.local/bin" go install github.com/go-task/task/v3/cmd/task@latest
# 或者官方脚本 / 包管理器
# sh -c "$(curl -fsSL https://taskfile.dev/install.sh)" -- -d -b ~/.local/bin
# sudo snap install task --classic
```

`~/.local/bin` 记得在 `PATH` 里（`export PATH="$HOME/.local/bin:$PATH"` 写进 shell rc）；
`.vscode/tasks.json` 已经自己补了这个 PATH，没配也能用任务面板。

入口与实现分工：仓库根的 `Taskfile.yml` 负责调度，`.dev/` 是具体实现。

```text
.dev/
|-- compose.yml              # Odoo + PostgreSQL 编排（唯一入口；数据绑定挂载到 .dev/data）
|-- odoo.conf                # 容器内配置（挂到 /etc/odoo/odoo.conf）
|-- .gitignore               # 本目录的不入库规则（data/、backups/、.env、.cache/）
|-- docker/                  # 镜像与容器内入口（构建上下文就是这个子目录）
|   |-- Dockerfile.odoo      #   odoo 镜像：官方 odoo:19.0 + watchdog / debugpy / 中文字体
|   |-- Dockerfile.pg        #   pg 镜像：官方 postgres:16 + 共用入口脚本（支持 PUID/PGID）
|   `-- run-as.sh            #   两个镜像共用：按 PUID/PGID 改属主 + 降权，然后执行传入的命令
|-- scripts/                 # Taskfile 各任务调用的脚本
|   |-- db-sync.sh           #   拉服务器现场数据（含 filestore）
|   |-- i18n-reload.sh       #   强制刷新已有译文（-u 不覆盖旧值）
|   |-- deploy.sh            #   rsync 发布到服务器
|   |-- check_repo.py        #   仓库自检（也用于 pre-commit；含 TODO.md 结构检查）
|   `-- todo_status.py       #   待办池看板：跑 TODO.md 条目自带的「检测：」条件
|-- data/                    # 运行时数据（不入库）：data/odoo = filestore、data/postgres = 数据库
`-- backups/                 # db-sync.sh 的备份 zip（不入库）
```

---

## 1. 为什么这么轻

- **不连远程容器**：文件在宿主机上，Pylance / pre-commit / git 都是本机速度，没有远程往返。
- **不维护自建镜像**：基础镜像是官方 `odoo:19.0`（已含 Odoo、wkhtmltopdf、psql 客户端），
  `.dev/docker/Dockerfile.odoo` 只有 4 步，补三样：`watchdog`（热重载）、`debugpy`（断点，并包出
  `/usr/local/bin/odoo-debug`）、`fonts-noto-cjk`（中文 PDF）。
- **容器进程身份 = 宿主机用户（`PUID` / `PGID`）**：镜像以 root 启动，`.dev/docker/run-as.sh` 先把
  数据目录属主改成 `PUID:PGID`、再用 `setpriv` 降权，然后才跑 Odoo。所以往挂载的仓库里写文件
  （`__pycache__`、导出物）不会 Permission denied、也不会留下 root 属主文件；**改 PUID/PGID 是运行时的
  事，`task up` 就生效，不用重建镜像**（这是 LinuxServer.io 镜像的通行做法）。
- **数据直接挂在 `.dev/data/`，不用任何具名 volume**：`.dev/data/odoo`（filestore / sessions）与
  `.dev/data/postgres`（数据库）都是宿主机上的普通目录，属主就是你，随时可看、可备份、可 `rm`；
  `task reset` 一键清空。`task up` 会在启动前用当前用户建好这两个目录。

代价（接受即可）：

- 容器里没有你的 shell 工具链（zsh / fzf 等），要什么自己 `task bash` 进去装。
- Odoo 日志走 `task logs`（官方镜像前台运行），不再有本地日志文件。
- 想跑 PDF 报表以外的东西（比如 `wkhtmltopdf` 的手工调试），得进容器。

---

## 2. 容器里的固定路径

| 容器内路径 | 来源 | 说明 |
|-----------|------|------|
| `/mnt/extra-addons` | 绑定挂载**本仓库根目录** | `addons_path` 的一段；改代码即时生效 |
| `/etc/odoo/odoo.conf` | 绑定挂载 `.dev/odoo.conf`（只读） | 容器内配置（用 `ODOO_RC` 指给 Odoo） |
| `/var/lib/odoo` | 绑定挂载 **`.dev/data/odoo`** | filestore / sessions（图片、附件） |
| `/var/lib/postgresql/data` | 绑定挂载 **`.dev/data/postgres`** | 数据库（删掉即重置；initdb 要求目录为空） |
| `/usr/local/bin/odoo-debug` | 镜像内 | `debugpy` 包装脚本，固定路径省得记 |
| `/usr/lib/python3/dist-packages/odoo` | 镜像内 | **Odoo 核心源码**（`orm/`、`fields/`、`http.py`、标准模块 `addons/`） |
| `/usr/lib/python3/dist-packages/addons` | 镜像内 | 另一份 addons 包（`account`、`sale` …） |

**没有任何具名 volume**（`docker volume ls` 里看不到本项目），运行时可持久化的东西都在 `.dev/data/` 下。
目录由 `task up` 用当前用户创建，容器里的 `run-as.sh` 再把 `CHOWN_SRC` 列出的目录属主对齐到 `PUID:PGID`（属主已对就跳过）。

Odoo 核心 addons 由官方镜像自动加入，`odoo.conf` 里**不用**写；仓库里的模块优先级高于核心。

### 读 Odoo 核心源码：就在容器里，不要另存一份

仓库**不含** Odoo 源码，也不需要 `../odoo` 那样的一份本地克隆——镜像里那份才是运行时真正加载的
（`odoo.conf` 的 `addons_path` 指向它），版本与本地运行/服务器一致：

```bash
docker exec odoo19 grep -rn "def _compute_display_name" /usr/lib/python3/dist-packages/odoo/orm/
docker exec odoo19 sed -n '1,60p' /usr/lib/python3/dist-packages/odoo/orm/models.py
task bash        # 要连着看多处 / 用 less，就进容器里查
```

要在**编辑器里跳转、打断点**（Pylance / debugpy）：跑一次 `task odoo-src`，把镜像里的核心 `.py`
导出到 `.dev/.cache/odoo-src`（约 160MB，从镜像里取、不联网、已 gitignore；不想要了 `task odoo-src-clean`，
改了镜像 tag 重跑一次即可刷新）。`.vscode/settings.json` 的 `python.analysis.extraPaths` 与
`launch.json` 的 `pathMappings` 都已指向该目录，所以单步进核心代码会落到本地副本上。
XML / QWeb 模板与静态资源仍按上面的方式在容器里查。

> 这份副本是**从镜像里拷出来的**，不是下载：它跟本地/服务器运行时用的源码是同一份（同一个 tag），
> 所以不会再出现「本机 clone 的 odoo 和镜像里的版本对不上」这类问题。

### 开发库的初始状态（重建后自动到位）

`task up` 会检查 `dev` 库并**自动补齐**，所以重建镜像/容器后不需要再手工装一遍模块：

| 项 | 值 |
|----|-----|
| 网页登录 | `admin` / `admin`（<http://localhost:8069>）—— Odoo 建库默认值，脚本与配置都不去动它 |
| 数据库账号 | `odoo` / `odoo`（compose 的 `POSTGRES_USER` / `POSTGRES_PASSWORD`） |
| 模块 | **`.dev/init.yaml`**（`modules`，默认 `sale_management` Sales / `purchase` Purchase / `stock` Inventory） |
| 仓库扩展 | `.dev/init.yaml` 的 `addons`；**留空（`addons: []`）= 自动发现全部**（新模块不用登记） |
| 语言 | `en_US`（English US）+ `zh_CN`（Chinese, Simplified）：缺哪个装哪个，**连带把译文灌进库** |
| 演示数据 | 随首次安装加载（下面那条注意点） |
| 批次 | 演示数据写死的 `tracking=lot` 会在装完后被**清回 `none`**（下面那条注意点），自带 `stock.lot` 一并删掉 |
| 数据库管理页 | `admin` —— `odoo.conf` 的 `admin_passwd`，只管 `/web/database/manager`（建库 / 删库 / 备份），**不是**网页登录密码 |

实现是 `.dev/scripts/init-db.sh`（幂等，跑多少遍都一样）：

```bash
task init                 # 补齐：只装缺失模块 / 语言，不动已有数据
task init -- --fresh      # 删掉 dev 库重建（演示数据只有这一次机会）
task reset && task up     # 连 filestore 一起从零来过（最彻底）
```

两个清单分工：`modules` 写 **Odoo 官方 / 第三方模块**，`addons` 写**本仓库扩展**（模块目录名）。
改完再跑 `task init` 即可 —— 不用重启容器、不用删库、不影响已有数据。

清单在 **`.dev/init.yaml`**（YAML，与 `compose.yml` 同风格），三个顶层 key：

```yaml
# --- Odoo 官方 / 第三方模块 -------------------------------------------------
modules:
  - sale_management
  - purchase
  - stock

# --- 本仓库扩展（自研模块，名字 = 模块目录名）---------------------------------
addons:
  - product_card_view
  - product_image
  - product_packing
  - product_reference
  - product_variant_conversion
  - sale_order_no
  - sale_product_hover
  - web_image_paste
  - web_multi_tabs

# --- 语言（行内数组，值少时紧凑）---------------------------------------------
langs: [en_US, zh_CN]
```

- 块列表（`- xxx` 一行一个）与行内数组（`[a, b]`）等价，注释随便加。
- 解析用宿主机的 `python3` + PyYAML；宿主机没有时自动退回 **Odoo 容器里的 python3**（镜像自带 PyYAML，
  只是每次解析要起一次容器，慢几秒）。

- 只写**模块技术名**（`sale_management` ✅，写 `Sales` 这种应用名装不上）。
  Odoo 对认不出的模块名只会在日志打 `invalid module names, ignored`、**不报错**，所以脚本装完会复查
  一次并警告「这些模块没装上」。
- `addons` 留空（写成 `addons: []`，或整项删掉）→ 自动发现全部，新模块不用登记；
  想只装其中几个就列出来。写错名字时脚本会直接警告并打印仓库里实际有的扩展。
  **删掉某一项不会卸载已装的模块**，卸载请用网页「应用」。
- 行尾 / 整行注释都允许（`#` 或 `;`），整行注释可夹在列表中间；**项之间留空行**用来结束上一项的续行。

**语言**（`[init] langs = en_US, zh_CN`）同样按「缺哪个装哪个」补齐，走 Odoo 自己的加载路径（等价于网页
「设置 → 语言 → 添加语言」）：不只是把语言激活，还会把各模块 `i18n/<lang>.po` 与官方译文灌进库，
所以装完就能在用户偏好里直接切中文界面，不需要再跑一遍 `task i18n`。首次装语言要几分钟
（`odoo shell` 里逐个导入术语），日志会打印进度，别打断。想临时换要装的语言：
`DEV_LANGS=en_US,zh_CN,zh_TW task init`（环境变量优先于配置文件）。

> **演示数据是「模块安装那一刻」灌进去的**：Odoo 19 起 CLI 默认**不装**演示数据，脚本里显式传了
> `--with-demo`（老的 `--without-demo` 只是保留的取反别名）。所以已经装好模块的库补不了演示数据，
> 只能 `--fresh` 重建。
>
> `task rebuild`（重建镜像/容器）**不会**碰数据库：库与 filestore 都在 `.dev/data/` 的绑定挂载里。
>
> **演示数据里的批次**：`stock` / `product` 的 demo 数据会把 Flipover / Drawer / Cable Management Box
> 等产品设成 `tracking='lot'` 并塞 `stock.lot`，看上去像「批次功能被打开了」。`init-db.sh` 末尾会
> 顺手把这几个产品（在库数量归零 → 删批次 → `tracking='none'`），只认带 `ir.model.data` 的演示产品
> 不动自录数据；想留着练批次流程就 `DEV_KEEP_DEMO_LOTS=1 task init`。

容器进程以 **`PUID` / `PGID`**（默认 1000:1000）运行。`.dev/docker/run-as.sh` 认五个运行时变量
——`PUID`、`PGID`、`USER`（目标用户名，默认 `odoo`；要换名字在 `.dev/.env` 里设 **`ODOO_USER`**，
别设 `USER`，原因见第 9 节）、`HOME`（容器侧的家目录）、`CHOWN_SRC`（要归到 `PUID:PGID` 的
绑定源目录，空格分隔，默认 `$HOME`）——启动时依次做三件事：

1. **腾位 + 调用户**：`PUID`/`PGID` 若已被别的账号占用（如基础镜像的 `ubuntu` 占着 1000），
   先把占用者挪到第一个空闲 id（从 2000 起找）腾出位置；然后 `USER` 不存在就按 `PUID:PGID` 新建，
   已存在就把它的 uid/gid 改成 `PUID`/`PGID`（值已一致则整段跳过）。**uid/gid 0（root）例外**：
   不挪 root，只能共用，日志会告警。
2. **调属主**：对 `CHOWN_SRC` 里每个目录 `chown -R PUID:PGID`（odoo 是 `/var/lib/odoo`，
   pg 是 `/var/lib/postgresql/data`，都写在 compose 的环境变量里）。这两个位置必须写成
   **绑定挂载的宿主机源目录本身**（= `.dev/data/odoo`、`.dev/data/postgres`）：
   **顶层目录属主已经对了就整段跳过**（`chown -R` 会递归遍历 filestore / PGDATA，数据一大每次启动
   就白等），而这个判断只有在属主被持久化到宿主机时才成立。写成镜像层目录（比如
   pg 的上一级 `/var/lib/postgresql`）会每次都判不等 —— 每次重建容器属主都回到 `postgres(999)`。
   所以日志里通常看不到 chown，只有属主不对时才打印一行并递归纠正。
   它**不碰** `/mnt/extra-addons`——仓库本来就是你的，`PUID` 与宿主机 uid 不一致时才需要改
   `.dev/.env` 里的 `PUID`/`PGID`，否则写仓库会 Permission denied。
3. **降权**：`setpriv` 切到 `PUID:PGID`，然后原样执行传进来的命令。
   官方 entrypoint 不由这个脚本转发，而是写在镜像 `ENTRYPOINT` 的第二段
   （`Dockerfile.odoo` 里是 `/entrypoint.sh`，`Dockerfile.pg` 里是 `/usr/local/bin/docker-entrypoint.sh`），
   拼出来的整条命令就是「降权脚本 + 官方入口 + compose 的 command」。

所以 `.dev/data/odoo`、`.dev/data/postgres` 的属主都是你，容器里写文件不会改属主，宿主机上也能直接读写删；
`/mnt/extra-addons`（仓库）本来就是你自己的目录，`PUID` 与宿主机一致即可直接写。
**改 `PUID`/`PGID`（或 `USER`）只要 `task up` 重建容器，不需要 `task rebuild`。**

`.dev/.env` 会被 compose 自动加载（已验证），用来做**并行实例**与身份的本地覆盖，不必改被跟踪的
`.dev/compose.yml`：`COMPOSE_PROJECT_NAME` / `ODOO_CONTAINER` / `DB_CONTAINER` /
`ODOO_HTTP_PORT` / `ODOO_DEBUG_PORT` / `PG_PORT` / `PUID` / `PGID`
（见第 8 节「多版本并行」）。

---

## 3. 热重载到底覆盖到什么程度

`--dev=all` 在 Odoo 19 里等价于四项：`access,qweb,reload,xml`（`odoo/tools/config.py:29`）：

- `reload`：`watchdog` 监听各 `addons_path`，`.py` 变化即 **`os.execve` 原地重启进程**
  （`odoo/service/server.py`、`tools/misc.py:stripped_sys_argv`）——所以要装 `watchdog`，否则这个特性静默降级
- `xml`：视图 `arch` 每次请求直接读 XML 文件（`odoo/addons/base/models/ir_ui_view.py`），
  前提是该视图没在界面里被改过（`arch_updated` 为假）
- `qweb`：QWeb 编译报错输出带行号的编译结果（关闭模板缓存）
- `access`：权限错误打印完整 traceback

> `--dev` 在 Odoo 里是 `file_exportable=False`，**写不进 `odoo.conf`**，只能走命令行；
> 所以启动统一用 `.dev/compose.yml` 的 `command` 或 `.vscode/tasks.json`，别自己拼命令。

| 改动内容 | 需要做什么 | 原因 |
|----------|-----------|------|
| 模型 / 控制器 / widget Python | **无需操作**，日志出现 restart 即可 | `reload` 监听 addons_path |
| 已存在的视图 XML | 刷新浏览器 | `xml` dev 模式直读文件 |
| `static/src/xml` QWeb 模板 | 刷新浏览器（不行就 Ctrl+Shift+R） | 模板缓存被关闭 |
| `static/src/js|scss`（**已在 manifest assets 里**） | 刷新浏览器；必要时清浏览器缓存 | 资产指纹可能被缓存 |
| **新增** static 文件、改 manifest 的 `assets` | 任务「Odoo：升级模块（-u）」 | assets 只在安装/升级时注册（改前端最容易踩） |
| manifest `version` / `depends` / `data` | 任务「Odoo：升级模块（-u）」 | 都在安装/升级阶段读 |
| `security/ir.model.access.csv`、新增模型、新增字段 | 任务「Odoo：升级模块（-u）」 | 元数据要进库 |
| `i18n/*.po` 后端条目（模型名/字段标签/help/selection/约束消息） | 任务「Odoo：升级模块（-u）」 | po 在 `-u` 时导入 |
| `i18n/*.po` 里**已在库的译文**改动 | `task i18n -- zh_CN <模块>` | 记录 `noupdate=True`，`-u` 不覆盖（AGENTS.md 4.8） |
| 前端术语（JS `_t` / QWeb 文本）改译文 | `-u` 之后**强刷浏览器** | 前端术语有浏览器缓存（AGENTS.md 4.7） |
| `migrations/` 迁移脚本 | 升级到目标版本触发，或重装该模块 | 只在版本变化时执行 |

一句话：**80% 的日常改动（Python / 视图 / QWeb）不需要任何命令**，剩下 20% 走 `-u`。

---

## 4. 常用命令与 VS Code 任务

命令都走 `task`（任务面板里的 label 与之一一对应）：

| 任务 | 命令 |
|------|------|
| Odoo：启动 / 停止 / 重启 | `task up` / `down` / `restart`（改了 `.dev/docker/Dockerfile*` 用 `task rebuild`） |
| 开发库：补齐 / 删库重建 | `task init` / `task init -- --fresh`（模块 + 演示数据 + `admin/admin`，见第 2 节） |
| Odoo：日志（tail -f） | `task logs`（日志走 stdout，不再有本地日志文件） |
| Odoo：升级模块（-u） | `task update -- <模块...>`（自动：停服务 → 升级 → 起服务） |
| Odoo：安装模块（-i） | `task install -- <模块...>` |
| Odoo：跑测试 | `task test -- <模块>`（先重建 `test` 库；默认只跑这几个模块的 tag，不跑 base 全套，要自定义就自己传 `--test-tags=`） |
| Odoo：交互式 shell / 进容器 / psql | `task shell` / `bash` / `psql` |
| Odoo：导出核心源码（给编辑器跳转） | `task odoo-src`（从镜像取，约 160MB，落在 `.dev/.cache/odoo-src`） |
| Odoo：调试启动 | `task debug`（挂 5678，再按 F5 attach） |
| Odoo：任意子命令 | `task odoo -- db dump dev /tmp/x.zip`（**子命令必须写在最前面**，见第 9 节） |
| 数据：拉服务器数据 | `SSH_HOST=... REMOTE_DB=prod task pull` |
| 数据：复制 / 备份 / 装载 | `task db-sync -- duplicate dev dev_clean`、`task db-sync -- dump [库] [out.zip]`、`task db-sync -- load <dump.zip> [库]` |
| 译文：强制刷新 zh_CN | `task i18n -- zh_CN <模块...>` |
| 自检：仓库检查 | `task check`（`task check -- --strict` 把警告也算失败；含 TODO.md 结构：条目格式 / ID / 模块目录 / 文档链接 / 检测条件语法） |
| 需求：待办池看板 | `task todo`（跑条目自带的「检测：」条件，报「可能已实现 / 未实现」；`task todo -- --all` 连归档一起列，`task todo -- T-017` 看单条） |
| 发布 / 重置一切 | `DEPLOY_HOST=... task deploy` / `task reset`（清空 `.dev/data`，等于重置库与附件） |

`Taskfile.yml` 只是调度层：真正干活的是 `.dev/compose.yml`（Odoo + PostgreSQL）
与 `.dev/scripts/*`（拉数据 / 译文刷新 / 发布 / 自检 / 待办看板），想看清底层命令直接读那两个地方。

> **为什么升级/测试一律用 `run --rm` 而不是 `exec`**：`run` 起独立进程，不依赖服务是否在跑，
> 也不会占用 8069；`-u` 前先 `stop odoo` 是避免两个进程同时改元数据。
> 日常改 Python 根本不用跑升级——热重载已经覆盖。

---

## 5. 调试

**断点（推荐 attach）**

1. `task debug`（或任务「Odoo：启动并挂调试端口 5678」）
2. F5 → **Odoo：attach 到容器**
3. 调试完回到普通模式：跑一次 `task up`（容器会按新的 `command` 重建）

`launch.json` 里配了 `pathMappings`（`/mnt/extra-addons` ↔ 工作区），**删了断点就不生效**。

**其他手段**

```bash
task bash      # 进 odoo 容器
task shell     # Odoo shell（验 ORM / 改数据）
task psql      # 直接连本地 dev 库
```

**前端**：URL 加 `?debug=assets`（不合并压缩，便于打断点）。
Odoo 19 的 `--dev=all` **不含** Werkzeug 交互 debugger（19 只有 `access,qweb,reload,xml`），报错以日志为准。

---

## 6. 数据：从服务器搬到本地

复现生产问题的前提是**同一份数据 + 同一份 filestore**（本仓库 `product_image` / `sale_order_no` 强依赖图片）。

```bash
ssh-add ~/.ssh/id_ed25519        # 用宿主机 ssh-agent，私钥不进容器
SSH_HOST=odoo@server REMOTE_DB=prod task pull
task db-sync -- duplicate dev dev_clean    # 先留个干净副本，折腾坏了能回来
```

脚本内部走 Odoo 的 zip 备份（含 filestore），装载时 `-n` 做 `neutralize`（禁邮件 / 禁外部凭据），
备份文件落在 `.dev/backups/`（不入库，规则在 `.dev/.gitignore`）。

---

## 7. 让容器真的等价于服务器

热重载解决速度，「能不能复现」取决于这几件事对齐：

| 维度 | 怎么对齐 |
|------|----------|
| Odoo 版本 | 镜像 tag 与服务器一致（当前 `odoo:19.0`）；**源码就在镜像里**，容器内查即可，不用另存 `../odoo`（见第 2 节「读 Odoo 核心源码」） |
| Python 依赖 | 基础镜像自带 Odoo 官方依赖；服务器额外补过的包，加进 `.dev/docker/Dockerfile.odoo` 再 `task rebuild` |
| 数据 | `task pull`（zip 含 filestore） |
| 配置差异 | 容器内刻意不同：`workers = 0`（热重载要求）、`http_interface = 0.0.0.0`（宿主机要访问）。涉及 cron / 多进程行为的改动仍要在服务器复核 |
| 定时任务 | `max_cron_threads = 1` 才会跑 cron；不想被打扰就设 0 |
| PDF 报表 | 镜像里已装 `wkhtmltopdf` + 中文字体 `fonts-noto-cjk` |

---

## 8. 版本控制集成

`.pre-commit-config.yaml` + `.dev/scripts/check_repo.py`（宿主机装一次：`pipx install pre-commit && pre-commit install`）：

- `i18n/*.po` **重复 msgid**（会让整份译文解析失败）与缺 `#. module:`（导入抛异常）
- **应用列表元数据**（`shortdesc` / `summary` / `description`）的 `msgid` 与 `__manifest__.py` 是否逐字符一致
- XML 合法性、JS 语法（`node --check`）、JSON 合法性
- 界面文本残留中文（注释 / Python docstring 不算）
- trailing whitespace、EOF、密钥泄漏、大文件

其他约定：

- 分支 `feat/<模块>-<要点>`、`fix/<模块>-<要点>`；commit 用 `fix(product_image): ...` 作用域前缀，
  与 TODO.md 任务编号对应（AGENTS.md 要求改动同步 CHANGELOG / README）
- **多版本并行**：`git worktree add ../wt-old <分支>` → 在 worktree 的 `.dev/` 下建一个 `.env`
  （`.dev/.env` 不入库，见 `.dev/.gitignore`；不用动被跟踪的 `compose.yml`），换个工程名与端口即可同时跑两份：

  ```dotenv
  COMPOSE_PROJECT_NAME=odoo-addons-dev-b   # 工程名变了，容器/网络名跟着独立（已无卷）
  ODOO_CONTAINER=odoo19-b
  DB_CONTAINER=odoo19-db-b
  ODOO_HTTP_PORT=8169
  ODOO_DEBUG_PORT=5679
  PG_PORT=5433
  ```
- 上线：本地验收通过后 `MODULES=x task deploy`，服务器侧仍按 AGENTS.md 出「待验证清单」

---

## 9. 常见坑

| 项 | 说明 |
|----|------|
| 端口占用 | 宿主 8069 / 5432 / 5678 会被占用。本机已有 PostgreSQL 时删掉 compose 里 `db` 的 `ports` 那段 |
| `odoo.conf` 不要写行尾注释 | Odoo 的 configparser 把 `1  # 注释` 整个当值，`int()` 直接抛 `ValueError: invalid literal for int()`。说明只能写成整行注释 |
| Postgres 的 locale | 只能是镜像里已生成的：`postgres:16` 只有 `C` / `C.UTF-8` / `en_US.utf8`，写 `zh_CN.UTF-8` 会让 `initdb` 直接失败 |
| 首次没有 `dev` 库 / 缺模块 | `task up` 会调 `.dev/scripts/init-db.sh` 自动建库并补齐（Odoo 传 `-d <库>` 只会建**空库**、不装模块，表现是页面 500、日志报 `relation "ir_module_module" does not exist`）。手工重来：`task init`；想连演示数据一起重来：`task init -- --fresh` |
| 演示数据装不上 | Odoo **19.0 起 CLI 默认不装**演示数据（`--without-demo` 只是保留的取反别名，默认值是「不装」）→ 脚本里显式传 `--with-demo`。而且演示数据只在「模块安装那一刻」灌进去，已装好的库补不了，只能 `--fresh` 重建 |
| 别把 `admin_passwd` 当登录密码 | `odoo.conf` 的 `admin_passwd` 只用于 `/web/database/manager`（建库 / 删库 / 备份），改它**不会**影响网页登录。网页登录 `admin / admin` 是 Odoo 建库时写进 `res_users` 的默认值（纯净 CLI 建库实测：login=admin、password=admin），`.dev/scripts/init-db.sh` 不碰它 —— 自己改过密码想重置，就用 `odoo shell` 里的 `env.ref('base.user_admin').write({'password': 'admin'})` |
| 带参数的任务报 `Task "xxx" does not exist` | `task` 会把裸参数当成**任务名**，传参数必须加 `--`：`task update -- product_image`（任务本身的 `desc` 里都写了正确写法） |
| odoo 子命令必须写在最前面 | Odoo 的 CLI 只看 `argv[0]`（`odoo/cli/command.py:119`）：`odoo -c conf db dump ...` 会被当成 **server** 命令，报 `unrecognized parameters: db dump ...`。所以配置一律走 compose 里的 `ODOO_RC=/etc/odoo/odoo.conf`，命令写成 `odoo db dump dev -` 这种形式（`-c/--config` 的 `env_name` 就是 `ODOO_RC`，见 `odoo/tools/config.py:223`） |
| 容器写不进挂载目录 | 容器进程身份是 `PUID`/`PGID`（默认 1000:1000），宿主机 uid 不是 1000 就在 `.dev/.env` 里设 `PUID=$(id -u)`、`PGID=$(id -g)`，然后 `task up`（**不用** `task rebuild`）。启动时 `run-as.sh` 只在顶层属主不对时才递归 chown（日志会打印 `[entrypoint] 把 … 属主从 X:Y 改为 …`）；嵌套层里的异常属主要手动修：`sudo chown -R $(id -u):$(id -g) .dev/data/<x>` 或 `task reset` |
| `.dev/init.yaml` 里写了不存在的模块名 | Odoo 对认不出的模块名**只打 warning、不报错**（`invalid module names, ignored`，见 `odoo/modules/loading.py:_check_module_names`），所以命令照样成功、模块却一直没装 → `task init` 装完会复查并警告。检查名字是不是**模块技术名**（`sale_management` ✅ / `Sales` ❌），改完再 `task init` |
| 想加 / 去掉一个模块 | 官方 / 第三方改 `.dev/init.yaml` 的 `modules`，本仓库扩展改 `addons`（改完 `task init`）；**删掉某一项不会卸载它**，卸载请用网页「应用」 |
| `.dev/data` 里的文件不归我 | 正常情况下归你（entrypoint 启动时就 chown 成 `PUID:PGID`）。若你设的 `PUID` 不是宿主机 uid，属主就是那个 uid → 想直接 `rm` 会失败，用 `task reset`（它走一次性 root 容器删） |
| `task reset` 为什么用容器删 | ① 数据目录属主可能是 `PUID`（≠ 宿主机用户）；② 有些环境给 `rm` 挂了「批量删除保护」（本机就有：`rm` 是个安全垫片，>500 个文件直接拒绝）→ 容器里的 `rm` 不受这两条影响，删完还会把目录重建回当前用户所有 |
| `task up` 会先建 `.dev/data/{odoo,postgres}` | 用**当前用户**建（`prepare-dirs` 内部任务）：Docker 自己创建绑定源会是 root 属主，虽然 entrypoint 会纠正，但先建成你的更直观 |
| 为什么容器以 root 启动 | 只有 root 能改数据目录属主、切身份；`.dev/docker/run-as.sh` 降权后才执行命令（官方 entrypoint 写在镜像 `ENTRYPOINT` 里）。因此 **compose 里不能写 `user:`**（写了就没有 root 去降权），`task bash` 也显式带了 `-u $(id -u):$(id -g)`，免得你在仓库里留下 root 属主文件 |
| 目标 uid/gid 被占用 | 基础镜像里 `ubuntu` 占着 1000：entrypoint 会把它（连它的组）挪到第一个空闲 id（从 2000 起），再把 `odoo` 挪到 1000 —— 所以 `id odoo` 显示的就是 `odoo`。**uid/gid 0 例外**：root 不挪，只能让 `USER` 与 root 共用（日志告警；Odoo 自己也会打印 `Running as user 'root' is a security risk.`）。改动只落在容器内的 `/etc/passwd`，每次 `task up` 重建容器即还原，不碰宿主机 |
| 改名用 `ODOO_USER`，别写 `USER` | `USER` 既是 entrypoint 的目标用户名、也是官方 entrypoint 认的**数据库用户名**。而宿主机 shell 一般已导出 `USER`（本机 `USER=edwin`），所以 compose 里写的是 `USER: ${ODOO_USER:-odoo}`。**要换名字在 `.dev/.env` 里设 `ODOO_USER`**；直接设 `USER` 会把你的登录名带进容器（实测踩过：容器里被建了个 `edwin` 用户，`--db_user` 也会跟着错，只是我们 `odoo.conf` 里写了 `db_user` 才没炸） |
| 备份为什么走 stdout | `odoo db dump dev - > .dev/backups/x.zip`：容器内 uid 与宿主机一致，直接写挂载目录也行，但走 stdout 少一次容器内落盘，也不受属主配置影响（`db-sync.sh` 的处理） |
| `i18n` 刷新报 language not found | 库里还没装中文语言。`task init` 会自动装 `zh_CN`（首装要几分钟），装完再跑 `task i18n`；想手工装就 `task shell` 里 `env['res.lang']._activate_lang('zh_CN')` |
| 断点不生效 | 忘了 `pathMappings`，或没跑「启动并挂调试端口 5678」任务 |
| 改了 `compose.yml` 或 `.dev/docker/Dockerfile*` | 需要重建：`task rebuild`（= `docker compose up -d --build`；compose 不会自动重建镜像）。注意别写成 `task up --build`，`--build` 会被 task 当成自己的 flag 而报 `unknown flag` |
| 想重置一切 | `task reset`：停栈 + 删空 `.dev/data`（数据库与 filestore 一起清），下次 `task up` 自动重建空库并装 `base` |
| 旧 `.devcontainer/`（A 方案） | 已整目录删除（2026-09-16），连同 `odoo19-dev` / `odoo19-pg` 容器。若在别的机器上还留着：目录直接删，容器 `docker rm -f odoo19-dev odoo19-pg`，旧镜像 `docker rmi odoo-addons_devcontainer-app:latest`（约 2GB，非必需） |

---

## 10. 验证清单（2026-09-16 实跑）

已实测通过的：

1. ✅ `task up` / `task rebuild`：镜像构建 + 启动 + **首次自动建库**（`dev` 库；网页登录 `admin/admin` 是 Odoo 建库自带默认值，数据库管理页密码见 `odoo.conf`）
2. ✅ `http://localhost:8069` 返回 303（跳转登录页）
3. ✅ 容器里能看到仓库：`ls /mnt/extra-addons` 列出各模块与文档
4. ✅ 模块被发现且装得上：`task install -- product_packing` → 库里 `state = installed`
5. ✅ `task`（默认列命令）、`task ps`、`task check`、从子目录调用都能正常工作
6. ✅ `task update -- product_packing`：停服务 → `-u` → 起服务，一条命令跑通
7. ✅ `task db-sync -- dump dev`：产出 846KB 的 zip，内含 `dump.sql` + `filestore/`
8. ✅ `task db-sync -- duplicate dev dev_copy`、`task db-sync -- load <zip> dev_loaded` 均成功（验证后已 `task odoo -- db drop` 清掉）
9. ✅ `task test -- product_packing`：重建 `test` 库 → 退出码 0（默认只跑该模块的 tag）
10. ✅ `task i18n -- zh_CN product_packing`：`odoo shell` 路径跑通，处理到 `product_packing/i18n/zh_CN.po`
11. ✅ 缺参/非法参数一律拒绝执行（exit 201）：`task update`、`task update -- --stop-after-init`、`task install`、
   `task test`、`task odoo`、`task db-sync`、`task db-sync -- dup`、`task pull`（缺 SSH_HOST/REMOTE_DB）、
   `task deploy`（缺 DEPLOY_HOST）都给出用法提示
12. ✅ **数据全部绑定挂载在 `.dev/data/`**：启动后 `docker volume ls` 里没有本项目的卷；
   `.dev/data/postgres`（76MB，PGDATA）与 `.dev/data/odoo` 属主都是宿主机用户，可直接查看/删除
13. ✅ `task reset`：停栈 → 一次性 root 容器清空 `.dev/data` 并重建目录（归当前用户）→ 再次 `task up`
   自动建库装 base、页面 303
14. ✅ `PUID`/`PGID` 运行时切换（含腾位、0:0 例外）、`task debug`、`task pull` 之外的任务均已实测
15. ✅ **开发库一键到位**（`.dev/scripts/init-db.sh`，在临时库上以 `--fresh` 实跑）：
   `admin/admin` 可登录（`/web/session/authenticate` 返回 uid=2，错密码返回 Access Denied）、
   `sale_management` / `purchase` / `stock` 全部 installed、仓库 8 个模块全部 installed、
   演示数据已加载（`base.user_demo` 存在、`product_template` 37 条）；重复执行幂等（「模块齐全，跳过安装」）

实跑时踩到并已修掉的坑（都写进了第 9 节）：

- **空库陷阱**：Odoo 传 `-d <库>` 只建空库、不装模块 → 页面 500 + `relation "ir_module_module" does not exist`；
  现在 `task up` 会自己探测并初始化
- **`task` 的裸参数**：`task update product_image` 会被当成任务名报错，必须 `task update -- product_image`
- **odoo 子命令顺序**：`odoo -c conf db dump ...` 会被当 server 命令（`unrecognized parameters`）→ 改走 `ODOO_RC`
- **容器 uid 101 写不进挂载目录**：`db dump` 改为输出到 stdout 再落盘
- **base 全套测试**：`-i` 会连带跑 base 的测试（慢 + PG 序列化冲突）→ `test` 默认只跑指定模块的 tag
- **`config['addons_path']` 在 19 里是 list**：`i18n-reload.sh` 里原来按逗号字符串切分会报 `'list' object has no attribute 'split'`
- **pg 镜像的入口不叫 `/entrypoint.sh`**：两个镜像共用一个降权脚本时，如果脚本内部假定了官方入口的路径，
  db 容器会 exit 127（`env: '/entrypoint.sh': No such file or directory`）→ 现在官方入口写在各自镜像的
  `ENTRYPOINT` 第二段，脚本只 `exec "$@"`，不认识也不需要知道对方是谁
- **`getent` 未命中返回 2 + `pipefail`**：腾位函数里 `$(getent ... | cut ...)` 直接把脚本杀掉
  （exit 2、一行日志都没有）→ 加 `|| true` 兜住

还需你验的：

16. ☐ 改一个模型 `.py` → 日志出现原地重启；改视图 XML / QWeb → 刷新浏览器生效
17. ☐ `task debug` + F5 能断在自定义模块里
18. ☐ `task pull` 能拉到**服务器**含 filestore 的备份，本地图片正常显示
19. ☐ `pre-commit install` 后提交一次门禁生效

验证结果请回写到本清单与对应模块的 `CHANGELOG.md`（AGENTS.md 的交付要求）。
