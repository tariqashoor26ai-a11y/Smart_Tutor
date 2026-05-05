import os
import sqlite3
import subprocess
from flask import Flask, request, jsonify, send_file
from groq import Groq

app = Flask(__name__)

# إعداد مفتاح Groq API
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "ضع_مفتاحك_هنا")
client = Groq(api_key=GROQ_API_KEY)

# إعداد قاعدة البيانات SQLite
def init_db():
    conn = sqlite3.connect('academy.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS chat_history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_message TEXT, ai_response TEXT, mode TEXT)''')
    conn.commit()
    conn.close()

init_db()

# إعدادات شخصية المعلم (الـ Prompts)
SYSTEM_PROMPTS = {
    "child": "You are a friendly and fun English tutor for kids. Use very simple words, short sentences, and lots of encouragement. Correct mistakes gently.",
    "adult": "You are a professional English tutor for adult learners. Focus on advanced grammar, business vocabulary, and professional communication. Correct mistakes clearly and explain the grammatical rules."
}

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message', '')
    learner_mode = data.get('mode', 'adult') # القيمة الافتراضية للبالغين

    if not user_message:
        return jsonify({"error": "Message is required"}), 400

    # 1. جلب الرد من Groq API
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPTS.get(learner_mode, SYSTEM_PROMPTS['adult'])},
                {"role": "user", "content": user_message}
            ],
            model="llama3-8b-8192", # يمكنك تغيير الموديل حسب تفضيلك في Groq
            temperature=0.5,
        )
        ai_response = chat_completion.choices[0].message.content
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # 2. حفظ في قاعدة البيانات SQLite
    conn = sqlite3.connect('academy.db')
    c = conn.cursor()
    c.execute("INSERT INTO chat_history (user_message, ai_response, mode) VALUES (?, ?, ?)", 
              (user_message, ai_response, learner_mode))
    conn.commit()
    conn.close()

    # 3. توليد الصوت عبر Edge-TTS
    audio_file = "temp_response.mp3"
    voice = "en-US-AriaNeural" if learner_mode == "child" else "en-US-GuyNeural"
    
    try:
        # استخدام subprocess لتشغيل edge-tts بأمان وسرعة
        subprocess.run(['edge-tts', '--voice', voice, '--text', ai_response, '--write-media', audio_file], check=True)
    except subprocess.CalledProcessError:
        return jsonify({"response": ai_response, "audio_url": None, "warning": "Audio generation failed"}), 200

    return jsonify({
        "response": ai_response,
        "audio_url": "/api/audio"
    })

@app.route('/api/audio', methods=['GET'])
def get_audio():
    return send_file("temp_response.mp3", mimetype="audio/mpeg")

if __name__ == '__main__':
    # الكود جاهز للعمل على بيئات مثل Render
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=False)
