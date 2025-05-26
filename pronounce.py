from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn
import requests
import logging
import re

app = FastAPI()
templates = Jinja2Templates(directory="templates")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#ipa表示にするなどしている
def apply_pronunciation_styles(ipa_text: str, r_drop_color: str = "pink") -> str:
    if not ipa_text:
        return ""

    processed_text = ""
    i = 0
    while i < len(ipa_text):
        char = ipa_text[i]
        if char == "ˈ":
            processed_text += "ˈ"
            i += 1
            bold_chars = ""
            while i < len(ipa_text) and ipa_text[i] not in [".", " ", "ˌ", "ˈ"]:
                bold_chars += ipa_text[i]
                i += 1
            processed_text += f"<b>{bold_chars}</b>"
            continue
        if char == "ˌ":
            processed_text += "ˌ"
            i += 1
            continue
        match = re.match(r"([aæeɪiɒɔuʊəʌtdszʒʃθðŋlrwjy])r([. ]|$)", ipa_text[i:])
        if match and ipa_text[i] == 'r':
            processed_text += f'<span style="color:{r_drop_color};">{char}</span>'
        else:
            processed_text += char
        i += 1
    return processed_text

def fetch_pronunciations(word: str):
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word.lower()}"
    try:
        response = requests.get(url)
        data = response.json()
        logger.info(f"API response for '{word}': {data}")

        phonetics = data[0].get("phonetics", []) if data and isinstance(data, list) and len(data) > 0 else []
        uk_pron, us_pron = "", ""

        for p in phonetics:
            if "audio" in p and p["audio"]:
                audio_url = p["audio"].lower()
                if "uk" in audio_url and not uk_pron:
                    uk_pron = p.get("text", "")
                if "us" in audio_url and not us_pron:
                    us_pron = p.get("text", "")
            if "text" in p:
                if "(UK)" in p["text"] and not uk_pron:
                    uk_pron = p["text"].replace("(UK)", "").strip()
                if "(US)" in p["text"] and not us_pron:
                    us_pron = p["text"].replace("(US)", "").strip()

        if not uk_pron and phonetics:
            for p in phonetics:
                if "text" in p and "audio" not in p:
                    uk_pron = p["text"]
                    break
        if not us_pron and phonetics:
            for p in phonetics:
                if "text" in p and "audio" not in p and p["text"] != uk_pron:
                    us_pron = p["text"]
                    break

        styled_uk_pron = apply_pronunciation_styles(uk_pron, r_drop_color="pink")
        styled_us_pron = apply_pronunciation_styles(us_pron, r_drop_color="transparent")

        return styled_uk_pron, styled_us_pron, data

    except Exception as e:
        logger.error(f"API Error: {e}")
        return "", "", None

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/analyze", response_class=HTMLResponse)
async def analyze_text(request: Request, input_text: str = Form(...)):
    words = [w.strip(",.?!\"'()[]{}<>").lower() for w in input_text.split()]
    results = []
    for w in words:
        if not w:
            continue
        uk, us, api_data = fetch_pronunciations(w)
        if not uk and not us:
            uk = us = "N/A"
        results.append({
            "word": w,
            "uk": uk,
            "us": us,
            "api_data": api_data
        })
    return templates.TemplateResponse("index.html", {
        "request": request,
        "input_text": input_text,
        "results": results
    })

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
