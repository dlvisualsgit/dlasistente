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
ULTIMA_RESPUESTA = 0
RESPONDIDOS = set()  # IDs de mensajes ya respondidos en sala

def es_para_mi(texto, autor_es_bot=False):
    txt = texto.lower()
    # Palabras que activan a TODOS los agentes
    convocatoria = ["reunion", "equipo", "todos", "@everyone", "agentes", "presentacion", "estado", "ceremonia",
                    "daily", "standup", "coordinacion", "os presento", "bienvenidos", "hola equipo"]
    # Mi nombre y variantes
    mi_nombre = YO["nombre"].lower()
    variantes = [mi_nombre, f"@{mi_nombre}", f"@{AGENT_ID}", f"<@{client.user.id}>", YO["cargo"].lower()]
    if AGENT_ID == "pm": variantes += ["sofia", "project manager"]
    if AGENT_ID == "dev": variantes += ["alex", "developer"]
    if AGENT_ID == "copy": variantes += ["luna", "copywriter"]
    if AGENT_ID == "design": variantes += ["nova", "disenadora", "ux"]
    if AGENT_ID == "seo": variantes += ["vega", "especialista seo"]

    # Si el mensaje es de otro agente del equipo, responder si mencionan mi nombre
    if autor_es_bot:
        return any(v in txt for v in variantes)

    # Si es humano, responder a convocatoria general o a mi nombre
    return any(c in txt for c in convocatoria) or any(v in txt for v in variantes)

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
    ahora = datetime.now()
    h_ini, h_fin = YO["horario"]
    en_horario = h_ini <= ahora.hour < h_fin

    # Mensaje de inicio de jornada si esta en horario
    if CANAL_PROPIO and en_horario:
        c = client.get_channel(CANAL_PROPIO)
        if c:
            saludos = ["¡Buenos dias!", "¡Hola! Comenzando mi jornada.", "¡Arriba! Lista para trabajar.",
                       "Buenos dias, empecemos.", "¡A darle! Empezando mi turno."]
            import random
            try:
                asyncio.ensure_future(c.send(f"☀️ **{YO['nombre']}** — {random.choice(saludos)} Estare disponible de {h_ini}:00 a {h_fin}:00."))
            except: pass

    # Tarea para fin de jornada
    client.loop.create_task(fin_jornada())
    client.loop.create_task(proactivo_personal())
    if AGENT_ID in ["pm", "dev"]:
        client.loop.create_task(proactivo_sala())

async def fin_jornada():
    """Mensaje al finalizar la jornada laboral."""
    await client.wait_until_ready()
    _, h_fin = YO["horario"]
    while not client.is_closed():
        try:
            ahora = datetime.now()
            if ahora.hour == h_fin and ahora.minute == 0:
                canal = client.get_channel(CANAL_PROPIO)
                if canal:
                    despedidas = ["¡Jornada completada! Nos vemos manana.", "Fin de mi turno. ¡Buen descanso!",
                                  "Termino por hoy. ¡Hasta manana!", "Mi horario ha terminado. Cualquier cosa, manana."]
                    import random
                    await canal.send(f"🌙 **{YO['nombre']}** — {random.choice(despedidas)}")
                await asyncio.sleep(90)  # evitar repetir
        except: pass
        await asyncio.sleep(60)

async def proactivo_personal():
    """Cada agente en su propio canal: tareas, sugerencias, etc."""
    await client.wait_until_ready()
    while not client.is_closed():
        await asyncio.sleep(1200)  # cada 20 min
        try:
            ahora = datetime.now()
            if not (YO["horario"][0] <= ahora.hour < YO["horario"][1]): continue
            canal = client.get_channel(CANAL_PROPIO)
            if not canal: continue
            d = db()
            tareas = [t for t in d.get("tareas", []) if t.get("agente") == AGENT_ID and not t.get("ok")]
            prompt = f"Eres {YO['nombre']}, {YO['cargo']}. {'Tienes tareas: ' + str([t['texto'] for t in tareas[:3]]) if tareas else 'No tienes tareas. Que puedes hacer util? Revisa el estado o preguntale a David.'}"
            reply = await ai([{"role":"user","content":"Actua."}], prompt)
            if reply and len(reply) > 20:
                tres = await tools(reply)
                if tres: reply += "\n\n" + tres
                await canal.send(reply[:1997])
        except: pass

async def proactivo_sala():
    """Iniciar conversacion natural en sala-junta como compañeros de oficina."""
    import random
    temas = ["¿Que tal va todo?", "Buenos dias equipo", "¿Alguna novedad?", "¿Como vamos con los proyectos?",
             "¿Todo bien por aqui?", "¿Necesitais algo de mi?", "Vaya dia, ¿no?", "¿Alguna noticia interesante?"]
    await client.wait_until_ready()
    while not client.is_closed():
        await asyncio.sleep(2700)
        try:
            ahora = datetime.now()
            if not (YO["horario"][0] <= ahora.hour < YO["horario"][1]): continue
            canal = client.get_channel(CANAL_SALA)
            if not canal: continue

            mensaje = f"{YO['nombre']}: {random.choice(temas)}"
            reply = await ai([{"role":"user","content":mensaje}], f"Eres {YO['nombre']}, {YO['cargo']}. Inicia conversacion casual en #sala-junta.")
            if reply and len(reply) > 15:
                await canal.send(reply[:1997])
        except: pass

@client.event
async def on_message(msg):
    global ULTIMA_RESPUESTA, RESPONDIDOS
    canal_id = msg.channel.id
    es_mi_canal = canal_id == CANAL_PROPIO
    es_sala = canal_id == CANAL_SALA
    if not es_mi_canal and not es_sala: return

    # Ignorar mis propios mensajes
    if client.user and msg.author.id == client.user.id:
        return

    ahora = datetime.now().timestamp()

    # === MI CANAL PERSONAL ===
    if es_mi_canal:
        if msg.author.bot: return
        if (ahora - ULTIMA_RESPUESTA) < 3: return
        memoria.append({"role": "user", "content": f"{msg.author.display_name}: {msg.content}"})
        async with msg.channel.typing():
            reply = await ai(list(memoria), "")
            if not reply or len(reply) < 10: reply = "Dime, ¿en qué necesitas ayuda?"
            tres = await tools(reply)
            if tres: reply += "\n\n" + tres
        memoria.append({"role": "assistant", "content": reply})
        ULTIMA_RESPUESTA = ahora
        await msg.reply(reply[:1997], mention_author=False)
        return

    # === SALA-JUNTA ===
    # Detectar si es humano o agente del equipo
    es_agente = msg.author.bot
    sala_id = f"{msg.author.id}_{msg.id}"
    if sala_id in RESPONDIDOS: return
    RESPONDIDOS.add(sala_id)
    if len(RESPONDIDOS) > 200: RESPONDIDOS = set(list(RESPONDIDOS)[-100:])

    # Cooldown segun quien habla
    cooldown_sala = 8 if es_agente else 3
    if (ahora - ULTIMA_RESPUESTA) < cooldown_sala: return

    # Si es humano: comprobar si va dirigido al equipo
    if not es_agente:
        txt = msg.content.lower()
        sin_tilde = txt.replace("ó","o").replace("í","i").replace("é","e").replace("á","a").replace("ú","u").replace("ñ","n")
        convocatoria = ["reunion", "equipo", "todos", "@everyone", "@here", "agentes", "presentacion",
                        "bienvenidos", "hola equipo", "hola a todos", "estado", "daily", "standup"]
        mi_nombre = YO["nombre"].lower()
        variantes = [mi_nombre, f"@{mi_nombre}", f"@{AGENT_ID}", YO["cargo"].lower()]
        if AGENT_ID == "pm": variantes += ["sofia", "project manager"]
        if AGENT_ID == "dev": variantes += ["alex", "developer"]
        if AGENT_ID == "copy": variantes += ["luna", "copywriter"]
        if AGENT_ID == "design": variantes += ["nova", "disenadora"]
        if AGENT_ID == "seo": variantes += ["vega"]
        if not any(c in sin_tilde for c in convocatoria) and not any(v in txt for v in variantes):
            return

    # Escalonar respuestas entre agentes (0, 2, 4, 6, 8 seg)
    orden = ["pm", "dev", "copy", "design", "seo"]
    idx = orden.index(AGENT_ID) if AGENT_ID in orden else 0
    await asyncio.sleep(idx * 2)

    extra = ""
    if es_agente:
        extra = f"\n{msg.author.display_name} ha hablado en #sala-junta. Si te menciona o tienes algo relevante que decir, responde naturalmente como en una conversacion de oficina. Si no, no digas nada. Se breve y natural."
    else:
        extra = f"\nEn #sala-junta con el equipo. Responde naturalmente como {YO['nombre']}, como si estuvieras en la oficina con tus companeros."

    memoria.append({"role": "user", "content": f"{msg.author.display_name}: {msg.content}"})
    async with msg.channel.typing():
        reply = await ai(list(memoria), extra)
        if not reply or len(reply) < 10: return
        tres = await tools(reply)
        if tres: reply += "\n\n" + tres
    memoria.append({"role": "assistant", "content": reply})
    ULTIMA_RESPUESTA = datetime.now().timestamp()
    try:
        await msg.channel.send(reply[:1997])
    except:
        try:
            await msg.reply(reply[:1997], mention_author=False)
        except:
            pass

client.run(DISCORD_TOKEN)
