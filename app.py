import os
from flask import Flask, request, jsonify, render_template_string
from groq import Groq

app = Flask(__name__)
# جلب المفتاح السري الذي سنضعه في الخادم لاحقاً
client = Groq(api_key=os.environ.get("ييييييييييي"))

# واجهة الموقع (HTML & JavaScript)
HTML_PAGE = """
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <title>المدرس الذكي</title>
    <style>
        body { font-family: Arial; text-align: center; margin-top: 50px; background: #f4f4f9;}
        input, select, button { padding: 10px; font-size: 16px; margin: 5px; }
        #chatBox { width: 80%; max-width: 600px; margin: 20px auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1); min-height: 100px;}
    </style>
</head>
<body>
    <h2>🇬🇧 مدرس اللغة الإنجليزية الذكي</h2>
    <select id="mode">
        <option value="adult">وضع الكبار (احترافي وعملي)</option>
        <option value="child">وضع الأطفال (مرح وبسيط)</option>
    </select>
    <br><br>
    <input type="text" id="userMsg" placeholder="اكتب رسالتك بالإنجليزية أو العربية..." style="width: 60%;">
    <button onclick="sendMsg()">إرسال</button>
    <div id="chatBox">الرد سيظهر هنا...</div>

    <script>
        async function sendMsg() {
            let msg = document.getElementById("userMsg").value;
            let mode = document.getElementById("mode").value;
            document.getElementById("chatBox").innerText = "جاري التفكير...";

            let res = await fetch("/chat", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({message: msg, mode: mode})
            });

            let data = await res.json();
            document.getElementById("chatBox").innerText = data.reply;
        }
    </script>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML_PAGE)

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    mode = data.get("mode", "adult")
    user_msg = data.get("message", "")

    # توجيهات الذكاء الاصطناعي بناءً على اختيار المستخدم
    if mode == "child":
        sys_msg = "أنت مدرس لغة إنجليزية مرح وصبور جداً مخصص للأطفال. استخدم كلمات إنجليزية بسيطة جداً مع ترجمتها للعربية. استخدم الكثير من الرموز التعبيرية 🦁🌟. شجع الطفل دائماً."
    else:
        sys_msg = "أنت مدرب لغة إنجليزية محترف للبالغين. ركز على المحادثات العملية ومصطلحات بيئة العمل. قدم تصحيحات دقيقة مع شرح القاعدة النحوية ببساطة. حافظ على نبرة احترافية ومشجعة."

    # التواصل مع نموذج LLaMA 3 عبر Groq لسرعة فائقة
    completion = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": user_msg}
        ]
    )
    return jsonify({"reply": completion.choices[0].message.content})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
