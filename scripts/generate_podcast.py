import os
import json
import time
import asyncio
import feedparser
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from dotenv import load_dotenv
import edge_tts
from pydub import AudioSegment
from datetime import datetime

load_dotenv()

# --- CONFIGURATION ---
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
# Google API Key for Gemini 3 Flash (Google AI Studio / Generative API)
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GOOGLE_MODEL = os.environ.get("GOOGLE_MODEL", "gemini-3-flash-preview")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
# OpenRouter free fallback models (tried in order)
OPENROUTER_MODELS = [
    model.strip() for model in os.environ.get(
        "OPENROUTER_MODELS",
        "meta-llama/llama-3.1-8b-instruct:free,mistralai/mistral-7b-instruct:free"
    ).split(",") if model.strip()
]
STATUS_FILE = "public/status.json"
EPISODES_DIR = "public/episodes"

FEEDS = {
    "cricinfo": "https://static.cricinfo.com/rss/livescores.xml",
    "ndtv": "https://feeds.feedburner.com/ndtvsports-cricket",
    "news18": "https://www.news18.com/commonfeeds/v1/eng/rss/cricket.xml",
    "crictracker": "https://www.crictracker.com/t20/ipl-indian-premier-league/feed/",
    "indian_express": "https://indianexpress.com/section/sports/cricket/feed/"
}

# Ensure directories exist
os.makedirs(EPISODES_DIR, exist_ok=True)
os.makedirs("public", exist_ok=True)

def update_status(phase, progress, message):
    status = {"phase": phase, "progress": progress, "message": message, "updated_at": datetime.now().isoformat()}
    with open(STATUS_FILE, "w") as f:
        json.dump(status, f)
    print(f"[{phase}] {message}")

# --- TOOLS ---
def scrape_page(url):
    """Scrapes clean text from a match page."""
    try:
        res = requests.get(url, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        paragraphs = soup.find_all(['p', 'h1', 'h2', 'h3'])
        text = ' '.join([p.get_text() for p in paragraphs])
        return text[:5000] # Limit tokens
    except Exception as e:
        return f"Error scraping {url}: {e}"

def search_google_news(query):
    """Searches Google News via RSS."""
    url = f"https://news.google.com/rss/search?q={query}"
    feed = feedparser.parse(url)
    results = [{"title": entry.title, "link": entry.link} for entry in feed.entries[:5]]
    return json.dumps(results)

# --- WORKFLOW ---
def fetch_feeds():
    update_status("Scraping", 10, "Fetching RSS feeds...")
    compiled_news = []
    for source, url in FEEDS.items():
        feed = feedparser.parse(url)
        for entry in feed.entries[:10]:
            compiled_news.append({"source": source, "title": entry.title, "link": getattr(entry, 'link', '')})
    return compiled_news

def generate_script(news_data):
    update_status("Scripting", 40, "Generating 30-minute dual-host script via LLM...")
    prompt = f"""
    Act as a Senior Cricket Analyst. Using the provided news, write a 30-minute podcast script (approx 4500 words).
    Focus 80% on deep scorecard/match analysis (partnerships, overs) and 20% on general IPL news.
    Hosts: 
    - Prabhat (Analytical, deep insights)
    - Neerja (Expressive, energetic, fan perspective)
    
    Return the response as a valid JSON array of objects. 
    Each object MUST have 'speaker' and 'text' keys. 
    Do NOT include Markdown blocks like ```json. Just the raw JSON.
    
    News Data: {json.dumps(news_data[:20])}
    """
    # Prefer Google Gemini 3 Flash via Google AI Studio / Generative API when configured
    if GOOGLE_API_KEY:
        update_status("Scripting", 42, f"Using Google Gemini model: {GOOGLE_MODEL}")
        try:
            return generate_with_google(prompt)
        except Exception as e:
            print("Google generation failed:", e)
            update_status("Scripting", 48, "Falling back to Groq...")

    # Fallback to Groq if available
    if GROQ_API_KEY:
        try:
            update_status("Scripting", 50, f"Trying Groq fallback model: {GROQ_MODEL}")
            client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=GROQ_API_KEY
            )
            return generate_with_openai_compatible(client, GROQ_MODEL, prompt)
        except Exception as e:
            print(f"Groq generation failed ({GROQ_MODEL}): {e}")
            update_status("Scripting", 51, "Falling back to OpenRouter free models...")

    # Fallback to OpenRouter free models if available
    if OPENROUTER_API_KEY:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY
        )
        for model_name in OPENROUTER_MODELS:
            try:
                update_status("Scripting", 52, f"Trying OpenRouter fallback model: {model_name}")
                return generate_with_openai_compatible(client, model_name, prompt)
            except Exception as e:
                print(f"OpenRouter model failed ({model_name}): {e}")

    update_status("Scripting", 60, "No LLM available or all models failed. Using fallback static text.")
    return [{"speaker": "Prabhat", "text": "Welcome to IPL Pulse 2026. We had an error generating today's script."}, 
            {"speaker": "Neerja", "text": "Yes, we'll be back tomorrow with more updates!"}]


def generate_with_google(prompt_text):
    """Call Google Generative API (Gemini 3 Flash) using streaming when possible.
    Requires `GOOGLE_API_KEY` to be set in env.
    Returns parsed JSON array output from the model.
    """
    model = GOOGLE_MODEL
    api_key = GOOGLE_API_KEY
    # Use v1beta for generateContent with gemini-3-flash
    endpoints = [
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    ]

    # Try modern generateContent first
    errors = []
    for endpoint in endpoints:
        try:
            payload = {
                "contents": [{"role": "user", "parts": [{"text": prompt_text}]}],
                "generationConfig": {
                    "temperature": 0.2, 
                    "maxOutputTokens": 8192,
                    "response_mime_type": "application/json"
                }
            }

            r = requests.post(endpoint, json=payload, timeout=120)
            if r.status_code != 200:
                try:
                    err = r.json()
                except Exception:
                    err = r.text
                errors.append({"endpoint": endpoint, "error": err})
                continue

            resp_json = r.json()
            collected = ""
            if "candidates" in resp_json and len(resp_json["candidates"]) > 0:
                candidate = resp_json["candidates"][0]
                if isinstance(candidate.get("content"), dict):
                    parts = candidate["content"].get("parts", [])
                    collected = "".join([p.get("text", "") for p in parts if isinstance(p, dict)])
                else:
                    collected = candidate.get("content", "")
            elif "text" in resp_json:
                collected = resp_json.get("text", "")
            else:
                collected = json.dumps(resp_json)

            if "```json" in collected:
                collected = collected.split("```json")[1].split("```")[0]

            return json.loads(collected)
        except Exception as e:
            errors.append({"endpoint": endpoint, "error": str(e)})

    raise RuntimeError(f"Google API error: {errors}")


def generate_with_openai_compatible(client, model_name, prompt_text):
    response = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt_text}],
        stream=False
    )
    content = response.choices[0].message.content
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    return json.loads(content)

async def render_audio_edge_tts(script):
    update_status("TTS Rendering", 70, "Rendering audio chunks with Edge-TTS...")
    
    voices = {
        "Prabhat": "en-IN-PrabhatNeural",
        "Neerja": "en-IN-NeerjaExpressiveNeural"
    }
    
    audio_files = []
    for i, line in enumerate(script):
        speaker = line.get("speaker", "Prabhat")
        text = line.get("text", "")
        voice = voices.get(speaker, voices["Prabhat"])
        
        output_file = f"chunk_{i}.mp3"
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_file)
        audio_files.append(output_file)
    
    update_status("TTS Rendering", 85, "Stitching audio chunks via pydub...")
    combined = AudioSegment.empty()
    for file in audio_files:
        combined += AudioSegment.from_mp3(file)
        os.remove(file) # Cleanup
        
    date_str = datetime.now().strftime("%Y-%m-%d")
    final_filename = f"{EPISODES_DIR}/ipl_{date_str}.mp3"
    combined.export(final_filename, format="mp3")
    return final_filename

async def main():
    update_status("Initializing", 0, "Starting IPL Pulse Generator")
    news_data = fetch_feeds()
    
    update_status("Analyzing", 30, "Analyzing feeds for Match Pages...")
    # Add logic here to trigger scrape_page() on specific cricinfo links if needed
    
    script = generate_script(news_data)
    
    final_audio = await render_audio_edge_tts(script)
    
    # Save transcript
    date_str = datetime.now().strftime("%Y-%m-%d")
    with open(f"{EPISODES_DIR}/ipl_{date_str}_transcript.json", "w") as f:
        json.dump(script, f)
    
    # Update episodes index for static hosting
    try:
        episodes = []
        for fname in sorted(os.listdir(EPISODES_DIR)):
            if fname.endswith('.mp3'):
                base = fname.replace('.mp3', '')
                transcript_file = f"{base}_transcript.json"
                transcript = []
                try:
                    with open(os.path.join(EPISODES_DIR, transcript_file), 'r', encoding='utf-8') as tf:
                        transcript = json.load(tf)
                except Exception:
                    transcript = []

                episodes.append({
                    'id': base,
                    'audio': f"/episodes/{fname}",
                    'transcript_file': transcript_file,
                    'date': base.split('_')[1] if '_' in base else ''
                })

        index_path = os.path.join(EPISODES_DIR, 'index.json')
        with open(index_path, 'w', encoding='utf-8') as idxf:
            json.dump(episodes, idxf)
    except Exception as e:
        print('Failed writing episodes index:', e)

    update_status("Deploying", 100, f"Generated successfully: {final_audio}")

if __name__ == "__main__":
    asyncio.run(main())
