from flask import Flask, request, jsonify, session
import google.generativeai as genai
import json
import re

# إعدادات التطبيق و Gemini (بافتراض وجود إعدادات SQLite والـ QA Agent Thread مسبقاً)
app = Flask(__name__)
app.secret_key = 'smart_academy_secure_key_123'
genai.configure(api_key="AIzaSyB-DGGcAPoc6LauViKqOAfYLIOo-tKK8lw")

# إعداد نموذج Gemini مع تعليمات نظام صارمة (System Instructions)
system_instruction = """
أنت 'Smart Tutor'، معلم لغة إنجليزية خبير، ودود، ومبادر (Proactive) تصمت أحياناً لتشجيع الطالب على التحدث.
تلتزم بمنهجية CEFR العالمية.
الضوابط الصارمة:
1. التزام تام بالشريعة الإسلامية في كافة الأمثلة والحوارات.
2. احترام حقوق الملكية الفكرية وعدم اقتباس محتوى محمي.
3. قاعدة برمجية حتمية: أي إيموجي تستخدمه يجب أن يُغلف بهذا الوسم لتخطي القارئ الصوتي: <span class='no-tts'>الإيموجي هنا</span>.
"""
model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=system_instruction)

def get_stage_prompt(current_stage, topic, questions_asked=0):
    """توليد الـ Prompt الفرعي بناءً على المرحلة الحالية للدرس"""
    stages = {
        "EXPLANATION": f"اشرح موضوع '{topic}' بأسلوب ممتع ومناسب لعمر الطالب. أنهِ الشرح بسؤال تشويقي مبادر لتتأكد من استيعابه.",
        "PRACTICE": f"نحن في مرحلة التدريب. لقد سألت حتى الآن {questions_asked} من أصل 3 أسئلة. اطرح سؤالاً واحداً فقط، وانتظر إجابة الطالب لتقييمها، ثم اطرح السؤال التالي.",
        "ASSESSMENT": "لقد انتهى التدريب. حلل إجابات الطالب في الأسئلة الثلاثة السابقة وأرجع النتيجة بصيغة JSON فقط بهذا الهيكل: {\"score\": رقم_من_100, \"passed\": boolean (true if >= 85), \"feedback\": \"نصيحة قصيرة\"}. لا تكتب أي نص خارج الـ JSON."
    }
    return stages.get(current_stage, "")

@app.route('/api/lesson/chat', methods=['POST'])
def lesson_chat():
    data = request.json
    user_message = data.get('message', '')
    
    # تهيئة أو استرجاع حالة الجلسة
    if 'lesson_stage' not in session:
        session['lesson_stage'] = 'EXPLANATION'
        session['questions_asked'] = 0
        session['topic'] = data.get('topic', 'Greetings and Introductions') # مثال لمستوى A1
        session['history'] = [] # يجب حفظه لاحقاً في SQLite لضمان الاستمرارية

    current_stage = session['lesson_stage']
    topic = session['topic']
    
    # بناء التعليمات اللحظية للنموذج
    context_prompt = get_stage_prompt(current_stage, topic, session.get('questions_asked', 0))
    full_prompt = f"{context_prompt}\n\nرد الطالب: {user_message}"

    try:
        chat = model.start_chat(history=session['history'])
        response = chat.send_message(full_prompt)
        ai_reply = response.text

        # تحديث حالة الـ Session History
        session['history'].append({"role": "user", "parts": [user_message]})
        session['history'].append({"role": "model", "parts": [ai_reply]})

        # منطق الانتقال بين المراحل (State Machine Logic)
        if current_stage == 'EXPLANATION' and len(session['history']) > 4: 
            # انتقال افتراضي للتدريب بعد تفاعلين في الشرح
            session['lesson_stage'] = 'PRACTICE'
            
        elif current_stage == 'PRACTICE':
            session['questions_asked'] += 1
            if session['questions_asked'] >= 3:
                session['lesson_stage'] = 'ASSESSMENT'
                
        elif current_stage == 'ASSESSMENT':
            # معالجة مخرجات الـ JSON تمهيداً لحفظها في SQLite وتفعيل الترقية/الشهادات
            assessment_data = json.loads(ai_reply.strip('```json\n').strip('```'))
            # [TODO: استدعاء دالة تحديث قاعدة البيانات SQLite لجدول Assessments وتوليد QR إذا كان passed == True]
            session.clear() # تصفير الجلسة بعد انتهاء الدرس
            return jsonify({"status": "completed", "data": assessment_data})

        return jsonify({"status": "success", "stage": current_stage, "response": ai_reply})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # يعمل كـ Micro-Monolith جاهز للنشر لاحقاً عبر Gunicorn
    app.run(debug=True, threaded=True)
