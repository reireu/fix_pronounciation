from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn
import requests
import logging

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def emphasize_stress(ipa_text: str) -> str:
    """
    IPA表記中の強勢記号 ˈ の直後の音節を <b>太字化</b>する処理。
    例: ˈɪm.pɔːt → ˈ<b>ɪm</b>.pɔːt
    """
    if not ipa_text:
        return ""

    result = ""
    i = 0
    while i < len(ipa_text):
        if ipa_text[i] == "ˈ":
            result += "ˈ"
            i += 1
            bold_chars = ""
            while i < len(ipa_text) and ipa_text[i] not in [".", " ", "ˌ"]:
                bold_chars += ipa_text[i]
                i += 1
            result += f"<b>{bold_chars}</b>"
        else:
            result += ipa_text[i]
            i += 1
    return result

def fetch_pronunciations(word: str):
    """
    DictionaryAPI.dev から発音データを取得し、UK/US IPA を強勢付きで整形。
    """
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word.lower()}"
    try:
        response = requests.get(url)
        data = response.json()
        logger.info(f"API response for '{word}': {data}")

        phonetics = data[0].get("phonetics", []) if data else []
        uk_pron = ""
        us_pron = ""

        for p in phonetics:
            if "audio" in p and p["audio"]:
                audio_url = p["audio"].lower()
                if "uk" in audio_url:
                    uk_pron = p.get("text", "")
                elif "us" in audio_url:
                    us_pron = p.get("text", "")

        # バックアップ用：先頭2件をUK/US用として補完
        if not uk_pron and len(phonetics) >= 1:
            uk_pron = phonetics[0].get("text", "")
        if not us_pron and len(phonetics) >= 2:
            us_pron = phonetics[1].get("text", "")

        # 強勢記号の太字化
        uk_pron = emphasize_stress(uk_pron)
        us_pron = emphasize_stress(us_pron)

        return uk_pron, us_pron, data

    except Exception as e:
        logger.error(f"API呼び出し中にエラー発生: {e}")
        return "", "", None

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/analyze", response_class=HTMLResponse)
async def analyze_text(request: Request, input_text: str = Form(...)):
    words = [w.strip(",.?!") for w in input_text.split()]
    results = []
    for w in words:
        if not w:
            continue
        uk, us, api_data = fetch_pronunciations(w)
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
