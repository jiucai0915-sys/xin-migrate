#!/bin/bash
# ============================================================
#  信迁 Demo · 一键启动（双击或在终端运行 bash start_demo.sh）
#  会依次拉起：① Ollama 模型服务 ② Streamlit 界面 ③ ngrok 公网隧道
#  全部跑在后台，最后打印出「公网链接」给你
# ============================================================

ROOT="$HOME/黑客松/xin-migrate"
NGROK="/tmp/ngrok"
OLLAMA="$HOME/.local/bin/ollama"

echo "========================================"
echo "  信迁 Demo 启动中…（请保持此窗口不要关）"
echo "========================================"

# ① Ollama
if curl -sS -m3 http://localhost:11434/ >/dev/null 2>&1; then
  echo "[1/3] ✅ Ollama 已在运行"
else
  echo "[1/3] 启动 Ollama…"
  nohup "$OLLAMA" serve > /tmp/ollama.log 2>&1 &
  sleep 4
fi

# ② Streamlit
if curl -sS -m3 http://localhost:8501/ >/dev/null 2>&1; then
  echo "[2/3] ✅ 界面已在运行 (localhost:8501)"
else
  echo "[2/3] 启动界面…"
  cd "$ROOT" || { echo "❌ 找不到项目目录 $ROOT"; exit 1; }
  source .venv/bin/activate
  nohup streamlit run web/app.py > /tmp/streamlit.log 2>&1 &
  sleep 8
fi

# ③ ngrok 隧道（固定域名）
pkill -f "ngrok http" 2>/dev/null
sleep 1
echo "[3/3] 启动公网隧道…"
nohup "$NGROK" http 8501 --log=stdout > /tmp/ngrok.log 2>&1 &
sleep 6

URL=$(grep -oE "https://[a-z0-9-]+\.ngrok[a-z.-]*\.(app|dev)" /tmp/ngrok.log | head -1)

echo ""
echo "========================================"
if [ -n "$URL" ]; then
  echo "  🎉 全部启动成功！公网链接："
  echo ""
  echo "     $URL"
  echo ""
  echo "  （首次打开请点 \"Visit Site\" 按钮）"
else
  echo "  ⚠️ 隧道链接没抓到，看 /tmp/ngrok.log"
fi
echo "========================================"
echo ""
echo "  ⚠️ 重要：演示期间不要关这个窗口、不要让电脑休眠！"
echo "  停止：运行 bash stop_demo.sh"
echo ""
