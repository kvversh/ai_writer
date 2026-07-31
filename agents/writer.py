import os
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
            "комедия": """
КОМЕДИЙНЫЕ ПРИНЦИПЫ:
1. Setup-Punchline: обычная ситуация переходит в абсурдный поворот
2. Контраст: персонаж не вписывается в мир
3. Физическая комедия: неуклюжесть, разрушение
4. Ирония: читатель понимает больше, чем персонаж""",
            "драма": """
ДРАМАТИЧЕСКИЕ ПРИНЦИПЫ:
1. Внутренний конфликт персонажа
2. Напряжение нарастает к кульминации
3. Эмоции через действия, не объяснения
4. Открытый финал""",
            "детектив": """
ДЕТЕКТИВНЫЕ ПРИНЦИПЫ:
1. Загадка в начале
2. Улики в деталях
3. Развязка с поворотом""",
            "фэнтези": """
ФЭНТЕЗИЙНЫЕ ПРИНЦИПЫ:
1. Магический мир с правилами
2. Герой с миссией""",
            "хоррор": """
ХОРРОР-ПРИНЦИПЫ:
1. Нарастающее напряжение
2. Страх неизвестного
3. Зловещая атмосфера"""
        }

        genre_block = genre_instructions.get(genre.lower(), """
ОБЩИЕ ПРИНЦИПЫ:
1. Сильный конфликт
2. Живые диалоги
3. Плотный сюжет""")

        system_prompt = (
            "Ты - литературный архитектор. Спроектируй КРАТКУЮ структуру рассказа в жанре " + genre.upper() + ".\n\n"
            + genre_block + "\n\n"
            "СТРУКТУРА (СТРОГО 3 СЦЕНЫ):\n"
            "1. ЗАВЯЗКА - знакомство с героем\n"
            "2. КУЛЬМИНАЦИЯ - пик напряжения\n"
            "3. РАЗВЯЗКА - холодный финал без морали\n\n"
            "ЗАПРЕТ НА МОРАЛИЗАТОРСТВО: персонажи НЕ ДОЛЖНЫ делать выводы вслух.\n\n"
            "Ответь СТРОГО в формате JSON (БЕЗ markdown, БЕЗ комментариев):\n"
            "{\n"
            '  "title": "название",\n'
            '  "characters": [\n'
            '    {"name": "имя", "traits": "2-3 ключевые черты"},\n'
            '    {"name": "имя", "traits": "2-3 ключевые черты"}\n'
            '  ],\n'
            '  "location": "основная локация",\n'
            '  "arc": [\n'
            '    {"scene_type": "завязка", "event": "1 предложение"},\n'
            '    {"scene_type": "кульминация", "event": "1 предложение"},\n'
            '    {"scene_type": "развязка", "event": "1 предложение БЕЗ морали"}\n'
            '  ]\n'
            "}\n\n"
            "БУДЬ КРАТОК. Каждый event - максимум 1 предложение. Отвечай ТОЛЬКО JSON."
        )

        user_prompt = f"Жанр: {genre}\nТема: {theme}\n\nСпроектируй КРАТКУЮ структуру."

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
            
            # Нормализуем структуру под ожидаемый формат
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
            print(f"\n[ВНИМАНИЕ] Ошибка парсинга JSON: {e}")
            print(f"Сырой ответ:\n{response[:500]}")
            return {"error": "Архитектор не вернул JSON", "raw": response}

    def plan_next_scene(self, ontology_context: dict, scene_number: int) -> dict:
        system_prompt = """Ты - литературный архитектор. Спланируй сцену.
Ответь СТРОГО в JSON:
{
  "scene_goal": "цель сцены",
  "event": "что происходит"
}"""
        user_prompt = f"Онтология:\n{json.dumps(ontology_context, ensure_ascii=False, indent=2)}\n\nНомер сцены: {scene_number}"
        response = self.chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ], max_tokens=800)
        try:
            clean = response.replace("```json", "").replace("```", "").strip()
            return json.loads(clean)
        except json.JSONDecodeError:
            return {"error": "Не удалось распарсить", "raw": response}