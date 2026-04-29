from __future__ import annotations

import json
import os
import sys

from dotenv import load_dotenv

from core.agents import BioPrecisionAgents
from core.config import DEEPSEEK_DEFAULT_MODEL, ENV_PATH, ensure_runtime_dirs


sys.stdout.reconfigure(encoding="utf-8")


def main() -> None:
    ensure_runtime_dirs()
    load_dotenv(ENV_PATH)
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("Missing DEEPSEEK_API_KEY. Add it to .env before running the CLI demo.")
        return

    system = BioPrecisionAgents(api_key=api_key)
    user_input = (
        "Design a differential expression workflow for the DREB gene family in bamboo, "
        "including evidence-backed analysis steps and recommended code packages."
    )

    print(f"Bio-Precision Agent V5 CLI demo ({DEEPSEEK_DEFAULT_MODEL})")
    print("=" * 72)
    print(f"Input: {user_input}\n")

    print("[1/3] Architect parsing")
    architecture = system.run_architect(user_input)
    print(json.dumps(architecture, indent=2, ensure_ascii=False))

    print("\n[2/3] Evidence research")
    research = system.run_researcher(user_input, architecture)
    print(f"Evidence chunks: {len(research['chunks'])}")
    print(research["synthesis"][:900])

    print("\n[3/3] Protocol validation")
    report = system.run_validator(user_input, architecture, research)
    output_path = "bpa_v5_cli_report.md"
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(report)
    print(f"Report written to {output_path}")


if __name__ == "__main__":
    main()
