import os
import json
import requests
import urllib3
import uuid
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

class EditorAgent:
    """
    Редактор - удаляет штампы, ИИ-артефакты, исправляет стилистические ошибки.
    НЕ выставляет оценки, НЕ критикует.
    """
    
    # Списки запрещенных фраз (такие же как у PedantAgent)
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

    def chat(self, messages: list) -> str:
        if not self.token:
            self._get_token()
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        payload = {"model": "GigaChat", "messages": messages, "temperature": self.temperature}
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

    def edit_text(self, text: str, ontology_snapshot: dict, scene_plan: dict, genre: str = "") -> dict:
        """
        Редактирует текст: удаляет штампы, морализаторство, исправляет стиль.
        Возвращает исправленный текст и список исправлений.
        """
        banned = self.check_banned_phrases(text)
        moralizing = self.check_moralizing(text)

        system_prompt = f"""Ты - строгий литературный редактор. Твоя задача - исправить текст, НЕ меняя сюжет.

        ЧТО НУЖНО ИСПРАВИТЬ:
        1. Удали все ИИ-штампы и клише
        2. Удали морализаторство (персонажи НЕ должны делать выводы вслух)
        3. Исправь повторы
        4. Сделай язык более живым и конкретным
        5. Удали общие слова, добавь конкретику

        ЧТО НЕЛЬЗЯ МЕНЯТЬ:
        - Сюжет и события
        - Имена персонажей
        - Основные диалоги

        Верни JSON с исправленным текстом:
        {{
            "cleaned_text": "исправленный текст",
            "changes": ["список сделанных изменений"]
        }}"""

        user_prompt = f"""Жанр: {genre}
        
        План сцены:
        {json.dumps(scene_plan, ensure_ascii=False, indent=2)}
        
        Онтология:
        {json.dumps(ontology_snapshot, ensure_ascii=False, indent=2)}
        
        Найденные штампы: {banned}
        Найденное морализаторство: {moralizing}
        
        Текст для редактирования:
        {text}
        
        Отредактируй текст и верни JSON."""

        try:
            response = self.chat([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ])
            
            clean = response.replace("```json", "").replace("```JSON", "").replace("```", "").strip()
            start = clean.find("{")
            end = clean.rfind("}")
            if start != -1 and end != -1 and end > start:
                clean = clean[start:end+1]
            result = json.loads(clean)
            
            # Если результат пустой или слишком короткий - возвращаем исходный текст
            cleaned = result.get("cleaned_text", text)
            if not cleaned or len(cleaned.strip()) < 50:
                cleaned = text
                
            return {
                "cleaned_text": cleaned,
                "changes": result.get("changes", []),
                "banned_found": banned,
                "moralizing_found": moralizing
            }
            
        except Exception as e:
            return {
                "cleaned_text": text,
                "changes": [f"Ошибка редактирования: {e}"],
                "banned_found": banned,
                "moralizing_found": moralizing
            }