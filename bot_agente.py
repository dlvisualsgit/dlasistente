import os, discord, aiohttp, json, asyncio, urllib.parse
from datetime import datetime, timedelta
from collections import defaultdict, deque

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")
AGENT_ID = os.getenv("AGENT_ID", "pm")

DB_PATH = "datos.json"
PROYECTOS_DIR = "proyectos"
os.makedirs(PROYECTOS_DIR, exist_ok=True)

def db():
    if os.path.exists(DB_PATH):
        with open(DB_PATH, encoding="utf-8") as f: return json.load(f)
    return {"tareas": [], "metricas": {}, "mensajes_sala": []}
def guardar(d):
    with open(DB_PATH, "w", encoding="utf-8") as f: json.dump(d, f, ensure_ascii=False, indent=2)

# ─── PERFILES ───────────────────────────────────────────────────
PERFILES = {
    "pm": {
        "nombre": "Sofia", "cargo": "Project Manager", "emoji": "📋",
        "horario": (8, 18), "color": 0x4CAF50,
        "sistema": """Eres Sofia, la Project Manager de DLvisuals. Organizada, eficiente, comunicativa.
Gestionas proyectos, asignas tareas a otros agentes (@developer, @luna, @nova, @vega), haces seguimiento de deadlines.
Coordinacion: En #sala-junta puedes hablar con los otros agentes. Dirigete a ellos con @nombre.
Horario: 8:00-18:00. Deadline critico: Polleria Rebollo 7 junio 2026."""
    },
    "dev": {
        "nombre": "Alex", "cargo": "Desarrollador Web", "emoji": "💻",
        "horario": (9, 20), "color": 0x2196F3,
        "sistema": """Eres Alex, el Desarrollador Web de DLvisuals. Experto en HTML/CSS/JS Mobile-First.
Generas codigo limpio y funcional. Puedes crear archivos completos.
Cuando necesites especificaciones, preguntale a @nova (diseno) en #sala-junta.
Horario: 9:00-20:00."""
    },
    "copy": {
        "nombre": "Luna", "cargo": "Copywriter", "emoji": "✍️",
        "horario": (9, 17), "color": 0xE91E63,
        "sistema": """Eres Luna, la Copywriter de DLvisuals. Creativa y persuasiva.
Redactas textos comerciales, traducciones ES/EN/FR, posts redes sociales, emails.
Adaptas el tono al sector del cliente (hosteleria, ropa, servicios).
Horario: 9:00-17:00."""
    },
    "design": {
        "nombre": "Nova", "cargo": "Disenadora UX/UI", "emoji": "🎨",
        "horario": (10, 19), "color": 0x9C27B0,
        "sistema": """Eres Nova, la Disenadora UX/UI de DLvisuals. Creativa, tendencias, detalle.
Creacion de paletas de colores, branding, guias de estilo, variables CSS.
Estilo: moderno, limpio, mobile-first. Tendencias actuales.
Horario: 10:00-19:00."""
    },
    "seo": {
        "nombre": "Vega", "cargo": "Especialista SEO", "emoji": "🔍",
        "horario": (9, 17), "color": 0xFF9800,
        "sistema": """Eres Vega, la Especialista SEO de DLvisuals. Analitica y metodica.
Auditorias web, meta tags, Open Graph, sitemaps, palabras clave locales.
Puedes navegar webs para analizarlas con browse y search.
Horario: 9:00-17:00."""
    }
}

YO = PERFILES.get(AGENT_ID, PERFILES["pm"])
CANAL_PROPIO = None  # se asigna al iniciar
CANAL_SALA = None

memoria = deque(maxlen=40)
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

async def ai(mensajes, sistema_extra=""):
    sist = f"{YO['sistema']}\n\nHERRAMIENTAS:\n###TOOL: {{\"save_file\": {{\"ruta\": \"...\",\"contenido\": \"...\"}}}}\n###TOOL: {{\"add_task\": {{\"texto\": \"...\",\"agente\": \"dev\"}}}}\n###TOOL: {{\"browse\": {{\"url\": \"https://...\"}}}}\n###TOOL: {{\"search\": {{\"query\": \"...\"}}}}\n\nFECHA: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n{sistema_extra}"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post("https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"},
                json={"model": "google/gemini-2.0-flash-001", "messages": [{"role": "system", "content": sist}] + mensajes}) as r:
                d = await r.json()
                return d["choices"][0]["message"]["content"] if "choices" in d else ""
    except: return ""

async def tools(texto):
    res = []
    for linea in texto.split("\n"):
        if "###TOOL:" in linea:
            try:
                inst = json.loads(linea[linea.index("###TOOL:")+8:].strip())
                a, p = list(inst.keys())[0], inst[list(inst.keys())[0]]
                if a == "save_file":
                    ruta = os.path.join(PROYECTOS_DIR, p["ruta"].replace("/", os.sep))
                    os.makedirs(os.path.dirname(ruta), exist_ok=True)
                    with open(ruta, "w", encoding="utf-8") as f: f.write(p["contenido"])
                    res.append(f"💾 Archivo guardado en {p['ruta']}")
                elif a == "add_task":
                    d = db(); d["tareas"].append({"texto": p["texto"], "agente": p.get("agente","general"), "ok": False}); guardar(d)
                elif a == "browse":
                    async with aiohttp.ClientSession() as s:
                        async with s.get(p["url"], timeout=aiohttp.ClientTimeout(10), headers={"User-Agent":"Mozilla/5.0"}) as r:
                            h = await r.text()
                            r2 = await ai([{"role":"user","content":f"Resume:{p['url']}\n\n{h[:4000]}"}], "Eres analista web.")
                            res.append(f"🌐 {r2}")
                elif a == "search":
                    async with aiohttp.ClientSession() as s:
                        async with s.get(f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(p['query'])}", timeout=aiohttp.ClientTimeout(10), headers={"User-Agent":"Mozilla/5.0"}) as r:
                            h = await r.text()
                            r2 = await ai([{"role":"user","content":f"Resultados de '{p['query']}':\n{h[:4000]}"}], "Resume hallazgos clave.")
                            res.append(f"🔎 {r2}")
            except: pass
    return "\n".join(res) if res else ""

# ─── DETECTAR EN SALA SI EL MENSAJE ES PARA ESTE AGENTE ────────
def es_para_mi(texto):
    menciones = [YO["nombre"].lower(), f"@{YO['nombre'].lower()}", f"@{AGENT_ID}", f"<@{client.user.id}>", "todos", "@everyone", f"@{YO['cargo'].lower()}"]
    txt = texto.lower()
    return any(m in txt for m in menciones)

# ─── EVENTOS ────────────────────────────────────────────────────
@client.event
async def on_ready():
    global CANAL_PROPIO, CANAL_SALA
    print(f"{YO['emoji']} {YO['nombre']} ({YO['cargo']}) conectado como {client.user}")

    for guild in client.guilds:
        for ch in guild.channels:
            n = ch.name.lower()
            # Cada agente reconoce MULTIPLES nombres de canal
            nombres_canal = [AGENT_ID, YO["nombre"].lower(), YO["cargo"].lower().replace(" ","")]
            if AGENT_ID == "pm": nombres_canal += ["pm", "sofia", "projectmanager"]
            if AGENT_ID == "dev": nombres_canal += ["dev", "alex", "developer", "desarrollador"]
            if AGENT_ID == "copy": nombres_canal += ["copy", "luna", "copywriter", "redactor"]
            if AGENT_ID == "design": nombres_canal += ["design", "nova", "diseno", "uxui"]
            if AGENT_ID == "seo": nombres_canal += ["seo", "vega", "especialistaseo"]
            if n in nombres_canal: CANAL_PROPIO = ch.id
            if n in ["sala-junta", "sala", "junta"]: CANAL_SALA = ch.id

    print(f"  Canal propio: {CANAL_PROPIO} | Sala: {CANAL_SALA}")
    if YO["nombre"] in ["Sofia", "Alex"]:
        client.loop.create_task(proactivo())

async def proactivo():
    await client.wait_until_ready()
    while not client.is_closed():
        await asyncio.sleep(900)  # cada 15 min
        try:
            ahora = datetime.now()
            if not (YO["horario"][0] <= ahora.hour < YO["horario"][1]): continue
            canal = client.get_channel(CANAL_PROPIO or CANAL_SALA)
            if not canal: continue

            d = db()
            tareas_mias = [t for t in d.get("tareas", []) if t.get("agente") == AGENT_ID and not t.get("ok")]
            prompt = f"Eres {YO['nombre']}. {'Tienes tareas pendientes: ' + str([t['texto'] for t in tareas_mias[:3]]) if tareas_mias else 'No tienes tareas. Revisa el estado de los proyectos y haz algo util o preguntale a David si necesita algo.'}"
            reply = await ai([{"role":"user","content":"Revisa tu estado y actua."}], prompt)
            if len(reply) > 20:
                tres = await tools(reply)
                if tres: reply += "\n\n" + tres
                await canal.send(f"**{YO['nombre']}** dice: {reply[:1997]}")
        except: pass

@client.event
async def on_message(msg):
    if msg.author.bot: return
    canal_id = msg.channel.id
    es_mi_canal = canal_id == CANAL_PROPIO
    es_sala = canal_id == CANAL_SALA

    # Si es sala pero no va dirigido a mi, ignorar
    if es_sala and not es_para_mi(msg.content):
        return
    # Si no es mi canal ni la sala, ignorar
    if not es_mi_canal and not es_sala:
        return

    memoria.append({"role": "user", "content": f"{msg.author.display_name}: {msg.content}"})

    # Contexto de sala: los otros agentes pueden estar presentes
    extra = ""
    if es_sala:
        extra = "\nEstas en #sala-junta. Puedes interactuar con los otros agentes. Usa @nombre para dirigirte a ellos."

    async with msg.channel.typing():
        reply = await ai(list(memoria), extra)
        tres = await tools(reply)
        if tres: reply += "\n\n" + tres
    memoria.append({"role": "assistant", "content": reply})

    prefix = f"**{YO['nombre']}** dice: " if es_sala else ""
    await msg.reply(f"{prefix}{reply[:1997]}", mention_author=False)

client.run(DISCORD_TOKEN)
