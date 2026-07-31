import os
import json
import re
import requests
import urllib3
import uuid
from typing import Optional
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

class CriticAgent:
    """
    Критик - оценивает текст по 5 критериям из задания.
    НЕ редактирует текст, только оценивает.
    """
    
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

    def _extract_json(self, text: str) -> dict:
        """Пытается извлечь JSON из текста, даже если есть лишний мусор."""
        
        # 1. Убираем markdown
        clean = re.sub(r'```json\s*|```JSON\s*|```\s*', '', text)
        
        # 2. Ищем JSON объект
        start = clean.find('{')
        end = clean.rfind('}')
        
        if start == -1 or end == -1 or end <= start:
            raise ValueError("JSON не найден в ответе")
        
        json_str = clean[start:end+1]
        
        # 3. Пробуем распарсить как есть
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        
        # 4. Пробуем починить: заменяем одинарные кавычки на двойные
        # Но аккуратно: не трогаем кавычки внутри уже существующих строк
        try:
            # Заменяем ' на " только если это не внутри существующих "
            # Простой способ: экранируем все одинарные кавычки внутри строк
            fixed = re.sub(r"'([^']*)'", r'"\1"', json_str)
            # Убираем trailing commas
            fixed = re.sub(r',\s*}', '}', fixed)
            fixed = re.sub(r',\s*]', ']', fixed)
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass
        
        # 5. Пробуем найти JSON через регулярное выражение (самый простой способ)
        try:
            # Ищем JSON объект с помощью regex
            json_pattern = r'\{[^{}]*\}'
            matches = re.findall(json_pattern, clean)
            for match in matches:
                try:
                    return json.loads(match)
                except:
                    continue
        except:
            pass
        
        raise ValueError("Не удалось извлечь JSON из ответа")

    def evaluate(self, text: str, genre: str = "", scene_plan: Optional[dict] = None) -> dict:
        """
        Оценивает текст по 5 критериям из задания.
        
        Критерии:
        1. Стилистическая чистота (0-10) - отсутствие клише, канцелярита, ИИ-штампов
        2. Плотность и конкретика (0-10) - отсутствие общих слов и лишних элементов
        3. Глубина и подтекст (0-10) - читатель понимает больше, чем написано
        4. Архитектура рассказа (0-10) - динамика конфликта, сюжет, пропорциональность
        5. Оригинальность (0-10) - небанальность идеи и психологическая достоверность
        """
        
        # Безопасная обработка genre
        safe_genre = genre if genre else "не указан"
        
        # Определяем критерии для жанра
        genre_criteria = ""
        if genre:
            genre_lower = genre.lower()
            if "комед" in genre_lower:
                genre_criteria = "Оцени также комедийность: наличие юмора, абсурда, punchline'ов."
            elif "драм" in genre_lower:
                genre_criteria = "Оцени также драматичность: внутренний конфликт, напряжение."
            elif "детект" in genre_lower:
                genre_criteria = "Оцени также детективность: загадка, улики, повороты."
            elif "фэнтез" in genre_lower:
                genre_criteria = "Оцени также фэнтезийность: магический мир, правила."
            elif "хоррор" in genre_lower:
                genre_criteria = "Оцени также хоррорность: нарастающее напряжение, атмосфера страха."

        # Безопасное преобразование scene_plan в строку
        scene_plan_str = ""
        if scene_plan and isinstance(scene_plan, dict):
            try:
                scene_plan_str = f"План сцены: {json.dumps(scene_plan, ensure_ascii=False, indent=2)}"
            except Exception:
                scene_plan_str = f"План сцены: {str(scene_plan)[:200]}"
        else:
            scene_plan_str = "План сцены: не указан"

        # Ограничиваем длину текста
        safe_text = text[:3000] if text else "Текст отсутствует"
        if text and len(text) > 3000:
            safe_text += "\n...(текст обрезан)"

        system_prompt = f"""Ты - строгий литературный критик. Оцени текст по 5 критериям.

КРИТЕРИИ ОЦЕНКИ (каждый от 0 до 10):
1. Стилистическая чистота - отсутствие клише, канцелярита, ИИ-штампов
2. Плотность и конкретика - отсутствие общих слов, лишних элементов, персонажей
3. Глубина и подтекст - читатель понимает больше, чем написано буквально
4. Архитектура рассказа - динамика конфликта, сюжет, пропорциональность частей
5. Оригинальность - небанальность идеи и психологическая достоверность

{genre_criteria}

ОТВЕТЬ ТОЛЬКО JSON. НИКАКОГО ДРУГОГО ТЕКСТА.
Пример ответа:
{{
    "stylistic_purity": 8,
    "density": 7,
    "depth": 9,
    "architecture": 8,
    "originality": 7,
    "total_score": 39,
    "average_score": 7.8,
    "strengths": ["сильная сторона 1", "сильная сторона 2"],
    "weaknesses": ["слабая сторона 1", "слабая сторона 2"],
    "genre_match": 8,
    "comment": "краткий комментарий"
}}"""

        user_prompt = f"""Жанр: {safe_genre}

{scene_plan_str}

Текст для оценки:
{safe_text}

Оцени текст по всем критериям. Ответь ТОЛЬКО JSON."""

        try:
            response = self.chat([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ])
            
            # Используем улучшенный парсинг
            result = self._extract_json(response)
            
            # Добавляем недостающие поля
            default_result = {
                "stylistic_purity": 5,
                "density": 5,
                "depth": 5,
                "architecture": 5,
                "originality": 5,
                "total_score": 25,
                "average_score": 5.0,
                "genre_match": 5,
                "strengths": [],
                "weaknesses": [],
                "comment": "Оценка выполнена."
            }
            
            for key in default_result:
                if key not in result or result[key] is None:
                    result[key] = default_result[key]
            
            # Убеждаемся, что average_score - число
            if "average_score" not in result or result["average_score"] is None:
                total = sum([
                    result.get("stylistic_purity", 5),
                    result.get("density", 5),
                    result.get("depth", 5),
                    result.get("architecture", 5),
                    result.get("originality", 5)
                ])
                result["average_score"] = round(total / 5, 1)
                result["total_score"] = total
                
            return result
            
        except Exception as e:
            print(f"[ОШИБКА в CriticAgent]: {e}")
            print(f"Сырой ответ (первые 300 символов): {response[:300] if 'response' in locals() else 'Нет ответа'}")
            return {
                "stylistic_purity": 5,
                "density": 5,
                "depth": 5,
                "architecture": 5,
                "originality": 5,
                "total_score": 25,
                "average_score": 5.0,
                "genre_match": 5,
                "strengths": [],
                "weaknesses": ["Ошибка оценки от критика"],
                "comment": "Не удалось выполнить оценку"
            }