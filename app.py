from flask import Flask, render_template, request, jsonify
import json, re, random, unicodedata
from collections import Counter
import math
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
faq_path = os.path.join(BASE_DIR, "faq.json")


app = Flask(__name__)

# utilitários textuais
STOPWORDS_PT = {
    "a","e","o","as","os","um","uma","de","do","da","dos","das","em","no","na","nos","nas",
    "por","para","com","sem","ou","que","como","onde","qual","quais","é","são","eu","você",
    "voce","me","minha","meu","se","os","as","este","esta","isso","isso","isso","ao","à","às",
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
    # naive sentence split by . ? !
    parts = re.split(r'(?<=[\.\?\!])\s+', text)
    return [p.strip() for p in parts if p.strip()]

# sumarização 
def summarize(text: str, max_sentences: int = 2):
    text_norm = normalize(text)
    sents = tokenize_sentences(text)
    if len(sents) <= max_sentences:
        return text  

    words = [w for w in tokenize_words(text_norm) if w not in STOPWORDS_PT]
    if not words:
        return ' '.join(sents[:max_sentences])

    freq = Counter(words)

    scores = []
    for sent in sents:
        s_norm = normalize(sent)
        s_words = [w for w in tokenize_words(s_norm) if w not in STOPWORDS_PT]
        if not s_words:
            scores.append((sent, 0.0))
            continue
        score = sum(freq.get(w, 0) for w in s_words) / math.sqrt(len(s_words))
        scores.append((sent, score))
    # pick top sentences in original order
    top = sorted(scores, key=lambda x: x[1], reverse=True)[:max_sentences]
    top_sents = set(s for s,_ in top)
    ordered = [s for s in sents if s in top_sents]
    return ' '.join(ordered)


class ChatbotRegras:
    def __init__(self, faq_path="faq.json"):
        with open(faq_path, "r", encoding="utf-8") as f:
            self.kb = json.load(f)
        # compile regex patterns for each intent
        for intent in self.kb["intencoes"]:
            intent["regex"] = [re.compile(p, re.IGNORECASE) for p in intent.get("padroes", [])]

    def extract_keywords(self, text: str, top_k: int = 5):
        """
        Quebra a pergunta, remove stopwords e devolve as palavras mais frequentes
        (simples extração por frequência). Também gera n-grams (bigramas) para capturar padrões.
        """
        t = normalize(text)
        words = [w for w in tokenize_words(t) if w not in STOPWORDS_PT]
        freq = Counter(words)
        keywords = [w for w,_ in freq.most_common(top_k)]

        # bigrams
        bigrams = []
        for i in range(len(words)-1):
            bigrams.append(words[i] + ' ' + words[i+1])
        bigram_freq = Counter(bigrams)
        top_bigrams = [b for b,_ in bigram_freq.most_common(2)]
        # return combined (bigrams first if any)
        return top_bigrams + [k for k in keywords if k not in top_bigrams]

    def score_intent(self, text: str, intent: dict):
        """
        Pontua uma intenção de forma composta:
         - 1. padrões regex (cada regex match dá +3)
         - 2. interseção de keywords (+1 por keyword encontrada)
         - 3. presença de n-gram (bigram) exato em padrões (+2)
        """
        t = normalize(text)
        score = 0
        # regex patterns
        for rgx in intent.get("regex", []):
            if rgx.search(t):
                score += 3

        # keywords match
        keywords = self.extract_keywords(text, top_k=6)
        # count how many keywords appear in intent patterns or responses
        pattern_text = ' '.join(intent.get("padroes", [])).lower()
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', pattern_text):
                score += 1

        # bigram exact in patterns
        for kw in keywords:
            if ' ' in kw:
                if re.search(re.escape(kw), pattern_text):
                    score += 2
        return score

    def find_best_intent(self, text: str):
        best = None
        best_score = 0
        for intent in self.kb["intencoes"]:
            s = self.score_intent(text, intent)
            if s > best_score:
                best_score = s
                best = intent
        return best, best_score

    def responder(self, pergunta: str):
        # Racha texto, extrai keywords, busca melhor intenção
        if not pergunta or not pergunta.strip():
            return random.choice(self.kb.get("fallbacks", ["Desculpe, não entendi."]))

        # se o texto for longo, ofereça sintetizar (opcional): omitido aqui, mas sumarizar está disponível via route
        intent, score = self.find_best_intent(pergunta)

        # threshold simples: se score razoável -> responde com intenção
        if intent and score >= 2:
            return random.choice(intent.get("respostas", [random.choice(self.kb.get("fallbacks", ["..."]))]))
        else:
            # fallback com sugestão que usa keywords
            keys = self.extract_keywords(pergunta, top_k=4)
            if keys:
                return (random.choice(self.kb.get("fallbacks", ["Não entendi."])) +
                        " (Palavras detectadas: {})".format(', '.join(keys)))
            return random.choice(self.kb.get("fallbacks", ["Não entendi."]))


bot = ChatbotRegras()

# -------- Flask routes --------
@app.route("/", methods=["GET", "POST"])
def index():
    resposta = ""
    pergunta = ""
    resumo = ""
    if request.method == "POST":
        pergunta = request.form.get("pergunta", "")
        acao = request.form.get("acao", "pergunta")
        if acao == "pergunta":
            resposta = bot.responder(pergunta)
        elif acao == "sumarizar":
            # sumarização do texto enviado
            n = int(request.form.get("sentences", 2))
            resumo = summarize(pergunta, max_sentences=n)
    return render_template("index.html", resposta=resposta, pergunta=pergunta, resumo=resumo)


if __name__ == "__main__":
    app.run(debug=True)
