import os
import json
import urllib3
from dotenv import load_dotenv
from datetime import datetime
from ontology.memory import StoryOntology
from agents.writer import WriterAgent   # теперь это архитектор (класс переименован в файле)
from agents.stylist import StylistAgent      # стилист
from agents.editor import EditorAgent         # редактор
from agents.critic import CriticAgent         # критик
from experiments.runner import ExperimentRunner

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()


class StoryOrchestrator:
    """
    Оркестратор мультиагентной системы.
    Управляет потоком: Архитектор -> Стилист -> Редактор -> Критик
    """

    def __init__(self, story_id: str = "story_001"):
        self.ontology = StoryOntology(story_id)
        self.architect = WriterAgent()      # Архитектор (бывший WriterAgent, но переименован в файле)
        self.writer = StylistAgent()        # Стилист (пишет черновик)
        self.editor = EditorAgent()         # Редактор (исправляет текст)
        self.critic = CriticAgent()         # Критик (оценивает текст)
        self.runner = ExperimentRunner()
        self.max_iterations = int(os.getenv("MAX_ITERATIONS", 5))
        self.full_text = ""

    def run_experiment(self, hypothesis: str, config: dict) -> dict:
        print(f"\n{'='*60}")
        print(f"ЭКСПЕРИМЕНТ #{self.runner.experiments.__len__() + 1}")
        print(f"Гипотеза: {hypothesis}")
        print(f"Конфигурация: {json.dumps(config, ensure_ascii=False)}")
        print(f"{'='*60}")

        genre = config.get("genre", os.getenv("STORY_GENRE", "психологическая драма"))
        theme = config.get("theme", "человек и его работа как способ справиться с потерей")

        # Шаг 1: Архитектор проектирует структуру
        print("\n[1/5] Архитектор проектирует структуру...")
        design = self.architect.design_story(genre, theme)

        if "error" in design:
            print(f"\n[ОШИБКА АРХИТЕКТОРА]: {design.get('error')}")
            print(f"Сырой ответ (первые 500 символов):\n{design.get('raw', '')[:500]}")
            print("\n[ПОВТОРНАЯ ПОПЫТКА]...")
            design = self.architect.design_story(genre, theme)
            if "error" in design:
                print(f"[ПОВТОРНАЯ ОШИБКА]. Сырой ответ:\n{design.get('raw', '')[:500]}")
                return {"score": 1, "iterations": 0, "verdict": "Ошибка архитектора"}

        # ============================================================
        # ИНИЦИАЛИЗАЦИЯ ОНТОЛОГИИ (ИСПРАВЛЕННЫЙ БЛОК)
        # ============================================================
        self.ontology.metadata["genre"] = genre
        self.ontology.metadata["theme"] = theme

        # Получаем флаг использования скрытого слоя
        use_hidden = config.get("use_hidden_layer", True)

        # Добавляем персонажей
        characters = design.get("characters", [])
        for char in characters:
            char_name = char["name"]
            visible_traits = char.get("visible_traits", {})
            
            # Определяем скрытые черты отдельной переменной
            if use_hidden:
                hidden_traits = char.get("hidden_traits", {})
            else:
                hidden_traits = None
            
            self.ontology.add_character(
                char_name,
                visible_traits,
                hidden_traits
            )

        # Добавляем локации
        for loc in design.get("locations", []):
            self.ontology.add_location(loc["name"], loc.get("description", ""))

        # Добавляем объекты
        for obj in design.get("objects", []):
            self.ontology.add_object(obj["name"], obj.get("properties", {}))

        # Добавляем связи между сущностями
        for rel in design.get("relations", []):
            self.ontology.add_relation(rel["from"], rel["to"], rel["relation"])

        # Добавляем пространственные отношения
        for spatial in design.get("spatial_relations", []):
            if "subject" in spatial and "relation" in spatial and "object" in spatial:
                self.ontology.add_spatial_relation(
                    spatial["subject"],
                    spatial["relation"],
                    spatial["object"]
                )
        # ============================================================

        # Шаг 2: Генерация сцен (строго 3 сцены)
        scenes = design.get("arc", [])[:3]

        # Проверяем, что все 3 типа сцен есть
        scene_types_found = [s.get("scene_type") for s in scenes]
        if len(scenes) < 3 or not all(t in scene_types_found for t in ["завязка", "кульминация", "развязка"]):
            print("[ВНИМАНИЕ] Архитектор не вернул все 3 типа сцен. Дополняем...")
            required_types = ["завязка", "кульминация", "развязка"]
            while len(scenes) < 3:
                missing_type = required_types[len(scenes)]
                scenes.append({
                    "scene_type": missing_type,
                    "event": f"Сцена типа {missing_type}",
                    "node_changes": {}
                })

        full_text = ""
        iterations = 0
        total_score = 0

        for i, scene_plan in enumerate(scenes):
            iterations += 1
            scene_type = scene_plan.get("scene_type", "неизвестно")
            print(f"\n[2/5] Сцена {i+1}/{len(scenes)} ({scene_type.upper()}): {scene_plan.get('event', '')[:60]}...")

            ontology_snapshot = (
                self.ontology.get_architect_context() if config.get("use_hidden_layer", True)
                else self.ontology.get_scene_context()
            )
            writer_context = self.ontology.get_scene_context()

            # Проверяем пространственную согласованность перед отправкой Стилисту
            spatial_issues = self.ontology.check_spatial_consistency()
            if spatial_issues:
                print(f"  [ВНИМАНИЕ] Пространственные противоречия: {spatial_issues}")

            # Шаг 3: Стилист пишет черновик
            print(f"[3/5] Стилист пишет черновик...")
            draft = self.writer.write_scene(scene_plan, writer_context, full_text, genre=genre)

            # Шаг 4: Редактор исправляет текст
            print(f"[4/5] Редактор исправляет текст...")
            edit_result = self.editor.edit_text(draft, ontology_snapshot, scene_plan, genre=genre)
            cleaned = edit_result.get("cleaned_text", draft)

            # Защита: если cleaned пустой или мусорный - используем draft
            if not cleaned or len(cleaned.strip()) < 50:
                cleaned = draft

            full_text += "\n\n" + cleaned

            # Шаг 5: Критик оценивает текст
            print(f"[5/5] Критик оценивает текст...")
            critique = self.critic.evaluate(cleaned, genre, scene_plan)
            avg_score = critique.get("average_score", 5)
            total_score += avg_score

            print(f"  Оценка критика: {avg_score}/10")
            if critique.get("weaknesses"):
                print(f"  Слабые места: {critique['weaknesses'][:2]}")
            if critique.get("strengths"):
                print(f"  Сильные стороны: {critique['strengths'][:2]}")

            # Записываем событие в онтологию
            self.ontology.record_event({
                "description": scene_plan.get("event", f"Сцена {i+1}"),
                "scene_type": scene_type,
                "score": avg_score,
                "changes": edit_result.get("changes", [])
            })

            if iterations >= self.max_iterations:
                break

        avg_score = round(total_score / max(iterations, 1), 1)
        self.full_text = full_text

        # Финальная оценка
        print(f"\n[ФИНАЛ] Средняя оценка: {avg_score}/10")
        verdict = self._evaluate_result(avg_score, critique if 'critique' in locals() else {})

        result = {
            "score": avg_score,
            "iterations": iterations,
            "verdict": verdict,
            "text_preview": full_text[:500] + "..." if len(full_text) > 500 else full_text,
        }

        self.runner.log_experiment(hypothesis, config, result)
        self.ontology.save()

        print(f"\n[ГОТОВО] Эксперимент завершён. Средняя оценка: {avg_score}/10")
        return result

    def _evaluate_result(self, score: float, last_review: dict) -> str:
        if score >= 8.5:
            return "ОТЛИЧНО. Текст плотный, с подтекстом, без штампов. Можно публиковать."
        elif score >= 7:
            return "ХОРОШО. Есть потенциал, но нужно доработать."
        elif score >= 5:
            return "СРЕДНЕ. Много замечаний, требуется переработка."
        else:
            return "ПЛОХО. Система не справилась с задачей."

    def generate_final_story(self, genre: str, theme: str) -> str:
        # Очищаем состояние перед новой генерацией
        self.ontology = StoryOntology(f"story_{int(datetime.now().timestamp())}")
        self.full_text = ""

        best_config = self.runner.get_best_config()
        if not best_config:
            best_config = {
                "theme": theme,
                "genre": genre,
                "use_ontology": True,
                "use_hidden_layer": True,
                "agents": ["architect", "stylist", "editor", "critic"],
            }
        else:
            best_config["theme"] = theme
            best_config["genre"] = genre

        print(f"\n{'='*60}")
        print(f"ГЕНЕРАЦИЯ ФИНАЛЬНОГО РАССКАЗА")
        print(f"Жанр: {genre}")
        print(f"Тема: {theme}")
        print(f"{'='*60}")

        self.run_experiment("Финальная генерация с лучшей конфигурацией", best_config)
        return self.full_text


def main():
    orchestrator = StoryOrchestrator(story_id="final_story")

    print("=" * 60)
    print("  МУЛЬТИАГЕНТНАЯ СИСТЕМА ГЕНЕРАЦИИ РАССКАЗОВ")
    print("  с онтологической памятью (Event Sourcing)")
    print("=" * 60)

    while True:
        print("\nВыберите действие:")
        print("1. Запустить серию экспериментов (гипотезы из отчёта)")
        print("2. Сгенерировать финальный рассказ")
        print("3. Посмотреть журнал экспериментов")
        print("4. Выход")

        choice = input("\nВаш выбор: ").strip()

        if choice == "1":
            experiments = [
                {
                    "hypothesis": "Эксперимент 1: Базовый (Архитектор → Стилист)",
                    "config": {
                        "theme": "человек и его работа", 
                        "genre": "драма", 
                        "agents": ["architect", "stylist"], 
                        "use_ontology": False, 
                        "use_hidden_layer": False
                    },
                },
                {
                    "hypothesis": "Эксперимент 2: Добавлен Редактор",
                    "config": {
                        "theme": "человек и его работа", 
                        "genre": "драма", 
                        "agents": ["architect", "stylist", "editor"], 
                        "use_ontology": True, 
                        "use_hidden_layer": True
                    },
                },
                {
                    "hypothesis": "Эксперимент 3: Полная цепочка (Архитектор → Стилист → Редактор → Критик)",
                    "config": {
                        "theme": "человек и его работа как способ справиться с потерей", 
                        "genre": "драма", 
                        "agents": ["architect", "stylist", "editor", "critic"], 
                        "use_ontology": True, 
                        "use_hidden_layer": True
                    },
                },
                {
                    "hypothesis": "Эксперимент 4: Финальная калибровка (оптимизация)",
                    "config": {
                        "theme": "глубоководный сварщик и развод - подтекст через физический труд", 
                        "genre": "драма", 
                        "agents": ["architect", "stylist", "editor", "critic"], 
                        "use_ontology": True, 
                        "use_hidden_layer": True
                    },
                },
            ]
            for exp in experiments:
                orchestrator.run_experiment(exp["hypothesis"], exp["config"])

        elif choice == "2":
            genre = input("Жанр (по умолчанию: производственная психологическая драма): ").strip() or "производственная психологическая драма"
            theme = input("Тема/идея: ").strip() or "человек и его работа как способ справиться с потерей"
            text = orchestrator.generate_final_story(genre, theme)

            print("\n" + "=" * 60)
            print("ФИНАЛЬНЫЙ РАССКАЗ:")
            print("=" * 60)

            if text.strip():
                print(text)
            else:
                print("\n[ВНИМАНИЕ] Рассказ не был сгенерирован.")
                print("Попробуйте запустить снова или выберите другую тему.")

            with open("./final_story.txt", "w", encoding="utf-8") as f:
                f.write(text if text else "Рассказ не был сгенерирован.")
            print(f"\n[ГОТОВО] Результат сохранён в ./final_story.txt")

        elif choice == "3":
            print(orchestrator.runner.get_summary())

        elif choice == "4":
            print("Выход.")
            break

        else:
            print("Неверный выбор.")


if __name__ == "__main__":
    main()