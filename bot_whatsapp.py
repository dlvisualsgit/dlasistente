import os, json, asyncio, logging
from aiohttp import web
from datetime import datetime, timedelta
from collections import defaultdict, deque

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("WhatsAppBot")

# ─── CONFIG ─────────────────────────────────────────────────────
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")
PORT = int(os.getenv("PORT", "8080"))
AGENDA_PATH = "agenda.json"

# Datos de la agencia para responder preguntas frecuentes
INFO_AGENCIA = """
DLvisuals - Agencia de desarrollo web, Torrevieja, Alicante.
Servicios y precios:
- Landing Page (1 pagina): 180€ - 350€
- Web Multipage (varias paginas): 250€ - 600€
- E-Commerce (tienda online): 500€ - 2.000€
- Plan Cloud + Mantenimiento: 20€ - 100€/mes (OBLIGATORIO en todos los planes)

Incluye siempre: dominio, hosting, SEO local, diseño Mobile-First, formulario de contacto, botones WhatsApp y llamada, soporte por WhatsApp.

Contacto: David Lara
WhatsApp: +34 XXX XXX XXX
Email: info@dlvisuals.com
"""

# ─── AGENDA ─────────────────────────────────────────────────────
def cargar_agenda():
    if os.path.exists(AGENDA_PATH):
        with open(AGENDA_PATH, encoding="utf-8") as f: return json.load(f)
    return {"citas": [], "horario": {"lunes": "9-14,16-19", "martes": "9-14,16-19", "miercoles": "9-14,16-19", "jueves": "9-14,16-19", "viernes": "9-14,16-19"}, "preguntas_frecuentes": [
        {"pregunta": "precios", "respuesta": "Landing desde 180€, Multipage desde 250€, E-Commerce desde 500€. Plan de mantenimiento desde 20€/mes."},
        {"pregunta": "tiempo", "respuesta": "Entre 7 y 21 dias habiles segun el proyecto."},
        {"pregunta": "dominio", "respuesta": "El dominio y hosting van incluidos en el Plan Cloud."},
        {"pregunta": "pago", "respuesta": "50% al empezar, 50% al entregar."}
    ]}
def guardar_agenda(a):
    with open(AGENDA_PATH, "w", encoding="utf-8") as f: json.dump(a, f, ensure_ascii=False, indent=2)

# ─── SISTEMA ────────────────────────────────────────────────────
CONTEXTO = f"""
Eres el asistente de ATENCION AL CLIENTE de DLvisuals, una agencia de desarrollo web en Torrevieja.
Tu objetivo es atender a potenciales clientes que escriben por WhatsApp.

INFORMACION DE LA AGENCIA:
{INFO_AGENCIA}

INSTRUCCIONES:
1. Responde preguntas sobre servicios y precios de forma clara y amable
2. Si el cliente muestra interes, pide su nombre y telefono para pasarselo a David
3. Si pide agendar una reunion, dile que le diremos disponibilidad
4. Si es una queja o problema, pideme disculpas y di que David le contactara
5. Tono: profesional pero cercano, en espanol
6. NO inventes precios ni servicios: usa solo los datos de arriba
7. Si preguntan algo que no sabes, di que le pasas con David
8. Objetivo: captar leads y dar buena imagen de la agencia

FECHA ACTUAL: {datetime.now().strftime("%d/%m/%Y %H:%M")}
"""

memoria = defaultdict(lambda: deque(maxlen=20))
leads = []

async def preguntar_ai(mensajes):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post("https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"},
                json={"model": "google/gemini-2.0-flash-001", "messages": [{"role": "system", "content": CONTEXTO}] + mensajes}) as r:
                d = await r.json()
                return d["choices"][0]["message"]["content"] if "choices" in d else "Lo siento, ahora mismo no puedo responder. David te contactara pronto."
    except: return "Lo siento, hubo un error. David te contactara pronto."

async def procesar(texto, chat_id, nombre="Cliente"):
    memoria[chat_id].append({"role": "user", "content": f"{nombre}: {texto}"})
    reply = await preguntar_ai(list(memoria[chat_id]))
    memoria[chat_id].append({"role": "assistant", "content": reply})

    # Detectar si es un lead interesado
    texto_lower = texto.lower()
    if any(p in texto_lower for p in ["quiero", "presupuesto", "precio", "cuanto", "me interesa", "contratar", "hazme"]):
        if chat_id not in [l["chat_id"] for l in leads]:
            leads.append({"chat_id": chat_id, "nombre": nombre, "fecha": datetime.now().isoformat(), "ultimo_mensaje": texto})
            log.info(f"NUEVO LEAD: {nombre} ({chat_id}): {texto[:100]}")

    return reply

# ─── WEBHOOK (generico, configurable) ───────────────────────────
async def webhook_whatsapp(request):
    try:
        body = await request.json()
        mensaje = body.get("body") or body.get("message") or body.get("text") or ""
        chat_id = body.get("chatId") or body.get("from") or body.get("sender") or ""
        nombre = body.get("senderName") or "Cliente"

        if not mensaje or not chat_id:
            return web.Response(text="ok")

        log.info(f"WA [{nombre}]: {mensaje[:80]}")
        reply = await procesar(mensaje, chat_id, nombre)

        # Responder por la misma via que llego
        wa_url = os.getenv("WHATSAPP_API_URL", "")
        wa_token = os.getenv("WHATSAPP_API_TOKEN", "")
        if wa_url and wa_token:
            async with aiohttp.ClientSession() as s:
                await s.post(wa_url, json={"chatId": chat_id, "message": reply[:4096],
                    "token": wa_token})

        return web.Response(text="ok")
    except Exception as e:
        log.error(f"Error webhook: {e}")
        return web.Response(text="ok")

async def webhook_twilio(request):
    """Para Twilio WhatsApp Sandbox"""
    try:
        # Leer cuerpo como texto y parsear manualmente
        body_text = await request.text()
        log.info(f"Twilio raw: {body_text[:300]}")

        import urllib.parse
        data = urllib.parse.parse_qs(body_text)
        mensaje = (data.get("Body", [""])[0])
        chat_id = (data.get("From", [""])[0])
        nombre = (data.get("ProfileName", ["Cliente"])[0])

        log.info(f"Twilio [{nombre} ({chat_id})]: {mensaje[:100]}")

        if not mensaje or not chat_id:
            return web.Response(text="<Response></Response>", content_type="application/xml")

        reply = await procesar(mensaje, chat_id, nombre)
        reply = reply.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        xml = f'<?xml version="1.0"?><Response><Message>{reply[:1600]}</Message></Response>'
        return web.Response(text=xml, content_type="application/xml")
    except Exception as e:
        log.error(f"Twilio error: {e}", exc_info=True)
        return web.Response(text='<Response><Message>Gracias! David te contactara pronto.</Message></Response>',
            content_type="application/xml")

async def webhook_greenapi(request):
    """Para Green-API"""
    return await webhook_whatsapp(request)

# ─── PANEL DE CONTROL (para ver leads) ─────────────────────────
async def panel_leads(request):
    html = "<html><body><h2>Leads captados</h2><table border=1>"
    html += "<tr><th>Fecha</th><th>Nombre</th><th>Chat ID</th><th>Ultimo mensaje</th></tr>"
    for l in leads[-20:]:
        html += f"<tr><td>{l['fecha'][:16]}</td><td>{l['nombre']}</td><td>{l['chat_id']}</td><td>{l['ultimo_mensaje'][:80]}</td></tr>"
    html += "</table></body></html>"
    return web.Response(text=html, content_type="text/html")

# ─── SERVIDOR ───────────────────────────────────────────────────
async def init_app():
    app = web.Application()
    app.router.add_post("/webhook", webhook_whatsapp)
    app.router.add_post("/twilio", webhook_twilio)
    app.router.add_post("/greenapi", webhook_greenapi)
    app.router.add_get("/leads", panel_leads)
    app.router.add_get("/", lambda r: web.Response(text="WhatsApp Bot DLvisuals Online"))
    return app

if __name__ == "__main__":
    app = asyncio.run(init_app())
    web.run_app(app, port=PORT)
