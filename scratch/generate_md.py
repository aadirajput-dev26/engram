import sys, os
sys.path.append(os.path.dirname(__file__))
import run_full_evaluation as rfe

target = r"c:\Users\Aadityaraj\PROJECTS\RAG PIPELINE\TEST_RESULTS_35_PAGE_REPORT.md"
with open(target, "w", encoding="utf-8") as f:
    f.write(rfe.full_report)

print("SUCCESSFULLY WRITTEN TO:", target)
print("FILE SIZE:", os.path.getsize(target))
