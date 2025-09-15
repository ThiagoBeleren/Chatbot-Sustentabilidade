from flask import Flask, render_template, request, jsonify
import json, re, random, unicodedata, os
from collections import Counter
import math

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
faq_path = os.path.join(BASE_DIR, "faq.json")

app = Flask(__name__)

STOPWORDS_PT = {
    "a","e","o","as","os","um","uma","de","do","da","dos","das","em","no","na","nos",
    "por","para","com","sem","ou","que","como","onde","qual","quais","é","são","eu","você",
    "voce","me","minha","meu","se","os","as","este","esta","isso","ao","à","às",
    "pelo","pela","pelos","pelas","tambem","também","tem","temos","pode","poder","porquê","por que"
}

def normalize(text: str) -> str:
    text = text.lower().strip()
    text = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
    text = re.sub(r'[^a-z0-9\s\.\,\?\!]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text

def tokenize_words(text: str):
    return [w for w in re.findall(r'\b[a-z0-9]+\b', text)]

def tokenize_sentences(text: str):
    return [p.strip() for p in re.split(r'(?<=[\.\?\!])\s+', text) if p.strip()]

def summarize(text: str, max_sentences: int = 2):
    sents = tokenize_sentences(text)
    if len(sents) <= max_sentences:
        return text
    words = [w for w in tokenize_words(normalize(text)) if w not in STOPWORDS_PT]
    if not words:
        return ' '.join(sents[:max_sentences])
    freq = Counter(words)
    scores = []
    for sent in sents:
        s_words = [w for w in tokenize_words(normalize(sent)) if w not in STOPWORDS_PT]
        if not s_words:
            scores.append((sent,0.0))
            continue
        score = sum(freq.get(w,0) for w in s_words)/math.sqrt(len(s_words))
        scores.append((sent, score))
    top = sorted(scores, key=lambda x:x[1], reverse=True)[:max_sentences]
    top_sents = set(s for s,_ in top)
    ordered = [s for s in sents if s in top_sents]
    return ' '.join(ordered)

class ChatbotRegras:
    def __init__(self, faq_path=faq_path):
        with open(faq_path, "r", encoding="utf-8") as f:
            self.kb = json.load(f)
        for intent in self.kb.get("intencoes", []):
            intent["regex"] = [re.compile(p, re.IGNORECASE) for p in intent.get("padroes", [])]

    def detectar_materiais(self, pergunta):
        materiais_detectados = []
        for nome, info in self.kb.get("materiais", {}).items():
            for padrao in info.get("padroes", []):
                if re.search(r'\b' + re.escape(padrao.lower()) + r'\b', pergunta.lower()):
                    materiais_detectados.append(info.get("resposta"))
                    break
        return materiais_detectados

    def extract_keywords(self, text: str, top_k: int = 5):
        words = [w for w in tokenize_words(normalize(text)) if w not in STOPWORDS_PT]
        freq = Counter(words)
        keywords = [w for w,_ in freq.most_common(top_k)]
        bigrams = [words[i] + ' ' + words[i+1] for i in range(len(words)-1)]
        top_bigrams = [b for b,_ in Counter(bigrams).most_common(2)]
        return top_bigrams + [k for k in keywords if k not in top_bigrams]

    def score_intent(self, text: str, intent: dict):
        score = 0
        for rgx in intent.get("regex", []):
            if rgx.search(text):
                score += 3
        keywords = self.extract_keywords(text, top_k=6)
        pattern_text = ' '.join(intent.get("padroes", [])).lower()
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', pattern_text):
                score += 1
            if ' ' in kw and re.search(re.escape(kw), pattern_text):
                score += 2
        return score

    def find_best_intent(self, text: str):
        best = None
        best_score = 0
        for intent in self.kb.get("intencoes", []):
            s = self.score_intent(text, intent)
            if s > best_score:
                best_score = s
                best = intent
        return best, best_score

    def responder(self, pergunta: str):
        if not pergunta.strip():
            return random.choice(self.kb.get("fallbacks", ["Desculpe, não entendi."])), ""

        materiais_resp = self.detectar_materiais(pergunta)
        if materiais_resp:
            lista = "".join(f"<li>{m}</li>" for m in materiais_resp)
            resposta_html = f"<p>Identifiquei os materiais na sua pergunta:</p><ul>{lista}</ul><p>💡 Sempre separe corretamente!</p>"
            return resposta_html, ""

        intent, score = self.find_best_intent(pergunta)
        if intent and score >= 2:
            resposta = " ".join(intent.get("respostas", []))
            resumo = summarize(resposta, max_sentences=2) if len(tokenize_sentences(resposta))>2 else ""
            return resposta, resumo

        keys = self.extract_keywords(pergunta, top_k=4)
        fallback = random.choice(self.kb.get("fallbacks", ["Não entendi."]))
        return f"{fallback} (Palavras detectadas: {', '.join(keys)})", ""

bot = ChatbotRegras()
historico_global = []

# --- Rotas ---
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/send_message", methods=["POST"])
def send_message():
    data = request.get_json()
    pergunta = data.get("pergunta","")
    resposta, resumo = bot.responder(pergunta)
    historico_global.append({"pergunta": pergunta, "resposta": resposta, "resumo": resumo})
    return jsonify({"resposta": resposta, "resumo": resumo})

@app.route("/clear_history", methods=["POST"])
def clear_history():
    global historico_global
    historico_global = []
    return jsonify({"status":"ok"})

if __name__ == "__main__":
    app.run(debug=True)
