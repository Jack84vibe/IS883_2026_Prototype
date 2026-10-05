import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from google import genai
from google.genai import types

st.set_page_config(page_title="Black Hole Rescue", page_icon="🕳️", layout="wide")

### Load your API Key
try:
    gemini_api_key = st.secrets['MyGeminiKey']# Info: https://docs.streamlit.io/develop/api-reference/connections/st.secrets
except (KeyError, FileNotFoundError):
    st.error("No Gemini key found. Add `MyGeminiKey` under **Manage app → ⋮ → Settings → Secrets**, then refresh this page.")
    st.stop()
client = genai.Client(api_key=gemini_api_key)

# The second model is a backup for when the first one is overloaded (503 UNAVAILABLE)
MODELS = ["gemini-3.1-flash-lite", "gemini-2.5-flash-lite"]

# The game itself runs in the browser (Three.js); it lives next to this file
GAME_HTML = Path(__file__).parent / "black_hole_game.html"

LANGUAGES = {
    "中文": {
        "title": "🕳️ 黑洞救援",
        "intro": "飛船正被黑洞吞噬！點擊飛船啟動救援系統，讓船員乘坐救援艙逃離。求救信號由 Gemini 生成。",
        "button": "📡 接收新的求救信號",
        "loading": "正在接收求救信號……",
        "offline": "Gemini 暫時無法連線，飛船改用備用求救信號。",
        "prompt_language": "Traditional Chinese, each under 18 characters",
        "hud": {"rescued": "已救援船員", "lost": "損失飛船", "crew": "名船員",
                "hint": "點擊飛船，啟動救援系統"},
        "fallback": ["救命！引擎拉不動了！", "船體快撐不住了！", "重力讀數爆表，請求支援！",
                     "有人收到嗎？我們正在墜落！", "導航失靈，正被拉向黑洞！"],
    },
    "English": {
        "title": "🕳️ Black Hole Rescue",
        "intro": "Ships are falling into a black hole! Click a ship to fire its escape pods. Gemini writes their distress calls.",
        "button": "📡 Receive new distress calls",
        "loading": "Receiving distress calls...",
        "offline": "Gemini is unreachable right now, so the ships use backup distress calls.",
        "prompt_language": "English, each under 12 words",
        "hud": {"rescued": "Crew rescued", "lost": "Ships lost", "crew": "crew",
                "hint": "Click a ship to launch its escape pods"},
        "fallback": ["Mayday! Engines can't escape the pull!", "Hull is buckling, please help!",
                     "Gravity off the charts, need rescue!", "Anyone out there? We're falling!",
                     "Navigation is dead, we're being pulled in!"],
    },
}


### Ask Gemini ONCE for a batch of distress calls; cached so reruns don't spend your API quota
@st.cache_data(ttl=600, show_spinner=False)
def generate_distress_calls(prompt_language):
    prompt = (
        "You write radio chatter for a small arcade game. Spaceships are being pulled into a black hole. "
        f"Write 24 different short distress calls the crews send, in {prompt_language}. "
        "Vary the tone: panicked, calm and professional, darkly funny, desperate. "
        "No numbering and no quotation marks."
    )
    last_error = None
    for model in MODELS:
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                # Ask for a JSON list of strings, so there is no text to parse by hand
                config=types.GenerateContentConfig(temperature=1.2, response_mime_type="application/json",
                                                   response_schema=list[str]),
            )
            calls = [call.strip()[:80] for call in (response.parsed or []) if call.strip()]
            if calls:
                return calls
        except Exception as error:  # e.g. 503 overloaded or 429 quota: try the next model
            last_error = error
    raise RuntimeError(f"No distress calls from Gemini: {last_error}")  # errors are not cached, so the next run retries


language = st.sidebar.radio("Language / 語言", list(LANGUAGES))
text = LANGUAGES[language]

st.title(text["title"])
st.caption(text["intro"])

if st.sidebar.button(text["button"]):
    generate_distress_calls.clear()

try:
    with st.spinner(text["loading"]):
        calls = generate_distress_calls(text["prompt_language"])
except RuntimeError:
    st.warning(text["offline"])
    calls = text["fallback"]

### Hand the calls to the game page; "</" is escaped so a message can't close the <script> tag early
config = json.dumps({"messages": calls, "text": text["hud"]}, ensure_ascii=False).replace("</", "<\\/")
components.html(GAME_HTML.read_text(encoding="utf-8").replace("__CONFIG__", config), height=650)
