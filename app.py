from flask import Flask, render_template, request, redirect, url_for, flash
import json, os, smtplib
from email.mime.text import MIMEText

app = Flask(__name__)
app.secret_key = "clave_secreta" 

CONFIG_FILE = "config.json"
EMPRESAS_FILE = "empresas.json"

def load_json(path, default):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=4, ensure_ascii=False)
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

DEFAULT_CONFIG = {
    "email_origen": "",
    "password": "",
    "smtp_servidor": "smtp.gmail.com",
    "smtp_puerto": 587,
    "plantilla": "Hola {nombre_empresa},\n\nSomos una agencia que ayuda a negocios como {nombre_empresa} ({sector}) a tener presencia online en {ciudad}.\n\nUn saludo."
}
DEFAULT_EMPRESAS = []

config = load_json(CONFIG_FILE, DEFAULT_CONFIG)
empresas = load_json(EMPRESAS_FILE, DEFAULT_EMPRESAS)


@app.route("/")
def index():
    return redirect(url_for("list_empresas"))


@app.route("/config", methods=["GET", "POST"])
def config_page():
    cfg = load_json(CONFIG_FILE, DEFAULT_CONFIG)
    if request.method == "POST":
        cfg["email_origen"] = request.form.get("email_origen", "").strip()
        cfg["password"] = request.form.get("password", "").strip()
        cfg["smtp_servidor"] = request.form.get("smtp_servidor", "smtp.gmail.com").strip()
        try:
            cfg["smtp_puerto"] = int(request.form.get("smtp_puerto", cfg.get("smtp_puerto", 587)))
        except:
            cfg["smtp_puerto"] = 587
        cfg["plantilla"] = request.form.get("plantilla", "").strip()
        save_json(CONFIG_FILE, cfg)
        flash("Configuración guardada correctamente.", "success")
        return redirect(url_for("config_page"))
    return render_template("config.html", config=cfg)


@app.route("/empresas")
def list_empresas():
    empresas = load_json(EMPRESAS_FILE, DEFAULT_EMPRESAS)
    # attach id
    empresas_indexed = [{"id": i, **e} for i, e in enumerate(empresas)]
    return render_template("empresas.html", empresas=empresas_indexed)


@app.route("/empresas/pendientes")
def list_pendientes():
    empresas = load_json(EMPRESAS_FILE, DEFAULT_EMPRESAS)
    pendientes = [{"id": i, **e} for i, e in enumerate(empresas) if not e.get("enviado", False)]
    return render_template("pendientes.html", empresas=pendientes)


@app.route("/empresas/nueva", methods=["GET", "POST"])
def add_empresa():
    if request.method == "POST":
        nombre = request.form.get("nombre","").strip()
        email = request.form.get("email","").strip()
        sector = request.form.get("sector","").strip()
        ciudad = request.form.get("ciudad","").strip()
        if not nombre or not email:
            flash("Nombre y email son obligatorios.", "danger")
            return redirect(url_for("add_empresa"))
        empresas = load_json(EMPRESAS_FILE, DEFAULT_EMPRESAS)
        empresas.append({
            "nombre": nombre,
            "email": email,
            "sector": sector,
            "ciudad": ciudad,
            "enviado": False
        })
        save_json(EMPRESAS_FILE, empresas)
        flash("Empresa añadida.", "success")
        return redirect(url_for("list_empresas"))
    return render_template("add_empresa.html")


@app.route("/empresas/editar/<int:id>", methods=["GET", "POST"])
def edit_empresa(id):
    empresas = load_json(EMPRESAS_FILE, DEFAULT_EMPRESAS)
    if id < 0 or id >= len(empresas):
        flash("Empresa no encontrada.", "danger")
        return redirect(url_for("list_empresas"))
    if request.method == "POST":
        empresas[id]["nombre"] = request.form.get("nombre","").strip()
        empresas[id]["email"] = request.form.get("email","").strip()
        empresas[id]["sector"] = request.form.get("sector","").strip()
        empresas[id]["ciudad"] = request.form.get("ciudad","").strip()
        save_json(EMPRESAS_FILE, empresas)
        flash("Empresa actualizada.", "success")
        return redirect(url_for("list_empresas"))
    empresa = {"id": id, **empresas[id]}
    return render_template("edit_empresa.html", empresa=empresa)


@app.route("/empresas/eliminar/<int:id>", methods=["POST"])
def delete_empresa(id):
    empresas = load_json(EMPRESAS_FILE, DEFAULT_EMPRESAS)
    if id < 0 or id >= len(empresas):
        flash("Empresa no encontrada.", "danger")
    else:
        empresas.pop(id)
        save_json(EMPRESAS_FILE, empresas)
        flash("Empresa eliminada.", "success")
    return redirect(url_for("list_empresas"))


@app.route("/emails/enviar", methods=["GET", "POST"])
def send_emails():
    if request.method == "POST":
        empresas = load_json(EMPRESAS_FILE, DEFAULT_EMPRESAS)
        cfg = load_json(CONFIG_FILE, DEFAULT_CONFIG)

        origen = cfg.get("email_origen","")
        password = cfg.get("password","")
        servidor = cfg.get("smtp_servidor","smtp.gmail.com")
        puerto = cfg.get("smtp_puerto", 587)
        plantilla = cfg.get("plantilla", DEFAULT_CONFIG["plantilla"])

        if not origen or not password:
            flash("Configura el email y la contraseña en Configuración antes de enviar.", "danger")
            return redirect(url_for("config_page"))

        enviados = 0
        errores = 0

       
        try:
            if puerto == 465:
                server = smtplib.SMTP_SSL(servidor, puerto)
            else:
                server = smtplib.SMTP(servidor, puerto, timeout=20)
                server.ehlo()
                if puerto == 587:
                    server.starttls()
            server.login(origen, password)
        except Exception as ex:
            flash(f"Error conectando al servidor SMTP: {ex}", "danger")
            return redirect(url_for("config_page"))

        for idx, e in enumerate(empresas):
            if e.get("enviado", False):
                continue
            cuerpo = plantilla.format(
                nombre_empresa=e.get("nombre",""),
                nombre_contacto=e.get("nombre_contacto",""),
                sector=e.get("sector",""),
                ciudad=e.get("ciudad","")
            )
            msg = MIMEText(cuerpo, "plain", "utf-8")
            msg["Subject"] = f"Propuesta para {e.get('nombre','')}"
            msg["From"] = origen
            msg["To"] = e.get("email","")

            try:
                server.sendmail(origen, e.get("email",""), msg.as_string())
                empresas[idx]["enviado"] = True
                enviados += 1
            except Exception:
                empresas[idx]["enviado"] = False
                errores += 1

        try:
            server.quit()
        except:
            pass

        save_json(EMPRESAS_FILE, empresas)
        flash(f"Enviados: {enviados} | Errores: {errores}", "info")
        return redirect(url_for("list_pendientes"))

    
    empresas = load_json(EMPRESAS_FILE, DEFAULT_EMPRESAS)
    pendientes = [ {"id": i, **e} for i,e in enumerate(empresas) if not e.get("enviado", False) ]
    return render_template("send_emails.html", pendientes=pendientes)


if __name__ == "__main__":
    app.run(debug=True)
