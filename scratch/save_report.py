
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import run_full_evaluation as rfe

target = r"c:\Users\Aadityaraj\PROJECTS\RAG PIPELINE\TEST_RESULTS_35_PAGE_REPORT.md"
with open(target, "w", encoding="utf-8") as f:
    f.write(rfe.full_report)

print("FILE WRITTEN TO:", target)
print("FILE SIZE:", os.path.getsize(target))
