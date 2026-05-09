from flask import Flask, request, jsonify, render_template
import sqlite3
import os
from groq import Groq

app = Flask(__name__)
DB_NAME = "edtech_agent.db"

# محاولة جلب مفتاح API من البيئة
groq_api_key = os.environ.get("GROQ_API_KEY", "ضع_مفتاحك_هنا_في_حال_عدم_استخدام_بيئة_مخفية")
groq_client = Groq(api_key=groq_api_key)

SYSTEM_PROMPT = """
You are a professional, highly interactive English language tutor AI for both kids and adults.
STRICT RULES:
1. Islamic & Cultural Compliance: ALL content, examples, and stories MUST perfectly align with Islamic Sharia principles and conservative morals. No inappropriate content.
2. Formatter: Highlight important or new vocabulary words using **bold** (e.g., **vocabulary**).
3. Roleplay: Act like a human teacher. Give short assessments, correct mistakes gently, and provide tailored study plans if requested.
"""

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # جداول المستخدمين، المناهج (مع الشرط القانوني)، المحادثات، التقييمات
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE)''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS curriculums (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT,
            legal_disclaimer_accepted BOOLEAN CHECK (legal_disclaimer_accepted = 1)
        )
    ''')
    conn.commit()
    conn.close()

if not os.path.exists(DB_NAME):
    init_db()

@app.route('/', methods=['GET'])
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message', '')
    
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            model="llama3-8b-8192",
            temperature=0.7
        )
        return jsonify({"response": chat_completion.choices[0].message.content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/upload_curriculum', methods=['POST'])
def upload():
    data = request.json
    disclaimer_accepted = data.get('disclaimer_accepted', False)
    content = data.get('content', '')
    
    if not disclaimer_accepted:
        return jsonify({"error": "يجب الموافقة على إخلاء المسؤولية القانونية وحقوق الملكية أولاً."}), 400
        
    # هنا يتم حفظ المنهج في SQLite
    conn = get_db_connection()
    conn.execute('INSERT INTO curriculums (content, legal_disclaimer_accepted) VALUES (?, ?)', (content, 1))
    conn.commit()
    conn.close()
    
    return jsonify({"message": "تم استلام المنهج. سأقوم كوكيل بتقسيمه وعمل خطة دراسية الآن."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
