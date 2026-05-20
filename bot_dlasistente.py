import os, discord, aiohttp, json, asyncio, shutil, zipfile
from collections import defaultdict, deque
from datetime import datetime, timedelta

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))

DB_PATH = "datos.json"
PROYECTOS_DIR = "proyectos"
PLANTILLAS_DIR = "plantillas"
os.makedirs(PROYECTOS_DIR, exist_ok=True)
os.makedirs(PLANTILLAS_DIR, exist_ok=True)

def cargar_db():
    if os.path.exists(DB_PATH):
        with open(DB_PATH, encoding="utf-8") as f: return json.load(f)
    return {"clientes": {}, "tareas": [], "recordatorios": [], "presupuestos": [], "facturas": [], "mejoras": []}

def guardar_db(db):
    with open(DB_PATH, "w", encoding="utf-8") as f: json.dump(db, f, ensure_ascii=False, indent=2)

def nueva_tarea(t):
    db = cargar_db(); db["tareas"].append({"id": len(db["tareas"])+1, "texto": t, "completada": False}); guardar_db(db)

def completar_tarea(i):
    db = cargar_db()
    for t in db["tareas"]:
        if t["id"] == i: t["completada"] = True; guardar_db(db)

def guardar_recordatorio(f, t, c, recurrente=""):
    db = cargar_db(); db["recordatorios"].append({"id": len(db["recordatorios"])+1, "fecha": f, "texto": t, "canal": str(c), "enviado": False, "recurrente": recurrente}); guardar_db(db)

def guardar_nota(c, k, v):
    db = cargar_db(); db["clientes"].setdefault(c.lower(), {})[k] = v; guardar_db(db)

def guardar_archivo(ruta, contenido):
    ruta = os.path.join(PROYECTOS_DIR, ruta.replace("/", os.sep))
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f: f.write(contenido)
    return ruta

def guardar_presupuesto(c, s, t):
    db = cargar_db(); db["presupuestos"].append({"cliente": c, "servicios": s, "total": t}); guardar_db(db)

def generar_contrato(cliente, servicio, precio):
    return f"""CONTRATO DE SERVICIOS DIGITALES - DLVISUALS
Cliente: {cliente}
Servicio: {servicio}
Precio: {precio}
Fecha: {datetime.now().strftime('%d/%m/%Y')}

1. OBJETO: DLvisuals se compromete a desarrollar e implementar el servicio contratado.
2. PLAZO: Entrega en 14-21 dias habiles desde la recepcion de materiales.
3. PAGO: 50% al inicio, 50% contra entrega.
4. MANTENIMIENTO: Incluye Plan Cloud (20-100€/mes) obligatorio.
5. PROPIEDAD: El codigo es propiedad del cliente una vez pagado en su totalidad.

Firmado: David Lara - DLvisuals
"""

for n, a in {"landing-page": {"index.html": '<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NEGOCIO</title><link rel="stylesheet" href="style.css"></head><body><header><h1>NEGOCIO</h1><p>Descripcion</p><a href="tel:+34" class="btn">Llamar</a><a href="https://wa.me/34" class="btn wa">WhatsApp</a></header><section id="servicios"><h2>Servicios</h2></section><section id="contacto"></section></body></html>', "style.css": "*{margin:0;padding:0;box-sizing:border-box} body{font-family:system-ui,sans-serif;background:#111;color:#fff} .btn{display:inline-block;padding:.8rem 1.5rem;background:var(--a,#d32f2f);color:#fff;border-radius:8px;margin:.5rem;font-weight:700;text-decoration:none} .wa{background:#25D366}"}}.items():
    for r, c in a.items(): guardar_archivo(f"plantillas/{n}/{r}", c)

AHORA, HOY = datetime.now().strftime("%d/%m/%Y %H:%M"), datetime.now().strftime("%Y-%m-%d")
CONTEXTO = f"""
Eres DLAsistente, agente de DLvisuals (David Lara, CEO). Agencia web para negocios locales en Torrevieja.
Mobile-First, SEO Local. Clientes: La Caleta (OK), Polleria Rebollo (lanza 7-jun-2026), KandT (desarrollo).
Servicios: Landing 180-350€ | Multipage 250-600€ | E-Commerce 500-2000€ | Cloud 20-100€/mes (obligatorio)
Fecha: {AHORA}

HERRAMIENTAS (anade UNA LINEA ###TOOL: por accion al final):
###TOOL: {{"save_file": {{"ruta": "p/archivo.html", "contenido": "..."}}}}
###TOOL: {{"add_task": {{"texto": "descripcion"}}}}
###TOOL: {{"complete_task": {{"id": 1}}}}
###TOOL: {{"save_note": {{"cliente": "x", "clave": "k", "valor": "v"}}}}
###TOOL: {{"add_reminder": {{"fecha": "{HOY} 20:00", "texto": "...", "recurrente": ""}}}}
###TOOL: {{"list_tasks": {{}}}}
###TOOL: {{"list_notes": {{"cliente": "x"}}}}
###TOOL: {{"save_budget": {{"cliente": "x", "servicios": [], "total": "€"}}}}
###TOOL: {{"create_project": {{"nombre": "p", "plantilla": "landing-page"}}}}
###TOOL: {{"get_stats": {{}}}}
###TOOL: {{"setup_client": {{"nombre": "x", "tipo": "restaurante"}}}}
###TOOL: {{"generate_branding": {{"nombre": "x", "estilo": "urbano"}}}}
###TOOL: {{"generate_invoice": {{"cliente": "x", "concepto": "Landing", "importe": 250}}}}
###TOOL: {{"export_project": {{"nombre": "p"}}}}
###TOOL: {{"generate_social": {{"cliente": "x", "tema": "web", "idioma": "es", "n": 3}}}}
###TOOL: {{"generate_meta": {{"cliente": "x", "servicio": "restaurante", "idioma": "es"}}}}
###TOOL: {{"generate_sitemap": {{"cliente": "x", "paginas": ["index", "menu", "contacto"]}}}}
###TOOL: {{"generate_email": {{"cliente": "x", "servicio": "Landing Page"}}}}
###TOOL: {{"generate_contract": {{"cliente": "x", "servicio": "Multipage", "precio": "400€"}}}}
###TOOL: {{"launch_checklist": {{"cliente": "x"}}}}
###TOOL: {{"estimate_hours": {{"tipo": "landing-page"}}}}
###TOOL: {{"backup": {{}}}}
###TOOL: {{"export_chat": {{}}}}
###TOOL: {{"analyze_website": {{"url": "https://..."}}}}
###TOOL: {{"browse": {{"url": "https://..."}}}}
###TOOL: {{"search_web": {{"query": "restaurantes Torrevieja"}}}}

FUNCIONES:
- setup_client: Crea proyecto + 7 tareas iniciales.
- generate_meta: Crea archivo _meta.html con Open Graph, Twitter Cards, SEO basico.
- generate_sitemap: Crea sitemap.xml y robots.txt.
- generate_email: Crea email de bienvenida profesional para el cliente.
- generate_contract: Crea contrato de servicios formateado.
- launch_checklist: Crea las 20 tareas de pre-lanzamiento (dominio, hosting, formularios, analytics, SEO, test mobile, etc).
- estimate_hours: Crea tareas con horas estimadas segun el tipo de proyecto.
- backup: Comprime toda la base de datos y proyectos en un ZIP con fecha.
- export_chat: Genera un TXT con el historial reciente de la conversacion.
- browse: Visita cualquier URL, obtiene el contenido y lo analiza. Sirve para ver webs de clientes, competencia, inspiracion, etc.
- search_web: Busca en internet cualquier cosa. Sirve para investigar precios, tendencias, competidores, etc.
- add_reminder: Si tiene "recurrente" = "semanal"/"diario"/"mensual", se repite automaticamente.

Reglas: Recordatorios ISO. "Manana" = {str(datetime.now()+timedelta(1))[:10]}. Usa herramientas SIEMPRE.
"""

memoria = defaultdict(lambda: deque(maxlen=50))
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

async def preguntar_ai(mensajes, extra=""):
    async with aiohttp.ClientSession() as s:
        async with s.post("https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"},
            json={"model": "google/gemini-2.0-flash-001", "messages": [{"role": "system", "content": CONTEXTO + extra}] + mensajes}) as r:
            d = await r.json()
            return d["choices"][0]["message"]["content"] if "choices" in d else f"Error API: {d}"

async def ejecutar(texto, canal):
    res, nuevas = [], []
    for linea in texto.split("\n"):
        if "###TOOL:" in linea:
            try:
                inst = json.loads(linea[linea.index("###TOOL:")+8:].strip())
                a, p = list(inst.keys())[0], inst[list(inst.keys())[0]]

                if a == "save_file": res.append(f"✅ {guardar_archivo(p['ruta'], p['contenido'])}")

                elif a == "add_reminder":
                    guardar_recordatorio(p.get("fecha",""), p.get("texto",""), canal, p.get("recurrente",""))
                    res.append(f"⏰ Recordatorio {p.get('fecha','')}")

                elif a == "add_task": nueva_tarea(p["texto"])
                elif a == "complete_task": completar_tarea(int(p["id"]))
                elif a == "save_note": guardar_nota(p["cliente"], p["clave"], p["valor"])
                elif a == "save_budget": guardar_presupuesto(p["cliente"], p["servicios"], p["total"])

                elif a == "list_tasks":
                    pts = [t for t in cargar_db()["tareas"] if not t["completada"]]
                    res.append("📋 **Tareas:**\n" + "\n".join(f"  {t['id']}. {t['texto']}" for t in pts) if pts else "✅ Sin tareas")

                elif a == "list_notes":
                    db = cargar_db(); c = p.get("cliente","").lower()
                    res.append(f"📝 {c}:\n" + "\n".join(f"  • {k}: {v}" for k,v in db["clientes"].get(c,{}).items()) if c in db["clientes"] else f"ℹ️ Sin notas de {c}")

                elif a == "get_stats":
                    d = len([x for x in os.listdir(PROYECTOS_DIR) if os.path.isdir(os.path.join(PROYECTOS_DIR, x))])
                    db = cargar_db()
                    res.append(f"📊 **DLvisuals:** {d} proyectos | {len([t for t in db['tareas'] if not t['completada']])} tareas | {len(db['presupuestos'])} presupuestos | {len(db['facturas'])} facturas | {len(db['clientes'])} clientes")

                elif a == "create_project":
                    dst = os.path.join(PROYECTOS_DIR, p["nombre"])
                    src = os.path.join(PLANTILLAS_DIR, p.get("plantilla","landing-page"))
                    shutil.copytree(src, dst, dirs_exist_ok=True) if os.path.exists(src) else os.makedirs(dst, exist_ok=True)
                    res.append(f"🚀 '{p['nombre']}' creado")

                elif a == "setup_client":
                    n = p["nombre"].lower().replace(" ","-"); os.makedirs(os.path.join(PROYECTOS_DIR, n), exist_ok=True)
                    for t in [f"Contactar {p['nombre']} (logo)", f"Pedir horarios/datos a {p['nombre']}", f"Redactar textos {p['nombre']}", f"Fotos de {p['nombre']}", f"Maquetar web {n}", f"Preview a {p['nombre']}", f"Lanzar {p['nombre']}"]: nueva_tarea(t)
                    guardar_nota(n, "tipo", p.get("tipo","")); res.append(f"✅ **{p['nombre']}** dado de alta (7 tareas)")

                elif a == "generate_branding":
                    css = f":root {{--a:#d32f2f;--bg:#111;--t:#fff;--f:'Inter',sans-serif;}}/* {p['nombre']} - {p.get('estilo','moderno')} */"
                    res.append(f"🎨 {guardar_archivo(f'{p["nombre"].lower().replace(" ","-")}/_branding.css', css)}")

                elif a == "generate_invoice":
                    imp = float(p.get("importe",0)); iva = imp*0.21
                    fac = f"FACTURA {datetime.now().strftime('%Y-%m')}\n{p['cliente']} | {p['concepto']} | Base: {imp}€ | IVA: {iva:.2f}€ | TOTAL: {imp+iva:.2f}€"
                    guardar_archivo(f"facturas/{p['cliente'].lower().replace(' ','-')}.txt", fac); res.append(f"🧾\n{fac}")

                elif a == "generate_meta":
                    c = p["cliente"].lower().replace(" ","-")
                    h = f'<!-- META TAGS - {p["cliente"]} -->\n<meta name="description" content="{p.get("servicio","")} en Torrevieja. Calidad y servicio.">\n<meta property="og:title" content="{p["cliente"]} | DLvisuals">\n<meta property="og:description" content="Web oficial de {p["cliente"]} en Torrevieja">\n<meta property="og:type" content="website">\n<meta name="twitter:card" content="summary_large_image">\n<meta name="twitter:title" content="{p["cliente"]}">\n<link rel="canonical" href="https://{c}.com/">'
                    res.append(f"🔍 Meta tags: {guardar_archivo(f'{c}/_meta.html', h)}")

                elif a == "generate_sitemap":
                    c = p["cliente"].lower().replace(" ","-"); base = f"https://{c}.com"
                    urls = "\n".join(f"  <url><loc>{base}/{pag}.html</loc></url>" for pag in p.get("paginas",["index"]))
                    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'
                    robots = f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml"
                    guardar_archivo(f"{c}/sitemap.xml", xml); guardar_archivo(f"{c}/robots.txt", robots)
                    res.append(f"🗺️ sitemap.xml + robots.txt creados en {c}/")

                elif a == "generate_email":
                    res.append(f"📧 **Email de bienvenida para {p['cliente']}**\n\nAsunto: Bienvenido a DLvisuals - Comenzamos con tu {p.get('servicio','web')}\n\nHola {p['cliente']},\n\nGracias por confiar en DLvisuals para tu proyecto.\n\nPara empezar necesito que me envies:\n- Logotipo e imagenes de tu negocio\n- Horarios, direccion y telefono\n- Textos y descripcion de servicios\n- Ejemplos de referencias que te gusten\n\nEn cuanto tenga eso, en 3-4 dias te tendre un primer borrador listo.\n\nUn saludo,\nDavid Lara\nDLvisuals")

                elif a == "generate_contract":
                    res.append(f"📄 **Contrato**\n\n{generar_contrato(p['cliente'], p['servicio'], p.get('precio',''))}")

                elif a == "launch_checklist":
                    n = p["cliente"].lower().replace(" ","-")
                    for t in [f"[PRE-LANZAMIENTO] Configurar dominio para {p['cliente']}", f"[PRE-LANZAMIENTO] Activar hosting y SSL", f"[PRE-LANZAMIENTO] Instalar Analytics", f"[PRE-LANZAMIENTO] Crear formulario funcional", f"[PRE-LANZAMIENTO] Testear envio de emails del formulario", f"[PRE-LANZAMIENTO] Optimizar imagenes (WebP)", f"[PRE-LANZAMIENTO] Probar SEO (meta tags, OG)", f"[PRE-LANZAMIENTO] Test mobile-first en 3 dispositivos", f"[PRE-LANZAMIENTO] Probar velocidad (Lighthouse >85)", f"[PRE-LANZAMIENTO] Verificar enlaces y botones", f"[PRE-LANZAMIENTO] Configurar Google My Business", f"[PRE-LANZAMIENTO] Anadir WhatsApp Button", f"[PRE-LANZAMIENTO] Revisar textos finales con cliente", f"[PRE-LANZAMIENTO] Subir sitemap a Google Search Console", f"[PRE-LANZAMIENTO] Backup pre-lanzamiento", f"[PRE-LANZAMIENTO] Desplegar en produccion", f"[PRE-LANZAMIENTO] Test post-despliegue", f"[PRE-LANZAMIENTO] Enviar enlace final al cliente", f"[PRE-LANZAMIENTO] Facturar 2a mitad", f"[PRE-LANZAMIENTO] Pedir resena o testimonio"]: nueva_tarea(t)
                    res.append(f"✅ Checklist lanzamiento de **{p['cliente']}** creada (20 tareas)")

                elif a == "estimate_hours":
                    tab = {"landing-page": "Landing Page: 12-20h\n- Diseno: 3h\n- Maquetacion: 5h\n- Contenido: 3h\n- SEO/Testing: 4h\n- Revisiones: 3h", "multipage": "Multipage: 25-40h\n- Diseno: 6h\n- Maquetacion: 12h\n- Contenido: 6h\n- SEO/Testing: 6h\n- Revisiones: 5h", "ecommerce": "E-Commerce: 50-80h\n- Planificacion: 8h\n- Diseno: 10h\n- Desarrollo: 30h\n- Contenido: 10h\n- Testing/SEO: 12h"}
                    t = p.get("tipo","landing-page")
                    res.append(f"⏱️ **Estimacion {t}:**\n{tab.get(t, 'No disponible')}")

                elif a == "backup":
                    fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
                    os.makedirs("backups", exist_ok=True)
                    with zipfile.ZipFile(f"backups/dlvisuals_{fecha}.zip", "w") as z:
                        if os.path.exists(DB_PATH): z.write(DB_PATH)
                        for root, _, fs in os.walk(PROYECTOS_DIR):
                            for f2 in fs: z.write(os.path.join(root, f2))
                    res.append(f"💾 Backup: backups/dlvisuals_{fecha}.zip")

                elif a == "export_chat":
                    os.makedirs("exports", exist_ok=True); fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
                    with open(f"exports/chat_{fecha}.txt", "w", encoding="utf-8") as f:
                        for m in list(memoria.get(canal, [])): f.write(f"{m['role']}: {m['content']}\n\n")
                    res.append(f"📝 Chat exportado: exports/chat_{fecha}.txt")

                elif a == "export_project":
                    rp = os.path.join(PROYECTOS_DIR, p["nombre"])
                    if os.path.exists(rp):
                        os.makedirs("exports", exist_ok=True)
                        with zipfile.ZipFile(f"exports/{p['nombre']}.zip", "w") as z:
                            for root, _, fs in os.walk(rp):
                                for f2 in fs: z.write(os.path.join(root, f2), os.path.relpath(os.path.join(root, f2), PROYECTOS_DIR))
                        res.append(f"📦 exports/{p['nombre']}.zip")
                    else: res.append(f"⚠️ {p['nombre']} no existe")

                elif a == "browse":
                    url = p.get("url","")
                    try:
                        async with aiohttp.ClientSession() as s:
                            async with s.get(url, timeout=aiohttp.ClientTimeout(15), headers={"User-Agent":"Mozilla/5.0"}) as r:
                                html = await r.text()
                                # Guardar el HTML para que el AI lo procese
                                res.append(f"🌐 Contenido de {url} obtenido ({len(html)} chars). Procesando...")
                                # Hacer segunda llamada al AI para analizar el contenido
                                extra = f"\n\n[CONTENIDO DE {url}]:\n{html[:5000]}..."
                                reply2 = await preguntar_ai([{"role":"user","content":f"Analiza esta pagina web y extrae la informacion relevante: {url}\n\n{html[:5000]}..."}])
                                res.append(f"🔍 **Analisis de {url}:**\n{reply2}")
                    except Exception as e: res.append(f"⚠️ Error al navegar a {url}: {e}")

                elif a == "search_web":
                    q = p.get("query","")
                    try:
                        url = f"https://html.duckduckgo.com/html/?q={q.replace(' ', '+')}"
                        async with aiohttp.ClientSession() as s:
                            async with s.get(url, timeout=aiohttp.ClientTimeout(15), headers={"User-Agent":"Mozilla/5.0"}) as r:
                                html = await r.text()
                                reply2 = await preguntar_ai([{"role":"user","content":f"Busque en internet: '{q}'. Responde con los resultados relevantes extraidos de este HTML:\n\n{html[:5000]}"}])
                                res.append(f"🔎 **Resultados de busqueda para '{q}':**\n{reply2}")
                    except Exception as e: res.append(f"⚠️ Error en busqueda: {e}")

                elif a == "generate_social": res.append("📱 Posts (abajo)")
                elif a == "analyze_website": res.append("🔍 Analisis (abajo)")

            except Exception as e: res.append(f"⚠️ {e}")
        else: nuevas.append(linea)
    return "\n".join(nuevas), "\n".join(res) if res else ""

async def procesar(texto, canal, user="Usuario"):
    memoria[canal].append({"role": "user", "content": f"{user}: {texto}"})
    extra = ""
    if "analiza" in texto.lower():
        for w in texto.split():
            if w.startswith("http"):
                try:
                    async with aiohttp.ClientSession() as s:
                        async with s.get(w, timeout=aiohttp.ClientTimeout(10)) as r:
                            extra = f"\n[HTML: {(await r.text())[:3000]}...]"
                except: extra = f"\n[Error al acceder a {w}]"
    reply = await preguntar_ai(list(memoria[canal]), extra)
    limpio, tres = await ejecutar(reply, canal)
    if tres: limpio += "\n\n" + tres
    memoria[canal].append({"role": "assistant", "content": limpio})
    return limpio

async def check_reminders():
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            db = cargar_db(); cambio = False
            for r in db["recordatorios"]:
                if r.get("enviado"): continue
                try:
                    if datetime.now() >= datetime.fromisoformat(r["fecha"]):
                        ch = int(r["canal"]) if r["canal"] else CHANNEL_ID
                        c = client.get_channel(ch)
                        if c: await c.send(f"⏰ {r['texto']}")
                        if r.get("recurrente") == "diario":
                            r["fecha"] = (datetime.fromisoformat(r["fecha"]) + timedelta(1)).isoformat()
                        elif r.get("recurrente") == "semanal":
                            r["fecha"] = (datetime.fromisoformat(r["fecha"]) + timedelta(7)).isoformat()
                        elif r.get("recurrente") == "mensual":
                            r["fecha"] = (datetime.fromisoformat(r["fecha"]) + timedelta(30)).isoformat()
                        else: r["enviado"] = True
                        cambio = True
                except: pass
            if cambio: guardar_db(db)
        except: pass
        await asyncio.sleep(30)

ULTIMA_PROACTIVA = 0
INACTIVIDAD_MIN = 20  # minutos sin mensajes para que el bot se active solo

@client.event
async def on_ready():
    print(f"DLAsistente conectado como {client.user}")
    client.loop.create_task(check_reminders())
    client.loop.create_task(proactive_check())

@client.event
async def on_message(msg):
    global ULTIMA_PROACTIVA
    if msg.author.bot or msg.channel.id != CHANNEL_ID: return
    ULTIMA_PROACTIVA = datetime.now().timestamp()
    reply = await procesar(msg.content, msg.channel.id, msg.author.display_name)
    await msg.reply(reply[:1997] if len(reply) > 2000 else reply, mention_author=False)

async def proactive_check():
    """El bot toma iniciativa: pregunta, sugiere, propone cosas periodicamente."""
    global ULTIMA_PROACTIVA
    await client.wait_until_ready()
    while not client.is_closed():
        await asyncio.sleep(300)  # revisa cada 5 minutos
        try:
            ahora = datetime.now()
            # Solo entre 8:00 y 23:00
            if ahora.hour < 8 or ahora.hour >= 23: continue
            # Si ha habido actividad reciente del usuario, esperar
            if (ahora.timestamp() - ULTIMA_PROACTIVA) < INACTIVIDAD_MIN * 60: continue
            # Esperar al menos 45 min desde la ultima proactiva
            if hasattr(proactive_check, "ultima") and (ahora.timestamp() - proactive_check.ultima) < 2700: continue
            proactive_check.ultima = ahora.timestamp()

            canal = client.get_channel(CHANNEL_ID)
            if not canal: continue

            db = cargar_db()
            tareas_pend = [t for t in db["tareas"] if not t["completada"]]
            proyectos = [d for d in os.listdir(PROYECTOS_DIR) if os.path.isdir(os.path.join(PROYECTOS_DIR, d))]

            # Contexto para que el AI genere acciones utiles
            estado = f"Proyectos: {proyectos}\nTareas pendientes: {len(tareas_pend)}: {[t['texto'] for t in tareas_pend[:5]]}\nClientes: {list(db['clientes'].keys())}\nFecha: {AHORA}\nRecuerda: Polleria Rebollo lanza 7-jun-2026"
            prompt_proactivo = f"""
Eres DLAsistente, el agente AUTONOMO de DLvisuals. Tu mision es SER PRODUCTIVO SIN QUE TE LO PIDAN.
Estado actual:
{estado}

ACCIONES PRODUCTIVAS QUE PUEDES EJECUTAR SOLO (elige la MAS UTIL):
- Navegar por la web de un cliente para analizarla: ###TOOL: browse {"url": "https://clientes-web.com"}
- Buscar inspiracion o competidores: ###TOOL: search_web {"query": "mejores webs restaurantes Torrevieja"}
- Buscar precios de mercado o tendencias: ###TOOL: search_web {"query": "precios diseño web 2026"}
- Si Polleria Rebollo no tiene menu generado --> generar codigo HTML del menu con ###TOOL: save_file
- Si un cliente no tiene branding --> generarlo con ###TOOL: generate_branding
- Si un proyecto no tiene meta tags --> generarlas con ###TOOL: generate_meta
- Si hay tareas de hace dias sin completar --> preguntar si necesita ayuda
- Si se acerca un deadline --> generar avance del proyecto o codigo necesario
- Si un proyecto no tiene sitemap --> crearlo con ###TOOL: generate_sitemap
- Buscar nuevas oportunidades de negocio: ###TOOL: search_web {"query": "pymes Torrevieja sin pagina web"}

INSTRUCCIONES:
1. Piensa que es lo MAS UTIL que puedes hacer AHORA sin que te lo pidan
2. Si puedes EJECUTAR algo (generar codigo, crear archivos, anadir tareas), HAZLO y avisa a David
3. Si no hay nada que ejecutar, haz una pregunta util y breve (max 2 frases)
4. Usa ###TOOL: para ejecutar acciones reales
5. NO seas generico. Se concreto y util.
6. David es el CEO, tratale como tal: directo, sin rodeos.
"""
            async with aiohttp.ClientSession() as s:
                async with s.post("https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"},
                    json={"model": "google/gemini-2.0-flash-001", "messages": [{"role": "system", "content": prompt_proactivo}]}) as r:
                    d = await r.json()
                    msg_bot = d["choices"][0]["message"]["content"] if "choices" in d else ""
                    if msg_bot and len(msg_bot) > 20:
                        limpio, tres = await ejecutar(msg_bot, CHANNEL_ID)
                        if tres: limpio += "\n\n" + tres
                        await canal.send(limpio[:1997])
                        ULTIMA_PROACTIVA = ahora.timestamp()
        except Exception as e:
            print(f"Error en proactive: {e}")

client.run(DISCORD_TOKEN)
