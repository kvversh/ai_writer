import os
import json
import requests
import urllib3
import uuid
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()


class StylistAgent:
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

    def chat(self, messages: list) -> str:
        if not self.token:
            self._get_token()
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        payload = {"model": "GigaChat", "messages": messages, "temperature": self.temperature}
        resp = requests.post(url, headers=headers, json=payload, verify=False)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def write_scene(self, scene_plan: dict, ontology_snapshot: dict, previous_text: str = "", genre: str = "") -> str:
        genre_styles = {
            "комедия": """
ТЫ ПИШЕШЬ КОМЕДИЮ в стиле Дугласа Адамса.
- Абсурд, контраст, физическая комедия
- Каждая сцена - минимум ОДИН punchline
- Диалоги с подтекстом и иронией
- ПЛОХО: "Герой чувствовал себя неловко."
- ХОРОШО: "Герой сел на стул. Стул треснул. Все обернулись."
- Ноль пафоса, ноль морализаторства""",
            "драма": """
ТЫ ПИШЕШЬ ДРАМУ в стиле Хемингуэя.
- Напряжение, внутренний конфликт
- Эмоции только через действия
- Диалоги с подтекстом, обрывами
- Ноль объяснений чувств""",
            "детектив": """
ТЫ ПИШЕШЬ ДЕТЕКТИВ.
- Напряжение через неполную информацию
- Улики в деталях
- Подозрительные персонажи
- Финал с поворотом""",
            "фэнтези": """
ТЫ ПИШЕШЬ ФЭНТЕЗИ.
- Магический мир с правилами
- Герой с миссией
- Мифология и легенды""",
            "хоррор": """
ТЫ ПИШЕШЬ ХОРРОР.
- Нарастающее напряжение
- Страх неизвестного
- Зловещая атмосфера через детали"""
        }

        genre_block = genre_styles.get(genre.lower(), """
ТЫ ПИШЕШЬ ХУДОЖЕСТВЕННУЮ ПРОЗУ.
- Плотный сюжет, живые диалоги
- Эмоции через действия""")

        # Определяем тип сцены
        scene_type = scene_plan.get("scene_type", "")
        scene_instruction = ""
        if scene_type == "завязка":
            scene_instruction = "\nЭто ЗАВЯЗКА. Познакомь читателя с героем, обозначь конфликт. Не раскрывай финал."
        elif scene_type == "кульминация":
            scene_instruction = "\nЭто КУЛЬМИНАЦИЯ. Пик напряжения. Ключевое событие. Максимум конфликта."
        elif scene_type == "развязка":
            scene_instruction = """
Это РАЗВЯЗКА. ПОСЛЕДНЯЯ СЦЕНА.
СТРОГИЕ ПРАВИЛА ДЛЯ РАЗВЯЗКИ:
1. Заверши конфликт через ДЕЙСТВИЕ персонажа, а не через слова.
2. ЗАПРЕЩЕНО: персонажи НЕ ДОЛЖНЫ говорить мораль, делать выводы, объяснять смысл.
3. ЗАПРЕЩЕНО: фразы типа "теперь я понял", "оказывается", "главное что", "важно что".
4. Финал должен быть холодным, открытым, без морализаторства.
5. НЕ добавляй продолжения после финала.
Пример ПЛОХОГО финала: "Теперь они поняли, что дружба важна, и пошли дальше."
Пример ХОРОШЕГО финала: "Он молча поднял корзину и пошёл. Осёл посмотрел ему в спину и тоже двинулся в путь." """

        # Получаем пространственный контекст
        spatial_info = ""
        if "spatial" in ontology_snapshot and ontology_snapshot["spatial"]:
            spatial_info = "\nПРОСТРАНСТВЕННЫЕ ОТНОШЕНИЯ (соблюдай их строго):\n"
            for sp in ontology_snapshot["spatial"]:
                spatial_info += f"- {sp['from']} {sp['relation']} {sp['to']}\n"

        system_prompt = f"""Ты - писатель. {genre_block}

АБСОЛЮТНЫЙ ЗАПРЕТ на слова: "чувствовал", "ощутил", "осознал", "понял", "тяжело", "грустно", "невероятный", "ткань реальности", "симфония", "в мире, где", "словно", "как будто", "казалось", "на самом деле", "краснея", "охваченный паникой", "чувствуя себя", "чувствовал", "ощущал", "переживал".

ЗАПРЕТ НА МОРАЛИЗАТОРСТВО:
- Персонажи НЕ ДОЛЖНЫ делать выводы вслух
- НЕ ДОЛЖНЫ говорить "теперь я понял", "оказывается", "главное что", "важно что"
- НЕ ДОЛЖНЫ объяснять смысл происходящего
- Вместо морали - действие, жест, пауза

ПРАВИЛА ПРОСТРАНСТВЕННОЙ ЛОГИКИ:
- Если персонаж "внутри" объекта - он НЕ МОЖЕТ одновременно быть "рядом с" этим же объектом
- Если персонаж "на" объекте - он НЕ МОЖЕТ быть "внутри" этого же объекта
- Соблюдай пространственные отношения строго

ПРАВИЛА:
1. Ноль внутренних монологов с объяснением эмоций
2. Только: действия, диалоги, физические детали
3. Диалоги - минимум 30% текста
4. Каждая сцена двигает сюжет
5. Длина: 200-300 слов на сцену
6. НЕ ПИШИ продолжение после финала сцены.{scene_instruction}"""

        visible_context = {k: v for k, v in ontology_snapshot.items() if k != "hidden_layer"}

        user_prompt = f"""План сцены:
{json.dumps(scene_plan, ensure_ascii=False, indent=2)}

Контекст онтологии:
{json.dumps(visible_context, ensure_ascii=False, indent=2)}
{spatial_info}
ЖАНР: {genre.upper()}

{f'Предыдущий текст:\n{previous_text}\n' if previous_text else ''}

Напиши текст сцены. ТОЛЬКО художественный текст. БЕЗ комментариев и продолжений."""

        response = self.chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])
        return response.strip()