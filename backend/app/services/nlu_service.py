"""
NLU Service — uses LLM to extract structured intents and entities from natural language.
Handles fuzzy time parsing, self-correction, and multi-turn context.
"""

import json
import re
from datetime import datetime, timedelta
from typing import Optional

import logging

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are an intelligent calendar scheduling assistant. Extract structured scheduling intents from user input.

Output ONLY valid JSON with this structure:
{{
  "intent": "create_event|query_events|update_event|delete_event|auto_schedule|set_reminder|general_chat",
  "title": "event title if applicable",
  "start_time": "ISO 8601 datetime string if applicable",
  "end_time": "ISO 8601 datetime string if applicable",
  "location": "location if mentioned",
  "description": "additional details",
  "priority": 0,
  "confidence": 0.0-1.0,
  "needs_clarification": false,
  "clarification_question": "",
  "advance_minutes": 15,
  "remind_type": "popup",
  "origin": ""
}}

Rules:
- Today is {today}. The current time is {current_time}.
- "上午" = morning (8:00-12:00), "下午" = afternoon (13:00-18:00), "晚上" = evening (19:00-22:00)
- "明天" = tomorrow, "后天" = day after tomorrow, "下周" = next week
- "下班前" = before 18:00 today, "午饭后" = around 13:00
- If time is vague, set needs_clarification=true and provide a clarification_question
- For auto_schedule, extract multiple tasks into a tasks array
- If the user is correcting themselves, use the LATEST/corrected information only
- For "提醒" / "提醒我" / "设提醒", intent="set_reminder", extract advance_minutes from phrases like "提前10分钟" (default 15)
- For "出发提醒" / "通勤" / "要多久到" / "多远", include origin and location fields
"""


class NLUService:
    """Natural Language Understanding via LLM."""

    @staticmethod
    def _build_prompt(user_text: str, context: list[dict]) -> list[dict]:
        now = datetime.now()
        system = SYSTEM_PROMPT.format(
            today=now.strftime("%Y-%m-%d"),
            current_time=now.strftime("%H:%M"),
        )
        messages = [{"role": "system", "content": system}]
        messages.extend(context)
        messages.append({"role": "user", "content": user_text})
        return messages

    async def parse(self, text: str, context: Optional[list[dict]] = None) -> dict:
        """Send text to LLM and return structured intent JSON."""
        messages = self._build_prompt(text, context or [])

        # Fallback local parser if LLM is unavailable
        if not settings.llm_api_key:
            return self._local_fallback_parse(text)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    settings.llm_api_url,
                    headers={
                        "Authorization": f"Bearer {settings.llm_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.llm_model,
                        "messages": messages,
                        "temperature": 0.1,
                        "max_tokens": 500,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return self._extract_json(content)
        except Exception as e:
            logger.warning("LLM parse failed, falling back to local parser: %s", e)
            return self._local_fallback_parse(text)

    @staticmethod
    def _extract_json(content: str) -> dict:
        """Extract JSON from LLM response, handling markdown code blocks."""
        # Try to find JSON in code blocks
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
        if match:
            content = match.group(1)
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to find a JSON object in the text
            match = re.search(r'\{[\s\S]*\}', content)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            return {"intent": "general_chat", "confidence": 0.0}

    @staticmethod
    def _local_fallback_parse(text: str) -> dict:
        """Rule-based fallback when LLM is unavailable."""
        result = {
            "intent": "general_chat",
            "title": "",
            "start_time": None,
            "end_time": None,
            "location": "",
            "description": "",
            "priority": 0,
            "confidence": 0.5,
            "needs_clarification": False,
            "clarification_question": "",
            "tasks": [],
            "advance_minutes": 15,
            "remind_type": "popup",
            "origin": "",
        }

        now = datetime.now()

        # Destructive/modify keywords checked FIRST — "提醒我删除..." should
        # be delete_event, not set_reminder.
        if any(kw in text for kw in ["删除", "取消", "去掉"]):
            result["intent"] = "delete_event"
        elif any(kw in text for kw in ["修改", "改成", "改到", "更新", "调整"]):
            result["intent"] = "update_event"
        elif any(kw in text for kw in ["提醒我", "设提醒", "设置提醒", "提醒", "出发提醒", "通勤提醒"]):
            if any(kw in text for kw in ["出发", "通勤", "路程", "多远", "多久到", "交通"]):
                result["intent"] = "set_reminder"
                result["remind_type"] = "commute"
            else:
                result["intent"] = "set_reminder"
        elif any(kw in text for kw in ["创建", "添加", "安排", "约", "预约", "新建", "预定", "预订", "定", "帮我"]):
            result["intent"] = "create_event"
        elif any(kw in text for kw in ["查询", "查看", "今天有什么", "明天有什么", "日程"]):
            result["intent"] = "query_events"
        elif any(kw in text for kw in ["自动安排", "智能排程", "帮我安排", "自动排"]):
            result["intent"] = "auto_schedule"
            result["tasks"] = re.split(r'[，,、]', text)
        elif NLUService._has_specific_time(text) or any(kw in text for kw in ["开会", "见面", "去看", "参加", "面试", "上课", "看病"]):
            # Shorthand: "下午三点开会" or "明天见面" → create_event
            result["intent"] = "create_event"

        # Extract title (simple heuristic: content between keywords)
        title_patterns = [
            r'(?:约|预约|安排|创建|添加|预定|预订|帮我定|帮我约)(?:一个|个|一下|下)?(.+?)(?:在|于|的|，|,|。|$)',
            r'(.+?)(?:在|于)(?:周[一二三四五六日]|今天|明天|后天|下)',
        ]
        for pattern in title_patterns:
            match = re.search(pattern, text)
            if match and match.group(1).strip():
                result["title"] = match.group(1).strip()
                break

        # For delete/update intents, strip prefix keywords and extract time as filter
        if result["intent"] in ("delete_event", "update_event"):
            # Remove command prefix to get the target description
            cleaned = re.sub(r'^(?:删除|取消|去掉|修改|改成|改到|更新|调整)\s*', '', text)
            # Also remove trailing "的日程"/"的安排" etc.
            cleaned = re.sub(r'(?:的日程|的安排|的预约|这个)$', '', cleaned)
            # Extract time from the command, use it for filtering
            extracted_time = NLUService._extract_time(cleaned, now)
            if extracted_time:
                result["start_time"] = extracted_time.isoformat()
            # The title is a hint — strip all time-related words
            hint = re.sub(
                r'[上下中早晚午]午|[点時点半刻]|十[一二]?|[一二两三四五六七八九]|'
                r'今天|明天|后天|大后天|\d{1,2}[：:点分]|'
                r'早上|上午|中午|下午|晚上|周末|周[一二三四五六日]',
                '', cleaned
            )
            hint = re.sub(r'\s+', '', hint).strip()
            if hint and len(hint) >= 1:
                result["title"] = hint
            elif result.get("title") and len(result["title"]) > 20:
                result["title"] = result["title"][:20]

        # If the extracted "title" looks like a time expression, the real title
        # is likely after "的" (e.g. "帮我预定下午三点的会议" → title is "会议")
        if result.get("title") and re.search(r'[上下中早晚午]午|[点時半刻]', result["title"]):
            after_de = re.search(r'的\s*(.+?)(?:$|[，,。])', text)
            if after_de:
                candidate = after_de.group(1).strip()
                if len(candidate) >= 1 and not re.search(r'[上下中早晚午]午|[点時半刻]', candidate):
                    result["title"] = candidate

        if not result.get("title") or len(result["title"]) < 2:
            result["title"] = text[:50]

        # Time extraction
        has_specific = NLUService._has_specific_time(text)
        has_vague_period = any(kw in text for kw in ["上午", "下午", "中午", "晚上", "早上"])
        has_date_keyword = any(kw in text for kw in ["今天", "明天", "后天", "大后天", "周", "星期"])

        if has_specific or has_date_keyword:
            # Only extract a concrete time if one was explicitly given
            result["start_time"] = NLUService._extract_time(text, now)
            if result["start_time"]:
                result["end_time"] = result["start_time"] + timedelta(hours=1)
        elif has_vague_period and result["intent"] == "create_event":
            # Vague "下午" / "上午" with no specific hour → ask for clarification
            result["needs_clarification"] = True
            result["clarification_question"] = "请问大概在几点呢？比如下午三点还是两点？"
            result["start_time"] = None
        else:
            result["start_time"] = NLUService._extract_time(text, now)
            if result["start_time"]:
                result["end_time"] = result["start_time"] + timedelta(hours=1)

        # Extract origin for commute
        origin_match = re.search(r'(?:从|出发地|起点)[：:]?\s*(.+?)(?:到|去|前往)', text)
        if origin_match:
            result["origin"] = origin_match.group(1).strip()

        # Extract location
        loc_match = re.search(r'(?:在|到|去|地点|位置)[：:]?\s*(.+?)(?:，|,|。|$|等|开会|参加|见面)', text)
        if loc_match:
            result["location"] = loc_match.group(1).strip()

        # Extract advance_minutes for reminders
        adv_match = re.search(r'提前(\d+)分钟', text)
        if adv_match:
            result["advance_minutes"] = int(adv_match.group(1))

        return result

    # Map Chinese numeral characters to integers
    CN_NUM = {
        "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
        "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
        "十一": 11, "十二": 12, "零": 0,
    }

    @classmethod
    def _parse_cn_hour(cls, text: str) -> tuple[int | None, int]:
        """Extract hour and minute from Chinese time expressions. Returns (hour, minute)."""
        # Try digit first: "3点", "15:30"
        m = re.search(r'(\d{1,2})[：:点](\d{0,2})?(半)?', text)
        if m:
            hour = int(m.group(1))
            if m.group(3) == "半":  # "3点半"
                return hour, 30
            minute = int(m.group(2)) if m.group(2) else 0
            return hour, minute

        # Chinese numerals: "三点", "两点半", "十一点二十"
        cn_pattern = r'(十[一二]?|[一二两三四五六七八九])[点時](\d{0,2})?(半|刻)?'
        m = re.search(cn_pattern, text)
        if m:
            raw = m.group(1)
            if raw.startswith("十"):
                if len(raw) == 1:
                    hour = 10
                else:  # "十一", "十二"
                    hour = 10 + cls.CN_NUM.get(raw[1], 1)
            else:
                hour = cls.CN_NUM.get(raw, 0)

            minute = 0
            if m.group(2):
                minute = int(m.group(2))
            if m.group(3) == "半":
                minute = 30
            elif m.group(3) == "刻":
                minute = 15
            return hour, minute

        # "半" in context without hour: e.g. "两点半" already handled above, "半" alone is unusual
        return None, 0

    @classmethod
    def _has_specific_time(cls, text: str) -> bool:
        """Check if text contains a specific time reference (digit or Chinese numeral)."""
        if re.search(r'\d{1,2}[：:点]', text):
            return True
        if re.search(r'[一二两三四五六七八九十][点時]', text):
            return True
        return False

    @staticmethod
    def _extract_time(text: str, now: datetime) -> Optional[datetime]:
        """Extract datetime from Chinese natural language."""
        dt = now.replace(second=0, microsecond=0)

        # Date patterns
        if "今天" in text:
            pass  # dt is already today
        elif "明天" in text:
            dt += timedelta(days=1)
        elif "后天" in text:
            dt += timedelta(days=2)
        elif "大后天" in text:
            dt += timedelta(days=3)

        # Day of week
        day_map = {"周一": 0, "周二": 1, "周三": 2, "周四": 3, "周五": 4, "周六": 5, "周日": 6,
                    "星期一": 0, "星期二": 1, "星期三": 2, "星期四": 3, "星期五": 4, "星期六": 5, "星期日": 6,
                    "下周一": 7, "下周二": 8, "下周三": 9, "下周四": 10, "下周五": 11, "下周六": 12, "下周日": 13}
        for kw, target in day_map.items():
            if kw in text:
                days_ahead = target - now.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                dt = now + timedelta(days=days_ahead)
                break

        # Time patterns — try Chinese numerals first, then digits
        hour, minute = NLUService._parse_cn_hour(text)
        if hour is not None:
            if "下午" in text and hour < 12:
                hour += 12
            if "晚上" in text and hour < 19:
                hour += 12
            dt = dt.replace(hour=hour, minute=minute)
        else:
            # Vague time references (no specific hour mentioned)
            if "早上" in text or "上午" in text:
                dt = dt.replace(hour=9, minute=0)
            elif "中午" in text:
                dt = dt.replace(hour=12, minute=0)
            elif "下午" in text:
                dt = dt.replace(hour=15, minute=0)
            elif "晚上" in text:
                dt = dt.replace(hour=20, minute=0)
            elif "下班" in text:
                dt = dt.replace(hour=18, minute=0)
            else:
                return None  # time not specified

        return dt


nlu_service = NLUService()
