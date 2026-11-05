import os

import httpx

from app.config import settings


def fallback_explanation(course_name: str, grade: str, interests: str, prereq_ok: bool = True) -> str:
    parts = []
    if grade:
        parts.append(f'Nilai {course_name} terkait {grade}')
    if interests:
        parts.append(f'minat {interests}')
    if prereq_ok:
        parts.append('prasyarat terpenuhi')
    return '; '.join(parts) if parts else f'Kesesuaian kursus {course_name} cukup tinggi.'


async def generate_explanation(course_name: str, interests: str, related_grade: str, prereq_ok: bool = True) -> str:
    key = settings.gemini_api_key or os.getenv('GEMINI_API_KEY', '')
    if not key:
        return fallback_explanation(course_name, related_grade, interests, prereq_ok)
    model = settings.gemini_model or os.getenv('GEMINI_MODEL', 'gemini-2.0-flash-lite')
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}'
    prompt = (
        'Buat penjelasan singkat dalam bahasa Indonesia untuk rekomendasi mata kuliah. '
        'Gunakan fakta teknis anonim: nama mata kuliah, minat mahasiswa, nilai terkait, status prasyarat. '
        'Tidak boleh menentukan skor atau melanggar prasyarat. '
        f'Nama mata kuliah: {course_name}; minat: {interests}; nilai terkait: {related_grade}; prasyarat terpenuhi: {str(prereq_ok).lower()}. '
        'Jawab maksimal 2 kalimat.'
    )
    payload = {'contents': [{'parts': [{'text': prompt}]}]}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(url, json=payload)
            if response.status_code in (429, 500):
                return fallback_explanation(course_name, related_grade, interests, prereq_ok)
            data = response.json()
            return data['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception:
        return fallback_explanation(course_name, related_grade, interests, prereq_ok)
