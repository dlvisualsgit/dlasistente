import os, discord, aiohttp, json, asyncio, shutil, zipfile, urllib.parse
from datetime import datetime, timedelta
from collections import defaultdict, deque

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")

DB_PATH = "agencia.json"
PROYECTOS_DIR = "proyectos"
os.makedirs(PROYECTOS_DIR, exist_ok=True)

# ─── BASE DE DATOS ──────────────────────────────────────────────
def db():
    if os.path.exists(DB_PATH):
        with open(DB_PATH, encoding="utf-8") as f: return json.load(f)
    return {"tareas": [], "proyectos": [], "metricas": {}, "reuniones": []}

def guardar(d):
    with open(DB_PATH, "w", encoding="utf-8") as f: json.dump(d, f, ensure_ascii=False, indent=2)

def registrar_metrica(agente, accion):
    d = db()
    d.setdefault("metricas", {}).setdefault(agente, {"acciones": 0, "codigo": 0, "tareas": 0, "ultima": ""})
    d["metricas"][agente]["acciones"] += 1
    d["metricas"][agente]["ultima"] = datetime.now().isoformat()
    if accion == "codigo": d["metricas"][agente]["codigo"] += 1
    if accion == "tarea": d["metricas"][agente]["tareas"] += 1
    guardar(d)

# ─── AGENTES ────────────────────────────────────────────────────
AGENTES = {
    "pm": {
        "nombre": "Sofia",
        "cargo": "Project Manager",
        "canal": None,  # se asigna abajo
        "horario": (8, 18),
        "emoji": "📋",
        "sistema": """Eres Sofia, la Project Manager de DLvisuals. Eres organizada, eficiente y comunicativa.
Tus funciones:
- Planificar proyectos y asignar tareas a los otros agentes
- Hacer seguimiento de deadlines (Pollería Rebollo: 7 junio 2026)
- Coordinar al equipo: cuando algo require a otro agente, escribes en #sala-junta
- Resolver dudas sobre planificacion
- Reportar el estado de los proyectos diariamente

Para comunicarte con otros agentes, escribes en #sala-junta con @AGENTE: mensaje
Ej: "@developer: genera el menu de la polleria en HTML"

No trabajes fuera de tu horario (8:00-18:00). Se profesional pero cercana."""
    },
    "dev": {
        "nombre": "Alex",
        "cargo": "Desarrollador Web",
        "canal": None,
        "horario": (9, 20),
        "emoji": "💻",
        "sistema": """Eres Alex, el Desarrollador Web de DLvisuals. Eres experto en HTML, CSS, JavaScript Mobile-First.
Tus funciones:
- Generar codigo HTML/CSS/JS limpio y optimizado
- Mobile-First extremo, SEO Local
- Traducir disenos a codigo funcional
- Crear componentes reutilizables
- Optimizar velocidad de carga

Cuando te pidan codigo, genera archivos completos y funcionales.
Si necesitas especificaciones de diseno, preguntale a @designer en #sala-junta.
Horario: 9:00-20:00."""
    },
    "copy": {
        "nombre": "Luna",
        "cargo": "Redactora / Copywriter",
        "canal": None,
        "horario": (9, 17),
        "emoji": "✍️",
        "sistema": """Eres Luna, la Redactora y Copywriter de DLvisuals. Eres creativa, persuasiva y experta en marketing digital.
Tus funciones:
- Redactar textos comerciales para webs (hero, servicios, about, CTA)
- Traducir contenido entre ES/EN/FR
- Escribir posts para redes sociales
- Crear copys persuasivos de alta conversion
- Redactar emails profesionales para clientes

Adaptas el tono segun el sector (hosteleria, ropa, servicios).
Horario: 9:00-17:00."""
    },
    "designer": {
        "nombre": "Nova",
        "cargo": "Disenadora UX/UI",
        "canal": None,
        "horario": (10, 19),
        "emoji": "🎨",
        "sistema": """Eres Nova, la Disenadora UX/UI de DLvisuals. Eres creativa, con ojo para el detalle y tendencias.
Tus funciones:
- Crear paletas de colores y branding
- Proponer estructuras visuales para las webs
- Generar guias de estilo y variables CSS
- Asegurar consistencia visual entre proyectos
- Crear identidad visual para clientes

Estilo: moderno, limpio, mobile-first. Usa tendencias actuales (glassmorphism, minimal, etc).
Horario: 10:00-19:00."""
    },
    "seo": {
        "nombre": "Vega",
        "cargo": "Especialista SEO",
        "canal": None,
        "horario": (9, 17),
        "emoji": "🔍",
        "sistema": """Eres Vega, la Especialista SEO de DLvisuals. Eres analitica, metodica y actualizada.
Tus funciones:
- Auditar webs y recomendar mejoras SEO
- Generar meta tags, Open Graph, Twitter Cards
- Crear sitemaps y robots.txt
- Investigar palabras clave locales
- Analizar competencia en Torrevieja
- Monitorear rendimiento de las webs

Puedes navegar webs para analizarlas. Usa datos concretos.
Horario: 9:00-17:00."""
    }
}

# Asignar canales (se configura con IDs del servidor)
CANALES = {}
ID_SALA = None

# ─── SISTEMA DE COORDINACION ────────────────────────────────────
SALA_SISTEMA = """
Eres el coordinador de la sala de juntas de DLvisuals. Tu rol es:
- Cuando un agente se dirige a otro (@agente: mensaje), procesa el mensaje
- Cuando se pide "reunion" o "reunion de equipo", cada agente da su estado
- Cuando alguien pregunta "que hace X", responde como ese agente
- Manten un tono profesional pero natural
- Si no sabes algo, dilo directamente
"""

memorias = defaultdict(lambda: deque(maxlen=30))
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# ─── LLAMADA AI ─────────────────────────────────────────────────
async def ai(mensajes, sistema, agente=""):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post("https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"},
                json={"model": "google/gemini-2.0-flash-001",
                      "messages": [{"role": "system", "content": sistema}] + mensajes}) as r:
                d = await r.json()
                txt = d["choices"][0]["message"]["content"] if "choices" in d else ""
                if agente: registrar_metrica(agente, "codigo" if "save_file" in txt else "accion")
                return txt
    except: return "Error de conexion. Intentalo de nuevo."

# ─── EJECUTAR TOOLS ─────────────────────────────────────────────
async def tools(texto, canal_id):
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
                    res.append(f"💾 Archivo guardado: {p['ruta']}")
                elif a == "add_task":
                    d = db(); d["tareas"].append({"texto": p["texto"], "agente": p.get("agente","general"), "ok": False}); guardar(d)
                    res.append(f"✅ Tarea anadida: {p['texto']}")
                elif a == "meeting":
                    d = db(); d.setdefault("reuniones", []).append({"fecha": datetime.now().isoformat(), "notas": p.get("notas",""), "agentes": p.get("agentes",[])}); guardar(d)
                elif a == "browse":
                    try:
                        async with aiohttp.ClientSession() as s:
                            async with s.get(p["url"], timeout=aiohttp.ClientTimeout(10), headers={"User-Agent":"Mozilla/5.0"}) as r:
                                h = await r.text()
                                res.append(f"🌐 Navegue a {p['url']} ({len(h)} chars). Informacion extraida...")
                                r2 = await ai([{"role":"user","content":f"Resume esta pagina: {p['url']}\n\n{h[:4000]}"}], "Eres un analista web. Se breve.")
                                res.append(f"📊 {r2}")
                    except: res.append(f"⚠️ No pude acceder a {p['url']}")
                elif a == "search":
                    try:
                        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(p['query'])}"
                        async with aiohttp.ClientSession() as s:
                            async with s.get(url, timeout=aiohttp.ClientTimeout(10), headers={"User-Agent":"Mozilla/5.0"}) as r:
                                h = await r.text()
                                r2 = await ai([{"role":"user","content":f"Busque: '{p['query']}'. Resultados:\n{h[:4000]}"}], "Eres un investigador. Resume los hallazgos clave.")
                                res.append(f"🔎 {r2}")
                    except: res.append("⚠️ Error en busqueda")
            except: pass
    return "\n".join(res) if res else ""

# ─── PROCESAR MENSAJE ───────────────────────────────────────────
async def procesar(texto, canal_id, autor, perfil):
    ag = perfil["nombre"]
    mem_id = f"{canal_id}_{ag}"
    memorias[mem_id].append({"role": "user", "content": f"{autor}: {texto}"})

    ahora = datetime.now()
    h_inicio, h_fin = perfil["horario"]
    fuera_horario = not (h_inicio <= ahora.hour < h_fin)
    horario_msg = f" (son las {ahora.hour}:00, fuera de mi horario {h_inicio}:00-{h_fin}:00)" if fuera_horario else ""

    # Sistema base + herramientas disponibles
    sist = perfil["sistema"] + f"\n\nHERRAMIENTAS:\n###TOOL: {{{{'save_file':{{'ruta':'...','contenido':'...'}}}}}}\n###TOOL: {{{{'add_task':{{'texto':'...','agente':'dev'}}}}}}\n###TOOL: {{{{'meeting':{{'notas':'...','agentes':[]}}}}}}\n###TOOL: {{{{'browse':{{'url':'https://...'}}}}}}\n###TOOL: {{{{'search':{{'query':'...'}}}}}}\n\nFECHA: {datetime.now().strftime('%d/%m/%Y %H:%M')}\nPROYECTOS: {[p for p in os.listdir(PROYECTOS_DIR) if os.path.isdir(os.path.join(PROYECTOS_DIR, p))]}{horario_msg}"

    reply = await ai(list(memorias[mem_id]), sist, perfil.get("cargo",""))
    tres = await tools(reply, canal_id)
    if tres: reply += "\n\n" + tres
    memorias[mem_id].append({"role": "assistant", "content": reply})
    return reply

# ─── SALA DE JUNTAS ─────────────────────────────────────────────
async def procesar_sala(texto, canal_id, autor):
    d = db()
    d.setdefault("reuniones", [])
    mem_id = f"sala_{canal_id}"
    memorias[mem_id].append({"role": "user", "content": f"{autor}: {texto}"})

    # Contexto del equipo para la sala
    estado = "ESTADO DE LA AGENCIA:\n"
    estado += f"Tareas: {len([t for t in d['tareas'] if not t['ok']])} pendientes\n"
    estado += f"Proyectos: {[p for p in os.listdir(PROYECTOS_DIR) if os.path.isdir(os.path.join(PROYECTOS_DIR, p))]}\n"
    estado += f"Metricas:\n"
    for ag, m in d.get("metricas", {}).items():
        estado += f"  {ag}: {m['acciones']} acciones, {m['codigo']} archivos generados\n"

    sist = f"{SALA_SISTEMA}\n\n{estado}\n\nHERRAMIENTAS:\n###TOOL: {{{{'add_task':{{'texto':'...','agente':'dev'}}}}}}\n###TOOL: {{{{'meeting':{{'notas':'...','agentes':['sofia','alex','luna','nova','vega']}}}}}}\n###TOOL: {{{{'browse':{{'url':'https://...'}}}}}}\n###TOOL: {{{{'search':{{'query':'...'}}}}}}"
    reply = await ai(list(memorias[mem_id]), sist)
    tres = await tools(reply, canal_id)
    if tres: reply += "\n\n" + tres
    memorias[mem_id].append({"role": "assistant", "content": reply})
    return reply

# ─── METRICAS ───────────────────────────────────────────────────
async def generar_metricas():
    d = db()
    txt = "📊 **PANEL DE METRICAS DLVISUALS**\n\n"
    for ag, info in AGENTES.items():
        m = d.get("metricas", {}).get(ag, {"acciones":0,"codigo":0,"tareas":0})
        txt += f"{info['emoji']} **{info['nombre']}** ({info['cargo']})\n"
        txt += f"  Acciones: {m['acciones']} | Codigo generado: {m['codigo']} | Tareas: {m['tareas']}\n"
        txt += f"  Horario: {info['horario'][0]}:00-{info['horario'][1]}:00\n\n"
    txt += f"**Tareas pendientes:** {len([t for t in d.get('tareas',[]) if not t['ok']])}\n"
    txt += f"**Proyectos activos:** {len([p for p in os.listdir(PROYECTOS_DIR) if os.path.isdir(os.path.join(PROYECTOS_DIR, p))])}\n"
    txt += f"**Reuniones:** {len(d.get('reuniones',[]))}\n"
    return txt

# ─── PROACTIVIDAD POR AGENTE ────────────────────────────────────
async def proactividad_agentes():
    await client.wait_until_ready()
    contador = 0
    while not client.is_closed():
        await asyncio.sleep(60)  # cada 1 minuto
        contador += 1
        try:
            ahora = datetime.now()
            d = db()
            proyectos = [p for p in os.listdir(PROYECTOS_DIR) if os.path.isdir(os.path.join(PROYECTOS_DIR, p))]
            tareas_pend = [t for t in d.get("tareas",[]) if not t.get("ok")]
            tareas_por_agente = {}
            for t in tareas_pend: tareas_por_agente.setdefault(t.get("agente","general"), []).append(t)

            for ag_id, info in AGENTES.items():
                h_ini, h_fin = info["horario"]
                if not (h_ini <= ahora.hour < h_fin): continue
                canal_id = info.get("canal")
                if not canal_id: continue
                canal = client.get_channel(canal_id)
                if not canal: continue

                # Cada agente revisa cada ~15 min (15 ciclos de 60s)
                m = d.get("metricas", {}).get(ag_id, {})
                ult_pro = m.get("ultima_proactiva", "")
                cooldown = 900  # 15 min
                if ult_pro:
                    try:
                        if (ahora - datetime.fromisoformat(ult_pro)).total_seconds() < cooldown: continue
                    except: pass

                # El contador escalona para que no hablen todos a la vez
                idx = list(AGENTES.keys()).index(ag_id)
                if contador % 15 != idx: continue

                tareas_mias = tareas_por_agente.get(ag_id, [])

                prompt = f"""Eres {info['nombre']}, {info['cargo']} en DLvisuals. Debes SER PROACTIVO.

ESTADO ACTUAL:
- Tareas pendientes totales: {len(tareas_pend)}
- Tus tareas asignadas: {len(tareas_mias)}: {[t['texto'] for t in tareas_mias[:3]]}
- Proyectos: {proyectos}
- Fecha: {ahora.strftime('%d/%m/%Y %H:%M')}

INSTRUCCION:
1. Si TIENES TAREAS pendientes, EJECUTALAS ahora mismo
2. Si no tienes tareas, piensa que puedes hacer util para mejorar la agencia: generar codigo, proponer mejoras, investigar algo, etc.
3. Si no hay absolutamente nada que hacer, proponle algo a David (ej: "¿Quieres que prepare algo para X?")
4. USA ###TOOL: para ejecutar acciones (save_file, add_task, browse, search)
5. NO digas "no tengo nada que hacer" - siempre hay algo
6. Se breve pero concreto"""
                reply = await ai([{"role":"user","content":"Actua. Revisa tu estado y haz algo util ahora."}], prompt, info["cargo"])
                if len(reply) < 20: continue

                tres = await tools(reply, canal_id)
                if tres: reply += "\n\n" + tres
                await canal.send(reply[:1997])

                d = db()
                d.setdefault("metricas", {}).setdefault(ag_id, {})["ultima_proactiva"] = ahora.isoformat()
                guardar(d)
        except Exception as e:
            print(f"Error proactividad: {e}")

# ─── EVENTOS ────────────────────────────────────────────────────
@client.event
async def on_ready():
    print(f"Oficina DLvisuals abierta como {client.user}")

    # Auto-crear canales si no existen
    global ID_SALA
    for guild in client.guilds:
        # Definir canales que queremos
        canales_necesarios = {
            "sala-junta": None,
            "metricas": None,
            "pm": "pm",
            "developer": "dev",
            "copywriter": "copy",
            "design": "designer",
            "seo": "seo"
        }

        # Mapear canales existentes
        for ch in guild.channels:
            n = ch.name.lower()
            if n == "sala-junta": ID_SALA = ch.id; canales_necesarios.pop("sala-junta", None)
            elif n == "metricas": CANALES["metricas"] = ch.id; canales_necesarios.pop("metricas", None)
            elif n in canales_necesarios:
                ag_id = canales_necesarios.pop(n)
                if ag_id: AGENTES[ag_id]["canal"] = ch.id

        # Crear los que faltan
        for nombre_canal, ag_id in canales_necesarios.items():
            try:
                nuevo = await guild.create_text_channel(nombre_canal)
                if nombre_canal == "sala-junta": ID_SALA = nuevo.id
                elif nombre_canal == "metricas": CANALES["metricas"] = nuevo.id
                elif ag_id: AGENTES[ag_id]["canal"] = nuevo.id
                print(f"  ✅ Canal creado: #{nombre_canal}")
            except Exception as e:
                print(f"  ❌ No pude crear #{nombre_canal}: {e}")

    print(f"Canales: PM={AGENTES['pm']['canal']}, Dev={AGENTES['dev']['canal']}, Copy={AGENTES['copy']['canal']}, Designer={AGENTES['designer']['canal']}, SEO={AGENTES['seo']['canal']}, Sala={ID_SALA}, Metricas={CANALES.get('metricas')}")
    client.loop.create_task(proactividad_agentes())

@client.event
async def on_message(msg):
    if msg.author.bot: return
    canal_id = msg.channel.id

    # Sala de juntas
    if canal_id == ID_SALA:
        async with msg.channel.typing():
            reply = await procesar_sala(msg.content, canal_id, msg.author.display_name)
        await msg.reply(reply[:1997] if len(reply) > 2000 else reply, mention_author=False)
        return

    # Metricas
    if canal_id == CANALES.get("metricas"):
        await msg.reply(await generar_metricas(), mention_author=False)
        return

    # Enrutar a cada agente segun su canal
    for ag_id, info in AGENTES.items():
        if canal_id == info["canal"]:
            async with msg.channel.typing():
                reply = await procesar(msg.content, canal_id, msg.author.display_name, info)
            await msg.reply(reply[:1997] if len(reply) > 2000 else reply, mention_author=False)
            return

client.run(DISCORD_TOKEN)
