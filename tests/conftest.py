"""让 tests/ 能 import 到项目根的 agent / tools 包。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
