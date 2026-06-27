# 换机部署 & 启动手册（演示界面 web/）

> 给"演示机"或新同事用：从零把界面跑起来。**演示用「离线回放」模式，不需要 Ollama、不需要数据库、可断网。**

---

## 0. 最快路径（已装好 Python 的机器）

```bash
git clone <仓库地址> && cd xin-migrate
python -m venv .venv
source .venv/Scripts/activate      # Windows Git Bash；PowerShell 用 .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
streamlit run web/app.py
```

浏览器开 `http://localhost:8501` → 侧边栏选「离线回放」→ 选场景 → 点「🚀 开始迁移」。

---

## 1. 坑：Python 命令失效 / 中文安装路径

本项目开发机踩过一个坑，**换机如遇 `python` 没反应或报"找不到路径"，照这里排查**：

- **症状**：`python --version` 无输出（Windows 商店占位 stub），或 `py` 报 `Unable to create process using 'D:\????\python.exe'`。
- **根因**：Python 装在**中文目录**且后来被改名，注册表/启动器指向了失效的旧路径。
- **解法**（任选）：
  1. 用 `python.exe` 的**绝对路径**直接调，例如 `"/d/你的python目录/python.exe" -m venv .venv`；
  2. 或重装官方 Python 到**纯英文路径**（如 `C:\Python313`）并勾选"Add to PATH"；
  3. venv 一旦建好，后续一律用 `.venv/Scripts/python.exe`（位于英文仓库路径，绕开中文路径问题）。

---

## 2. 内网 / 离线环境装依赖

主打"内网离线"，演示机往往连不了公网 PyPI。三种方式：

- **国内镜像**（能连内网镜像时最简单）：
  ```bash
  pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
  ```
- **企业内网私服**：`pip install -i http://<内网pypi>/simple --trusted-host <内网pypi> -r requirements.txt`
- **完全离线**：在有网机器上 `pip download -r requirements.txt -d wheels/`，把 `wheels/` 拷到演示机后
  `pip install --no-index --find-links wheels/ -r requirements.txt`

依赖清单见根目录 `requirements.txt`（streamlit / openai / python-dotenv / sqlparse / psycopg2-binary）。

---

## 3. 启动 & 首次运行提示

```bash
streamlit run web/app.py
```

- **首次启动会问邮箱**：直接回车跳过，或预先免提示：
  ```bash
  mkdir -p ~/.streamlit && printf '[general]\nemail = ""\n' > ~/.streamlit/credentials.toml
  ```
- 改了根目录 `.streamlit/config.toml`（深色主题）后**需重启 streamlit** 才生效；界面内的细节 CSS 即时生效。
- 指定端口/对外：`streamlit run web/app.py --server.port 8501 --server.address 0.0.0.0`

---

## 4. 两种模式说明

| 模式 | 依赖 | 用途 |
|---|---|---|
| **离线回放**（默认，演示用） | 仅 `data/demo_replay/*.json` | 确定性脚本，100% 稳定复现"失败→自修复"高光，**免 Ollama / 免数据库 / 可断网** |
| **实时端侧模型** | 本地 Ollama + 已 pull 模型 | 真模型联调；连不上会在界面友好提示，不崩 |

回放数据由 B 维护在 `data/demo_replay/`，改 SQL/剧情后跑 `python data/demo_replay/build.py` 重新生成 `basic.json` / `advanced.json`。

---

## 5. ⚠️ 给 A 的协调备注（tools/ 归 A）

KB 新增了 `SUBSTR`、`CONCAT`（`||`拼接）两条规则。要让它们在**实时模式**下被 `grep_dialect` 自动扫出来，需 A 在 `tools/dialect.py` 的 `DIALECT_PATTERNS` 加两条（**回放模式不受影响**，无需等这个）：

```python
"SUBSTR": (r"\bSUBSTR\s*\(",  "Oracle 字符串截取，核对位置/负数语义", "低"),
"CONCAT": (r"\|\|",            "字符串 || 拼接，注意 NULL 拼接语义差异", "中"),
```

> 注意 KB 的键要与 dialect 的 feature 名一致（`query_migration_kb` 会把 feature 转大写匹配）：`SUBSTR`、`CONCAT`。

并建议在 `tools/validate.py` 的 `_FIX_HINTS` 里也各加一条（静态校验失败时会把"怎么改"喂给弱模型，提高一次改对率）：

```python
"SUBSTR": "SUBSTR 多数国产库兼容；迁 PG 可用 SUBSTRING(str FROM pos FOR len)",
"CONCAT": "|| 拼接保留；可空列用 COALESCE(col,'') 包裹避免 NULL 传染",
```

---

## 6. 上台前

现场口播脚本和检查清单见 `docs/DEMO.md`；PPT 文案见 `docs/PITCH.md`。
