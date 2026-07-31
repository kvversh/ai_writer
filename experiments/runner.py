import json
import os
from datetime import datetime


class ExperimentRunner:
    def __init__(self, log_path: str = "./experiments_log.json"):
        self.log_path = log_path
        self.experiments = []
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                self.experiments = json.load(f)

    def log_experiment(self, hypothesis: str, config: dict, result: dict):
        entry = {
            "id": len(self.experiments) + 1,
            "timestamp": datetime.now().isoformat(),
            "hypothesis": hypothesis,
            "config": config,
            "result": result,
        }
        self.experiments.append(entry)
        with open(self.log_path, "w", encoding="utf-8") as f:
            json.dump(self.experiments, f, ensure_ascii=False, indent=2)
        return entry

    def get_summary(self) -> str:
        if not self.experiments:
            return "Экспериментов пока нет."
        lines = ["=== ЖУРНАЛ ЭКСПЕРИМЕНТОВ ==="]
        for exp in self.experiments:
            r = exp["result"]
            lines.append(f"\n#{exp['id']}: {exp['hypothesis']}")
            lines.append(f"  Конфигурация: {json.dumps(exp['config'], ensure_ascii=False)}")
            lines.append(f"  Оценка: {r.get('score', 'N/A')}/10")
            lines.append(f"  Итераций: {r.get('iterations', 'N/A')}")
            lines.append(f"  Итог: {r.get('verdict', 'N/A')}")
        return "\n".join(lines)

    def get_best_config(self) -> dict:
        if not self.experiments:
            return {}
        best = max(self.experiments, key=lambda e: e["result"].get("score", 0))
        return best["config"]