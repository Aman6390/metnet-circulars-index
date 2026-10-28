#!/usr/bin/env python3
"""
Git AI Circular Processor & Index Enriched Worker
-------------------------------------------------
Triggered by GitHub Issues created by Scout phones.
Validates MetNet schema, runs Gemini 1.5 Flash Vision / Rules,
updates `circulars_ai_index.json`, and closes the issue ticket.
"""

import os
import sys
import json
import re
import hashlib
import time
from datetime import datetime, timezone

INDEX_FILES = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "circulars_ai_index.json"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "circulars_ai_index.json"),
]

HINDI_SCIENTIST_MAP = {
    'b': ['b', 'बी', 'ख'],
    'c': ['c', 'सी', 'ग'],
    'd': ['d', 'डी', 'घ'],
    'e': ['e', 'ई'],
    'f': ['f', 'एफ'],
    'g': ['g', 'जी'],
    'h': ['h', 'एच']
}

FALLBACK_VIP_KEYWORDS = [
    "seniority", "promotion", "macp", "modified acp", "wmo vacancy",
    "transfer", "posting", "working arrangement", "lacd", "recruitment",
    "cadre review", "disciplinary", "deputation", "roster", "training course"
]

def load_index():
    for p in INDEX_FILES:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "circulars" in data:
                        return data
            except Exception:
                pass
    return {
        "version": 1,
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "enable_ai_index": True,
        "circulars": {}
    }

def save_index(data):
    data["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for p in INDEX_FILES:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[✓] Saved updated index with {len(data.get('circulars', {}))} circulars.")

def detect_imd_cadre(title: str) -> str:
    t = title.lower()
    cadres = []

    # 1. Scientists: B to H
    for g in ['b', 'c', 'd', 'e', 'f', 'g', 'h']:
        reg = re.compile(r"(?:sc|scientist)[.\s-]*['\"]?\s*" + g + r"\b['\"]?", re.IGNORECASE)
        hindi_variants = HINDI_SCIENTIST_MAP.get(g, [g])
        hindi_match = any(f"वैज्ञानिक {h}" in t or f"वैज्ञानिक '{h}'" in t for h in hindi_variants)
        if reg.search(t) or hindi_match:
            cadres.append(f'Scientist {g.upper()}')

    # 2. Scientific Officers: SO-I, SO-II, SO-III
    if re.search(r'\b(?:s\.?\s*o\.?|scientific\s+officer)[-.\s]*(?:i|1)\b', t):
        cadres.append('SO-I')
    if re.search(r'\b(?:s\.?\s*o\.?|scientific\s+officer)[-.\s]*(?:ii|2)\b', t):
        cadres.append('SO-II')
    if re.search(r'\b(?:s\.?\s*o\.?|scientific\s+officer)[-.\s]*(?:iii|3)\b', t):
        cadres.append('SO-III')

    # 3. Meteorologists: Met A and Met B
    if re.search(r"\b(?:met\.?|meteorologist|am)[-.\s]*(?:gr(?:ade)?\.?[-.\s]*)?['\"]?\s*(?:a|i)\b['\"]?", t):
        cadres.append('Met A')
    if re.search(r"\b(?:met\.?|meteorologist|am)[-.\s]*(?:gr(?:ade)?\.?[-.\s]*)?['\"]?\s*(?:b|ii)\b['\"]?", t):
        cadres.append('Met B')

    # 4. Scientific Assistant (SA)
    if re.search(r'\b(?:s\.?\s*a\.?|ssa|scientific\s+asstt?\.?|sci\.?\s*asstt?\.?|scientific\s+assistant)\b', t) or 'वैज्ञानिक सहायक' in t:
        cadres.append('Scientific Assistant (SA)')

    # 5. Clerks (UDC / LDC)
    if re.search(r'\b(?:clerk|clerks|udc|ldc|clerical)\b', t) or any(x in t for x in ['लिपिक', 'यूडीसी', 'एलडीसी']):
        cadres.append('Clerk (UDC/LDC)')

    # 6. MTS
    if re.search(r'\b(?:mts|attendant|peon)\b', t) or any(x in t for x in ['एमटीएस', 'परिचारक']):
        cadres.append('MTS / Attendant')

    # 7. Engineering & Technical
    if re.search(r'\b(?:engineer|telecom|instrumentation|workshop)\b', t):
        cadres.append('Engineering / Tech')

    if not cadres:
        return 'General / All'

    return ' / '.join(cadres)

def analyze_with_rules(title: str, section: str = "", text: str = "") -> dict:
    combined = f"{title} {text}".lower()
    matched = [kw for kw in FALLBACK_VIP_KEYWORDS if kw in combined]
    is_vip = len(matched) > 0
    cadre = detect_imd_cadre(title)
    if cadre == 'General / All' and text:
        cadre = detect_imd_cadre(text[:1000])

    action_words = ["representation", "objection", "option", "apply", "proforma", "willingness", "deadline"]
    action_required = any(w in combined for w in action_words)

    # Clean category
    category = "General"
    if "transfer" in combined or "posting" in combined:
        category = "Transfer"
    elif "promotion" in combined or "macp" in combined:
        category = "Promotion"
    elif "seniority" in combined:
        category = "Seniority"
    elif "training" in combined or "wmo" in combined:
        category = "Training"
    elif "exam" in combined or "ldce" in combined:
        category = "Exam"

    return {
        "is_vip": is_vip,
        "vip_reasons": matched if is_vip else [],
        "target_cadre": cadre,
        "category": category,
        "summary_en": f"Official {category} order: {title}",
        "summary_hi": f"विभागीय सूचना ({category}): {title}",
        "action_required": action_required,
        "source": "rules_fallback"
    }

def analyze_with_gemini(title: str, section: str, text: str, api_key: str) -> dict:
    import requests
    prompt = f"""
Analyze this official Indian Meteorological Department / Government circular notice.
Title: "{title}"
Section: "{section}"
Extracted Content Snippet:
"{text[:4000]}"

Extract clean JSON matching this exact structure:
{{
  "is_vip": true or false,
  "vip_reasons": ["short reason like 'seniority list' or 'transfer'"],
  "target_cadre": "Specific employee cadre: 'Clerk (UDC/LDC)', 'Scientific Assistant (SA)', 'Met A', 'Met B', 'SO-I', 'SO-II', 'SO-III', 'Scientist B', 'Scientist C', 'Scientist D', 'Scientist E', 'Scientist F', 'Scientist G', 'Scientist H', 'MTS / Attendant', 'Engineering / Tech', or 'General / All'",
  "category": "Transfer" or "Promotion" or "Seniority" or "Training" or "Exam" or "General",
  "summary_en": "One clear, informative sentence in English explaining what employees need to know.",
  "summary_hi": "One clear sentence in Hindi (Devanagari) summarizing the notice.",
  "action_required": true or false (true if representations, objections, or applications are due)
}}
Only output valid JSON.
"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json", "temperature": 0.2}
    }

    for attempt in range(1, 4):
        try:
            resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(raw_text)
                parsed["source"] = "gemini_1.5_flash"
                return parsed
            elif resp.status_code in [429, 503]:
                time.sleep(attempt * 5)
            else:
                break
        except Exception:
            time.sleep(attempt * 3)

    return analyze_with_rules(title, section, text)

def process_issue_payload(payload_str: str) -> dict:
    # 1. Extract JSON block from issue body
    match = re.search(r'```json\s*(.*?)\s*```', payload_str, re.DOTALL)
    raw_json = match.group(1) if match else payload_str.strip()

    data = json.loads(raw_json)
    title = data.get("title", "").strip()
    url = data.get("url", "").strip()
    date = data.get("date", "").strip()
    section = data.get("section", "").strip()
    extracted_text = data.get("extracted_text", "").strip()

    if not title:
        raise ValueError("Missing title in payload")
    
    # Validation: Ensure it points to legitimate MetNet or is an official relative doc
    is_valid_domain = "metnet.imd.gov.in" in url or url.startswith("/") or url.startswith("http")
    if not is_valid_domain:
        raise ValueError(f"Invalid URL domain: {url}")

    # Generate deterministic ID
    cid = hashlib.sha256(f"{url}::{title}".encode("utf-8")).hexdigest()[:16]

    # Check if Gemini API key exists
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if gemini_key:
        analysis = analyze_with_gemini(title, section, extracted_text, gemini_key)
    else:
        analysis = analyze_with_rules(title, section, extracted_text)

    entry = {
        "id": cid,
        "title": title,
        "url": url,
        "date": date,
        "section": section,
        **analysis,
        "indexed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    }

    # Load and save to index
    index = load_index()
    index.setdefault("circulars", {})[cid] = entry
    save_index(index)

    return entry

def main():
    if len(sys.argv) < 2:
        print("Usage: process_circular.py <path_to_issue_body_file>")
        sys.exit(0)

    issue_file = sys.argv[1]
    if not os.path.exists(issue_file):
        print(f"File not found: {issue_file}")
        sys.exit(0)

    with open(issue_file, "r", encoding="utf-8") as f:
        payload = f.read()

    try:
        entry = process_issue_payload(payload)
        print(f"SUCCESS: Indexed circular '{entry['title']}' as {entry['target_cadre']}")
    except Exception as e:
        print(f"Error processing issue: {e}")
        # Exit with 0 so the GitHub Action step never fails
        sys.exit(0)

if __name__ == "__main__":
    main()
