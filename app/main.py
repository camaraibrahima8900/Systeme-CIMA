# ============================================================
# main.py — Système CIMA avec Login Keycloak + 4 interfaces
# Auteur : Ibrahima Camara - USSEIN L3 Informatique 2024-2025
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import mysql.connector
from mysql.connector import Error
import urllib.request
import urllib.parse
import json
from datetime import datetime, date, timedelta
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def formater_ligne(ligne):
    """Convertit toute valeur datetime d'une ligne SQL en date lisible (JJ/MM/AAAA), sans l'heure."""
    resultat = []
    for v in ligne:
        if isinstance(v, datetime):
            resultat.append(v.strftime("%d/%m/%Y"))
        else:
            resultat.append(v)
    return tuple(resultat)
import os
import webbrowser
import shutil
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor

# ============================================================
# CONFIGURATION
# ============================================================
KEYCLOAK_URL      = "http://cima_keycloak:8080"
REALM             = "cima"
CLIENT_ID         = "cima-client"
KC_ADMIN_CLIENT_ID     = os.environ.get("KC_ADMIN_CLIENT_ID", "cima-service")
KC_ADMIN_CLIENT_SECRET = os.environ.get("KC_ADMIN_CLIENT_SECRET", "")
DB_HOST           = os.environ.get("DB_HOST", "mysql")
DB_PORT           = int(os.environ.get("DB_PORT", "3306"))
DB_USER           = os.environ.get("DB_USER", "ibrahima")
DB_PASSWORD       = os.environ.get("DB_PASSWORD", "8900")
DB_NAME           = os.environ.get("DB_NAME", "gestion_dossiers_victimes")

# ---- Configuration SMTP (envoi d'emails en parallèle des notifications) ----
SMTP_HOST         = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT         = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER         = os.environ.get("SMTP_USER", "")        # ex: tonadresse@gmail.com
SMTP_PASSWORD     = os.environ.get("SMTP_PASSWORD", "")    # mot de passe d'application (16 caractères)
SMTP_FROM_NAME    = os.environ.get("SMTP_FROM_NAME", "Système CIMA")
EMAIL_ACTIVE      = bool(SMTP_USER and SMTP_PASSWORD)

# ============================================================
# PALETTE DE COULEURS
# ============================================================
C = {
    "bg":        "#0d1117",
    "panel":     "#161b22",
    "card":      "#21262d",
    "border":    "#30363d",
    "text":      "#e6edf3",
    "muted":     "#8b949e",
    "victime":   "#238636",
    "assistant": "#1f6feb",
    "assureur":  "#9e6a03",
    "admin":     "#8957e5",
    "danger":    "#da3633",
    "success":   "#238636",
    "white":     "#ffffff",
}

# ============================================================
# CONNEXION MYSQL
# ============================================================
def connecter_db():
    try:
        return mysql.connector.connect(
            host=DB_HOST, port=DB_PORT,
            user=DB_USER, password=DB_PASSWORD,
            database=DB_NAME
        )
    except Error as e:
        messagebox.showerror("Erreur BDD", str(e))
        return None

# ============================================================
# AUTHENTIFICATION KEYCLOAK
# ============================================================
def login_keycloak(username, password):
    """
    Retourne (token_data, roles, infos, erreur_message).
    En cas d'échec, erreur_message contient la VRAIE raison donnée par
    Keycloak (email non vérifié, mot de passe incorrect, compte désactivé...).
    """
    try:
        url = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token"
        data = urllib.parse.urlencode({
            "client_id":  CLIENT_ID,
            "username":   username,
            "password":   password,
            "grant_type": "password",
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req, timeout=10) as resp:
            token_data = json.loads(resp.read())

        import base64
        payload = token_data["access_token"].split(".")[1]
        payload += "=" * (4 - len(payload) % 4)
        claims = json.loads(base64.b64decode(payload))
        roles  = claims.get("realm_access", {}).get("roles", [])
        infos = {
            "email":  claims.get("email", ""),
            "nom":    claims.get("family_name", ""),
            "prenom": claims.get("given_name", ""),
        }
        return token_data, roles, infos, None
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode())
            desc = err.get("error_description", "Erreur d'authentification.")
        except Exception:
            desc = "Erreur d'authentification."
        # Traduction des messages Keycloak les plus courants
        traductions = {
            "Invalid user credentials": "Nom d'utilisateur ou mot de passe incorrect.",
            "Account is not fully set up": "Votre email n'est pas encore vérifié — consultez votre boîte mail.",
            "Account disabled": "Ce compte a été désactivé. Contactez l'administrateur.",
            "User is disabled": "Ce compte a été désactivé. Contactez l'administrateur.",
        }
        return None, [], {}, traductions.get(desc, desc)
    except Exception as e:
        return None, [], {}, "Impossible de contacter le serveur d'authentification. Réessayez."

def obtenir_token_admin():
    """Obtient un jeton d'accès admin via le client de service cima-service (client_credentials)."""
    if not KC_ADMIN_CLIENT_SECRET:
        return None, "Le client de service Keycloak n'est pas configuré (KC_ADMIN_CLIENT_SECRET manquant)."
    try:
        url = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token"
        data = urllib.parse.urlencode({
            "client_id":     KC_ADMIN_CLIENT_ID,
            "client_secret": KC_ADMIN_CLIENT_SECRET,
            "grant_type":    "client_credentials",
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req, timeout=10) as resp:
            token_data = json.loads(resp.read())
        return token_data["access_token"], None
    except Exception as e:
        return None, f"Impossible d'obtenir un jeton admin : {e}"

def creer_utilisateur_keycloak(username, email, password, prenom, nom):
    """
    Crée un utilisateur directement via l'API Admin Keycloak (sans navigateur),
    puis déclenche l'envoi de l'email de vérification.
    Retourne (succes: bool, message: str).
    """
    token, err = obtenir_token_admin()
    if not token:
        return False, err
    try:
        url = f"{KEYCLOAK_URL}/admin/realms/{REALM}/users"
        payload = json.dumps({
            "username": username,
            "email": email,
            "firstName": prenom,
            "lastName": nom,
            "enabled": True,
            "emailVerified": False,
            "credentials": [{"type": "password", "value": password, "temporary": False}],
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=10) as resp:
            location = resp.headers.get("Location", "")
        id_utilisateur = location.rstrip("/").split("/")[-1] if location else None

        # Déclenche l'envoi de l'email de vérification (SMTP déjà configuré côté Keycloak)
        if id_utilisateur:
            try:
                url_verif = f"{KEYCLOAK_URL}/admin/realms/{REALM}/users/{id_utilisateur}/send-verify-email"
                req2 = urllib.request.Request(url_verif, data=b"", method="PUT")
                req2.add_header("Authorization", f"Bearer {token}")
                urllib.request.urlopen(req2, timeout=10)
            except Exception:
                pass  # la création reste valide même si l'envoi échoue

        return True, id_utilisateur
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode())
            msg = err_body.get("errorMessage", "Erreur inconnue.")
        except Exception:
            msg = "Erreur inconnue."
        if "already exists" in msg.lower() or e.code == 409:
            return False, "Ce nom d'utilisateur ou cet email est déjà utilisé."
        return False, msg
    except Exception as e:
        return False, f"Erreur de connexion à Keycloak : {e}"

# ============================================================
# HELPERS UI
# ============================================================
def clear_window(root):
    for w in root.winfo_children():
        w.destroy()

def tableau(parent, colonnes, largeurs, hauteur=12):
    frame = tk.Frame(parent, bg=C["card"])
    frame.pack(fill="both", expand=True, padx=15, pady=8)
    style = ttk.Style()
    style.configure("Custom.Treeview",
        background=C["card"], foreground=C["text"],
        rowheight=28, fieldbackground=C["card"], font=("Segoe UI", 9))
    style.configure("Custom.Treeview.Heading",
        background=C["bg"], foreground="#58a6ff",
        font=("Segoe UI", 9, "bold"), relief="flat")
    style.map("Custom.Treeview", background=[("selected", "#1f6feb")])
    sb = ttk.Scrollbar(frame, orient="vertical")
    sb.pack(side="right", fill="y")
    tbl = ttk.Treeview(frame, columns=colonnes, show="headings",
                       height=hauteur, style="Custom.Treeview",
                       yscrollcommand=sb.set)
    for col, larg in zip(colonnes, largeurs):
        tbl.heading(col, text=col)
        tbl.column(col, width=larg, minwidth=40)
    tbl.tag_configure("pair",  background="#1c2128")
    tbl.tag_configure("impair",background=C["card"])
    sb.config(command=tbl.yview)
    tbl.pack(fill="both", expand=True)
    return tbl

def btn(parent, texte, cmd, couleur, fg="white", side="left", pady=0):
    b = tk.Button(parent, text=texte, command=cmd,
                  bg=couleur, fg=fg, font=("Segoe UI", 9, "bold"),
                  relief="flat", cursor="hand2", padx=14, pady=6)
    b.pack(side=side, padx=6, pady=pady)
    return b

def section(parent, titre, couleur):
    tk.Frame(parent, bg=couleur, height=3).pack(fill="x", padx=12, pady=(10,2))
    tk.Label(parent, text=titre, font=("Segoe UI", 10, "bold"),
             bg=C["panel"], fg=couleur).pack(anchor="w", padx=14)

def champ(parent, label):
    tk.Label(parent, text=label, bg=C["panel"], fg=C["muted"],
             font=("Segoe UI", 8)).pack(anchor="w", padx=14, pady=(4,0))
    e = tk.Entry(parent, font=("Segoe UI", 9), bg=C["card"], fg=C["text"],
                 insertbackground=C["text"], relief="flat",
                 highlightthickness=1, highlightcolor="#58a6ff",
                 highlightbackground=C["border"])
    e.pack(padx=14, pady=2, ipady=5, fill="x")
    return e

def stat_card(parent, label, valeur, couleur):
    f = tk.Frame(parent, bg=couleur, padx=16, pady=10)
    f.pack(side="left", padx=6)
    tk.Label(f, text=valeur, font=("Segoe UI", 22, "bold"),
             bg=couleur, fg="white").pack()
    tk.Label(f, text=label, font=("Segoe UI", 8),
             bg=couleur, fg="white").pack()

def obtenir_id_acteur(username, email=None):
    """
    Retrouve l'id_acteur réel à partir de l'identifiant Keycloak, quelle que soit
    la forme utilisée pour se connecter : pseudo libre, email, ou format prenom.nom.
    Auto-répare les comptes créés avant l'ajout de la colonne 'username'
    en la renseignant dès qu'une correspondance fiable est trouvée.
    """
    db = connecter_db()
    if not db:
        return None
    try:
        c = db.cursor()

        # 1) Correspondance directe sur le username stocké (cas normal)
        c.execute("SELECT id_acteur FROM acteur WHERE username=%s LIMIT 1", (username,))
        row = c.fetchone()
        if row:
            return row[0]

        # 2) Le username saisi est en fait un email
        c.execute("SELECT id_acteur FROM acteur WHERE LOWER(email)=%s LIMIT 1", (username.lower(),))
        row = c.fetchone()
        if row:
            c.execute("UPDATE acteur SET username=%s WHERE id_acteur=%s AND username IS NULL", (username, row[0]))
            db.commit()
            return row[0]

        # 3) Email réel fourni par Keycloak (compte créé avant la colonne username)
        if email:
            c.execute("SELECT id_acteur FROM acteur WHERE LOWER(email)=%s LIMIT 1", (email.lower(),))
            row = c.fetchone()
            if row:
                c.execute("UPDATE acteur SET username=%s WHERE id_acteur=%s AND username IS NULL", (username, row[0]))
                db.commit()
                return row[0]

        # 4) Format historique prenom.nom
        parts = username.split(".")
        if len(parts) >= 2:
            prenom, nom = parts[0], parts[1]
            c.execute("SELECT id_acteur FROM acteur WHERE LOWER(prenom)=%s AND LOWER(nom)=%s LIMIT 1",
                      (prenom.lower(), nom.lower()))
            row = c.fetchone()
            if row:
                c.execute("UPDATE acteur SET username=%s WHERE id_acteur=%s AND username IS NULL", (username, row[0]))
                db.commit()
                return row[0]

        return None

    finally:
        db.close()

def envoyer_email(destinataire_email, destinataire_nom, sujet, message):
    """Envoie un email réel via SMTP (en arrière-plan, ne bloque pas l'interface)."""
    if not EMAIL_ACTIVE or not destinataire_email:
        return

    def _envoi():
        try:
            msg = MIMEMultipart()
            msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
            msg["To"] = destinataire_email
            msg["Subject"] = f"[CIMA] {sujet}"

            corps_html = f"""
            <html><body style="font-family: Arial, sans-serif; color:#222;">
                <div style="max-width:600px;margin:auto;border:1px solid #ddd;border-radius:8px;overflow:hidden;">
                    <div style="background:#1B4F72;color:white;padding:16px 20px;">
                        <h2 style="margin:0;">🏥 Système CIMA</h2>
                        <p style="margin:4px 0 0;font-size:13px;">Gestion des Dossiers Victimes d'Accidents Routiers</p>
                    </div>
                    <div style="padding:20px;">
                        <p>Bonjour {destinataire_nom},</p>
                        <p style="background:#f4f4f4;border-left:4px solid #1B4F72;padding:12px;border-radius:4px;">
                            {message}
                        </p>
                        <p style="font-size:12px;color:#888;margin-top:24px;">
                            Ceci est une notification automatique. Connectez-vous à l'application pour plus de détails.
                        </p>
                    </div>
                </div>
            </body></html>
            """
            msg.attach(MIMEText(corps_html, "html"))

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as serveur:
                serveur.starttls()
                serveur.login(SMTP_USER, SMTP_PASSWORD)
                serveur.sendmail(SMTP_USER, destinataire_email, msg.as_string())
        except Exception as e:
            print(f"⚠️ Échec envoi email à {destinataire_email} : {e}")

    threading.Thread(target=_envoi, daemon=True).start()

def envoyer_notification_auto(id_acteur, id_dossier, message):
    """Insère une notification en base ET envoie un email en parallèle à l'acteur concerné."""
    db = connecter_db()
    if not db:
        return
    try:
        c = db.cursor()
        c.execute("""INSERT INTO notification (id_acteur, id_dossier, message)
                     VALUES (%s, %s, %s)""", (id_acteur, id_dossier, message))
        db.commit()

        # Récupérer l'email et le nom de l'acteur pour l'envoi en parallèle
        c.execute("SELECT nom, prenom, email FROM acteur WHERE id_acteur=%s", (id_acteur,))
        row = c.fetchone()
        if row:
            nom, prenom, email = row
            envoyer_email(email, f"{prenom} {nom}", "Nouvelle notification sur votre dossier", message)
    except Error:
        pass
    finally:
        db.close()

def generer_lettre_decision(id_decision):
    """
    Génère automatiquement la lettre officielle (validation ou rejet) en PDF
    suite à la décision de l'assureur, l'enregistre sur disque et la lie au dossier
    comme document consultable par la victime et l'assistant.
    Retourne (chemin_pdf, numero_dossier) ou (None, None) en cas d'échec.
    """
    db = connecter_db()
    if not db:
        return None, None
    try:
        c = db.cursor()
        c.execute("""
            SELECT de.resultat, de.motif, de.date_decision,
                   d.id_dossier, d.numero_dossier,
                   av.nom, av.prenom,
                   aa.nom, aa.prenom, aa.email, aa.telephone,
                   s.nom_compagnie, s.numero_agrement_cima,
                   di.montant_reclame, di.montant_evalue, di.id_demande
            FROM decision de
            JOIN demande_indemnisation di ON de.id_demande = di.id_demande
            JOIN dossier d ON di.id_dossier = d.id_dossier
            JOIN acteur av ON d.id_victime = av.id_acteur
            JOIN acteur aa ON di.id_assureur = aa.id_acteur
            JOIN assureur s ON aa.id_acteur = s.id_acteur
            WHERE de.id_decision = %s
        """, (id_decision,))
        row = c.fetchone()
        if not row:
            return None, None

        (resultat, motif, date_decision, id_dossier, numero_dossier,
         nom_v, prenom_v, nom_a, prenom_a, email_a, tel_a,
         compagnie, agrement, montant_reclame, montant_evalue, id_demande) = row

        dossier_lettres = "/app/documents_stockes/lettres"
        os.makedirs(dossier_lettres, exist_ok=True)
        type_lettre = "VALIDATION" if resultat == "VALIDEE" else "REJET"
        nom_fichier = f"LETTRE_{type_lettre}_{numero_dossier}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        chemin_pdf = os.path.join(dossier_lettres, nom_fichier)

        c_pdf = canvas.Canvas(chemin_pdf, pagesize=A4)
        largeur, hauteur = A4
        BLEU = HexColor("#1B4F72")
        GRIS = HexColor("#555555")

        # En-tête
        c_pdf.setFillColor(BLEU)
        c_pdf.setFont("Helvetica-Bold", 16)
        c_pdf.drawString(20*mm, hauteur-25*mm, compagnie or "Compagnie d'Assurance")
        c_pdf.setFont("Helvetica", 9)
        c_pdf.setFillColor(GRIS)
        c_pdf.drawString(20*mm, hauteur-31*mm, f"N° Agrément CIMA : {agrement or '—'}")
        c_pdf.line(20*mm, hauteur-35*mm, largeur-20*mm, hauteur-35*mm)

        # Date et référence
        c_pdf.setFillColor(HexColor("#000000"))
        c_pdf.setFont("Helvetica", 10)
        c_pdf.drawRightString(largeur-20*mm, hauteur-45*mm, f"Fait le {date_decision.strftime('%d/%m/%Y')}")
        c_pdf.drawString(20*mm, hauteur-45*mm, f"Réf. Dossier : {numero_dossier}")

        # Destinataire
        c_pdf.setFont("Helvetica-Bold", 11)
        c_pdf.drawString(20*mm, hauteur-60*mm, f"À l'attention de : {prenom_v} {nom_v}")

        # Objet
        y = hauteur-75*mm
        c_pdf.setFont("Helvetica-Bold", 12)
        if resultat == "VALIDEE":
            c_pdf.setFillColor(HexColor("#1E8449"))
            c_pdf.drawString(20*mm, y, "OBJET : NOTIFICATION DE VALIDATION D'INDEMNISATION")
        else:
            c_pdf.setFillColor(HexColor("#C0392B"))
            c_pdf.drawString(20*mm, y, "OBJET : NOTIFICATION DE REJET DE DEMANDE D'INDEMNISATION")
        c_pdf.setFillColor(HexColor("#000000"))

        # Corps de la lettre
        y -= 15*mm
        c_pdf.setFont("Helvetica", 10)
        texte = c_pdf.beginText(20*mm, y)
        texte.setLeading(15)

        if resultat == "VALIDEE":
            montant_final = montant_evalue if montant_evalue else montant_reclame
            lignes = [
                f"Madame, Monsieur {prenom_v} {nom_v},",
                "",
                f"Nous faisons suite à l'examen de votre dossier n° {numero_dossier} concernant",
                "votre demande d'indemnisation suite à l'accident de la circulation dont vous",
                "avez été victime.",
                "",
                "Après évaluation de votre préjudice conformément au Code CIMA, nous avons",
                "le plaisir de vous informer que votre demande a été VALIDÉE.",
                "",
                f"Montant de l'indemnisation accordée : {montant_final:,.0f} FCFA".replace(",", " "),
                "",
                "Conformément au Code CIMA, le règlement de cette somme interviendra dans",
                "un délai de 15 jours à compter de la présente notification.",
                "",
                f"Votre dossier est suivi par : {prenom_a} {nom_a}",
                f"Contact : {email_a}  |  {tel_a}",
                "",
                "Nous vous prions d'agréer, Madame, Monsieur, l'expression de nos salutations",
                "distinguées.",
            ]
        else:
            lignes = [
                f"Madame, Monsieur {prenom_v} {nom_v},",
                "",
                f"Nous faisons suite à l'examen de votre dossier n° {numero_dossier} concernant",
                "votre demande d'indemnisation suite à l'accident de la circulation dont vous",
                "avez été victime.",
                "",
                "Après étude approfondie de votre dossier, nous sommes au regret de vous",
                "informer que votre demande a été REJETÉE, pour le motif suivant :",
                "",
            ]
            motif_lignes = [motif[i:i+85] for i in range(0, len(motif or "Motif non précisé"), 85)] or ["Motif non précisé"]
            lignes += [f"    « {l} »" if i == 0 else f"      {l}" for i, l in enumerate(motif_lignes)]
            lignes += [
                "",
                "DROIT DE RECOURS : Conformément à la réglementation en vigueur, vous disposez",
                "d'un délai pour contester cette décision auprès de notre compagnie. Pour ce",
                "faire, veuillez vous rapprocher de votre assistant dans les meilleurs délais.",
                "",
                f"Votre dossier est suivi par : {prenom_a} {nom_a}",
                f"Contact : {email_a}  |  {tel_a}",
                "",
                "Nous vous prions d'agréer, Madame, Monsieur, l'expression de nos salutations",
                "distinguées.",
            ]

        for ligne in lignes:
            texte.textLine(ligne)
        c_pdf.drawText(texte)

        # Pied de page
        c_pdf.setFont("Helvetica-Oblique", 8)
        c_pdf.setFillColor(GRIS)
        c_pdf.drawCentredString(largeur/2, 15*mm,
            "Document généré automatiquement — Système CIMA de gestion des dossiers victimes d'accidents routiers")

        c_pdf.save()

        # Enregistrement comme document lié au dossier
        c.execute("""INSERT INTO document (id_dossier, type_document, chemin_fichier, statut_validation)
                     VALUES (%s, 'LETTRE_DECISION', %s, 'VALIDE')""", (id_dossier, chemin_pdf))
        db.commit()

        return chemin_pdf, numero_dossier
    except Exception as e:
        print(f"Erreur génération lettre PDF : {e}")
        return None, None
    finally:
        db.close()

def generer_code_accident():
    """Génère un code lisible type ACC-20260723-001"""
    db = connecter_db()
    if not db:
        return f"ACC-{datetime.now().strftime('%Y%m%d')}-001"
    try:
        c = db.cursor()
        prefixe = f"ACC-{datetime.now().strftime('%Y%m%d')}"
        c.execute("SELECT COUNT(*) FROM accident WHERE numero_pv LIKE %s", (f"{prefixe}%",))
        n = c.fetchone()[0] + 1
        return f"{prefixe}-{n:03d}"
    finally:
        db.close()

def supprimer_ligne_selectionnee(tbl, table_sql, col_id, callback_refresh, label="élément"):
    """Supprime la ligne sélectionnée d'un tableau Treeview + la BDD."""
    sel = tbl.selection()
    if not sel:
        messagebox.showwarning("Aucune sélection", f"Sélectionnez un {label} dans le tableau."); return
    vals = tbl.item(sel[0])["values"]
    id_val = vals[0]
    if not messagebox.askyesno("⚠️ Confirmer la suppression",
            f"Supprimer définitivement {label} #{id_val} ?\nCette action est irréversible."):
        return
    db = connecter_db()
    if not db: return
    try:
        c = db.cursor()
        c.execute(f"DELETE FROM {table_sql} WHERE {col_id} = %s", (id_val,))
        db.commit()
        if c.rowcount == 0:
            messagebox.showerror("Erreur", f"{label} #{id_val} introuvable.")
        else:
            messagebox.showinfo("✅ Supprimé", f"{label.capitalize()} #{id_val} supprimé.")
            callback_refresh()
    except Error as e:
        messagebox.showerror("Erreur de suppression",
            f"{e}\n\n(Cet élément est peut-être lié à d'autres données.)")
    finally:
        db.close()

def barre_recherche(parent, placeholder="Rechercher..."):
    """Crée une barre de recherche stylée au-dessus d'un tableau. Retourne le widget Entry."""
    f = tk.Frame(parent, bg=C["card"])
    f.pack(fill="x", padx=8, pady=(8,0))
    tk.Label(f, text="🔍", bg=C["card"], fg=C["muted"], font=("Segoe UI", 10)).pack(side="left")
    ent = tk.Entry(f, font=("Segoe UI", 9), bg=C["bg"], fg=C["text"],
        insertbackground=C["text"], relief="flat", highlightthickness=1,
        highlightcolor="#58a6ff", highlightbackground=C["border"], width=38)
    ent.pack(side="left", padx=6, ipady=4)
    tk.Label(f, text=placeholder, bg=C["card"], fg=C["muted"], font=("Segoe UI", 8)).pack(side="left")
    return ent

def panneau_scrollable(cadre, largeur=280):
    """Panneau gauche défilable à la molette — fonctionne sur tout le panneau, y compris au-dessus des champs."""
    container = tk.Frame(cadre, bg=C["panel"], width=largeur)
    container.pack(side="left", fill="y", padx=(0,8))
    container.pack_propagate(False)

    canvas = tk.Canvas(container, bg=C["panel"], highlightthickness=0, width=largeur)
    scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
    inner = tk.Frame(canvas, bg=C["panel"])

    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas_window = canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    def _resize(event):
        canvas.itemconfig(canvas_window, width=event.width)
    canvas.bind("<Configure>", _resize)

    # Barre de boutons ▲▼ (packée EN PREMIER pour réserver sa place tout en bas)
    barre_scroll = tk.Frame(container, bg=C["panel"])
    barre_scroll.pack(side="bottom", fill="x", pady=4)
    tk.Button(barre_scroll, text="▲ Monter", command=lambda: canvas.yview_scroll(-4, "units"),
              bg="#30363d", fg="white", font=("Segoe UI", 8, "bold"),
              relief="flat", cursor="hand2").pack(side="left", expand=True, fill="x", padx=(10,3))
    tk.Button(barre_scroll, text="▼ Descendre", command=lambda: canvas.yview_scroll(4, "units"),
              bg="#30363d", fg="white", font=("Segoe UI", 8, "bold"),
              relief="flat", cursor="hand2").pack(side="left", expand=True, fill="x", padx=(3,10))

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def _on_scroll_up(event):
        canvas.yview_scroll(-2, "units")

    def _on_scroll_down(event):
        canvas.yview_scroll(2, "units")

    def _bind_scroll(e):
        canvas.bind_all("<MouseWheel>", _on_mousewheel)   # Windows
        canvas.bind_all("<Button-4>", _on_scroll_up)        # Linux/X11 molette haut
        canvas.bind_all("<Button-5>", _on_scroll_down)      # Linux/X11 molette bas

    def _unbind_scroll(e):
        canvas.unbind_all("<MouseWheel>")
        canvas.unbind_all("<Button-4>")
        canvas.unbind_all("<Button-5>")

    # Liaison globale activée/désactivée à l'entrée/sortie du panneau entier
    # (fonctionne même quand la souris survole un champ Entry ou Combobox)
    container.bind("<Enter>", _bind_scroll)
    container.bind("<Leave>", _unbind_scroll)

    return inner

# ============================================================
# INTERFACE LOGIN
# ============================================================
def afficher_login(root):
    clear_window(root)
    root.title("Système CIMA — Connexion")
    root.geometry("480x660")
    root.configure(bg=C["bg"])
    root.resizable(False, False)

    tk.Frame(root, bg=C["bg"], height=40).pack()
    tk.Label(root, text="🏥", font=("Segoe UI", 48), bg=C["bg"]).pack()
    tk.Label(root, text="Système CIMA", font=("Segoe UI", 20, "bold"),
             bg=C["bg"], fg=C["text"]).pack()
    tk.Label(root, text="Gestion des Dossiers Victimes d'Accidents Routiers",
             font=("Segoe UI", 9), bg=C["bg"], fg=C["muted"]).pack(pady=(2,20))

    card = tk.Frame(root, bg=C["panel"], padx=30, pady=30)
    card.pack(padx=40, fill="x")

    tk.Label(card, text="Connexion", font=("Segoe UI", 13, "bold"),
             bg=C["panel"], fg=C["text"]).pack(anchor="w", pady=(0,15))

    tk.Label(card, text="Nom d'utilisateur", font=("Segoe UI", 9),
             bg=C["panel"], fg=C["muted"]).pack(anchor="w")
    ent_user = tk.Entry(card, font=("Segoe UI", 11), bg=C["card"], fg=C["text"],
                        insertbackground=C["text"], relief="flat",
                        highlightthickness=1, highlightcolor="#58a6ff",
                        highlightbackground=C["border"])
    ent_user.pack(fill="x", pady=(2,12), ipady=8)
    ent_user.insert(0, "mamoudou.ndao")

    tk.Label(card, text="Mot de passe", font=("Segoe UI", 9),
             bg=C["panel"], fg=C["muted"]).pack(anchor="w")
    ent_pass = tk.Entry(card, font=("Segoe UI", 11), bg=C["card"], fg=C["text"],
                        insertbackground=C["text"], relief="flat", show="•",
                        highlightthickness=1, highlightcolor="#58a6ff",
                        highlightbackground=C["border"])
    ent_pass.pack(fill="x", pady=(2,20), ipady=8)
    ent_pass.insert(0, "victime8900")

    lbl_statut = tk.Label(card, text="", font=("Segoe UI", 9),
                          bg=C["panel"], fg=C["danger"])
    lbl_statut.pack()

    def faire_login():
        username = ent_user.get().strip()
        password = ent_pass.get().strip()
        if not username or not password:
            lbl_statut.config(text="⚠️ Remplissez tous les champs.")
            return
        lbl_statut.config(text="⏳ Connexion en cours...", fg="#58a6ff")
        root.update()

        token_data, roles, infos, erreur = login_keycloak(username, password)
        if token_data is None:
            # Mode secours si Keycloak est injoignable — comptes de démonstration uniquement
            if erreur and "Impossible de contacter" in erreur:
                roles_test = {
                    "mamoudou.ndao":  ["victime"],
                    "vieux.cisse":    ["assistant"],
                    "babacar.diop":   ["assureur"],
                    "ibrahima.camara":["administrateur"],
                }
                roles = roles_test.get(username, [])
                infos = {}
                if roles:
                    token_data = True  # marque la connexion comme réussie en mode secours
            if not token_data:
                lbl_statut.config(text=f"❌ {erreur or 'Identifiants incorrects.'}", fg=C["danger"])
                return

        # Nouveau compte Keycloak sans profil MySQL correspondant → provisionnement
        if obtenir_id_acteur(username, infos.get("email")) is None:
            afficher_completer_profil(root, username, roles, infos)
            return

        if "administrateur" in roles:
            afficher_admin(root, username)
        elif "assistant" in roles:
            afficher_assistant(root, username)
        elif "assureur" in roles:
            afficher_assureur(root, username)
        elif "victime" in roles:
            afficher_victime(root, username)
        else:
            lbl_statut.config(text="❌ Rôle non reconnu.", fg=C["danger"])

    btn_login = tk.Button(card, text="Se connecter →", command=faire_login,
                          bg="#238636", fg="white", font=("Segoe UI", 11, "bold"),
                          relief="flat", cursor="hand2", pady=10)
    btn_login.pack(fill="x", pady=(10,0))
    root.bind("<Return>", lambda e: faire_login())

    # ---- Séparateur "ou" ----
    sep_frame = tk.Frame(card, bg=C["panel"])
    sep_frame.pack(fill="x", pady=(18,10))
    tk.Frame(sep_frame, bg=C["border"], height=1).pack(side="left", fill="x", expand=True, pady=8)
    tk.Label(sep_frame, text="  ou  ", bg=C["panel"], fg=C["muted"], font=("Segoe UI", 8)).pack(side="left")
    tk.Frame(sep_frame, bg=C["border"], height=1).pack(side="left", fill="x", expand=True, pady=8)

    btn_inscription = tk.Button(card, text="📝 Créer un compte", command=lambda: afficher_inscription(root),
                          bg=C["card"], fg="#58a6ff", font=("Segoe UI", 10, "bold"),
                          relief="flat", cursor="hand2", pady=9,
                          highlightthickness=1, highlightbackground="#58a6ff")
    btn_inscription.pack(fill="x")

    tk.Label(root, text="USSEIN — Licence 3 Informatique 2024-2025",
             font=("Segoe UI", 8), bg=C["bg"], fg=C["muted"]).pack(side="bottom", pady=10)

# ============================================================
# INTERFACE VICTIME
# ============================================================
def afficher_inscription(root):
    """
    Écran d'inscription 100% natif Tkinter — crée le compte directement
    via l'API Admin Keycloak (aucun navigateur nécessaire), puis crée le
    profil correspondant en base MySQL en une seule étape.
    """
    clear_window(root)
    root.title("Système CIMA — Créer un compte")
    root.geometry("500x820")
    root.configure(bg=C["bg"])
    root.resizable(False, False)

    canvas_insc = tk.Canvas(root, bg=C["bg"], highlightthickness=0)
    scrollbar_insc = ttk.Scrollbar(root, orient="vertical", command=canvas_insc.yview)
    inner = tk.Frame(canvas_insc, bg=C["bg"])
    inner.bind("<Configure>", lambda e: canvas_insc.configure(scrollregion=canvas_insc.bbox("all")))
    canvas_window = canvas_insc.create_window((0, 0), window=inner, anchor="nw")
    canvas_insc.configure(yscrollcommand=scrollbar_insc.set)
    canvas_insc.bind("<Configure>", lambda e: canvas_insc.itemconfig(canvas_window, width=e.width))
    canvas_insc.pack(side="left", fill="both", expand=True)
    scrollbar_insc.pack(side="right", fill="y")

    def _wheel(e): canvas_insc.yview_scroll(int(-1*(e.delta/120)), "units")
    def _wheel_up(e): canvas_insc.yview_scroll(-2, "units")
    def _wheel_down(e): canvas_insc.yview_scroll(2, "units")
    canvas_insc.bind("<Enter>", lambda e: (canvas_insc.bind_all("<MouseWheel>", _wheel),
                                             canvas_insc.bind_all("<Button-4>", _wheel_up),
                                             canvas_insc.bind_all("<Button-5>", _wheel_down)))
    canvas_insc.bind("<Leave>", lambda e: (canvas_insc.unbind_all("<MouseWheel>"),
                                             canvas_insc.unbind_all("<Button-4>"),
                                             canvas_insc.unbind_all("<Button-5>")))

    tk.Frame(inner, bg=C["bg"], height=20).pack()
    tk.Label(inner, text="📝", font=("Segoe UI", 36), bg=C["bg"]).pack()
    tk.Label(inner, text="Créer un compte", font=("Segoe UI", 18, "bold"),
             bg=C["bg"], fg=C["text"]).pack()
    tk.Label(inner, text="Rejoignez le système CIMA en quelques secondes",
             font=("Segoe UI", 9), bg=C["bg"], fg=C["muted"]).pack(pady=(2,12))

    card = tk.Frame(inner, bg=C["panel"], padx=30, pady=25)
    card.pack(padx=30, fill="x")

    champs_insc = {}
    for label in ["Nom", "Prénom", "Email", "Téléphone", "Nom d'utilisateur"]:
        tk.Label(card, text=label, font=("Segoe UI", 9),
                 bg=C["panel"], fg=C["muted"]).pack(anchor="w", pady=(6,0))
        e = tk.Entry(card, font=("Segoe UI", 10), bg=C["card"], fg=C["text"],
                     insertbackground=C["text"], relief="flat",
                     highlightthickness=1, highlightcolor="#58a6ff",
                     highlightbackground=C["border"])
        e.pack(fill="x", pady=(2,0), ipady=6)
        champs_insc[label] = e

    tk.Label(card, text="Mot de passe", font=("Segoe UI", 9),
             bg=C["panel"], fg=C["muted"]).pack(anchor="w", pady=(6,0))
    ent_pwd = tk.Entry(card, font=("Segoe UI", 10), bg=C["card"], fg=C["text"],
                 insertbackground=C["text"], relief="flat", show="•",
                 highlightthickness=1, highlightcolor="#58a6ff",
                 highlightbackground=C["border"])
    ent_pwd.pack(fill="x", pady=(2,0), ipady=6)

    tk.Label(card, text="Confirmer le mot de passe", font=("Segoe UI", 9),
             bg=C["panel"], fg=C["muted"]).pack(anchor="w", pady=(6,0))
    ent_pwd2 = tk.Entry(card, font=("Segoe UI", 10), bg=C["card"], fg=C["text"],
                 insertbackground=C["text"], relief="flat", show="•",
                 highlightthickness=1, highlightcolor="#58a6ff",
                 highlightbackground=C["border"])
    ent_pwd2.pack(fill="x", pady=(2,0), ipady=6)

    tk.Label(card, text="Je m'inscris en tant que :", font=("Segoe UI", 9, "bold"),
             bg=C["panel"], fg=C["text"]).pack(anchor="w", pady=(14,4))
    role_var = tk.StringVar(value="victime")
    for valeur, libelle in [
        ("victime",   "🏥 Victime — j'ai été impliqué(e) dans un accident"),
        ("assistant", "📋 Assistant — je gère des dossiers de sinistres"),
        ("assureur",  "🏦 Assureur — je représente une compagnie d'assurance"),
    ]:
        tk.Radiobutton(card, text=libelle, variable=role_var, value=valeur,
                       bg=C["panel"], fg=C["text"], selectcolor=C["card"],
                       activebackground=C["panel"], activeforeground=C["text"],
                       font=("Segoe UI", 9), anchor="w",
                       highlightthickness=0).pack(fill="x", pady=2)

    tk.Label(card, text="Nom de la compagnie (si Assureur)", font=("Segoe UI", 9),
             bg=C["panel"], fg=C["muted"]).pack(anchor="w", pady=(10,0))
    ent_compagnie = tk.Entry(card, font=("Segoe UI", 10), bg=C["card"], fg=C["text"],
                 insertbackground=C["text"], relief="flat",
                 highlightthickness=1, highlightcolor="#58a6ff",
                 highlightbackground=C["border"])
    ent_compagnie.pack(fill="x", pady=(2,0), ipady=6)

    tk.Label(card, text="Zone d'intervention (si Assistant)", font=("Segoe UI", 9),
             bg=C["panel"], fg=C["muted"]).pack(anchor="w", pady=(10,0))
    ent_zone = tk.Entry(card, font=("Segoe UI", 10), bg=C["card"], fg=C["text"],
                 insertbackground=C["text"], relief="flat",
                 highlightthickness=1, highlightcolor="#58a6ff",
                 highlightbackground=C["border"])
    ent_zone.pack(fill="x", pady=(2,0), ipady=6)

    lbl_statut_insc = tk.Label(card, text="", font=("Segoe UI", 9),
                                bg=C["panel"], fg=C["danger"], wraplength=400, justify="left")
    lbl_statut_insc.pack(pady=(10,0))

    def valider_inscription():
        vals = {k: v.get().strip() for k, v in champs_insc.items()}
        pwd, pwd2 = ent_pwd.get(), ent_pwd2.get()
        role_choisi = role_var.get()

        if not all(vals.values()) or not pwd or not pwd2:
            lbl_statut_insc.config(text="⚠️ Remplissez tous les champs."); return
        if pwd != pwd2:
            lbl_statut_insc.config(text="⚠️ Les mots de passe ne correspondent pas."); return
        if len(pwd) < 6:
            lbl_statut_insc.config(text="⚠️ Le mot de passe doit contenir au moins 6 caractères."); return
        if role_choisi == "assureur" and not ent_compagnie.get().strip():
            lbl_statut_insc.config(text="⚠️ Indiquez le nom de votre compagnie d'assurance."); return
        if role_choisi == "assistant" and not ent_zone.get().strip():
            lbl_statut_insc.config(text="⚠️ Indiquez votre zone d'intervention."); return

        lbl_statut_insc.config(text="⏳ Création du compte en cours...", fg="#58a6ff")
        root.update()

        username = vals["Nom d'utilisateur"]
        succes, resultat = creer_utilisateur_keycloak(
            username, vals["Email"], pwd, vals["Prénom"], vals["Nom"])
        if not succes:
            lbl_statut_insc.config(text=f"❌ {resultat}", fg=C["danger"])
            return

        # Crée immédiatement le profil MySQL correspondant
        db = connecter_db()
        if not db:
            lbl_statut_insc.config(text="❌ Compte Keycloak créé mais la base de données est injoignable.", fg=C["danger"])
            return
        try:
            c = db.cursor()
            c.execute("""INSERT INTO acteur (nom, prenom, email, username, telephone, mot_de_passe, role)
                         VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (vals["Nom"], vals["Prénom"], vals["Email"], username, vals["Téléphone"],
                 "keycloak_managed", role_choisi))
            db.commit()
            id_acteur = c.lastrowid
            if role_choisi == "victime":
                c.execute("INSERT INTO victime (id_acteur) VALUES (%s)", (id_acteur,))
            elif role_choisi == "assistant":
                c.execute("""INSERT INTO assistant (id_acteur, zone_intervention)
                             VALUES (%s, %s)""", (id_acteur, ent_zone.get().strip()))
            elif role_choisi == "assureur":
                c.execute("""INSERT INTO assureur (id_acteur, nom_compagnie)
                             VALUES (%s, %s)""", (id_acteur, ent_compagnie.get().strip()))
            db.commit()
            messagebox.showinfo("✅ Compte créé !",
                f"Bienvenue {vals['Prénom']} {vals['Nom']} !\n\n"
                f"📧 Un email de vérification a été envoyé à {vals['Email']}.\n"
                f"Vous devez cliquer sur le lien reçu avant de pouvoir vous connecter.")
            afficher_login(root)
        except Error as e:
            lbl_statut_insc.config(text=f"❌ Compte Keycloak créé mais erreur base de données : {e}", fg=C["danger"])
        finally:
            db.close()

    tk.Button(card, text="✅ Créer mon compte", command=valider_inscription,
              bg="#238636", fg="white", font=("Segoe UI", 11, "bold"),
              relief="flat", cursor="hand2", pady=10).pack(fill="x", pady=(15,0))

    tk.Button(inner, text="← Retour à la connexion", command=lambda: afficher_login(root),
              bg=C["bg"], fg=C["muted"], font=("Segoe UI", 9),
              relief="flat", cursor="hand2").pack(pady=20)

def afficher_completer_profil(root, username, roles, infos):
    """
    Affiché lors du 1er login d'un compte Keycloak nouvellement inscrit
    (auto-inscription) qui n'a pas encore de profil dans la base MySQL.
    L'utilisateur choisit lui-même son type de compte (Victime, Assistant
    ou Assureur — l'inscription en Administrateur n'est jamais proposée).
    """
    clear_window(root)
    root.title("Système CIMA — Compléter mon profil")
    root.geometry("480x680")
    root.configure(bg=C["bg"])
    root.resizable(False, False)

    tk.Frame(root, bg=C["bg"], height=25).pack()
    tk.Label(root, text="👋", font=("Segoe UI", 40), bg=C["bg"]).pack()
    prenom_kc = infos.get("prenom", "").strip()
    nom_kc = infos.get("nom", "").strip()
    titre_bienvenue = f"Bienvenue {prenom_kc} {nom_kc} !".strip() if (prenom_kc or nom_kc) else "Bienvenue !"
    titre_bienvenue = " ".join(titre_bienvenue.split())  # nettoie les espaces multiples
    tk.Label(root, text=titre_bienvenue, font=("Segoe UI", 18, "bold"),
             bg=C["bg"], fg=C["text"]).pack()
    tk.Label(root, text="Complétez votre profil pour accéder au système CIMA",
             font=("Segoe UI", 9), bg=C["bg"], fg=C["muted"]).pack(pady=(2,12))

    card = tk.Frame(root, bg=C["panel"], padx=30, pady=25)
    card.pack(padx=40, fill="x")

    champs_profil = {}
    for label, valeur_defaut in [
        ("Nom", infos.get("nom", "")),
        ("Prénom", infos.get("prenom", "")),
        ("Email", infos.get("email", "")),
        ("Téléphone", ""),
    ]:
        tk.Label(card, text=label, font=("Segoe UI", 9),
                 bg=C["panel"], fg=C["muted"]).pack(anchor="w", pady=(6,0))
        e = tk.Entry(card, font=("Segoe UI", 10), bg=C["card"], fg=C["text"],
                     insertbackground=C["text"], relief="flat",
                     highlightthickness=1, highlightcolor="#58a6ff",
                     highlightbackground=C["border"])
        e.pack(fill="x", pady=(2,0), ipady=6)
        e.insert(0, valeur_defaut)
        champs_profil[label] = e

    # Sélection du rôle par l'utilisateur — jamais "administrateur" en auto-inscription
    tk.Label(card, text="Je m'inscris en tant que :", font=("Segoe UI", 9, "bold"),
             bg=C["panel"], fg=C["text"]).pack(anchor="w", pady=(14,4))
    role_var = tk.StringVar(value="victime")
    roles_disponibles = [
        ("victime",   "🏥 Victime — j'ai été impliqué(e) dans un accident"),
        ("assistant", "📋 Assistant — je gère des dossiers de sinistres"),
        ("assureur",  "🏦 Assureur — je représente une compagnie d'assurance"),
    ]
    for valeur, libelle in roles_disponibles:
        tk.Radiobutton(card, text=libelle, variable=role_var, value=valeur,
                       bg=C["panel"], fg=C["text"], selectcolor=C["card"],
                       activebackground=C["panel"], activeforeground=C["text"],
                       font=("Segoe UI", 9), anchor="w",
                       highlightthickness=0).pack(fill="x", pady=2)

    # Champ complémentaire, affiché uniquement si "assureur" est choisi
    tk.Label(card, text="Nom de la compagnie (si Assureur)", font=("Segoe UI", 9),
             bg=C["panel"], fg=C["muted"]).pack(anchor="w", pady=(10,0))
    ent_compagnie = tk.Entry(card, font=("Segoe UI", 10), bg=C["card"], fg=C["text"],
                 insertbackground=C["text"], relief="flat",
                 highlightthickness=1, highlightcolor="#58a6ff",
                 highlightbackground=C["border"])
    ent_compagnie.pack(fill="x", pady=(2,0), ipady=6)

    # Champ complémentaire, affiché uniquement si "assistant" est choisi
    tk.Label(card, text="Zone d'intervention (si Assistant)", font=("Segoe UI", 9),
             bg=C["panel"], fg=C["muted"]).pack(anchor="w", pady=(10,0))
    ent_zone = tk.Entry(card, font=("Segoe UI", 10), bg=C["card"], fg=C["text"],
                 insertbackground=C["text"], relief="flat",
                 highlightthickness=1, highlightcolor="#58a6ff",
                 highlightbackground=C["border"])
    ent_zone.pack(fill="x", pady=(2,0), ipady=6)

    lbl_statut_profil = tk.Label(card, text="", font=("Segoe UI", 9),
                                  bg=C["panel"], fg=C["danger"], wraplength=380, justify="left")
    lbl_statut_profil.pack(pady=(10,0))

    def valider_profil():
        vals = {k: v.get().strip() for k, v in champs_profil.items()}
        role_choisi = role_var.get()
        if not all(vals.values()):
            lbl_statut_profil.config(text="⚠️ Remplissez tous les champs."); return
        if role_choisi == "assureur" and not ent_compagnie.get().strip():
            lbl_statut_profil.config(text="⚠️ Indiquez le nom de votre compagnie d'assurance."); return
        if role_choisi == "assistant" and not ent_zone.get().strip():
            lbl_statut_profil.config(text="⚠️ Indiquez votre zone d'intervention."); return
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            c.execute("""INSERT INTO acteur (nom, prenom, email, username, telephone, mot_de_passe, role)
                         VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (vals["Nom"], vals["Prénom"], vals["Email"], username, vals["Téléphone"],
                 "keycloak_managed", role_choisi))
            db.commit()
            id_acteur = c.lastrowid
            if role_choisi == "victime":
                c.execute("INSERT INTO victime (id_acteur) VALUES (%s)", (id_acteur,))
            elif role_choisi == "assistant":
                c.execute("""INSERT INTO assistant (id_acteur, zone_intervention)
                             VALUES (%s, %s)""", (id_acteur, ent_zone.get().strip()))
            elif role_choisi == "assureur":
                c.execute("""INSERT INTO assureur (id_acteur, nom_compagnie)
                             VALUES (%s, %s)""", (id_acteur, ent_compagnie.get().strip()))
            db.commit()
            messagebox.showinfo("✅ Bienvenue !", "Votre profil a été créé avec succès.")
            if role_choisi == "assistant":
                afficher_assistant(root, username)
            elif role_choisi == "assureur":
                afficher_assureur(root, username)
            else:
                afficher_victime(root, username)
        except Error as e:
            lbl_statut_profil.config(text=f"❌ Erreur : {e}")
        finally:
            db.close()

    tk.Button(card, text="✅ Valider et continuer →", command=valider_profil,
              bg="#238636", fg="white", font=("Segoe UI", 11, "bold"),
              relief="flat", cursor="hand2", pady=10).pack(fill="x", pady=(15,0))

    tk.Button(root, text="← Annuler", command=lambda: afficher_login(root),
              bg=C["bg"], fg=C["muted"], font=("Segoe UI", 9),
              relief="flat", cursor="hand2").pack(pady=10)

def afficher_victime(root, username):
    clear_window(root)
    root.title("CIMA — Espace Victime")
    root.geometry("1050x720")
    root.configure(bg=C["bg"])
    root.resizable(True, True)

    couleur = C["victime"]
    id_victime = obtenir_id_acteur(username)

    h = tk.Frame(root, bg=couleur, height=60)
    h.pack(fill="x")
    h.pack_propagate(False)
    tk.Label(h, text="🏥  CIMA — Espace Victime",
             font=("Segoe UI", 14, "bold"), bg=couleur, fg="white").pack(side="left", padx=20, pady=15)
    tk.Label(h, text=f"👤 {username}", font=("Segoe UI", 10),
             bg=couleur, fg="white").pack(side="right", padx=20)
    tk.Button(h, text="🚪 Déconnexion",
              command=lambda: afficher_login(root),
              bg="#1a6b29", fg="white", font=("Segoe UI", 9, "bold"),
              relief="flat", cursor="hand2", padx=10).pack(side="right", padx=10, pady=12)

    stats_frame = tk.Frame(root, bg=C["bg"])
    stats_frame.pack(fill="x", padx=15, pady=10)
    db = connecter_db()
    nb_dossiers = nb_docs = nb_notifs = 0
    if db and id_victime:
        c = db.cursor()
        c.execute("SELECT COUNT(*) FROM dossier WHERE id_victime=%s", (id_victime,)); nb_dossiers = c.fetchone()[0]
        c.execute("""SELECT COUNT(*) FROM document doc JOIN dossier d ON doc.id_dossier=d.id_dossier
                     WHERE d.id_victime=%s""", (id_victime,)); nb_docs = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM notification WHERE id_acteur=%s", (id_victime,)); nb_notifs = c.fetchone()[0]
        db.close()
    elif db:
        db.close()
    stat_card(stats_frame, "Mes Dossiers",     str(nb_dossiers), couleur)
    stat_card(stats_frame, "Documents",        str(nb_docs),     "#1f6feb")
    stat_card(stats_frame, "Notifications",    str(nb_notifs),   "#8957e5")

    if not id_victime:
        tk.Label(root, text="⚠️ Impossible d'identifier votre profil. Contactez l'administrateur.",
                 bg=C["bg"], fg=C["danger"], font=("Segoe UI", 10, "bold")).pack(pady=10)

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=15, pady=5)

    ong1 = tk.Frame(nb, bg=C["card"])
    nb.add(ong1, text="  📁 Mes Dossiers  ")
    tbl_dos = tableau(ong1, ("N° Dossier","Statut","Assistant","Date création","Date clôture"),
                      [130, 150, 150, 140, 140])

    def charger_dossiers_victime():
        for r in tbl_dos.get_children(): tbl_dos.delete(r)
        if not id_victime: return
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            c.execute("""
                SELECT d.numero_dossier, d.statut,
                       CONCAT(a.prenom,' ',a.nom),
                       d.date_creation, IFNULL(d.date_cloture,'—')
                FROM dossier d
                JOIN acteur a ON d.id_assistant=a.id_acteur
                WHERE d.id_victime=%s
                ORDER BY d.id_dossier ASC
            """, (id_victime,))
            couleurs_statut = {
                "REJETE": "#3d1a1a", "VALIDE": "#1a3d2b", "PAYE": "#1a2d3d",
                "CLOTURE": "#2a2a2a", "SOUMIS": "#2d3a1e", "EN_EVALUATION": "#2e2a10",
            }
            for i, l in enumerate(c.fetchall()):
                l = formater_ligne(l)
                statut = l[1]
                tag = f"stat_{statut}"
                tbl_dos.tag_configure(tag, background=couleurs_statut.get(statut, "#1c2128"))
                tbl_dos.insert("","end",values=l,tags=(tag,))
        finally:
            db.close()

    def contester_rejet():
        sel = tbl_dos.selection()
        if not sel:
            messagebox.showwarning("Aucune sélection", "Sélectionnez un dossier dans la liste."); return
        vals = tbl_dos.item(sel[0])["values"]
        num_dossier, statut = vals[0], vals[1]
        if statut != "REJETE":
            messagebox.showinfo("Non applicable", "Vous ne pouvez contester que les dossiers au statut REJETE."); return
        motif = simpledialog.askstring("❌ Contester le rejet",
            f"Dossier {num_dossier} — Statut : REJETÉ\n\nExpliquez pourquoi vous contestez ce rejet :",
            parent=root)
        if not motif or not motif.strip():
            return
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            c.execute("SELECT id_dossier, id_assistant FROM dossier WHERE numero_dossier=%s", (num_dossier,))
            row = c.fetchone()
            if row:
                envoyer_notification_auto(row[1], row[0],
                    f"🔄 DEMANDE DE RECOURS — La victime conteste le rejet du dossier {num_dossier}.\nMotif : {motif.strip()}")
            messagebox.showinfo("Contestation envoyée",
                "Votre contestation a été transmise à votre assistant.\n🔔 Il va examiner la possibilité d'un recours auprès de l'assureur.")
        finally:
            db.close()

    barre1 = tk.Frame(ong1, bg=C["card"])
    barre1.pack(fill="x", padx=10, pady=5)
    btn(barre1, "🔃 Actualiser", charger_dossiers_victime, "#1f6feb")
    btn(barre1, "❌ Contester le rejet", contester_rejet, C["danger"])
    charger_dossiers_victime()

    ong2 = tk.Frame(nb, bg=C["card"])
    nb.add(ong2, text="  📄 Mes Documents  ")
    tbl_doc = tableau(ong2, ("Dossier","Type","Statut validation","Date upload"),
                      [130, 180, 150, 150])

    def charger_docs_victime():
        for r in tbl_doc.get_children(): tbl_doc.delete(r)
        if not id_victime: return
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            c.execute("""
                SELECT d.numero_dossier, IF(doc.type_document='PV_POLICE','Procès verbal (PV)',doc.type_document),
                       doc.statut_validation, doc.date_upload
                FROM document doc
                JOIN dossier d ON doc.id_dossier=d.id_dossier
                WHERE d.id_victime=%s
                ORDER BY doc.id_document ASC
            """, (id_victime,))
            for i, l in enumerate(c.fetchall()):
                l = formater_ligne(l)
                tbl_doc.insert("","end",values=l,tags=("pair" if i%2==0 else "impair",))
        finally:
            db.close()

    barre2 = tk.Frame(ong2, bg=C["card"])
    barre2.pack(fill="x", padx=10, pady=5)
    btn(barre2, "🔃 Actualiser", charger_docs_victime, "#1f6feb")
    charger_docs_victime()

    ong3 = tk.Frame(nb, bg=C["card"])
    nb.add(ong3, text="  🔔 Notifications  ")
    tbl_notif = tableau(ong3, ("Dossier","Message","Statut","Date envoi"),
                        [120, 400, 100, 150])

    def charger_notifs():
        for r in tbl_notif.get_children(): tbl_notif.delete(r)
        if not id_victime: return
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            c.execute("""
                SELECT d.numero_dossier, n.message, n.statut_envoi, n.date_envoi
                FROM notification n
                JOIN dossier d ON n.id_dossier=d.id_dossier
                WHERE n.id_acteur=%s
                ORDER BY n.id_notification DESC
            """, (id_victime,))
            for i, l in enumerate(c.fetchall()):
                l = formater_ligne(l)
                tbl_notif.insert("","end",values=l,tags=("pair" if i%2==0 else "impair",))
        finally:
            db.close()

    barre3 = tk.Frame(ong3, bg=C["card"])
    barre3.pack(fill="x", padx=10, pady=5)
    btn(barre3, "🔃 Actualiser", charger_notifs, "#1f6feb")
    charger_notifs()

    # ---- Onglet Contacts : Mes Assistants ----
    ong4 = tk.Frame(nb, bg=C["card"])
    nb.add(ong4, text="  📞 Mes Assistants  ")
    ent_rech_ass_vic = barre_recherche(ong4, "(par nom ou zone d'intervention)")
    tbl_ass_vic = tableau(ong4, ("Nom","Prénom","📧 Email","📱 Téléphone","Zone d'intervention"), [130,130,220,130,180])

    def charger_assistants_victime(filtre=""):
        for r in tbl_ass_vic.get_children(): tbl_ass_vic.delete(r)
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            if filtre:
                c.execute("""SELECT a.nom, a.prenom, a.email, a.telephone, IFNULL(s.zone_intervention,'—')
                            FROM acteur a JOIN assistant s ON a.id_acteur=s.id_acteur
                            WHERE a.role='assistant' AND (a.nom LIKE %s OR a.prenom LIKE %s OR s.zone_intervention LIKE %s)
                            ORDER BY a.id_acteur ASC""",
                            (f"%{filtre}%", f"%{filtre}%", f"%{filtre}%"))
            else:
                c.execute("""SELECT a.nom, a.prenom, a.email, a.telephone, IFNULL(s.zone_intervention,'—')
                            FROM acteur a JOIN assistant s ON a.id_acteur=s.id_acteur
                            WHERE a.role='assistant' ORDER BY a.id_acteur ASC""")
            for i, l in enumerate(c.fetchall()):
                l = formater_ligne(l)
                tbl_ass_vic.insert("","end",values=l,tags=("pair" if i%2==0 else "impair",))
        finally:
            db.close()

    ent_rech_ass_vic.bind("<KeyRelease>", lambda e: charger_assistants_victime(ent_rech_ass_vic.get().strip()))

    barre4 = tk.Frame(ong4, bg=C["card"])
    barre4.pack(fill="x", padx=10, pady=5)
    btn(barre4, "🔃 Actualiser", charger_assistants_victime, "#1f6feb")
    charger_assistants_victime()

    tk.Label(ong4, text="💡 Ce sont les assistants susceptibles de traiter votre dossier. Contactez-les par email ou téléphone si besoin.",
             bg=C["card"], fg=C["muted"], font=("Segoe UI", 8), wraplength=900, justify="left").pack(anchor="w", padx=10, pady=(0,8))

    # ---- Onglet Mes Paiements (confirmer / contester) ----
    ong5 = tk.Frame(nb, bg=C["card"])
    nb.add(ong5, text="  💰 Mes Paiements  ")
    tbl_pai_vic = tableau(ong5, ("ID Paiement","Type","Dossier","Montant payé","Provisions déduites","Mode","Statut","Date paiement"),
                          [80, 100, 110, 130, 140, 110, 120, 120])

    def charger_paiements_victime():
        for r in tbl_pai_vic.get_children(): tbl_pai_vic.delete(r)
        if not id_victime: return
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            c.execute("""
                SELECT p.id_paiement, p.type_paiement, d.numero_dossier,
                       CONCAT(FORMAT(p.montant_paye,0),' FCFA'),
                       IF(p.montant_provisions_deduites>0, CONCAT('−',FORMAT(p.montant_provisions_deduites,0),' FCFA'), '—'),
                       p.mode_paiement, p.statut_confirmation, p.date_paiement
                FROM paiement p
                JOIN decision de ON p.id_decision = de.id_decision
                JOIN demande_indemnisation di ON de.id_demande = di.id_demande
                JOIN dossier d ON di.id_dossier = d.id_dossier
                WHERE d.id_victime = %s

                UNION

                SELECT p.id_paiement, p.type_paiement, d.numero_dossier,
                       CONCAT(FORMAT(p.montant_paye,0),' FCFA'), '—',
                       p.mode_paiement, p.statut_confirmation, p.date_paiement
                FROM paiement p
                JOIN dossier d ON p.id_dossier = d.id_dossier
                WHERE d.id_victime = %s AND p.type_paiement = 'PROVISION'

                ORDER BY id_paiement DESC
            """, (id_victime, id_victime))
            for i, l in enumerate(c.fetchall()):
                l = formater_ligne(l)
                statut = l[6]
                couleurs_statut = {
                    "EN_ATTENTE": "#2d3a1e",
                    "CONFIRME": "#1a3d2b",
                    "CONTESTE": "#3d1a1a",
                    "TRANSMIS_ASSUREUR": "#2e2a10",
                }
                tag = f"stat_{statut}"
                tbl_pai_vic.tag_configure(tag, background=couleurs_statut.get(statut, "#1c2128"))
                tbl_pai_vic.insert("","end",values=l,tags=(tag,))
        finally:
            db.close()

    def confirmer_paiement():
        sel = tbl_pai_vic.selection()
        if not sel:
            messagebox.showwarning("Aucune sélection", "Sélectionnez un paiement dans la liste."); return
        vals = tbl_pai_vic.item(sel[0])["values"]
        id_paiement, type_pai, num_dossier, montant, provisions_ded, mode, statut, date_pai = vals
        if type_pai == "PROVISION":
            messagebox.showinfo("Acompte", "Ceci est une provision (acompte). Seul le paiement définitif nécessite une confirmation."); return
        if statut == "CONFIRME":
            messagebox.showinfo("Déjà confirmé", "Ce paiement a déjà été confirmé."); return
        if not messagebox.askyesno("✅ Confirmer réception",
                f"Confirmez-vous avoir reçu le paiement de {montant} pour le dossier {num_dossier} ?"):
            return
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            c.execute("""UPDATE paiement SET confirmation_victime=1, statut_confirmation='CONFIRME',
                         date_confirmation=NOW() WHERE id_paiement=%s""", (id_paiement,))
            db.commit()
            c.execute("""SELECT d.id_dossier, d.id_assistant FROM paiement p
                         JOIN decision de ON p.id_decision=de.id_decision
                         JOIN demande_indemnisation di ON de.id_demande=di.id_demande
                         JOIN dossier d ON di.id_dossier=d.id_dossier
                         WHERE p.id_paiement=%s""", (id_paiement,))
            row = c.fetchone()
            if row:
                envoyer_notification_auto(row[1], row[0],
                    f"✅ La victime a confirmé la réception du paiement de {montant} pour le dossier {num_dossier}.")
            messagebox.showinfo("✅ Confirmé", "Merci ! Votre confirmation a été enregistrée.\n🔔 L'assistant a été notifié.")
            charger_paiements_victime()
        except Error as e:
            messagebox.showerror("Erreur", str(e))
        finally:
            db.close()

    def contester_paiement():
        sel = tbl_pai_vic.selection()
        if not sel:
            messagebox.showwarning("Aucune sélection", "Sélectionnez un paiement dans la liste."); return
        vals = tbl_pai_vic.item(sel[0])["values"]
        id_paiement, type_pai, num_dossier, montant, provisions_ded, mode, statut, date_pai = vals
        if type_pai == "PROVISION":
            messagebox.showinfo("Acompte", "Ceci est une provision (acompte). Seul le paiement définitif peut être contesté."); return
        if statut == "CONFIRME":
            messagebox.showinfo("Déjà confirmé", "Ce paiement a déjà été confirmé, il ne peut plus être contesté."); return
        motif = simpledialog.askstring("❌ Contester le montant",
            f"Dossier {num_dossier} — Montant payé : {montant}\n\nExpliquez pourquoi ce montant ne vous convient pas :",
            parent=root)
        if not motif or not motif.strip():
            return
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            c.execute("""UPDATE paiement SET statut_confirmation='CONTESTE', commentaire_victime=%s
                         WHERE id_paiement=%s""", (motif.strip(), id_paiement))
            db.commit()
            c.execute("""SELECT d.id_dossier, d.id_assistant FROM paiement p
                         JOIN decision de ON p.id_decision=de.id_decision
                         JOIN demande_indemnisation di ON de.id_demande=di.id_demande
                         JOIN dossier d ON di.id_dossier=d.id_dossier
                         WHERE p.id_paiement=%s""", (id_paiement,))
            row = c.fetchone()
            if row:
                envoyer_notification_auto(row[1], row[0],
                    f"⚠️ La victime CONTESTE le paiement de {montant} pour le dossier {num_dossier}.\nMotif : {motif.strip()}")
            messagebox.showinfo("Contestation envoyée",
                "Votre contestation a été enregistrée.\n🔔 L'assistant a été notifié et va transmettre votre message à l'assureur.")
            charger_paiements_victime()
        except Error as e:
            messagebox.showerror("Erreur", str(e))
        finally:
            db.close()

    barre5 = tk.Frame(ong5, bg=C["card"])
    barre5.pack(fill="x", padx=10, pady=5)
    btn(barre5, "🔃 Actualiser", charger_paiements_victime, "#1f6feb")
    btn(barre5, "✅ Confirmer réception", confirmer_paiement, "#3fb950")
    btn(barre5, "❌ Contester le montant", contester_paiement, C["danger"])
    charger_paiements_victime()

    tk.Label(ong5, text="💡 Statuts : EN_ATTENTE (à traiter) · CONFIRME (accepté) · CONTESTE (motif envoyé à l'assistant) · TRANSMIS_ASSUREUR (réexamen en cours).",
             bg=C["card"], fg=C["muted"], font=("Segoe UI", 8), wraplength=900, justify="left").pack(anchor="w", padx=10, pady=(0,8))


# ============================================================
# INTERFACE ASSISTANT
# ============================================================
def afficher_assistant(root, username):
    clear_window(root)
    root.title("CIMA — Espace Assistant")
    root.geometry("1200x750")
    root.configure(bg=C["bg"])
    root.resizable(True, True)
    root.minsize(1000, 600)

    couleur = C["assistant"]
    id_assistant_connecte = obtenir_id_acteur(username)

    h = tk.Frame(root, bg=couleur, height=60)
    h.pack(fill="x")
    h.pack_propagate(False)
    tk.Label(h, text="📋  CIMA — Espace Assistant",
             font=("Segoe UI", 14, "bold"), bg=couleur, fg="white").pack(side="left", padx=20, pady=15)
    tk.Label(h, text=f"👤 {username}", font=("Segoe UI", 10),
             bg=couleur, fg="white").pack(side="right", padx=20)
    tk.Button(h, text="🚪 Déconnexion",
              command=lambda: afficher_login(root),
              bg="#164e8e", fg="white", font=("Segoe UI", 9, "bold"),
              relief="flat", cursor="hand2", padx=10).pack(side="right", padx=10, pady=12)

    cadre = tk.Frame(root, bg=C["bg"])
    cadre.pack(fill="both", expand=True, padx=10, pady=8)

    # ---- Panneau gauche SCROLLABLE ----
    p_g = panneau_scrollable(cadre, largeur=290)

    # Créer accident
    section(p_g, "🚗 1. Enregistrer Accident", "#e3b341")
    ent_date_acc = champ(p_g, "Date accident (AAAA-MM-JJ)")
    ent_date_acc.insert(0, datetime.now().strftime("%Y-%m-%d"))
    ent_lieu_acc = champ(p_g, "Lieu de l'accident")
    ent_pv_acc = champ(p_g, "N° Procès verbal (PV) — code accident")
    ent_pv_acc.insert(0, generer_code_accident())
    ent_desc_acc = champ(p_g, "Description")

    def creer_accident():
        date_acc = ent_date_acc.get().strip()
        lieu = ent_lieu_acc.get().strip()
        pv = ent_pv_acc.get().strip()
        desc = ent_desc_acc.get().strip()
        if not all([date_acc, lieu, pv]):
            messagebox.showwarning("Champs manquants", "Date, lieu et N° PV sont requis."); return
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            c.execute("""INSERT INTO accident (date_accident,lieu,description,numero_pv)
                         VALUES (%s,%s,%s,%s)""", (date_acc, lieu, desc, pv))
            db.commit()
            messagebox.showinfo("✅ Succès", f"Accident enregistré !\nID accident : {c.lastrowid}\n\nUtilisez cet ID pour créer le dossier ci-dessous.")
            charger_accidents()
        except Error as e:
            messagebox.showerror("Erreur", str(e))
        finally:
            db.close()

    tk.Button(p_g, text="🚗 Enregistrer l'accident", command=creer_accident,
              bg="#e3b341", fg="#1c2128", font=("Segoe UI", 9, "bold"),
              relief="flat", cursor="hand2").pack(padx=14, pady=8, fill="x", ipady=6)

    tk.Frame(p_g, bg=C["border"], height=1).pack(fill="x", padx=10, pady=6)

    # Créer dossier
    section(p_g, "➕ 2. Créer un Dossier", couleur)
    ent_num = champ(p_g, "N° Dossier")
    ent_num.insert(0, f"DOS-{datetime.now().strftime('%Y%m%d')}-001")
    ent_id_vic = champ(p_g, "ID Victime")
    ent_id_acc = champ(p_g, "ID Accident")

    def creer_dossier():
        num = ent_num.get().strip()
        id_vic = ent_id_vic.get().strip()
        id_acc = ent_id_acc.get().strip()
        if not all([num, id_vic, id_acc]):
            messagebox.showwarning("Champs manquants", "Remplissez tous les champs."); return
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            c.execute("SELECT id_acteur FROM assistant LIMIT 1")
            ass = c.fetchone()
            if not ass:
                messagebox.showerror("Erreur","Aucun assistant trouvé."); return
            c.execute("""INSERT INTO dossier
                (numero_dossier,id_victime,id_assistant,id_accident,statut)
                VALUES (%s,%s,%s,%s,'EN_CONSTITUTION')""",
                (num, id_vic, ass[0], id_acc))
            db.commit()
            envoyer_notification_auto(int(id_vic), c.lastrowid,
                f"Un dossier ({num}) a été créé pour vous suite à votre accident. Un assistant traite votre demande.")
            messagebox.showinfo("✅ Succès", f"Dossier '{num}' créé !\n🔔 Notification envoyée à la victime.")
            charger_dossiers_ass()
        except Error as e:
            messagebox.showerror("Erreur", str(e))
        finally:
            db.close()

    btn_c = tk.Button(p_g, text="✅ Créer le dossier", command=creer_dossier,
                      bg=couleur, fg="white", font=("Segoe UI", 9, "bold"),
                      relief="flat", cursor="hand2")
    btn_c.pack(padx=14, pady=8, fill="x", ipady=6)

    tk.Frame(p_g, bg=C["border"], height=1).pack(fill="x", padx=10, pady=6)

    # Changer statut
    section(p_g, "🔄 3. Mettre à jour Statut", "#f78166")
    ent_dos_stat = champ(p_g, "N° Dossier")
    tk.Label(p_g, text="Nouveau statut", bg=C["panel"], fg=C["muted"],
             font=("Segoe UI", 8)).pack(anchor="w", padx=14, pady=(4,0))
    statut_var = tk.StringVar(value="DOSSIER_COMPLET")
    ttk.Combobox(p_g, textvariable=statut_var, width=26,
        values=["EN_CONSTITUTION","DOSSIER_COMPLET","SOUMIS",
                "EN_EVALUATION","VALIDE","REJETE","PAYE","CLOTURE"],
        state="readonly").pack(padx=14, pady=2, ipady=4, fill="x")

    def maj_statut():
        num = ent_dos_stat.get().strip()
        if not num:
            messagebox.showwarning("Champ vide","Entrez le numéro du dossier."); return
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            c.execute("SELECT id_dossier, id_victime FROM dossier WHERE numero_dossier=%s", (num,))
            row = c.fetchone()
            if not row:
                messagebox.showerror("Introuvable", f"Dossier '{num}' non trouvé."); return
            c.execute("UPDATE dossier SET statut=%s WHERE numero_dossier=%s",
                      (statut_var.get(), num))
            db.commit()
            envoyer_notification_auto(row[1], row[0],
                f"Le statut de votre dossier ({num}) a changé : {statut_var.get()}.")
            messagebox.showinfo("✅","Statut mis à jour !\n🔔 Notification envoyée à la victime.")
            charger_dossiers_ass()
        finally:
            db.close()

    tk.Button(p_g, text="🔄 Mettre à jour", command=maj_statut,
              bg="#f78166", fg="white", font=("Segoe UI", 9, "bold"),
              relief="flat", cursor="hand2").pack(padx=14, pady=8, fill="x", ipady=6)

    tk.Frame(p_g, bg=C["border"], height=1).pack(fill="x", padx=10, pady=6)

    # Ajouter document
    section(p_g, "📄 4. Ajouter Document", "#3fb950")
    ent_dos_doc = champ(p_g, "ID Dossier")
    tk.Label(p_g, text="Type document", bg=C["panel"], fg=C["muted"],
             font=("Segoe UI", 8)).pack(anchor="w", padx=14, pady=(4,0))
    type_doc_var = tk.StringVar(value="CNI")
    ttk.Combobox(p_g, textvariable=type_doc_var, width=26,
        values=["CNI","PASSEPORT","Procès verbal (PV)","CERTIFICAT_MEDICAL",
                "FACTURE_MEDICALE","PHOTO_ACCIDENT","ATTESTATION_ASSURANCE","RIB","AUTRE"],
        state="readonly").pack(padx=14, pady=2, ipady=4, fill="x")

    ent_chemin = champ(p_g, "Fichier sélectionné")
    ent_chemin.config(state="readonly")

    def parcourir_fichier():
        chemin = filedialog.askopenfilename(
            title="Sélectionner un document",
            initialdir="/mnt/c",
            filetypes=[
                ("Documents", "*.pdf *.jpg *.jpeg *.png *.doc *.docx"),
                ("PDF", "*.pdf"),
                ("Images", "*.jpg *.jpeg *.png"),
                ("Tous les fichiers", "*.*"),
            ]
        )
        if chemin:
            ent_chemin.config(state="normal")
            ent_chemin.delete(0, tk.END)
            ent_chemin.insert(0, chemin)
            ent_chemin.config(state="readonly")

    tk.Button(p_g, text="📂 Parcourir...", command=parcourir_fichier,
              bg="#30363d", fg="white", font=("Segoe UI", 9, "bold"),
              relief="flat", cursor="hand2").pack(padx=14, pady=(0,6), fill="x", ipady=5)

    def ajouter_doc():
        id_dos = ent_dos_doc.get().strip()
        chemin_source = ent_chemin.get().strip()
        type_doc_reel = "PV_POLICE" if type_doc_var.get() == "Procès verbal (PV)" else type_doc_var.get()
        if not all([id_dos, chemin_source]):
            messagebox.showwarning("Champs manquants","Sélectionnez un fichier et un dossier."); return
        if not os.path.isfile(chemin_source):
            messagebox.showerror("Fichier introuvable", "Le fichier sélectionné n'existe plus."); return
        try:
            dossier_stockage = "/app/documents_stockes"
            os.makedirs(dossier_stockage, exist_ok=True)
            nom_fichier = f"{id_dos}_{type_doc_reel}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{os.path.basename(chemin_source)}"
            chemin_dest = os.path.join(dossier_stockage, nom_fichier)
            shutil.copy2(chemin_source, chemin_dest)
        except Exception as e:
            messagebox.showerror("Erreur copie fichier", str(e)); return

        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            c.execute("""INSERT INTO document (id_dossier,type_document,chemin_fichier)
                         VALUES (%s,%s,%s)""", (id_dos, type_doc_reel, chemin_dest))
            db.commit()
            messagebox.showinfo("✅","Document ajouté et fichier stocké !")
            ent_chemin.config(state="normal")
            ent_chemin.delete(0, tk.END)
            ent_chemin.config(state="readonly")
            charger_docs_ass()
        except Error as e:
            messagebox.showerror("Erreur", str(e))
        finally:
            db.close()

    tk.Button(p_g, text="📄 Ajouter document", command=ajouter_doc,
              bg="#3fb950", fg="white", font=("Segoe UI", 9, "bold"),
              relief="flat", cursor="hand2").pack(padx=14, pady=8, fill="x", ipady=6)

    tk.Frame(p_g, bg=C["border"], height=1).pack(fill="x", padx=10, pady=6)

    # Soumettre demande d'indemnisation
    section(p_g, "💼 5. Soumettre Demande", "#db6d28")
    ent_dos_dem = champ(p_g, "ID Dossier")
    ent_ass_dem = champ(p_g, "ID Assureur")
    ent_suivi_dem = champ(p_g, "N° Suivi")
    ent_suivi_dem.insert(0, f"DEM-{datetime.now().strftime('%Y%m%d')}-001")
    ent_montant_dem = champ(p_g, "Montant réclamé (FCFA) — optionnel")

    def soumettre_demande():
        id_dos = ent_dos_dem.get().strip()
        id_ass = ent_ass_dem.get().strip()
        suivi = ent_suivi_dem.get().strip()
        montant = ent_montant_dem.get().strip()
        if not all([id_dos, id_ass, suivi]):
            messagebox.showwarning("Champs manquants", "ID Dossier, ID Assureur et N° Suivi sont obligatoires."); return
        montant_val = float(montant) if montant else 0.0
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            c.execute("""INSERT INTO demande_indemnisation
                (id_dossier,id_assureur,numero_suivi,montant_reclame,statut)
                VALUES (%s,%s,%s,%s,'SOUMISE')""",
                (id_dos, id_ass, suivi, montant_val))
            db.commit()
            c.execute("SELECT id_victime FROM dossier WHERE id_dossier=%s", (id_dos,))
            row = c.fetchone()
            c.execute("UPDATE dossier SET statut='SOUMIS' WHERE id_dossier=%s", (id_dos,))
            db.commit()
            if row:
                envoyer_notification_auto(row[0], id_dos,
                    f"Votre demande d'indemnisation ({suivi}) a été soumise à l'assureur.")
            envoyer_notification_auto(int(id_ass), id_dos,
                f"Nouvelle demande d'indemnisation reçue : {suivi} (montant réclamé : {montant_val:,.0f} FCFA).")
            messagebox.showinfo("✅ Succès",
                f"Demande '{suivi}' soumise à l'assureur !\nID demande : {c.lastrowid}\n🔔 Notifications envoyées (victime + assureur).")
            charger_dossiers_ass()
            charger_demandes_assistant()
        except Error as e:
            messagebox.showerror("Erreur", str(e))
        finally:
            db.close()

    tk.Button(p_g, text="💼 Soumettre à l'assureur", command=soumettre_demande,
              bg="#db6d28", fg="white", font=("Segoe UI", 9, "bold"),
              relief="flat", cursor="hand2").pack(padx=14, pady=8, fill="x", ipady=6)

    tk.Frame(p_g, bg=C["border"], height=1).pack(fill="x", padx=10, pady=6)

    # Clôture et archivage
    section(p_g, "🔒 6. Clôturer & Archiver", "#8957e5")
    ent_dos_clot = champ(p_g, "N° Dossier à clôturer")
    tk.Label(p_g, text="⚠️ Un dossier doit être PAYÉ avant clôture.\nArchivage automatique : 10 ans (Code CIMA)",
             bg=C["panel"], fg=C["muted"], font=("Segoe UI", 8), justify="left",
             wraplength=250).pack(anchor="w", padx=14, pady=(2,6))

    def cloturer_dossier():
        num = ent_dos_clot.get().strip()
        if not num:
            messagebox.showwarning("Champ vide", "Entrez le numéro du dossier."); return
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            c.execute("SELECT id_dossier, statut, id_victime FROM dossier WHERE numero_dossier=%s", (num,))
            row = c.fetchone()
            if not row:
                messagebox.showerror("Introuvable", f"Dossier '{num}' non trouvé."); return
            if row[1] != "PAYE":
                if not messagebox.askyesno("⚠️ Statut inhabituel",
                        f"Le dossier a le statut '{row[1]}' (pas encore PAYÉ).\nClôturer quand même ?"):
                    return
            c.execute("""UPDATE dossier SET statut='CLOTURE', date_cloture=NOW()
                         WHERE numero_dossier=%s""", (num,))
            db.commit()

            from datetime import timedelta
            date_archivage_fin = (datetime.now() + timedelta(days=365*10)).strftime("%d/%m/%Y")
            envoyer_notification_auto(row[2], row[0],
                f"Votre dossier ({num}) a été clôturé et archivé conformément au Code CIMA (conservation 10 ans).")
            messagebox.showinfo("✅ Dossier clôturé",
                f"Dossier '{num}' clôturé avec succès.\n\n"
                f"📦 Archivage Code CIMA : conservation 10 ans\n"
                f"🗓️ Date de clôture : {datetime.now().strftime('%d/%m/%Y')}\n"
                f"🗑️ Destruction autorisée à partir du : {date_archivage_fin}\n"
                f"🔔 Notification envoyée à la victime.")
            ent_dos_clot.delete(0, tk.END)
            charger_dossiers_ass()
        except Error as e:
            messagebox.showerror("Erreur", str(e))
        finally:
            db.close()

    tk.Button(p_g, text="🔒 Clôturer le dossier", command=cloturer_dossier,
              bg="#8957e5", fg="white", font=("Segoe UI", 9, "bold"),
              relief="flat", cursor="hand2").pack(padx=14, pady=8, fill="x", ipady=6)

    tk.Frame(p_g, bg=C["panel"], height=20).pack()

    # ---- Panneau droit — Tableaux ----
    p_d = tk.Frame(cadre, bg=C["bg"])
    p_d.pack(side="right", fill="both", expand=True)

    nb2 = ttk.Notebook(p_d)
    nb2.pack(fill="both", expand=True)

    ong1 = tk.Frame(nb2, bg=C["card"])
    nb2.add(ong1, text="  📁 Dossiers  ")

    barre_rech_dos = tk.Frame(ong1, bg=C["card"])
    barre_rech_dos.pack(fill="x", padx=8, pady=(8,0))
    tk.Label(barre_rech_dos, text="🔍", bg=C["card"], fg=C["muted"], font=("Segoe UI", 10)).pack(side="left")
    ent_rech_dos = tk.Entry(barre_rech_dos, font=("Segoe UI", 9), bg=C["bg"], fg=C["text"],
        insertbackground=C["text"], relief="flat", highlightthickness=1,
        highlightcolor="#58a6ff", highlightbackground=C["border"], width=35)
    ent_rech_dos.pack(side="left", padx=6, ipady=4)

    tbl_dos = tableau(ong1, ("ID","N° Dossier","Victime","Statut","Date création","Archivage jusqu'à"), [50,120,130,130,130,130])

    def charger_dossiers_ass(filtre=""):
        for r in tbl_dos.get_children(): tbl_dos.delete(r)
        db = connecter_db()
        if not db: return
        try:
            from datetime import timedelta
            c = db.cursor()
            if filtre:
                c.execute("""SELECT d.id_dossier, d.numero_dossier,
                            CONCAT(a.prenom,' ',a.nom), d.statut, d.date_creation, d.date_cloture
                            FROM dossier d JOIN acteur a ON d.id_victime=a.id_acteur
                            WHERE d.numero_dossier LIKE %s OR a.nom LIKE %s OR a.prenom LIKE %s OR d.statut LIKE %s
                            ORDER BY d.id_dossier ASC""",
                            (f"%{filtre}%", f"%{filtre}%", f"%{filtre}%", f"%{filtre}%"))
            else:
                c.execute("""SELECT d.id_dossier, d.numero_dossier,
                            CONCAT(a.prenom,' ',a.nom), d.statut, d.date_creation, d.date_cloture
                            FROM dossier d JOIN acteur a ON d.id_victime=a.id_acteur ORDER BY d.id_dossier ASC""")
            for i, l in enumerate(c.fetchall()):
                l = formater_ligne(l)
                id_d, num_d, vic, statut, date_c, date_clot = l
                archivage = "—"
                if date_clot:
                    archivage = (date_clot + timedelta(days=365*10)).strftime("%d/%m/%Y")
                tbl_dos.insert("","end",
                    values=(id_d, num_d, vic, statut, date_c, archivage),
                    tags=("pair" if i%2==0 else "impair",))
        finally:
            db.close()

    ent_rech_dos.bind("<KeyRelease>", lambda e: charger_dossiers_ass(ent_rech_dos.get().strip()))

    def copier_dossier_vers_formulaires():
        sel = tbl_dos.selection()
        if not sel:
            messagebox.showwarning("Aucune sélection", "Cliquez sur un dossier dans la liste."); return
        vals = tbl_dos.item(sel[0])["values"]
        id_dossier, num_dossier = vals[0], vals[1]
        ent_dos_stat.delete(0, tk.END); ent_dos_stat.insert(0, str(num_dossier))
        ent_dos_doc.delete(0, tk.END); ent_dos_doc.insert(0, str(id_dossier))
        ent_dos_dem.delete(0, tk.END); ent_dos_dem.insert(0, str(id_dossier))
        ent_dos_clot.delete(0, tk.END); ent_dos_clot.insert(0, str(num_dossier))
        messagebox.showinfo("✅", f"Dossier '{num_dossier}' copié dans tous les formulaires concernés (Statut, Document, Demande, Clôture) !")

    barre_d = tk.Frame(ong1, bg=C["card"])
    barre_d.pack(fill="x", padx=8, pady=4)
    btn(barre_d, "🔃 Actualiser", charger_dossiers_ass, couleur)
    btn(barre_d, "📋 Utiliser ce dossier →", copier_dossier_vers_formulaires, "#3fb950")
    btn(barre_d, "🗑️ Supprimer", lambda: supprimer_ligne_selectionnee(
        tbl_dos, "dossier", "id_dossier", charger_dossiers_ass, "dossier"), C["danger"])
    charger_dossiers_ass()

    ong2 = tk.Frame(nb2, bg=C["card"])
    nb2.add(ong2, text="  📄 Documents  ")
    ent_rech_doc = barre_recherche(ong2, "(par N° dossier ou type de document)")
    tbl_doc_ass = tableau(ong2, ("ID","Dossier","Type","Statut","Date upload"), [50,130,160,120,130])

    def charger_docs_ass(filtre=""):
        for r in tbl_doc_ass.get_children(): tbl_doc_ass.delete(r)
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            if filtre:
                c.execute("""SELECT doc.id_document, d.numero_dossier,
                            IF(doc.type_document='PV_POLICE','Procès verbal (PV)',doc.type_document), doc.statut_validation, doc.date_upload
                            FROM document doc JOIN dossier d ON doc.id_dossier=d.id_dossier
                            WHERE d.numero_dossier LIKE %s OR doc.type_document LIKE %s
                            ORDER BY doc.id_document ASC""", (f"%{filtre}%", f"%{filtre}%"))
            else:
                c.execute("""SELECT doc.id_document, d.numero_dossier,
                            IF(doc.type_document='PV_POLICE','Procès verbal (PV)',doc.type_document), doc.statut_validation, doc.date_upload
                            FROM document doc JOIN dossier d ON doc.id_dossier=d.id_dossier ORDER BY doc.id_document ASC""")
            for i, l in enumerate(c.fetchall()):
                l = formater_ligne(l)
                tbl_doc_ass.insert("","end",values=l,tags=("pair" if i%2==0 else "impair",))
        finally:
            db.close()

    ent_rech_doc.bind("<KeyRelease>", lambda e: charger_docs_ass(ent_rech_doc.get().strip()))

    barre_doc = tk.Frame(ong2, bg=C["card"])
    barre_doc.pack(fill="x", padx=8, pady=4)
    btn(barre_doc, "🔃 Actualiser", charger_docs_ass, couleur)
    btn(barre_doc, "🗑️ Supprimer", lambda: supprimer_ligne_selectionnee(
        tbl_doc_ass, "document", "id_document", charger_docs_ass, "document"), C["danger"])
    charger_docs_ass()

    ong3 = tk.Frame(nb2, bg=C["card"])
    nb2.add(ong3, text="  🚗 Accidents  ")
    ent_rech_acc = barre_recherche(ong3, "(par lieu ou N° PV)")
    tbl_acc = tableau(ong3, ("ID","Date","Lieu","N° PV"), [50,150,250,120])

    def charger_accidents(filtre=""):
        for r in tbl_acc.get_children(): tbl_acc.delete(r)
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            if filtre:
                c.execute("""SELECT id_accident,date_accident,lieu,numero_pv FROM accident
                            WHERE lieu LIKE %s OR numero_pv LIKE %s ORDER BY id_accident ASC""",
                            (f"%{filtre}%", f"%{filtre}%"))
            else:
                c.execute("SELECT id_accident,date_accident,lieu,numero_pv FROM accident ORDER BY id_accident ASC")
            for i, l in enumerate(c.fetchall()):
                l = formater_ligne(l)
                tbl_acc.insert("","end",values=l,tags=("pair" if i%2==0 else "impair",))
        finally:
            db.close()

    ent_rech_acc.bind("<KeyRelease>", lambda e: charger_accidents(ent_rech_acc.get().strip()))

    def copier_accident():
        sel = tbl_acc.selection()
        if not sel:
            messagebox.showwarning("Aucune sélection", "Cliquez sur un accident dans la liste."); return
        id_accident = tbl_acc.item(sel[0])["values"][0]
        ent_id_acc.delete(0, tk.END); ent_id_acc.insert(0, str(id_accident))
        messagebox.showinfo("✅", f"ID Accident {id_accident} copié dans 'Créer un Dossier' !")

    barre_acc = tk.Frame(ong3, bg=C["card"])
    barre_acc.pack(fill="x", padx=8, pady=4)
    btn(barre_acc, "🔃 Actualiser", charger_accidents, couleur)
    btn(barre_acc, "📋 Utiliser cet ID →", copier_accident, "#3fb950")
    btn(barre_acc, "🗑️ Supprimer", lambda: supprimer_ligne_selectionnee(
        tbl_acc, "accident", "id_accident", charger_accidents, "accident"), C["danger"])
    charger_accidents()

    ong4 = tk.Frame(nb2, bg=C["card"])
    nb2.add(ong4, text="  💼 Demandes  ")
    ent_rech_dem_ass = barre_recherche(ong4, "(par N° suivi, N° dossier ou statut)")
    tbl_dem_ass = tableau(ong4, ("ID","N° Suivi","Dossier","Assureur","Montant","Statut"), [50,110,120,130,130,90])

    def charger_demandes_assistant(filtre=""):
        for r in tbl_dem_ass.get_children(): tbl_dem_ass.delete(r)
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            if filtre:
                c.execute("""SELECT di.id_demande, di.numero_suivi, d.numero_dossier,
                            CONCAT(a.prenom,' ',a.nom),
                            CONCAT(FORMAT(di.montant_reclame,0),' FCFA'), di.statut
                            FROM demande_indemnisation di
                            JOIN dossier d ON di.id_dossier=d.id_dossier
                            JOIN acteur a ON di.id_assureur=a.id_acteur
                            WHERE di.numero_suivi LIKE %s OR d.numero_dossier LIKE %s OR di.statut LIKE %s
                            ORDER BY di.id_demande ASC""",
                            (f"%{filtre}%", f"%{filtre}%", f"%{filtre}%"))
            else:
                c.execute("""SELECT di.id_demande, di.numero_suivi, d.numero_dossier,
                            CONCAT(a.prenom,' ',a.nom),
                            CONCAT(FORMAT(di.montant_reclame,0),' FCFA'), di.statut
                            FROM demande_indemnisation di
                            JOIN dossier d ON di.id_dossier=d.id_dossier
                            JOIN acteur a ON di.id_assureur=a.id_acteur ORDER BY di.id_demande ASC""")
            for i, l in enumerate(c.fetchall()):
                l = formater_ligne(l)
                tbl_dem_ass.insert("","end",values=l,tags=("pair" if i%2==0 else "impair",))
        finally:
            db.close()

    ent_rech_dem_ass.bind("<KeyRelease>", lambda e: charger_demandes_assistant(ent_rech_dem_ass.get().strip()))

    barre_dem_ass = tk.Frame(ong4, bg=C["card"])
    barre_dem_ass.pack(fill="x", padx=8, pady=4)
    btn(barre_dem_ass, "🔃 Actualiser", charger_demandes_assistant, couleur)
    btn(barre_dem_ass, "🗑️ Supprimer", lambda: supprimer_ligne_selectionnee(
        tbl_dem_ass, "demande_indemnisation", "id_demande", charger_demandes_assistant, "demande"), C["danger"])
    charger_demandes_assistant()

    ong5 = tk.Frame(nb2, bg=C["card"])
    nb2.add(ong5, text="  🧑 Victimes  ")
    tbl_vic = tableau(ong5, ("ID Victime","Nom","Prénom","Téléphone","Email","Adresse"), [80,120,120,110,180,180])

    def charger_victimes():
        for r in tbl_vic.get_children(): tbl_vic.delete(r)
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            c.execute("""SELECT a.id_acteur, a.nom, a.prenom, a.telephone, a.email,
                        IFNULL(v.adresse,'—')
                        FROM acteur a
                        JOIN victime v ON a.id_acteur = v.id_acteur
                        WHERE a.role = 'victime'""")
            for i, l in enumerate(c.fetchall()):
                l = formater_ligne(l)
                tbl_vic.insert("","end",values=l,tags=("pair" if i%2==0 else "impair",))
        finally:
            db.close()

    def copier_id_victime():
        sel = tbl_vic.selection()
        if not sel:
            messagebox.showwarning("Aucune sélection", "Cliquez sur une victime dans la liste."); return
        id_vic = tbl_vic.item(sel[0])["values"][0]
        ent_id_vic.delete(0, tk.END)
        ent_id_vic.insert(0, str(id_vic))
        messagebox.showinfo("✅", f"ID Victime {id_vic} copié dans le formulaire 'Créer un Dossier' !")

    barre_vic = tk.Frame(ong5, bg=C["card"])
    barre_vic.pack(fill="x", padx=8, pady=4)
    btn(barre_vic, "🔃 Actualiser", charger_victimes, couleur)
    btn(barre_vic, "📋 Utiliser cet ID →", copier_id_victime, "#3fb950")
    charger_victimes()

    tk.Label(ong5, text="💡 Astuce : clique sur une victime puis sur '📋 Utiliser cet ID' pour remplir automatiquement le champ 'ID Victime' du formulaire de création de dossier.",
             bg=C["card"], fg=C["muted"], font=("Segoe UI", 8), wraplength=800, justify="left").pack(anchor="w", padx=8, pady=(0,8))

    ong6 = tk.Frame(nb2, bg=C["card"])
    nb2.add(ong6, text="  🏦 Assureurs  ")
    ent_rech_assu = barre_recherche(ong6, "(par compagnie, nom ou prénom)")
    tbl_assu = tableau(ong6, ("ID Assureur","Compagnie","Nom contact","📧 Email","📱 Téléphone","N° Agrément CIMA"), [90,180,140,190,110,140])

    def charger_assureurs(filtre=""):
        for r in tbl_assu.get_children(): tbl_assu.delete(r)
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            if filtre:
                c.execute("""SELECT a.id_acteur, s.nom_compagnie, CONCAT(a.prenom,' ',a.nom),
                            a.email, a.telephone, IFNULL(s.numero_agrement_cima,'—')
                            FROM acteur a
                            JOIN assureur s ON a.id_acteur = s.id_acteur
                            WHERE a.role = 'assureur'
                            AND (s.nom_compagnie LIKE %s OR a.nom LIKE %s OR a.prenom LIKE %s)
                            ORDER BY a.id_acteur ASC""",
                            (f"%{filtre}%", f"%{filtre}%", f"%{filtre}%"))
            else:
                c.execute("""SELECT a.id_acteur, s.nom_compagnie, CONCAT(a.prenom,' ',a.nom),
                            a.email, a.telephone, IFNULL(s.numero_agrement_cima,'—')
                            FROM acteur a
                            JOIN assureur s ON a.id_acteur = s.id_acteur
                            WHERE a.role = 'assureur'
                            ORDER BY a.id_acteur ASC""")
            for i, l in enumerate(c.fetchall()):
                l = formater_ligne(l)
                tbl_assu.insert("","end",values=l,tags=("pair" if i%2==0 else "impair",))
        finally:
            db.close()

    def copier_id_assureur():
        sel = tbl_assu.selection()
        if not sel:
            messagebox.showwarning("Aucune sélection", "Cliquez sur un assureur dans la liste."); return
        id_assu = tbl_assu.item(sel[0])["values"][0]
        ent_ass_dem.delete(0, tk.END)
        ent_ass_dem.insert(0, str(id_assu))
        messagebox.showinfo("✅", f"ID Assureur {id_assu} copié dans le formulaire 'Soumettre Demande' !")

    ent_rech_assu.bind("<KeyRelease>", lambda e: charger_assureurs(ent_rech_assu.get().strip()))

    barre_assu = tk.Frame(ong6, bg=C["card"])
    barre_assu.pack(fill="x", padx=8, pady=4)
    btn(barre_assu, "🔃 Actualiser", charger_assureurs, couleur)
    btn(barre_assu, "📋 Utiliser cet ID →", copier_id_assureur, "#3fb950")
    charger_assureurs()

    tk.Label(ong6, text="💡 Astuce : clique sur un assureur puis sur '📋 Utiliser cet ID' pour remplir automatiquement le champ 'ID Assureur' du formulaire de soumission de demande.",
             bg=C["card"], fg=C["muted"], font=("Segoe UI", 8), wraplength=800, justify="left").pack(anchor="w", padx=8, pady=(0,8))

    ong7 = tk.Frame(nb2, bg=C["card"])
    nb2.add(ong7, text="  🔍 Recherche  ")

    barre_rech_globale = tk.Frame(ong7, bg=C["card"])
    barre_rech_globale.pack(fill="x", padx=10, pady=10)
    tk.Label(barre_rech_globale, text="🔍 Rechercher un dossier :",
             font=("Segoe UI", 10, "bold"), bg=C["card"], fg=C["text"]).pack(side="left", padx=(0,8))
    ent_rech_globale = tk.Entry(barre_rech_globale, font=("Segoe UI", 10), bg=C["bg"], fg=C["text"],
        insertbackground=C["text"], relief="flat", highlightthickness=1,
        highlightcolor="#58a6ff", highlightbackground=C["border"], width=40)
    ent_rech_globale.pack(side="left", ipady=6, padx=(0,8))
    tk.Label(barre_rech_globale, text="(par N° dossier, nom victime, statut ou N° accident)",
             font=("Segoe UI", 8), bg=C["card"], fg=C["muted"]).pack(side="left")

    tbl_rech = tableau(ong7, ("ID","N° Dossier","Victime","Assistant","Statut","N° PV Accident","Date création"),
                        [50,120,140,130,140,140,140])

    def rechercher_globale():
        terme = ent_rech_globale.get().strip()
        for r in tbl_rech.get_children(): tbl_rech.delete(r)
        if not terme:
            return
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            c.execute("""
                SELECT d.id_dossier, d.numero_dossier,
                       CONCAT(av.prenom,' ',av.nom),
                       CONCAT(aa.prenom,' ',aa.nom),
                       d.statut, acc.numero_pv, d.date_creation
                FROM dossier d
                JOIN acteur av ON d.id_victime=av.id_acteur
                JOIN acteur aa ON d.id_assistant=aa.id_acteur
                JOIN accident acc ON d.id_accident=acc.id_accident
                WHERE d.numero_dossier LIKE %s OR av.nom LIKE %s OR av.prenom LIKE %s
                   OR d.statut LIKE %s OR acc.numero_pv LIKE %s
                ORDER BY d.id_dossier ASC
            """, tuple(f"%{terme}%" for _ in range(5)))
            resultats = c.fetchall()
            for i, l in enumerate(resultats):
                l = formater_ligne(l)
                tbl_rech.insert("","end",values=l,tags=("pair" if i%2==0 else "impair",))
            if not resultats:
                messagebox.showinfo("Recherche", f"Aucun dossier trouvé pour '{terme}'.")
        finally:
            db.close()

    ent_rech_globale.bind("<KeyRelease>", lambda e: rechercher_globale())
    ent_rech_globale.bind("<Return>", lambda e: rechercher_globale())

    tk.Button(barre_rech_globale, text="🔍 Rechercher", command=rechercher_globale,
              bg=couleur, fg="white", font=("Segoe UI", 9, "bold"),
              relief="flat", cursor="hand2", padx=12).pack(side="left", padx=8, ipady=4)

    # ---- Onglet Mes Notifications ----
    ong8 = tk.Frame(nb2, bg=C["card"])
    nb2.add(ong8, text="  🔔 Mes Notifications  ")
    tbl_notif_ass = tableau(ong8, ("Dossier","Message","Statut","Date envoi"), [120, 400, 100, 150])

    def charger_notifs_assistant():
        for r in tbl_notif_ass.get_children(): tbl_notif_ass.delete(r)
        if not id_assistant_connecte: return
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            c.execute("""SELECT d.numero_dossier, n.message, n.statut_envoi, n.date_envoi
                         FROM notification n JOIN dossier d ON n.id_dossier=d.id_dossier
                         WHERE n.id_acteur=%s ORDER BY n.id_notification DESC""", (id_assistant_connecte,))
            for i, l in enumerate(c.fetchall()):
                l = formater_ligne(l)
                tbl_notif_ass.insert("","end",values=l,tags=("pair" if i%2==0 else "impair",))
        finally:
            db.close()

    barre_notif_ass = tk.Frame(ong8, bg=C["card"])
    barre_notif_ass.pack(fill="x", padx=8, pady=4)
    btn(barre_notif_ass, "🔃 Actualiser", charger_notifs_assistant, couleur)
    charger_notifs_assistant()

    # ---- Onglet Contestations de paiement ----
    ong9 = tk.Frame(nb2, bg=C["card"])
    nb2.add(ong9, text="  ⚠️ Contestations  ")
    tk.Label(ong9, text="Paiements contestés par les victimes — à transmettre à l'assureur pour réexamen",
             bg=C["card"], fg="#f78166", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=(10,4))
    tbl_contest = tableau(ong9, ("ID Paiement","Dossier","Montant payé","Motif de la victime","Statut"),
                          [90, 120, 140, 350, 150])

    def charger_contestations():
        for r in tbl_contest.get_children(): tbl_contest.delete(r)
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            c.execute("""
                SELECT p.id_paiement, d.numero_dossier,
                       CONCAT(FORMAT(p.montant_paye,0),' FCFA'),
                       IFNULL(p.commentaire_victime,'—'), p.statut_confirmation
                FROM paiement p
                JOIN decision de ON p.id_decision = de.id_decision
                JOIN demande_indemnisation di ON de.id_demande = di.id_demande
                JOIN dossier d ON di.id_dossier = d.id_dossier
                WHERE p.statut_confirmation IN ('CONTESTE','TRANSMIS_ASSUREUR')
                ORDER BY p.id_paiement DESC
            """)
            for i, l in enumerate(c.fetchall()):
                l = formater_ligne(l)
                tag = "contest_actif" if l[4] == "CONTESTE" else "contest_transmis"
                tbl_contest.tag_configure("contest_actif", background="#3d1a1a")
                tbl_contest.tag_configure("contest_transmis", background="#2e2a10")
                tbl_contest.insert("","end",values=l,tags=(tag,))
        finally:
            db.close()

    def transmettre_assureur():
        sel = tbl_contest.selection()
        if not sel:
            messagebox.showwarning("Aucune sélection", "Sélectionnez une contestation dans la liste."); return
        vals = tbl_contest.item(sel[0])["values"]
        id_paiement, num_dossier, montant, motif, statut = vals
        if statut == "TRANSMIS_ASSUREUR":
            messagebox.showinfo("Déjà transmis", "Cette contestation a déjà été transmise à l'assureur."); return
        if not messagebox.askyesno("📢 Transmettre à l'assureur",
                f"Transmettre la contestation du dossier {num_dossier} à l'assureur pour réexamen du montant ?\n\nMotif : {motif}"):
            return
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            c.execute("""SELECT d.id_dossier, di.id_assureur FROM paiement p
                         JOIN decision de ON p.id_decision=de.id_decision
                         JOIN demande_indemnisation di ON de.id_demande=di.id_demande
                         JOIN dossier d ON di.id_dossier=d.id_dossier
                         WHERE p.id_paiement=%s""", (id_paiement,))
            row = c.fetchone()
            if not row:
                messagebox.showerror("Erreur", "Impossible de retrouver l'assureur concerné."); return
            id_dossier, id_assureur = row
            envoyer_notification_auto(id_assureur, id_dossier,
                f"⚠️ RÉEXAMEN DEMANDÉ — Dossier {num_dossier} : la victime conteste le montant payé ({montant}).\n"
                f"Motif : {motif}\nMerci de réévaluer le montant via une nouvelle évaluation.")
            c.execute("UPDATE paiement SET statut_confirmation='TRANSMIS_ASSUREUR' WHERE id_paiement=%s", (id_paiement,))
            db.commit()
            messagebox.showinfo("✅ Transmis", "La contestation a été transmise à l'assureur.\n🔔 L'assureur a été notifié pour réexamen.")
            charger_contestations()
        except Error as e:
            messagebox.showerror("Erreur", str(e))
        finally:
            db.close()

    barre_contest = tk.Frame(ong9, bg=C["card"])
    barre_contest.pack(fill="x", padx=8, pady=4)
    btn(barre_contest, "🔃 Actualiser", charger_contestations, couleur)
    btn(barre_contest, "📢 Transmettre à l'assureur", transmettre_assureur, "#f78166", C["bg"])
    charger_contestations()

    # ---- Onglet Recours (dossiers rejetés à réexaminer) ----
    ong10 = tk.Frame(nb2, bg=C["card"])
    nb2.add(ong10, text="  ⚖️ Recours  ")
    tk.Label(ong10, text="Dossiers REJETÉS — créez un recours si la victime conteste (voir motif dans 'Mes Notifications')",
             bg=C["card"], fg="#f78166", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=(10,4))
    tbl_recours = tableau(ong10, ("ID Dossier","N° Dossier","Victime","Date rejet","Type"), [80,130,160,140,110])

    def charger_dossiers_rejetes():
        for r in tbl_recours.get_children(): tbl_recours.delete(r)
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            c.execute("""
                SELECT d.id_dossier, d.numero_dossier,
                       CONCAT(a.prenom,' ',a.nom), d.date_creation,
                       IFNULL((SELECT MAX(di2.type_demande) FROM demande_indemnisation di2
                               WHERE di2.id_dossier = d.id_dossier AND di2.type_demande='RECOURS'),'—') AS deja_recours
                FROM dossier d
                JOIN acteur a ON d.id_victime = a.id_acteur
                WHERE d.statut = 'REJETE'
                ORDER BY d.id_dossier DESC
            """)
            for i, l in enumerate(c.fetchall()):
                l = formater_ligne(l)
                tag = "recours_deja" if l[4] == "RECOURS" else ("pair" if i%2==0 else "impair")
                tbl_recours.tag_configure("recours_deja", background="#2e2a10")
                tbl_recours.insert("","end",values=l,tags=(tag,))
        finally:
            db.close()

    def creer_recours():
        sel = tbl_recours.selection()
        if not sel:
            messagebox.showwarning("Aucune sélection", "Sélectionnez un dossier rejeté dans la liste."); return
        vals = tbl_recours.item(sel[0])["values"]
        id_dossier, num_dossier = vals[0], vals[1]

        justification = simpledialog.askstring("🔄 Créer un recours",
            f"Dossier {num_dossier}\n\nMotif du recours (raison de la contestation de la victime) :",
            parent=root)
        if not justification or not justification.strip():
            return
        nouveau_montant = simpledialog.askstring("🔄 Créer un recours",
            "Nouveau montant réclamé (FCFA) — laissez vide si inchangé :", parent=root)
        montant_val = 0.0
        try:
            montant_val = float(nouveau_montant) if nouveau_montant and nouveau_montant.strip() else 0.0
        except ValueError:
            montant_val = 0.0

        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            # Récupérer la demande d'origine (la plus récente, traitée, non-recours) et l'assureur
            c.execute("""SELECT id_demande, id_assureur, montant_reclame FROM demande_indemnisation
                         WHERE id_dossier=%s AND type_demande='INITIALE'
                         ORDER BY id_demande DESC LIMIT 1""", (id_dossier,))
            origine = c.fetchone()
            if not origine:
                messagebox.showerror("Erreur", "Aucune demande d'origine trouvée pour ce dossier."); return
            id_demande_origine, id_assureur, montant_origine = origine
            if montant_val == 0.0:
                montant_val = float(montant_origine)

            numero_suivi = f"REC-{datetime.now().strftime('%Y%m%d')}-{id_dossier:03d}"
            c.execute("""INSERT INTO demande_indemnisation
                (id_dossier,id_assureur,numero_suivi,montant_reclame,statut,type_demande,id_demande_origine,motif_recours)
                VALUES (%s,%s,%s,%s,'SOUMISE','RECOURS',%s,%s)""",
                (id_dossier, id_assureur, numero_suivi, montant_val, id_demande_origine, justification.strip()))
            db.commit()
            c.execute("UPDATE dossier SET statut='EN_EVALUATION' WHERE id_dossier=%s", (id_dossier,))
            db.commit()

            envoyer_notification_auto(id_assureur, id_dossier,
                f"🔄 RECOURS — Nouvelle demande de réexamen pour le dossier {num_dossier} suite à contestation du rejet initial.\n"
                f"Motif : {justification.strip()}\nMontant demandé : {montant_val:,.0f} FCFA")

            c.execute("SELECT id_victime FROM dossier WHERE id_dossier=%s", (id_dossier,))
            id_vic_row = c.fetchone()
            if id_vic_row:
                envoyer_notification_auto(id_vic_row[0], id_dossier,
                    f"🔄 Votre recours a été transmis à l'assureur pour réexamen (dossier {num_dossier}).")

            messagebox.showinfo("✅ Recours créé",
                f"Recours '{numero_suivi}' créé et transmis à l'assureur !\n"
                f"📌 Lié à la demande d'origine #{id_demande_origine} (historique conservé)\n"
                f"🔔 Notifications envoyées (assureur + victime).")
            charger_dossiers_rejetes()
            charger_dossiers_ass()
        except Error as e:
            messagebox.showerror("Erreur", str(e))
        finally:
            db.close()

    barre_recours = tk.Frame(ong10, bg=C["card"])
    barre_recours.pack(fill="x", padx=8, pady=4)
    btn(barre_recours, "🔃 Actualiser", charger_dossiers_rejetes, couleur)
    btn(barre_recours, "🔄 Créer un recours", creer_recours, "#8957e5")
    charger_dossiers_rejetes()

    tk.Label(ong10, text="💡 Un recours crée une NOUVELLE demande liée à la demande d'origine — l'historique complet (1er rejet + réexamen) reste consultable par l'administrateur.",
             bg=C["card"], fg=C["muted"], font=("Segoe UI", 8), wraplength=900, justify="left").pack(anchor="w", padx=10, pady=(0,8))

# ============================================================
# INTERFACE ASSUREUR
# ============================================================
def afficher_assureur(root, username):
    clear_window(root)
    root.title("CIMA — Espace Assureur")
    root.geometry("1150x700")
    root.configure(bg=C["bg"])
    root.resizable(True, True)
    root.minsize(950, 550)

    couleur = C["assureur"]
    id_assureur_connecte = obtenir_id_acteur(username)

    h = tk.Frame(root, bg=couleur, height=60)
    h.pack(fill="x")
    h.pack_propagate(False)
    tk.Label(h, text="🏦  CIMA — Espace Assureur",
             font=("Segoe UI", 14, "bold"), bg=couleur, fg="white").pack(side="left", padx=20, pady=15)
    tk.Label(h, text=f"👤 {username}", font=("Segoe UI", 10),
             bg=couleur, fg="white").pack(side="right", padx=20)
    tk.Button(h, text="🚪 Déconnexion",
              command=lambda: afficher_login(root),
              bg="#7a5200", fg="white", font=("Segoe UI", 9, "bold"),
              relief="flat", cursor="hand2", padx=10).pack(side="right", padx=10, pady=12)

    cadre = tk.Frame(root, bg=C["bg"])
    cadre.pack(fill="both", expand=True, padx=10, pady=8)

    # Panneau gauche SCROLLABLE
    p_g = panneau_scrollable(cadre, largeur=280)

    section(p_g, "⚖️ 1. Enregistrer Évaluation", couleur)
    ent_dem_eval = champ(p_g, "ID Demande")
    tk.Label(p_g, text="Type préjudice", bg=C["panel"], fg=C["muted"],
             font=("Segoe UI", 8)).pack(anchor="w", padx=14, pady=(4,0))
    prej_var = tk.StringVar(value="CORPOREL")
    ttk.Combobox(p_g, textvariable=prej_var, width=26,
        values=["CORPOREL","MATERIEL"], state="readonly").pack(padx=14, pady=2, ipady=4, fill="x")
    ent_montant = champ(p_g, "Montant évalué (FCFA)")
    ent_obs = champ(p_g, "Observations")

    def enregistrer_eval():
        id_dem = ent_dem_eval.get().strip()
        montant = ent_montant.get().strip()
        if not all([id_dem, montant]):
            messagebox.showwarning("Champs manquants","Remplissez tous les champs."); return
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            c.execute("""INSERT INTO evaluation
                (id_demande,type_prejudice,montant,observations)
                VALUES (%s,%s,%s,%s)""",
                (id_dem, prej_var.get(), float(montant), ent_obs.get()))
            db.commit()
            c.execute("UPDATE demande_indemnisation SET montant_evalue=%s, statut='EN_COURS' WHERE id_demande=%s",
                      (float(montant), id_dem))
            db.commit()
            messagebox.showinfo("✅","Évaluation enregistrée !")
            charger_demandes_ass()
        except Error as e:
            messagebox.showerror("Erreur", str(e))
        finally:
            db.close()

    tk.Button(p_g, text="⚖️ Enregistrer", command=enregistrer_eval,
              bg=couleur, fg="white", font=("Segoe UI", 9, "bold"),
              relief="flat", cursor="hand2").pack(padx=14, pady=8, fill="x", ipady=6)

    tk.Frame(p_g, bg=C["border"], height=1).pack(fill="x", padx=10, pady=6)

    section(p_g, "✅ 2. Enregistrer Décision", "#3fb950")
    ent_dem_dec = champ(p_g, "ID Demande")
    tk.Label(p_g, text="Résultat", bg=C["panel"], fg=C["muted"],
             font=("Segoe UI", 8)).pack(anchor="w", padx=14, pady=(4,0))
    res_var = tk.StringVar(value="VALIDEE")
    ttk.Combobox(p_g, textvariable=res_var, width=26,
        values=["VALIDEE","REJETEE"], state="readonly").pack(padx=14, pady=2, ipady=4, fill="x")
    ent_motif = champ(p_g, "Motif (si rejeté)")

    def enregistrer_decision():
        id_dem = ent_dem_dec.get().strip()
        if not id_dem:
            messagebox.showwarning("Champ vide","Entrez l'ID de la demande."); return
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            c.execute("""INSERT INTO decision (id_demande,resultat,motif)
                         VALUES (%s,%s,%s)""",
                (id_dem, res_var.get(), ent_motif.get()))
            db.commit()
            id_decision_creee = c.lastrowid
            c.execute("""SELECT d.id_dossier, d.id_victime, d.id_assistant
                         FROM demande_indemnisation di
                         JOIN dossier d ON di.id_dossier = d.id_dossier
                         WHERE di.id_demande=%s""", (id_dem,))
            row = c.fetchone()
            if row:
                id_dossier, id_victime, id_assistant = row
                nouveau_statut = "VALIDE" if res_var.get() == "VALIDEE" else "REJETE"
                c.execute("UPDATE dossier SET statut=%s WHERE id_dossier=%s", (nouveau_statut, id_dossier))
                c.execute("UPDATE demande_indemnisation SET statut='TRAITEE' WHERE id_demande=%s", (id_dem,))
                db.commit()
                message = f"Décision de l'assureur : votre demande a été {res_var.get()}."
                if res_var.get() == "REJETEE" and ent_motif.get():
                    message += f" Motif : {ent_motif.get()}"
                envoyer_notification_auto(id_victime, id_dossier, message)
                envoyer_notification_auto(id_assistant, id_dossier,
                    f"L'assureur a rendu sa décision ({res_var.get()}) pour le dossier lié à la demande #{id_dem}.")

            # Génération automatique de la lettre officielle (PDF)
            chemin_pdf, num_dossier_pdf = generer_lettre_decision(id_decision_creee)
            if chemin_pdf:
                envoyer_notification_auto(id_victime, id_dossier,
                    f"📄 Votre lettre de {'validation' if res_var.get()=='VALIDEE' else 'rejet'} est disponible dans l'onglet 'Mes Documents'.")
                messagebox.showinfo("✅ Décision enregistrée",
                    f"Décision '{res_var.get()}' enregistrée !\n"
                    f"🔔 Notifications envoyées (victime + assistant).\n"
                    f"📄 Lettre officielle générée : {os.path.basename(chemin_pdf)}")
            else:
                messagebox.showinfo("✅",f"Décision '{res_var.get()}' enregistrée !\n🔔 Notifications envoyées.\n⚠️ La lettre PDF n'a pas pu être générée.")
            charger_decisions_ass()
        except Error as e:
            messagebox.showerror("Erreur", str(e))
        finally:
            db.close()

    tk.Button(p_g, text="✅ Enregistrer décision", command=enregistrer_decision,
              bg="#3fb950", fg="white", font=("Segoe UI", 9, "bold"),
              relief="flat", cursor="hand2").pack(padx=14, pady=8, fill="x", ipady=6)

    tk.Frame(p_g, bg=C["border"], height=1).pack(fill="x", padx=10, pady=6)

    # Offre provisionnelle (acompte avant décision définitive - Code CIMA)
    section(p_g, "💵 Offre Provisionnelle (acompte)", "#e3b341")
    tk.Label(p_g, text="Pour blessures graves nécessitant des soins prolongés — avance possible avant l'indemnisation définitive (Code CIMA).",
             bg=C["panel"], fg=C["muted"], font=("Segoe UI", 8), justify="left",
             wraplength=250).pack(anchor="w", padx=14, pady=(2,6))
    ent_dos_prov = champ(p_g, "ID Dossier")
    ent_montant_prov = champ(p_g, "Montant de l'acompte (FCFA)")
    tk.Label(p_g, text="Mode de paiement", bg=C["panel"], fg=C["muted"],
             font=("Segoe UI", 8)).pack(anchor="w", padx=14, pady=(4,0))
    mode_prov_var = tk.StringVar(value="VIREMENT")
    ttk.Combobox(p_g, textvariable=mode_prov_var, width=26,
        values=["VIREMENT","CHEQUE","MOBILE_MONEY"], state="readonly").pack(padx=14, pady=2, ipady=4, fill="x")

    def verser_provision():
        id_dos = ent_dos_prov.get().strip()
        montant = ent_montant_prov.get().strip()
        if not all([id_dos, montant]):
            messagebox.showwarning("Champs manquants","Remplissez tous les champs."); return
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            c.execute("SELECT id_victime, id_assistant, numero_dossier FROM dossier WHERE id_dossier=%s", (id_dos,))
            row = c.fetchone()
            if not row:
                messagebox.showerror("Introuvable", f"Dossier #{id_dos} non trouvé."); return
            c.execute("""INSERT INTO paiement (id_decision, id_dossier, montant_paye, mode_paiement, type_paiement)
                         VALUES (NULL, %s, %s, %s, 'PROVISION')""",
                (id_dos, float(montant), mode_prov_var.get()))
            db.commit()
            envoyer_notification_auto(row[0], id_dos,
                f"💵 Une provision de {float(montant):,.0f} FCFA vous a été versée par {mode_prov_var.get()} en attendant l'indemnisation définitive.")
            envoyer_notification_auto(row[1], id_dos,
                f"💵 Provision versée à la victime — Montant : {float(montant):,.0f} FCFA (par {mode_prov_var.get()}), dossier {row[2]}.")
            messagebox.showinfo("✅ Provision versée",
                f"Acompte de {float(montant):,.0f} FCFA enregistré pour le dossier '{row[2]}'.\n🔔 Victime et assistant notifiés (montant inclus).")
            ent_dos_prov.delete(0, tk.END)
            ent_montant_prov.delete(0, tk.END)
        except Error as e:
            messagebox.showerror("Erreur", str(e))
        finally:
            db.close()

    tk.Button(p_g, text="💵 Verser la provision", command=verser_provision,
              bg="#e3b341", fg="#1c2128", font=("Segoe UI", 9, "bold"),
              relief="flat", cursor="hand2").pack(padx=14, pady=8, fill="x", ipady=6)

    tk.Frame(p_g, bg=C["border"], height=1).pack(fill="x", padx=10, pady=6)

    section(p_g, "💰 4. Enregistrer Paiement Définitif", "#3fb950")
    ent_dec_pai = champ(p_g, "ID Décision")
    ent_montant_pai = champ(p_g, "Montant indemnisation validée (FCFA)")
    tk.Label(p_g, text="⚠️ Montant TOTAL validé par l'assureur — les provisions déjà versées seront déduites automatiquement.",
             bg=C["panel"], fg=C["muted"], font=("Segoe UI", 8), justify="left",
             wraplength=250).pack(anchor="w", padx=14, pady=(2,6))
    tk.Label(p_g, text="Mode de paiement", bg=C["panel"], fg=C["muted"],
             font=("Segoe UI", 8)).pack(anchor="w", padx=14, pady=(4,0))
    mode_var = tk.StringVar(value="VIREMENT")
    ttk.Combobox(p_g, textvariable=mode_var, width=26,
        values=["VIREMENT","CHEQUE","MOBILE_MONEY"], state="readonly").pack(padx=14, pady=2, ipady=4, fill="x")

    def enregistrer_paiement():
        id_dec = ent_dec_pai.get().strip()
        montant = ent_montant_pai.get().strip()
        if not all([id_dec, montant]):
            messagebox.showwarning("Champs manquants","Remplissez tous les champs."); return
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            c.execute("""SELECT de.resultat FROM decision de WHERE de.id_decision=%s""", (id_dec,))
            dec_row = c.fetchone()
            if not dec_row:
                messagebox.showerror("Introuvable", f"Décision #{id_dec} non trouvée."); return
            if dec_row[0] != "VALIDEE":
                messagebox.showwarning("Décision non validée",
                    f"Cette décision est '{dec_row[0]}' — le paiement n'est possible qu'après une décision VALIDÉE."); return
            c.execute("SELECT 1 FROM paiement WHERE id_decision=%s", (id_dec,))
            if c.fetchone():
                messagebox.showwarning("Déjà payé", "Un paiement définitif existe déjà pour cette décision."); return

            # Retrouver le dossier concerné pour calculer les provisions déjà versées
            c.execute("""SELECT d.id_dossier, d.id_victime, d.id_assistant FROM decision de
                         JOIN demande_indemnisation di ON de.id_demande = di.id_demande
                         JOIN dossier d ON di.id_dossier = d.id_dossier
                         WHERE de.id_decision=%s""", (id_dec,))
            row = c.fetchone()
            if not row:
                messagebox.showerror("Erreur", "Impossible de retrouver le dossier lié à cette décision."); return
            id_dossier, id_victime, id_assistant = row

            c.execute("""SELECT IFNULL(SUM(montant_paye),0) FROM paiement
                         WHERE id_dossier=%s AND type_paiement='PROVISION'""", (id_dossier,))
            total_provisions = float(c.fetchone()[0])

            montant_valide = float(montant)
            montant_net = montant_valide - total_provisions

            if montant_net < 0:
                messagebox.showerror("Montant incohérent",
                    f"Les provisions déjà versées ({total_provisions:,.0f} FCFA) dépassent le montant validé "
                    f"({montant_valide:,.0f} FCFA).\nVérifiez le montant ou contactez l'administrateur.")
                return

            if not messagebox.askyesno("Confirmer le paiement",
                    f"Montant validé : {montant_valide:,.0f} FCFA\n"
                    f"Provisions déjà versées : −{total_provisions:,.0f} FCFA\n"
                    f"────────────────────────\n"
                    f"Solde net à payer : {montant_net:,.0f} FCFA\n\nConfirmer ce paiement ?"):
                return

            c.execute("""INSERT INTO paiement (id_decision,montant_paye,montant_provisions_deduites,mode_paiement)
                         VALUES (%s,%s,%s,%s)""", (id_dec, montant_net, total_provisions, mode_var.get()))
            db.commit()
            c.execute("UPDATE dossier SET statut='PAYE' WHERE id_dossier=%s", (id_dossier,))
            db.commit()
            msg_victime = f"Paiement effectué : {montant_net:,.0f} FCFA par {mode_var.get()}."
            if total_provisions > 0:
                msg_victime += f" (Indemnisation validée : {montant_valide:,.0f} FCFA, dont {total_provisions:,.0f} FCFA déjà versés en provision.)"
            msg_victime += " Merci de confirmer réception dans l'onglet 'Mes Paiements'."
            envoyer_notification_auto(id_victime, id_dossier, msg_victime)
            envoyer_notification_auto(id_assistant, id_dossier,
                f"💰 Solde définitif de {montant_net:,.0f} FCFA versé à la victime "
                f"(indemnisation totale {montant_valide:,.0f} FCFA, provisions déduites {total_provisions:,.0f} FCFA).")
            messagebox.showinfo("✅ Paiement enregistré",
                f"Solde net de {montant_net:,.0f} FCFA enregistré !\n🔔 Victime et assistant notifiés.\nStatut du dossier → PAYÉ")
            ent_dec_pai.delete(0, tk.END)
            ent_montant_pai.delete(0, tk.END)
        except Error as e:
            messagebox.showerror("Erreur", str(e))
        finally:
            db.close()

    tk.Button(p_g, text="💰 Enregistrer paiement", command=enregistrer_paiement,
              bg="#3fb950", fg="white", font=("Segoe UI", 9, "bold"),
              relief="flat", cursor="hand2").pack(padx=14, pady=8, fill="x", ipady=6)


    tk.Frame(p_g, bg=C["panel"], height=20).pack()

    # Panneau droit
    p_d = tk.Frame(cadre, bg=C["bg"])
    p_d.pack(side="right", fill="both", expand=True)

    nb3 = ttk.Notebook(p_d)
    nb3.pack(fill="both", expand=True)

    ong1 = tk.Frame(nb3, bg=C["card"])
    nb3.add(ong1, text="  💼 Demandes  ")
    ent_rech_dem = barre_recherche(ong1, "(par N° suivi, N° dossier ou statut)")
    tbl_dem = tableau(ong1, ("ID","ID Dossier","N° Suivi","Dossier","Montant réclamé","Statut","Date"), [50,80,120,120,130,100,130])

    def charger_demandes_ass(filtre=""):
        for r in tbl_dem.get_children(): tbl_dem.delete(r)
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            if filtre:
                c.execute("""SELECT di.id_demande, d.id_dossier, di.numero_suivi, d.numero_dossier,
                            CONCAT(FORMAT(di.montant_reclame,0),' FCFA'),
                            di.statut, di.date_soumission
                            FROM demande_indemnisation di
                            JOIN dossier d ON di.id_dossier=d.id_dossier
                            WHERE di.numero_suivi LIKE %s OR d.numero_dossier LIKE %s OR di.statut LIKE %s
                            ORDER BY di.id_demande ASC""",
                            (f"%{filtre}%", f"%{filtre}%", f"%{filtre}%"))
            else:
                c.execute("""SELECT di.id_demande, d.id_dossier, di.numero_suivi, d.numero_dossier,
                            CONCAT(FORMAT(di.montant_reclame,0),' FCFA'),
                            di.statut, di.date_soumission
                            FROM demande_indemnisation di
                            JOIN dossier d ON di.id_dossier=d.id_dossier ORDER BY di.id_demande ASC""")
            for i, l in enumerate(c.fetchall()):
                l = formater_ligne(l)
                tbl_dem.insert("","end",values=l,tags=("pair" if i%2==0 else "impair",))
        finally:
            db.close()

    def copier_demande_eval_dec():
        sel = tbl_dem.selection()
        if not sel:
            messagebox.showwarning("Aucune sélection", "Cliquez sur une demande dans la liste."); return
        vals = tbl_dem.item(sel[0])["values"]
        id_demande = vals[0]
        ent_dem_eval.delete(0, tk.END); ent_dem_eval.insert(0, str(id_demande))
        ent_dem_dec.delete(0, tk.END); ent_dem_dec.insert(0, str(id_demande))
        messagebox.showinfo("✅", f"ID Demande {id_demande} copié dans 'Évaluation' et 'Décision' !")

    def copier_dossier_provision():
        sel = tbl_dem.selection()
        if not sel:
            messagebox.showwarning("Aucune sélection", "Cliquez sur une demande dans la liste."); return
        vals = tbl_dem.item(sel[0])["values"]
        id_dossier = vals[1]
        ent_dos_prov.delete(0, tk.END); ent_dos_prov.insert(0, str(id_dossier))
        messagebox.showinfo("✅", f"ID Dossier {id_dossier} copié dans 'Offre Provisionnelle' !")

    ent_rech_dem.bind("<KeyRelease>", lambda e: charger_demandes_ass(ent_rech_dem.get().strip()))

    barre_dem = tk.Frame(ong1, bg=C["card"])
    barre_dem.pack(fill="x", padx=8, pady=4)
    btn(barre_dem, "🔃 Actualiser", charger_demandes_ass, couleur)
    btn(barre_dem, "📋 → Évaluation/Décision", copier_demande_eval_dec, "#3fb950")
    btn(barre_dem, "📋 → Provision", copier_dossier_provision, "#e3b341", C["bg"])
    btn(barre_dem, "🗑️ Supprimer", lambda: supprimer_ligne_selectionnee(
        tbl_dem, "demande_indemnisation", "id_demande", charger_demandes_ass, "demande"), C["danger"])
    charger_demandes_ass()

    ong2 = tk.Frame(nb3, bg=C["card"])
    nb3.add(ong2, text="  ⚖️ Décisions  ")
    ent_rech_dec = barre_recherche(ong2, "(par résultat ou motif)")
    tbl_dec = tableau(ong2, ("ID","Demande","Résultat","Motif","Date"), [50,80,100,250,130])

    def charger_decisions_ass(filtre=""):
        for r in tbl_dec.get_children(): tbl_dec.delete(r)
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            if filtre:
                c.execute("""SELECT id_decision,id_demande,resultat,motif,date_decision FROM decision
                            WHERE resultat LIKE %s OR motif LIKE %s ORDER BY id_decision ASC""",
                            (f"%{filtre}%", f"%{filtre}%"))
            else:
                c.execute("SELECT id_decision,id_demande,resultat,motif,date_decision FROM decision ORDER BY id_decision ASC")
            for i, l in enumerate(c.fetchall()):
                l = formater_ligne(l)
                tbl_dec.insert("","end",values=l,tags=("pair" if i%2==0 else "impair",))
        finally:
            db.close()

    ent_rech_dec.bind("<KeyRelease>", lambda e: charger_decisions_ass(ent_rech_dec.get().strip()))

    def copier_decision_paiement():
        sel = tbl_dec.selection()
        if not sel:
            messagebox.showwarning("Aucune sélection", "Cliquez sur une décision dans la liste."); return
        vals = tbl_dec.item(sel[0])["values"]
        id_decision, resultat = vals[0], vals[2]
        if resultat != "VALIDEE":
            messagebox.showwarning("Non éligible", f"Cette décision est '{resultat}' — seule une décision VALIDÉE peut être payée."); return
        ent_dec_pai.delete(0, tk.END); ent_dec_pai.insert(0, str(id_decision))
        messagebox.showinfo("✅", f"ID Décision {id_decision} copié dans 'Paiement Définitif' !")

    barre_dec = tk.Frame(ong2, bg=C["card"])
    barre_dec.pack(fill="x", padx=8, pady=4)
    btn(barre_dec, "🔃 Actualiser", charger_decisions_ass, couleur)
    btn(barre_dec, "📋 → Paiement Définitif", copier_decision_paiement, "#3fb950")
    btn(barre_dec, "🗑️ Supprimer", lambda: supprimer_ligne_selectionnee(
        tbl_dec, "decision", "id_decision", charger_decisions_ass, "décision"), C["danger"])
    charger_decisions_ass()

    # ---- Onglet Contacts : Assistants ----
    ong3 = tk.Frame(nb3, bg=C["card"])
    nb3.add(ong3, text="  📞 Assistants  ")
    ent_rech_ass_assu = barre_recherche(ong3, "(par nom ou zone d'intervention)")
    tbl_ass_assu = tableau(ong3, ("Nom","Prénom","📧 Email","📱 Téléphone","Zone d'intervention"), [130,130,220,130,180])

    def charger_assistants_assureur(filtre=""):
        for r in tbl_ass_assu.get_children(): tbl_ass_assu.delete(r)
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            if filtre:
                c.execute("""SELECT a.nom, a.prenom, a.email, a.telephone, IFNULL(s.zone_intervention,'—')
                            FROM acteur a JOIN assistant s ON a.id_acteur=s.id_acteur
                            WHERE a.role='assistant' AND (a.nom LIKE %s OR a.prenom LIKE %s OR s.zone_intervention LIKE %s)
                            ORDER BY a.id_acteur ASC""",
                            (f"%{filtre}%", f"%{filtre}%", f"%{filtre}%"))
            else:
                c.execute("""SELECT a.nom, a.prenom, a.email, a.telephone, IFNULL(s.zone_intervention,'—')
                            FROM acteur a JOIN assistant s ON a.id_acteur=s.id_acteur
                            WHERE a.role='assistant' ORDER BY a.id_acteur ASC""")
            for i, l in enumerate(c.fetchall()):
                l = formater_ligne(l)
                tbl_ass_assu.insert("","end",values=l,tags=("pair" if i%2==0 else "impair",))
        finally:
            db.close()

    ent_rech_ass_assu.bind("<KeyRelease>", lambda e: charger_assistants_assureur(ent_rech_ass_assu.get().strip()))

    barre_ass_assu = tk.Frame(ong3, bg=C["card"])
    barre_ass_assu.pack(fill="x", padx=8, pady=4)
    btn(barre_ass_assu, "🔃 Actualiser", charger_assistants_assureur, couleur)
    charger_assistants_assureur()

    tk.Label(ong3, text="💡 Contacte l'assistant en charge d'un dossier par email ou téléphone en cas de besoin.",
             bg=C["card"], fg=C["muted"], font=("Segoe UI", 8), wraplength=900, justify="left").pack(anchor="w", padx=8, pady=(0,8))

    # ---- Onglet Mes Notifications ----
    ong4 = tk.Frame(nb3, bg=C["card"])
    nb3.add(ong4, text="  🔔 Mes Notifications  ")
    tbl_notif_assu = tableau(ong4, ("Dossier","Message","Statut","Date envoi"), [120, 400, 100, 150])

    def charger_notifs_assureur():
        for r in tbl_notif_assu.get_children(): tbl_notif_assu.delete(r)
        if not id_assureur_connecte: return
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            c.execute("""SELECT d.numero_dossier, n.message, n.statut_envoi, n.date_envoi
                         FROM notification n JOIN dossier d ON n.id_dossier=d.id_dossier
                         WHERE n.id_acteur=%s ORDER BY n.id_notification DESC""", (id_assureur_connecte,))
            for i, l in enumerate(c.fetchall()):
                l = formater_ligne(l)
                tbl_notif_assu.insert("","end",values=l,tags=("pair" if i%2==0 else "impair",))
        finally:
            db.close()

    barre_notif_assu = tk.Frame(ong4, bg=C["card"])
    barre_notif_assu.pack(fill="x", padx=8, pady=4)
    btn(barre_notif_assu, "🔃 Actualiser", charger_notifs_assureur, couleur)
    charger_notifs_assureur()

# ============================================================
# INTERFACE ADMINISTRATEUR
# ============================================================
def afficher_admin(root, username):
    clear_window(root)
    root.title("CIMA — Espace Administrateur")
    root.geometry("1250x750")
    root.configure(bg=C["bg"])
    root.resizable(True, True)
    root.minsize(1000, 600)

    couleur = C["admin"]

    h = tk.Frame(root, bg=couleur, height=60)
    h.pack(fill="x")
    h.pack_propagate(False)
    tk.Label(h, text="⚙️  CIMA — Espace Administrateur",
             font=("Segoe UI", 14, "bold"), bg=couleur, fg="white").pack(side="left", padx=20, pady=15)
    tk.Label(h, text=f"👤 {username}", font=("Segoe UI", 10),
             bg=couleur, fg="white").pack(side="right", padx=20)
    tk.Button(h, text="🚪 Déconnexion",
              command=lambda: afficher_login(root),
              bg="#6e40c9", fg="white", font=("Segoe UI", 9, "bold"),
              relief="flat", cursor="hand2", padx=10).pack(side="right", padx=10, pady=12)

    stats_f = tk.Frame(root, bg=C["bg"])
    stats_f.pack(fill="x", padx=15, pady=10)
    db = connecter_db()
    stats = {"acteurs":0,"dossiers":0,"documents":0,"demandes":0,"decisions":0,"paiements":0}
    if db:
        c = db.cursor()
        for tbl, k in [("acteur","acteurs"),("dossier","dossiers"),
                       ("document","documents"),("demande_indemnisation","demandes"),
                       ("decision","decisions"),("paiement","paiements")]:
            c.execute(f"SELECT COUNT(*) FROM {tbl}")
            stats[k] = c.fetchone()[0]
        db.close()
    couleurs_stats = [couleur,"#238636","#1f6feb","#9e6a03","#da3633","#3fb950"]
    for (k,v), col in zip(stats.items(), couleurs_stats):
        stat_card(stats_f, k.capitalize(), str(v), col)

    nb4 = ttk.Notebook(root)
    nb4.pack(fill="both", expand=True, padx=15, pady=5)

    def creer_onglet(titre, colonnes, largeurs, requete, table_sql=None, col_id=None, label=None, rechercher_sur=None):
        ong = tk.Frame(nb4, bg=C["card"])
        nb4.add(ong, text=f"  {titre}  ")

        ent_rech = None
        if rechercher_sur:
            barre_rech = tk.Frame(ong, bg=C["card"])
            barre_rech.pack(fill="x", padx=8, pady=(8,0))
            tk.Label(barre_rech, text="🔍", bg=C["card"], fg=C["muted"], font=("Segoe UI", 10)).pack(side="left")
            ent_rech = tk.Entry(barre_rech, font=("Segoe UI", 9), bg=C["bg"], fg=C["text"],
                insertbackground=C["text"], relief="flat", highlightthickness=1,
                highlightcolor="#58a6ff", highlightbackground=C["border"], width=35)
            ent_rech.pack(side="left", padx=6, ipady=4)

        tbl = tableau(ong, colonnes, largeurs)
        def charger(filtre=""):
            for r in tbl.get_children(): tbl.delete(r)
            db = connecter_db()
            if not db: return
            try:
                c = db.cursor()
                if filtre and rechercher_sur:
                    conditions = " OR ".join([f"{col} LIKE %s" for col in rechercher_sur])
                    if "ORDER BY" in requete:
                        pos = requete.index("ORDER BY")
                        q_final = requete[:pos] + f" WHERE ({conditions}) " + requete[pos:]
                    else:
                        q_final = requete + f" WHERE ({conditions})"
                    c.execute(q_final, tuple(f"%{filtre}%" for _ in rechercher_sur))
                else:
                    c.execute(requete)
                for i, l in enumerate(c.fetchall()):
                    l = formater_ligne(l)
                    tbl.insert("","end",values=l,tags=("pair" if i%2==0 else "impair",))
            finally:
                db.close()
        if ent_rech:
            ent_rech.bind("<KeyRelease>", lambda e: charger(ent_rech.get().strip()))
        barre = tk.Frame(ong, bg=C["card"])
        barre.pack(fill="x", padx=8, pady=4)
        btn(barre, "🔃 Actualiser", charger, couleur)
        if table_sql:
            btn(barre, "🗑️ Supprimer", lambda: supprimer_ligne_selectionnee(
                tbl, table_sql, col_id, charger, label or table_sql), C["danger"])
        charger()
        return ong, tbl, charger

    ong_acteurs, tbl_acteurs, charger_acteurs_admin = creer_onglet("👥 Acteurs",
        ("ID","Nom","Prénom","Email","Rôle","Actif"),
        [50,120,120,200,130,60],
        "SELECT id_acteur,nom,prenom,email,role,actif FROM acteur ORDER BY id_acteur ASC",
        table_sql="acteur", col_id="id_acteur", label="acteur",
        rechercher_sur=["nom","prenom","email","role"])

    def modifier_acteur_admin():
        sel = tbl_acteurs.selection()
        if not sel:
            messagebox.showwarning("Aucune sélection", "Cliquez sur un acteur dans le tableau."); return
        vals = tbl_acteurs.item(sel[0])["values"]
        id_a, nom_a, prenom_a, email_a, role_a, actif_a = vals

        fen = tk.Toplevel()
        fen.title(f"Modifier — {prenom_a} {nom_a}")
        fen.geometry("420x420")
        fen.configure(bg=C["panel"])
        fen.resizable(False, False)
        fen.grab_set()

        tk.Label(fen, text=f"✏️ Modifier l'acteur #{id_a}", font=("Segoe UI", 12, "bold"),
                 bg=C["panel"], fg=C["text"]).pack(anchor="w", padx=20, pady=(18,10))

        champs_mod = {}
        for label, valeur in [("Nom", nom_a), ("Prénom", prenom_a),
                                ("Email", email_a)]:
            tk.Label(fen, text=label, font=("Segoe UI", 9),
                     bg=C["panel"], fg=C["muted"]).pack(anchor="w", padx=20, pady=(6,0))
            e = tk.Entry(fen, font=("Segoe UI", 10), bg=C["card"], fg=C["text"],
                         insertbackground=C["text"], relief="flat",
                         highlightthickness=1, highlightcolor="#58a6ff",
                         highlightbackground=C["border"])
            e.pack(fill="x", padx=20, pady=(2,0), ipady=6)
            e.insert(0, valeur)
            champs_mod[label] = e

        tk.Label(fen, text="Rôle", font=("Segoe UI", 9),
                 bg=C["panel"], fg=C["muted"]).pack(anchor="w", padx=20, pady=(6,0))
        role_mod_var = tk.StringVar(value=role_a)
        ttk.Combobox(fen, textvariable=role_mod_var, width=30,
            values=["victime","assistant","assureur","administrateur"],
            state="readonly").pack(padx=20, pady=(2,0), ipady=4, fill="x")

        actif_mod_var = tk.BooleanVar(value=bool(actif_a))
        tk.Checkbutton(fen, text="Compte actif", variable=actif_mod_var,
                       bg=C["panel"], fg=C["text"], selectcolor=C["card"],
                       activebackground=C["panel"], font=("Segoe UI", 9)
                       ).pack(anchor="w", padx=20, pady=(12,0))

        def enregistrer_modif():
            vals_mod = {k: v.get().strip() for k, v in champs_mod.items()}
            if not all(vals_mod.values()):
                messagebox.showwarning("Champs manquants", "Remplissez tous les champs.", parent=fen); return
            db = connecter_db()
            if not db: return
            try:
                c = db.cursor()
                c.execute("""UPDATE acteur SET nom=%s, prenom=%s, email=%s, role=%s, actif=%s
                             WHERE id_acteur=%s""",
                    (vals_mod["Nom"], vals_mod["Prénom"], vals_mod["Email"],
                     role_mod_var.get(), 1 if actif_mod_var.get() else 0, id_a))
                db.commit()
                messagebox.showinfo("✅", "Acteur modifié avec succès.", parent=fen)
                fen.destroy()
                charger_acteurs_admin()
            except Error as e:
                messagebox.showerror("Erreur", str(e), parent=fen)
            finally:
                db.close()

        tk.Button(fen, text="✅ Enregistrer les modifications", command=enregistrer_modif,
                  bg="#238636", fg="white", font=("Segoe UI", 10, "bold"),
                  relief="flat", cursor="hand2").pack(fill="x", padx=20, pady=(20,10), ipady=8)

    barre_mod_acteur = tk.Frame(ong_acteurs, bg=C["card"])
    barre_mod_acteur.pack(fill="x", padx=8, pady=(0,4))
    btn(barre_mod_acteur, "✏️ Modifier l'acteur sélectionné", modifier_acteur_admin, "#1f6feb")

    creer_onglet("📁 Dossiers",
        ("ID","N° Dossier","Victime","Statut","Date"),
        [50,130,160,150,140],
        """SELECT d.id_dossier,d.numero_dossier,
           CONCAT(a.prenom,' ',a.nom),d.statut,d.date_creation
           FROM dossier d JOIN acteur a ON d.id_victime=a.id_acteur ORDER BY d.id_dossier ASC""",
        table_sql="dossier", col_id="id_dossier", label="dossier",
        rechercher_sur=["d.numero_dossier","a.nom","a.prenom","d.statut"])

    creer_onglet("📄 Documents",
        ("ID","Dossier","Type","Statut","Date"),
        [50,130,170,120,140],
        """SELECT doc.id_document,d.numero_dossier,
           IF(doc.type_document='PV_POLICE','Procès verbal (PV)',doc.type_document),doc.statut_validation,doc.date_upload
           FROM document doc JOIN dossier d ON doc.id_dossier=d.id_dossier ORDER BY doc.id_document ASC""",
        table_sql="document", col_id="id_document", label="document")

    creer_onglet("💼 Demandes",
        ("ID","N° Suivi","Dossier","Montant","Statut"),
        [50,120,130,150,100],
        """SELECT di.id_demande,di.numero_suivi,d.numero_dossier,
           CONCAT(FORMAT(di.montant_reclame,0),' FCFA'),di.statut
           FROM demande_indemnisation di
           JOIN dossier d ON di.id_dossier=d.id_dossier ORDER BY di.id_demande ASC""",
        table_sql="demande_indemnisation", col_id="id_demande", label="demande")

    creer_onglet("⚖️ Décisions",
        ("ID","Demande","Résultat","Motif","Date"),
        [60,80,100,280,140],
        "SELECT id_decision,id_demande,resultat,motif,date_decision FROM decision ORDER BY id_decision ASC",
        table_sql="decision", col_id="id_decision", label="décision")

    creer_onglet("💰 Paiements",
        ("ID","Décision","Montant","Mode","Date"),
        [60,80,130,120,140],
        """SELECT id_paiement,id_decision,
           CONCAT(FORMAT(montant_paye,0),' FCFA'),mode_paiement,date_paiement
           FROM paiement ORDER BY id_paiement ASC""",
        table_sql="paiement", col_id="id_paiement", label="paiement")

    # Onglet Admin — Ajouter acteur
    ong_add = tk.Frame(nb4, bg=C["panel"])
    nb4.add(ong_add, text="  ➕ Ajouter Acteur  ")

    form = tk.Frame(ong_add, bg=C["panel"])
    form.pack(padx=30, pady=20, fill="x")
    tk.Label(form, text="Ajouter un nouvel acteur",
             font=("Segoe UI", 12, "bold"), bg=C["panel"], fg=C["text"]).pack(anchor="w", pady=(0,15))

    champs_add = {}
    for lbl in ["Nom","Prénom","Email","Téléphone","Mot de passe"]:
        f = tk.Frame(form, bg=C["panel"])
        f.pack(fill="x", pady=4)
        tk.Label(f, text=lbl, width=15, anchor="w", bg=C["panel"], fg=C["muted"],
                 font=("Segoe UI", 9)).pack(side="left")
        e = tk.Entry(f, font=("Segoe UI", 10), bg=C["card"], fg=C["text"],
                     insertbackground=C["text"], relief="flat",
                     highlightthickness=1, highlightcolor="#58a6ff",
                     highlightbackground=C["border"],
                     show="•" if lbl == "Mot de passe" else "")
        e.pack(side="left", fill="x", expand=True, ipady=5)
        champs_add[lbl] = e

    f_role = tk.Frame(form, bg=C["panel"])
    f_role.pack(fill="x", pady=4)
    tk.Label(f_role, text="Rôle", width=15, anchor="w",
             bg=C["panel"], fg=C["muted"], font=("Segoe UI", 9)).pack(side="left")
    role_add_var = tk.StringVar(value="victime")
    ttk.Combobox(f_role, textvariable=role_add_var,
        values=["victime","assistant","assureur","administrateur"],
        state="readonly", font=("Segoe UI", 10), width=30).pack(side="left", ipady=4)

    def ajouter_acteur_admin():
        vals = {k: v.get().strip() for k, v in champs_add.items()}
        if not all(vals.values()):
            messagebox.showwarning("Champs manquants","Remplissez tous les champs."); return
        db = connecter_db()
        if not db: return
        try:
            c = db.cursor()
            c.execute("""INSERT INTO acteur (nom,prenom,email,telephone,mot_de_passe,role)
                         VALUES (%s,%s,%s,%s,%s,%s)""",
                (vals["Nom"],vals["Prénom"],vals["Email"],
                 vals["Téléphone"],vals["Mot de passe"],role_add_var.get()))
            db.commit()
            messagebox.showinfo("✅",f"Acteur '{vals['Prénom']} {vals['Nom']}' ajouté !")
            for e in champs_add.values(): e.delete(0, tk.END)
        except Error as e:
            messagebox.showerror("Erreur", str(e))
        finally:
            db.close()

    tk.Button(form, text="✅ Ajouter l'acteur", command=ajouter_acteur_admin,
              bg=couleur, fg="white", font=("Segoe UI", 10, "bold"),
              relief="flat", cursor="hand2").pack(anchor="w", pady=15, ipady=8, ipadx=20)

# ============================================================
# LANCEMENT
# ============================================================
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Système CIMA")
    afficher_login(root)
    root.mainloop()
