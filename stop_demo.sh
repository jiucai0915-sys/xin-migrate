#!/bin/bash
# ============================================================
#  信迁 Demo · 一键停止（关掉 隧道 + 界面 + 模型 三个后台服务）
# ============================================================
echo "正在关闭 Demo 的后台服务…"
pkill -f "ngrok http" 2>/dev/null      && echo "  ✅ 已关 公网隧道" || echo "  · 隧道未在运行"
pkill -f "streamlit run" 2>/dev/null   && echo "  ✅ 已关 界面"     || echo "  · 界面未在运行"
pkill -f "ollama serve" 2>/dev/null    && echo "  ✅ 已关 模型服务" || echo "  · 模型未在运行"
echo "全部关闭完成。"
