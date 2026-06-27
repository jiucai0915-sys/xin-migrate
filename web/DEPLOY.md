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

## 5. 与 A 的协调记录（均已同步完成 ✅）

以下几项 A 已在 `tools/`、`agent/` 侧完成并合入 main，这里留档：

- ✅ **`run_validation` 离线降级 bug 已修**：装了 psycopg2 但库没起时，正确降级到静态校验（不再把连接超时误判为 SQL 报错）。
- ✅ **`SUBSTR` / `CONCAT`(`||`) 扫描规则已加**（`tools/dialect.py` + `_FIX_HINTS`），并新增 `COMPATIBLE_FEATURES` 集合：这类"兼容但提示"语法能被扫出来提示，但**不会判为迁移失败**（否则 `||` 这种合法语法会让自修复死循环）。这也是为什么进阶场景扫描数从 8 变 9（多识别出 SUBSTR）。
- ✅ **新增 `run_semantic_test`（数据级语义验证）**：在内置 SQLite 样本库上真跑迁移后的 SELECT、与标准答案逐行比对，抓"语法对但语义错"（如误用 INNER JOIN 丢掉无订单客户）。**本界面已接入**：基础场景回放在"语法关"后加了"语义关"，结果用 `st.table` 展示（事件结构 `{ok, msg, rows[, expected]}`）。

> 分工已厘清：`web/` 归 B，`agent/`+`tools/` 归 A，不再重叠。

---

## 6. 上台前

现场口播脚本和检查清单见 `docs/DEMO.md`；PPT 文案见 `docs/PITCH.md`。
