# Скрипт автоматической установки всех файлов
import os

print("[1/5] Создаём ontology/memory.py...")
os.makedirs("ontology", exist_ok=True)
with open("ontology/memory.py", "w", encoding="utf-8") as f:
    f.write('''import json
import os
from datetime import datetime
import networkx as nx


class StoryOntology:
    def __init__(self, story_id: str = "default"):
        self.story_id = story_id
        self.graph = nx.DiGraph()
        self.timeline = []
        self.hidden_layer = {}
        self.metadata = {"genre": "", "theme": "", "created_at": datetime.now().isoformat()}
        self._storage_dir = "./story_storage"
        os.makedirs(self._storage_dir, exist_ok=True)

    def add_character(self, name: str, traits: dict, hidden_traits: dict = None):
        self.graph.add_node(name, type="character", **traits)
        if hidden_traits:
            self.hidden_layer[name] = hidden_traits

    def add_object(self, name: str, properties: dict):
        self.graph.add_node(name, type="object", **properties)

    def add_location(self, name: str, description: str):
        self.graph.add_node(name, type="location", description=description)

    def add_relation(self, source: str, target: str, relation: str):
        self.graph.add_edge(source, target, relation=relation)

    def add_spatial_relation(self, subject: str, relation: str, object_name: str):
        self.graph.add_edge(subject, object_name, relation=f"spatial:{relation}")

    def get_spatial_context(self, entity: str) -> list:
        relations = []
        for u, v, data in self.graph.edges(data=True):
            if data.get("relation", "").startswith("spatial:"):
                rel_type = data["relation"].replace("spatial:", "")
                if u == entity:
                    relations.append(f"{entity} {rel_type} {v}")
                elif v == entity:
                    relations.append(f"{u} {rel_type} {entity}")
        return relations

    def check_spatial_consistency(self) -> list:
        issues = []
        for node in self.graph.nodes():
            inside = []
            near = []
            on = []
            for u, v, data in self.graph.edges(data=True):
                rel = data.get("relation", "")
                if not rel.startswith("spatial:"):
                    continue
                rel_type = rel.replace("spatial:", "")
                if u == node:
                    if rel_type == "внутри":
                        inside.append(v)
                    elif rel_type == "рядом с":
                        near.append(v)
                    elif rel_type == "на":
                        on.append(v)
            for obj in inside:
                if obj in near:
                    issues.append(f"{node} одновременно 'внутри' и 'рядом с' {obj}")
                if obj in on:
                    issues.append(f"{node} одновременно 'внутри' и 'на' {obj}")
            for obj in on:
                if obj in near:
                    issues.append(f"{node} одновременно 'на' и 'рядом с' {obj}")
        return issues

    def record_event(self, event: dict):
        event["timestamp"] = len(self.timeline)
        event["time"] = datetime.now().isoformat()
        self.timeline.append(event)
        if "node_changes" in event:
            for node, changes in event["node_changes"].items():
                if node in self.graph:
                    self.graph.nodes[node].update(changes)

    def get_scene_context(self, location: str = None) -> dict:
        context = {"characters": [], "objects": [], "locations": [], "relations": [], "spatial": []}
        for node, data in self.graph.nodes(data=True):
            node_type = data.get("type", "unknown")
            if node_type == "character":
                visible = {k: v for k, v in data.items() if k != "type"}
                context["characters"].append({"name": node, **visible})
            elif node_type == "object":
                context["objects"].append({"name": node, **{k: v for k, v in data.items() if k != "type"}})
            elif node_type == "location":
                context["locations"].append({"name": node, "description": data.get("description", "")})
        for u, v, data in self.graph.edges(data=True):
            rel = data.get("relation", "")
            if rel.startswith("spatial:"):
                context["spatial"].append({"from": u, "to": v, "relation": rel.replace("spatial:", "")})
            else:
                context["relations"].append({"from": u, "to": v, "relation": rel})
        context["recent_events"] = self.timeline[-5:] if self.timeline else []
        return context

    def get_architect_context(self) -> dict:
        context = self.get_scene_context()
        context["hidden_layer"] = self.hidden_layer
        context["full_timeline"] = self.timeline
        return context

    def save(self):
        data = {
            "story_id": self.story_id,
            "graph": nx.node_link_data(self.graph),
            "timeline": self.timeline,
            "hidden_layer": self.hidden_layer,
            "metadata": self.metadata,
        }
        path = os.path.join(self._storage_dir, f"{self.story_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
''')

print("[2/5] Создаём agents/architect.py (с max_tokens)...")
os.makedirs("agents", exist_ok=True)
with open("agents/architect.py", "w", encoding="utf-8") as f:
    f.write('''import os
import json
import requests
import urllib3
import uuid
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()


class ArchitectAgent:
    def __init__(self):
        self.credentials = os.getenv("GIGACHAT_CREDENTIALS")
        self.scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
        self.token = None
        self.temperature = 0.6

    def _get_token(self):
        url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        headers = {
            "Authorization": f"Basic {self.credentials}",
            "RqUID": str(uuid.uuid4()),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        resp = requests.post(url, headers=headers, data={"scope": self.scope}, verify=False)
        resp.raise_for_status()
        self.token = resp.json()["access_token"]

    def chat(self, messages: list, max_tokens: int = 2000) -> str:
        if not self.token:
            self._get_token()
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        payload = {
            "model": "GigaChat",
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": max_tokens,
        }
        resp = requests.post(url, headers=headers, json=payload, verify=False)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def design_story(self, genre: str, theme: str) -> dict:
        genre_instructions = {
            "комедия": "КОМЕДИЯ: абсурд, контраст, физическая комедия, ирония. Каждая сцена смешная.",
            "драма": "ДРАМА: внутренний конфликт, напряжение, эмоции через действия, открытый финал.",
            "детектив": "ДЕТЕКТИВ: загадка, улики, напряжение, поворот в финале.",
            "фэнтези": "ФЭНТЕЗИ: магический мир, герой с миссией.",
            "хоррор": "ХОРРОР: нарастающее напряжение, страх неизвестного."
        }
        genre_block = genre_instructions.get(genre.lower(), "Общие принципы: конфликт, диалоги, плотный сюжет.")

        system_prompt = (
            "Ты - литературный архитектор. Спроектируй КРАТКУЮ структуру рассказа в жанре " + genre.upper() + ".\\n\\n"
            + genre_block + "\\n\\n"
            "СТРОГО 3 СЦЕНЫ: ЗАВЯЗКА, КУЛЬМИНАЦИЯ, РАЗВЯЗКА.\\n"
            "Финал холодный, без морали. Персонажи НЕ делают выводов вслух.\\n\\n"
            "Ответь СТРОГО JSON (без markdown):\\n"
            "{\\n"
            '  "title": "название",\\n'
            '  "characters": [\\n'
            '    {"name": "имя", "traits": "2-3 черты"},\\n'
            '    {"name": "имя", "traits": "2-3 черты"}\\n'
            "  ],\\n"
            '  "location": "локация",\\n'
            '  "arc": [\\n'
            '    {"scene_type": "завязка", "event": "1 предложение"},\\n'
            '    {"scene_type": "кульминация", "event": "1 предложение"},\\n'
            '    {"scene_type": "развязка", "event": "1 предложение БЕЗ морали"}\\n'
            "  ]\\n"
            "}\\n\\n"
            "БУДЬ КРАТОК. Каждый event - 1 предложение. ТОЛЬКО JSON."
        )

        user_prompt = f"Жанр: {genre}\\nТема: {theme}\\n\\nСпроектируй КРАТКУЮ структуру."

        response = self.chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ], max_tokens=1500)

        try:
            clean = response
            clean = clean.replace("```json", "").replace("```JSON", "").replace("```", "")
            start = clean.find("{")
            end = clean.rfind("}")
            if start != -1 and end != -1 and end > start:
                clean = clean[start:end+1]
            clean = clean.strip()
            result = json.loads(clean)

            normalized = {
                "title": result.get("title", "Без названия"),
                "theme": theme,
                "characters": [],
                "locations": [{"name": result.get("location", "неизвестно"), "description": ""}],
                "objects": [],
                "relations": [],
                "spatial_relations": [],
                "arc": result.get("arc", []),
                "subtext_rules": "Показывай через действия"
            }
            for char in result.get("characters", []):
                if isinstance(char, dict):
                    normalized["characters"].append({
                        "name": char.get("name", "Персонаж"),
                        "visible_traits": {"описание": char.get("traits", "")},
                        "hidden_traits": {}
                    })
            return normalized
        except json.JSONDecodeError as e:
            print(f"\\n[ВНИМАНИЕ] Ошибка парсинга JSON: {e}")
            print(f"Сырой ответ:\\n{response[:500]}")
            return {"error": "Архитектор не вернул JSON", "raw": response}
''')

print("[3/5] Создаём agents/writer.py...")
with open("agents/writer.py", "w", encoding="utf-8") as f:
    f.write('''import os
import json
import requests
import urllib3
import uuid
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()


class WriterAgent:
    def __init__(self):
        self.credentials = os.getenv("GIGACHAT_CREDENTIALS")
        self.scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
        self.token = None
        self.temperature = 0.8

    def _get_token(self):
        url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        headers = {
            "Authorization": f"Basic {self.credentials}",
            "RqUID": str(uuid.uuid4()),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        resp = requests.post(url, headers=headers, data={"scope": self.scope}, verify=False)
        resp.raise_for_status()
        self.token = resp.json()["access_token"]

    def chat(self, messages: list, max_tokens: int = 2000) -> str:
        if not self.token:
            self._get_token()
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        payload = {
            "model": "GigaChat",
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": max_tokens,
        }
        resp = requests.post(url, headers=headers, json=payload, verify=False)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def write_scene(self, scene_plan: dict, ontology_snapshot: dict, previous_text: str = "", genre: str = "") -> str:
        genre_styles = {
            "комедия": "ТЫ ПИШЕШЬ КОМЕДИЮ. Абсурд, контраст, физическая комедия. Минимум ОДИН punchline на сцену. Ноль пафоса.",
            "драма": "ТЫ ПИШЕШЬ ДРАМУ. Напряжение, внутренний конфликт. Эмоции только через действия. Ноль объяснений чувств.",
            "детектив": "ТЫ ПИШЕШЬ ДЕТЕКТИВ. Напряжение через неполную информацию. Улики в деталях.",
            "фэнтези": "ТЫ ПИШЕШЬ ФЭНТЕЗИ. Магический мир с правилами. Герой с миссией.",
            "хоррор": "ТЫ ПИШЕШЬ ХОРРОР. Нарастающее напряжение. Страх неизвестного."
        }
        genre_block = genre_styles.get(genre.lower(), "ТЫ ПИШЕШЬ ХУДОЖЕСТВЕННУЮ ПРОЗУ. Плотный сюжет, живые диалоги.")

        scene_type = scene_plan.get("scene_type", "")
        scene_instruction = ""
        if scene_type == "завязка":
            scene_instruction = "\\nЭто ЗАВЯЗКА. Познакомь с героем, обозначь конфликт."
        elif scene_type == "кульминация":
            scene_instruction = "\\nЭто КУЛЬМИНАЦИЯ. Пик напряжения. Максимум конфликта."
        elif scene_type == "развязка":
            scene_instruction = "\\nЭто РАЗВЯЗКА. ПОСЛЕДНЯЯ СЦЕНА. ЗАПРЕЩЕНО: персонажи НЕ говорят мораль, НЕ делают выводов. Финал холодный, через действие."

        spatial_info = ""
        if "spatial" in ontology_snapshot and ontology_snapshot["spatial"]:
            spatial_info = "\\nПРОСТРАНСТВЕННЫЕ ОТНОШЕНИЯ (соблюдай строго):\\n"
            for sp in ontology_snapshot["spatial"]:
                spatial_info += f"- {sp['from']} {sp['relation']} {sp['to']}\\n"

        system_prompt = f"""Ты - писатель. {genre_block}

АБСОЛЮТНЫЙ ЗАПРЕТ: "чувствовал", "ощутил", "осознал", "понял", "тяжело", "грустно", "невероятный", "ткань реальности", "симфония", "в мире, где", "словно", "как будто", "казалось", "на самом деле", "краснея", "охваченный паникой", "чувствуя себя", "ощущал", "переживал".

ЗАПРЕТ НА МОРАЛИЗАТОРСТВО: персонажи НЕ делают выводов вслух. НЕ говорят "теперь я понял", "оказывается", "главное что".

ПРАВИЛА:
1. Ноль внутренних монологов с объяснением эмоций
2. Только: действия, диалоги, физические детали
3. Диалоги - минимум 30% текста
4. Длина: 200-300 слов{scene_instruction}"""

        visible_context = {k: v for k, v in ontology_snapshot.items() if k != "hidden_layer"}

        user_prompt = f"""План сцены:
{json.dumps(scene_plan, ensure_ascii=False, indent=2)}

Контекст онтологии:
{json.dumps(visible_context, ensure_ascii=False, indent=2)}
{spatial_info}
ЖАНР: {genre.upper()}

{f'Предыдущий текст:\\n{previous_text}\\n' if previous_text else ''}

Напиши текст сцены. ТОЛЬКО художественный текст."""

        response = self.chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ], max_tokens=1500)
        return response.strip()
''')

print("[4/5] Создаём agents/pedant.py (БЕЗ пробелов в фразах)...")
with open("agents/pedant.py", "w", encoding="utf-8") as f:
    f.write('''import os
import json
import requests
import urllib3
import uuid
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()


class PedantAgent:
    BANNED_PHRASES = [
        "невероятный", "ткань реальности", "симфония", "в мире, где",
        "осознал", "понял", "почувствовал", "тяжело", "грустно",
        "как будто", "словно", "казалось", "на самом деле",
        "важно отметить", "стоит сказать", "в заключение",
        "краснея", "охваченный паникой", "чувствуя себя",
        "чувствовал", "ощущал", "переживал",
    ]

    MORALIZING_PHRASES = [
        "теперь я понял", "теперь понял", "я понял, что",
        "оказывается", "главное что", "важно что",
        "делает меня особенным", "наши различия",
        "преимущество", "научился", "понял жизнь",
        "в этом смысл", "вот в чём дело",
    ]

    GARBAGE_PHRASES = [
        "оставить как есть", "см. оригинал", "без изменений",
        "см. выше", "см. текст", "как есть", "без правок",
        "не менял", "оставляю", "см. мой ответ", "оригинальный текст",
    ]

    def __init__(self):
        self.credentials = os.getenv("GIGACHAT_CREDENTIALS")
        self.scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
        self.token = None
        self.temperature = 0.3

    def _get_token(self):
        url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        headers = {
            "Authorization": f"Basic {self.credentials}",
            "RqUID": str(uuid.uuid4()),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        resp = requests.post(url, headers=headers, data={"scope": self.scope}, verify=False)
        resp.raise_for_status()
        self.token = resp.json()["access_token"]

    def chat(self, messages: list, max_tokens: int = 2000) -> str:
        if not self.token:
            self._get_token()
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        payload = {
            "model": "GigaChat",
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": max_tokens,
        }
        resp = requests.post(url, headers=headers, json=payload, verify=False)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def check_banned_phrases(self, text: str) -> list:
        found = []
        text_lower = text.lower()
        for phrase in self.BANNED_PHRASES:
            if phrase in text_lower:
                found.append(phrase)
        return found

    def check_moralizing(self, text: str) -> list:
        found = []
        text_lower = text.lower()
        for phrase in self.MORALIZING_PHRASES:
            if phrase in text_lower:
                found.append(phrase)
        return found

    def _is_garbage_text(self, cleaned: str) -> bool:
        if not cleaned or not isinstance(cleaned, str):
            return True
        cleaned_stripped = cleaned.strip()
        if len(cleaned_stripped) < 100:
            return True
        cleaned_lower = cleaned_stripped.lower()
        for phrase in self.GARBAGE_PHRASES:
            if phrase in cleaned_lower:
                return True
        return False

    def review_text(self, text: str, ontology_snapshot: dict, scene_plan: dict, genre: str = "") -> dict:
        banned = self.check_banned_phrases(text)
        moralizing = self.check_moralizing(text)

        genre_check = ""
        if genre:
            genre_lower = genre.lower()
            if "комед" in genre_lower:
                genre_check = "\\n5. КОМЕДИЙНОСТЬ: есть ли punchline, абсурд? Если НЕ смешная - 1-2 балла. Если СМЕШНАЯ - 8-10."
            elif "драм" in genre_lower:
                genre_check = "\\n5. ДРАМАТИЧНОСТЬ: есть ли конфликт, напряжение?"
            elif "детект" in genre_lower:
                genre_check = "\\n5. ДЕТЕКТИВНОСТЬ: есть ли загадка, улики?"
            elif "фэнтез" in genre_lower:
                genre_check = "\\n5. ФЭНТЕЗИЙНОСТЬ: магический мир?"
            elif "хоррор" in genre_lower:
                genre_check = "\\n5. ХОРРОРНОСТЬ: напряжение, страх?"

        system_prompt = f"""Ты - строгий редактор. Проверяешь:
1. Логические нестыковки (включая пространственные: персонаж не может быть одновременно "внутри" и "рядом с" одним объектом).
2. Принцип "Показывай, а не рассказывай".
3. Слабые диалоги.
4. МОРАЛИЗАТОРСТВО - КРИТИЧЕСКАЯ ОШИБКА. Если персонажи делают выводы вслух - оценка 1-2.
5. Повторы.
{genre_check}

Ответь СТРОГО JSON:
{{
  "score": <1-10>,
  "genre_match": <1-10>,
  "issues": ["проблемы"],
  "logic_violations": ["нарушения"],
  "cleaned_text": "ПОЛНЫЙ исправленный текст сцены. УДАЛИ морализаторство.",
  "event_to_record": {{"description": "что произошло", "node_changes": {{}}}}
}}"""

        user_prompt = f"""План сцены:
{json.dumps(scene_plan, ensure_ascii=False, indent=2)}

Онтология:
{json.dumps(ontology_snapshot, ensure_ascii=False, indent=2)}

Жанр: {genre if genre else "не указан"}

Текст:
{text}

Штампы: {banned}
Морализаторство: {moralizing}

Ревью. В cleaned_text верни ПОЛНЫЙ текст."""

        try:
            response = self.chat([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ], max_tokens=2000)
            clean = response.replace("```json", "").replace("```JSON", "").replace("```", "").strip()
            start = clean.find("{")
            end = clean.rfind("}")
            if start != -1 and end != -1 and end > start:
                clean = clean[start:end+1]
            clean = clean.replace("\\n", " ").replace("\\r", " ").replace("\\t", " ")
            clean = " ".join(clean.split())
            review = json.loads(clean)
        except Exception as e:
            review = {
                "score": 5,
                "genre_match": 5,
                "issues": [f"Ошибка парсинга: {e}"],
                "logic_violations": [],
                "cleaned_text": text,
                "event_to_record": {"description": "Сцена записана", "node_changes": {}},
            }

        if banned:
            review["issues"] = review.get("issues", []) + [f"Штампы: {', '.join(banned)}"]
            review["score"] = max(1, review.get("score", 5) - len(banned))

        if moralizing:
            review["issues"] = review.get("issues", []) + [f"Морализаторство: {', '.join(moralizing)}"]
            review["score"] = max(1, review.get("score", 5) - 4)

        if genre and review.get("genre_match", 10) < 5:
            review["score"] = max(1, review.get("score", 5) - 3)
            review["issues"] = review.get("issues", []) + [f"Жанр не соблюдается"]

        cleaned = review.get("cleaned_text", "")
        if self._is_garbage_text(cleaned):
            review["cleaned_text"] = text
            review["issues"] = review.get("issues", []) + ["Контролёр вернул мусор, используем исходный"]

        return review
''')

print("[5/5] Создаём agent.py...")
with open("agent.py", "w", encoding="utf-8") as f:
    f.write('''import os
import json
import urllib3
from dotenv import load_dotenv
from datetime import datetime
from ontology.memory import StoryOntology
from agents.architect import ArchitectAgent
from agents.writer import WriterAgent
from agents.pedant import PedantAgent
from experiments.runner import ExperimentRunner

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()


class StoryOrchestrator:
    def __init__(self, story_id: str = "story_001"):
        self.ontology = StoryOntology(story_id)
        self.architect = ArchitectAgent()
        self.writer = WriterAgent()
        self.pedant = PedantAgent()
        self.runner = ExperimentRunner()
        self.max_iterations = int(os.getenv("MAX_ITERATIONS", 5))
        self.full_text = ""

    def run_experiment(self, hypothesis: str, config: dict) -> dict:
        print(f"\\n{\\'=\\'*60}")
        print(f"ЭКСПЕРИМЕНТ #{self.runner.experiments.__len__() + 1}")
        print(f"Гипотеза: {hypothesis}")
        print(f"Конфигурация: {json.dumps(config, ensure_ascii=False)}")
        print(f"{\\'=\\'*60}")

        genre = config.get("genre", os.getenv("STORY_GENRE", "психологическая драма"))
        theme = config.get("theme", "человек и его работа")

        print("\\n[1/4] Архитектор проектирует структуру...")
        design = self.architect.design_story(genre, theme)

        if "error" in design:
            print(f"\\n[ОШИБКА АРХИТЕКТОРА]: {design.get(\'error\')}")
            print(f"Сырой ответ:\\n{design.get(\'raw\', \'\')[:500]}")
            print("\\n[ПОВТОРНАЯ ПОПЫТКА]...")
            design = self.architect.design_story(genre, theme)
            if "error" in design:
                print(f"[ПОВТОРНАЯ ОШИБКА]")
                return {"score": 1, "iterations": 0, "verdict": "Ошибка архитектора"}

        self.ontology.metadata["genre"] = genre
        self.ontology.metadata["theme"] = theme

        for char in design.get("characters", []):
            self.ontology.add_character(
                char["name"],
                char.get("visible_traits", {}),
                char.get("hidden_traits", {}) if config.get("use_hidden_layer", True) else None,
            )
        for loc in design.get("locations", []):
            self.ontology.add_location(loc["name"], loc.get("description", ""))
        for obj in design.get("objects", []):
            self.ontology.add_object(obj["name"], obj.get("properties", {}))
        for rel in design.get("relations", []):
            self.ontology.add_relation(rel["from"], rel["to"], rel["relation"])
        for spatial in design.get("spatial_relations", []):
            if "subject" in spatial and "relation" in spatial and "object" in spatial:
                self.ontology.add_spatial_relation(
                    spatial["subject"], spatial["relation"], spatial["object"]
                )

        scenes = design.get("arc", [])[:3]
        scene_types_found = [s.get("scene_type") for s in scenes]
        if len(scenes) < 3 or not all(t in scene_types_found for t in ["завязка", "кульминация", "развязка"]):
            print("[ВНИМАНИЕ] Дополняем сцены...")
            required_types = ["завязка", "кульминация", "развязка"]
            while len(scenes) < 3:
                missing_type = required_types[len(scenes)]
                scenes.append({"scene_type": missing_type, "event": f"Сцена {missing_type}", "node_changes": {}})

        full_text = ""
        iterations = 0
        total_score = 0

        for i, scene_plan in enumerate(scenes):
            iterations += 1
            scene_type = scene_plan.get("scene_type", "неизвестно")
            print(f"\\n[2/4] Сцена {i+1}/{len(scenes)} ({scene_type.upper()}): {scene_plan.get(\'event\', \'\')[:60]}...")

            ontology_snapshot = (
                self.ontology.get_architect_context() if config.get("use_hidden_layer", True)
                else self.ontology.get_scene_context()
            )
            writer_context = self.ontology.get_scene_context()

            spatial_issues = self.ontology.check_spatial_consistency()
            if spatial_issues:
                print(f"  [ВНИМАНИЕ] Пространственные противоречия: {spatial_issues}")

            draft = self.writer.write_scene(scene_plan, writer_context, full_text, genre=genre)

            print(f"[3/4] Контролёр проверяет сцену...")
            review = self.pedant.review_text(draft, ontology_snapshot, scene_plan, genre=genre)
            total_score += review.get("score", 5)

            cleaned = review.get("cleaned_text", draft)
            if not cleaned or len(cleaned.strip()) < 50:
                cleaned = draft

            full_text += "\\n\\n" + cleaned

            event = review.get("event_to_record", {})
            if event:
                self.ontology.record_event(event)

            print(f"  Оценка сцены: {review.get(\'score\', 5)}/10")
            if review.get("issues"):
                print(f"  Замечания: {review[\'issues\'][:2]}")

            if iterations >= self.max_iterations:
                break

        avg_score = round(total_score / max(iterations, 1), 1)
        self.full_text = full_text

        print(f"\\n[4/4] Финальная оценка...")
        verdict = self._evaluate_result(avg_score, review)

        result = {
            "score": avg_score,
            "iterations": iterations,
            "verdict": verdict,
            "text_preview": full_text[:500] + "..." if len(full_text) > 500 else full_text,
        }

        self.runner.log_experiment(hypothesis, config, result)
        self.ontology.save()

        print(f"\\n[ГОТОВО] Средняя оценка: {avg_score}/10")
        return result

    def _evaluate_result(self, score: float, last_review: dict) -> str:
        if score >= 8.5:
            return "ОТЛИЧНО."
        elif score >= 7:
            return "ХОРОШО."
        elif score >= 5:
            return "СРЕДНЕ."
        else:
            return "ПЛОХО."

    def generate_final_story(self, genre: str, theme: str) -> str:
        self.ontology = StoryOntology(f"story_{int(datetime.now().timestamp())}")
        self.full_text = ""

        best_config = self.runner.get_best_config()
        if not best_config:
            best_config = {
                "theme": theme, "genre": genre,
                "use_ontology": True, "use_hidden_layer": True,
                "agents": ["architect", "writer", "pedant"],
            }
        else:
            best_config["theme"] = theme
            best_config["genre"] = genre

        print(f"\\n{\\'=\\'*60}")
        print(f"ГЕНЕРАЦИЯ ФИНАЛЬНОГО РАССКАЗА")
        print(f"Жанр: {genre}")
        print(f"Тема: {theme}")
        print(f"{\\'=\\'*60}")

        self.run_experiment("Финальная генерация", best_config)
        return self.full_text


def main():
    orchestrator = StoryOrchestrator(story_id="final_story")

    print("=" * 60)
    print("  МУЛЬТИАГЕНТНАЯ СИСТЕМА ГЕНЕРАЦИИ РАССКАЗОВ")
    print("  с онтологической памятью (Event Sourcing)")
    print("=" * 60)

    while True:
        print("\\nВыберите действие:")
        print("1. Запустить серию экспериментов")
        print("2. Сгенерировать финальный рассказ")
        print("3. Посмотреть журнал экспериментов")
        print("4. Выход")

        choice = input("\\nВаш выбор: ").strip()

        if choice == "1":
            experiments = [
                {"hypothesis": "Базовая: без онтологии", "config": {"theme": "человек и его работа", "genre": "драма", "use_ontology": False, "use_hidden_layer": False}},
                {"hypothesis": "С онтологией", "config": {"theme": "человек и его работа", "genre": "драма", "use_ontology": True, "use_hidden_layer": True}},
                {"hypothesis": "Комедия с онтологией", "config": {"theme": "первый день в институте", "genre": "комедия", "use_ontology": True, "use_hidden_layer": True}},
                {"hypothesis": "Финальная калибровка", "config": {"theme": "глубоководный сварщик и развод", "genre": "драма", "use_ontology": True, "use_hidden_layer": True}},
            ]
            for exp in experiments:
                orchestrator.run_experiment(exp["hypothesis"], exp["config"])

        elif choice == "2":
            genre = input("Жанр (по умолчанию: драма): ").strip() or "драма"
            theme = input("Тема: ").strip() or "человек и его работа"
            text = orchestrator.generate_final_story(genre, theme)

            print("\\n" + "=" * 60)
            print("ФИНАЛЬНЫЙ РАССКАЗ:")
            print("=" * 60)

            if text.strip():
                print(text)
            else:
                print("\\n[ВНИМАНИЕ] Рассказ не сгенерирован.")

            with open("./final_story.txt", "w", encoding="utf-8") as f:
                f.write(text if text else "Рассказ не был сгенерирован.")
            print(f"\\n[ГОТОВО] Сохранён в ./final_story.txt")

        elif choice == "3":
            print(orchestrator.runner.get_summary())

        elif choice == "4":
            print("Выход.")
            break

        else:
            print("Неверный выбор.")


if __name__ == "__main__":
    main()
''')

print("\n[ГОТОВО] Все файлы обновлены!")
print("Теперь запустите: python agent.py")