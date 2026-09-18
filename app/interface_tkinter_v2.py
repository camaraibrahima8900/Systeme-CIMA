# ============================================================
# interface_tkinter_v2.py  (version Docker)
# Connexion via variables d'environnement du conteneur
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import mysql.connector
from mysql.connector import Error
from datetime import datetime
import os

# ============================================================
# PALETTE DE COULEURS
# ============================================================
C = {
    "bg_dark":   "#0f1923",
    "bg_panel":  "#162030",
    "bg_card":   "#1e2e40",
    "accent":    "#00c9a7",
    "accent2":   "#0088cc",
    "danger":    "#e63946",
    "warning":   "#f4a261",
    "text_main": "#e8f1f2",
    "text_muted":"#8899aa",
    "border":    "#264154",
    "row_even":  "#1a2b3c",
    "row_odd":   "#16232f",
    "header_tbl":"#0d1b2a",
}

# ============================================================
# CONNEXION — lit les variables d'environnement Docker
# ============================================================
def connecter():
    try:
        db = mysql.connector.connect(
            host=os.environ.get("DB_HOST", "127.0.0.1"),
            user=os.environ.get("DB_USER", "ibrahima"),
            password=os.environ.get("DB_PASSWORD", "8900"),
            database=os.environ.get("DB_NAME", "gestion_dossiers_victimes"),
            port=int(os.environ.get("DB_PORT", "3307")),
        )
        return db
    except Error as e:
        messagebox.showerror("Erreur de connexion", f"Impossible de se connecter :\n{e}")
        return None

# ============================================================
# FENÊTRE PRINCIPALE
# ============================================================
fenetre = tk.Tk()
fenetre.title("Système CIMA — Gestion des Dossiers Victimes")
fenetre.geometry("1100x680")
fenetre.configure(bg=C["bg_dark"])
fenetre.resizable(True, True)

style = ttk.Style()
style.theme_use("default")
style.configure("Treeview",
    background=C["bg_card"], foreground=C["text_main"],
    rowheight=26, fieldbackground=C["bg_card"], font=("Segoe UI", 9))
style.configure("Treeview.Heading",
    background=C["header_tbl"], foreground=C["accent"],
    font=("Segoe UI", 9, "bold"), relief="flat")
style.map("Treeview",
    background=[("selected", C["accent2"])],
    foreground=[("selected", "white")])
style.configure("TNotebook", background=C["bg_dark"], borderwidth=0)
style.configure("TNotebook.Tab",
    background=C["bg_card"], foreground=C["text_muted"],
    padding=[14, 6], font=("Segoe UI", 9, "bold"))
style.map("TNotebook.Tab",
    background=[("selected", C["accent"])],
    foreground=[("selected", C["bg_dark"])])

# ============================================================
# EN-TÊTE
# ============================================================
header = tk.Frame(fenetre, bg=C["accent"], height=55)
header.pack(fill="x")
header.pack_propagate(False)

tk.Label(header,
    text="🏥  Système CIMA — Gestion des Dossiers Victimes d'Accidents Routiers",
    font=("Segoe UI", 13, "bold"), bg=C["accent"], fg=C["bg_dark"]
).pack(side="left", padx=20, pady=12)

lbl_heure = tk.Label(header, text="", font=("Segoe UI", 9), bg=C["accent"], fg=C["bg_dark"])
lbl_heure.pack(side="right", padx=20)

def maj_heure():
    lbl_heure.config(text=datetime.now().strftime("📅 %d/%m/%Y   🕐 %H:%M:%S"))
    fenetre.after(1000, maj_heure)
maj_heure()

# ============================================================
# CADRE PRINCIPAL
# ============================================================
cadre = tk.Frame(fenetre, bg=C["bg_dark"])
cadre.pack(fill="both", expand=True, padx=12, pady=8)

# ---- PANNEAU GAUCHE ----
p_gauche = tk.Frame(cadre, bg=C["bg_panel"], width=230)
p_gauche.pack(side="left", fill="y", padx=(0, 10))
p_gauche.pack_propagate(False)

def section_lbl(txt, couleur):
    tk.Frame(p_gauche, bg=couleur, height=3).pack(fill="x", padx=10, pady=(12, 2))
    tk.Label(p_gauche, text=txt, font=("Segoe UI", 10, "bold"),
             bg=C["bg_panel"], fg=couleur).pack(anchor="w", padx=12)

def champ(label, show=""):
    tk.Label(p_gauche, text=label, bg=C["bg_panel"], fg=C["text_muted"],
             font=("Segoe UI", 8)).pack(anchor="w", padx=12, pady=(4, 0))
    e = tk.Entry(p_gauche, width=26, font=("Segoe UI", 9),
                 bg=C["bg_card"], fg=C["text_main"],
                 insertbackground=C["accent"], relief="flat",
                 highlightthickness=1, highlightcolor=C["accent"],
                 highlightbackground=C["border"], show=show)
    e.pack(padx=12, pady=2, ipady=4)
    return e

def btn(txt, cmd, couleur, fg=None):
    fg = fg or C["bg_dark"]
    b = tk.Button(p_gauche, text=txt, command=cmd,
                  bg=couleur, fg=fg, font=("Segoe UI", 9, "bold"),
                  relief="flat", cursor="hand2", bd=0)
    b.pack(padx=12, pady=4, fill="x", ipady=5)
    return b

# --- Ajouter acteur ---
section_lbl("➕  Ajouter un Acteur", C["accent"])
champs = {}
for lbl, sh in [("Nom",""),("Prénom",""),("Email",""),("Téléphone",""),("Mot de passe","*")]:
    champs[lbl] = champ(lbl, sh)

tk.Label(p_gauche, text="Rôle", bg=C["bg_panel"], fg=C["text_muted"],
         font=("Segoe UI", 8)).pack(anchor="w", padx=12, pady=(4, 0))
role_var = tk.StringVar(value="victime")
ttk.Combobox(p_gauche, textvariable=role_var, width=24,
    values=["victime","assistant","assureur","administrateur"],
    state="readonly", font=("Segoe UI", 9)).pack(padx=12, pady=2, ipady=3)

def ajouter_acteur():
    vals = {k: v.get().strip() for k, v in champs.items()}
    if not all(vals.values()):
        messagebox.showwarning("Champs manquants", "Remplissez tous les champs."); return
    db = connecter()
    if not db: return
    try:
        c = db.cursor()
        c.execute("INSERT INTO acteur (nom,prenom,email,telephone,mot_de_passe,role) VALUES (%s,%s,%s,%s,%s,%s)",
            (vals["Nom"],vals["Prénom"],vals["Email"],vals["Téléphone"],vals["Mot de passe"],role_var.get()))
        db.commit()
        messagebox.showinfo("✅ Succès", f"Acteur '{vals['Prénom']} {vals['Nom']}' ajouté !")
        for e in champs.values(): e.delete(0, tk.END)
        charger_acteurs(); maj_stats()
    except Error as e:
        messagebox.showerror("Erreur", str(e))
    finally:
        db.close()

btn("✅  Ajouter l'acteur", ajouter_acteur, C["accent"])

tk.Frame(p_gauche, bg=C["border"], height=1).pack(fill="x", padx=10, pady=6)

# --- Mise à jour dossier ---
section_lbl("🔄  Mise à jour Dossier", C["warning"])
ent_num = champ("N° Dossier")
tk.Label(p_gauche, text="Nouveau statut", bg=C["bg_panel"], fg=C["text_muted"],
         font=("Segoe UI", 8)).pack(anchor="w", padx=12, pady=(4, 0))
statut_var = tk.StringVar(value="DOSSIER_COMPLET")
ttk.Combobox(p_gauche, textvariable=statut_var, width=24,
    values=["EN_CONSTITUTION","DOSSIER_COMPLET","SOUMIS","EN_EVALUATION",
            "VALIDE","REJETE","PAYE","CLOTURE"],
    state="readonly", font=("Segoe UI", 9)).pack(padx=12, pady=2, ipady=3)

def changer_statut():
    numero = ent_num.get().strip()
    if not numero:
        messagebox.showwarning("Champ vide", "Entrez le numéro du dossier."); return
    db = connecter()
    if not db: return
    try:
        c = db.cursor()
        c.execute("SELECT id_dossier FROM dossier WHERE numero_dossier = %s", (numero,))
        row = c.fetchone()
        if not row:
            messagebox.showerror("Introuvable", f"Dossier '{numero}' non trouvé."); return
        c.execute("UPDATE dossier SET statut = %s WHERE id_dossier = %s", (statut_var.get(), row[0]))
        db.commit()
        messagebox.showinfo("✅ Mis à jour", f"Dossier '{numero}' → {statut_var.get()}")
        charger_dossiers()
    except Error as e:
        messagebox.showerror("Erreur", str(e))
    finally:
        db.close()

btn("🔄  Mettre à jour", changer_statut, C["warning"], C["bg_dark"])

tk.Frame(p_gauche, bg=C["border"], height=1).pack(fill="x", padx=10, pady=6)

# --- Supprimer acteur ---
section_lbl("🗑️  Supprimer un Acteur", C["danger"])
ent_del_id = champ("ID Acteur à supprimer")

def supprimer_acteur():
    id_val = ent_del_id.get().strip()
    if not id_val.isdigit():
        messagebox.showwarning("Invalide", "Entrez un ID numérique valide."); return
    if not messagebox.askyesno("⚠️ Confirmation", f"Supprimer l'acteur #{id_val} ?"): return
    db = connecter()
    if not db: return
    try:
        c = db.cursor()
        c.execute("DELETE FROM acteur WHERE id_acteur = %s", (int(id_val),))
        db.commit()
        if c.rowcount == 0:
            messagebox.showerror("Introuvable", f"Aucun acteur #{id_val}.")
        else:
            messagebox.showinfo("✅ Supprimé", f"Acteur #{id_val} supprimé.")
            ent_del_id.delete(0, tk.END)
            charger_acteurs(); maj_stats()
    except Error as e:
        messagebox.showerror("Erreur", str(e))
    finally:
        db.close()

btn("🗑️  Supprimer", supprimer_acteur, C["danger"], "white")

# ============================================================
# PANNEAU DROIT
# ============================================================
p_droit = tk.Frame(cadre, bg=C["bg_panel"])
p_droit.pack(side="right", fill="both", expand=True)

# Barre recherche + stats
barre_top = tk.Frame(p_droit, bg=C["bg_panel"])
barre_top.pack(fill="x", padx=10, pady=(10, 4))

tk.Label(barre_top, text="🔍", bg=C["bg_panel"], fg=C["text_muted"],
         font=("Segoe UI", 10)).pack(side="left")
ent_rech = tk.Entry(barre_top, width=25, font=("Segoe UI", 9),
    bg=C["bg_card"], fg=C["text_main"], insertbackground=C["accent"],
    relief="flat", highlightthickness=1, highlightcolor=C["accent"],
    highlightbackground=C["border"])
ent_rech.pack(side="left", padx=6, ipady=4)
ent_rech.insert(0, "Rechercher un acteur...")
ent_rech.bind("<FocusIn>", lambda e: ent_rech.delete(0, tk.END)
              if ent_rech.get() == "Rechercher un acteur..." else None)

def rechercher():
    terme = ent_rech.get().strip().lower()
    for r in tableau_acteurs.get_children(): tableau_acteurs.delete(r)
    db = connecter()
    if not db: return
    try:
        c = db.cursor()
        c.execute("SELECT id_acteur,nom,prenom,email,role,actif FROM acteur WHERE LOWER(nom) LIKE %s OR LOWER(prenom) LIKE %s OR LOWER(email) LIKE %s",
            (f"%{terme}%", f"%{terme}%", f"%{terme}%"))
        for i, l in enumerate(c.fetchall()):
            tableau_acteurs.insert("", "end", values=(l[0],l[1],l[2],l[3],l[4],"✅" if l[5] else "❌"),
                tags=("even" if i%2==0 else "odd",))
    finally:
        db.close()

tk.Button(barre_top, text="Rechercher", command=rechercher,
    bg=C["accent2"], fg="white", font=("Segoe UI", 9, "bold"),
    relief="flat", cursor="hand2", padx=8).pack(side="left", ipady=4)
tk.Button(barre_top, text="🔄 Tout afficher", command=lambda: charger_acteurs(),
    bg=C["bg_card"], fg=C["text_muted"], font=("Segoe UI", 9),
    relief="flat", cursor="hand2", padx=6).pack(side="left", padx=4, ipady=4)

stats_labels = {}
for titre, cle, couleur in [("Acteurs","acteurs",C["accent"]),
                              ("Dossiers","dossiers",C["accent2"]),
                              ("Documents","documents",C["warning"])]:
    f = tk.Frame(barre_top, bg=couleur, padx=8, pady=3)
    f.pack(side="right", padx=3)
    tk.Label(f, text=titre, font=("Segoe UI", 7, "bold"), bg=couleur, fg=C["bg_dark"]).pack()
    lbl = tk.Label(f, text="0", font=("Segoe UI", 12, "bold"), bg=couleur, fg=C["bg_dark"])
    lbl.pack()
    stats_labels[cle] = lbl

def maj_stats():
    db = connecter()
    if not db: return
    try:
        c = db.cursor()
        for tbl, cle in [("acteur","acteurs"),("dossier","dossiers"),("document","documents")]:
            c.execute(f"SELECT COUNT(*) FROM {tbl}")
            stats_labels[cle].config(text=str(c.fetchone()[0]))
    finally:
        db.close()

# ---- NOTEBOOK ----
notebook = ttk.Notebook(p_droit)
notebook.pack(fill="both", expand=True, padx=10, pady=5)

def creer_tableau(parent, colonnes, largeurs):
    frame = tk.Frame(parent, bg=C["bg_card"])
    frame.pack(fill="both", expand=True, padx=5, pady=5)
    sb = ttk.Scrollbar(frame, orient="vertical")
    sb.pack(side="right", fill="y")
    tbl = ttk.Treeview(frame, columns=colonnes, show="headings", yscrollcommand=sb.set)
    for col, larg in zip(colonnes, largeurs):
        tbl.heading(col, text=col)
        tbl.column(col, width=larg, minwidth=40)
    tbl.tag_configure("even", background=C["row_even"])
    tbl.tag_configure("odd",  background=C["row_odd"])
    sb.config(command=tbl.yview)
    tbl.pack(fill="both", expand=True)
    return tbl

# ---- Onglet Acteurs ----
ong_a = tk.Frame(notebook, bg=C["bg_card"])
notebook.add(ong_a, text="  👥 Acteurs  ")
tableau_acteurs = creer_tableau(ong_a, ("ID","Nom","Prénom","Email","Rôle","Actif"), [50,100,100,180,110,50])

def charger_acteurs():
    for r in tableau_acteurs.get_children(): tableau_acteurs.delete(r)
    db = connecter()
    if not db: return
    try:
        c = db.cursor()
        c.execute("SELECT id_acteur,nom,prenom,email,role,actif FROM acteur")
        for i, l in enumerate(c.fetchall()):
            tableau_acteurs.insert("","end",values=(l[0],l[1],l[2],l[3],l[4],"✅" if l[5] else "❌"),
                tags=("even" if i%2==0 else "odd",))
        maj_stats()
    finally:
        db.close()

def supprimer_selection():
    sel = tableau_acteurs.selection()
    if not sel:
        messagebox.showwarning("Aucune sélection","Cliquez sur un acteur."); return
    vals = tableau_acteurs.item(sel[0])["values"]
    if not messagebox.askyesno("⚠️ Confirmer", f"Supprimer '{vals[2]} {vals[1]}' ?"): return
    db = connecter()
    if not db: return
    try:
        c = db.cursor()
        c.execute("DELETE FROM acteur WHERE id_acteur = %s", (vals[0],))
        db.commit()
        charger_acteurs(); maj_stats()
        messagebox.showinfo("✅", f"Acteur #{vals[0]} supprimé.")
    except Error as e:
        messagebox.showerror("Erreur", str(e))
    finally:
        db.close()

barre_a = tk.Frame(ong_a, bg=C["bg_card"])
barre_a.pack(fill="x", padx=5, pady=4)
tk.Button(barre_a, text="🔃 Actualiser", command=charger_acteurs,
    bg=C["accent2"], fg="white", font=("Segoe UI", 9, "bold"),
    relief="flat", cursor="hand2", padx=10).pack(side="left", ipady=4)
tk.Button(barre_a, text="🗑️ Supprimer sélection", command=supprimer_selection,
    bg=C["danger"], fg="white", font=("Segoe UI", 9, "bold"),
    relief="flat", cursor="hand2", padx=10).pack(side="left", padx=6, ipady=4)

# ---- Onglet Dossiers ----
ong_d = tk.Frame(notebook, bg=C["bg_card"])
notebook.add(ong_d, text="  📁 Dossiers  ")
tableau_dossiers = creer_tableau(ong_d, ("ID","N° Dossier","Victime","Assistant","Statut","Date"), [50,120,140,120,140,130])

def charger_dossiers():
    for r in tableau_dossiers.get_children(): tableau_dossiers.delete(r)
    db = connecter()
    if not db: return
    try:
        c = db.cursor()
        c.execute("""
            SELECT d.id_dossier, d.numero_dossier,
                   CONCAT(av.prenom,' ',av.nom),
                   CONCAT(aa.prenom,' ',aa.nom),
                   d.statut, d.date_creation
            FROM dossier d
            JOIN acteur av ON d.id_victime=av.id_acteur
            JOIN acteur aa ON d.id_assistant=aa.id_acteur
        """)
        couleurs = {"EN_CONSTITUTION":"#264154","DOSSIER_COMPLET":"#1a3d2b",
                    "SOUMIS":"#2d3a1e","EN_EVALUATION":"#2e2a10",
                    "VALIDE":"#1a3d2b","REJETE":"#3d1a1a","PAYE":"#1a2d3d","CLOTURE":"#2a2a2a"}
        for l in c.fetchall():
            tag = f"s_{l[4]}"
            tableau_dossiers.tag_configure(tag, background=couleurs.get(l[4], C["row_even"]))
            tableau_dossiers.insert("","end", values=l, tags=(tag,))
        maj_stats()
    finally:
        db.close()

barre_d = tk.Frame(ong_d, bg=C["bg_card"])
barre_d.pack(fill="x", padx=5, pady=4)
tk.Button(barre_d, text="🔃 Actualiser", command=charger_dossiers,
    bg=C["accent2"], fg="white", font=("Segoe UI", 9, "bold"),
    relief="flat", cursor="hand2", padx=10).pack(side="left", ipady=4)

# ---- Onglet Documents ----
ong_doc = tk.Frame(notebook, bg=C["bg_card"])
notebook.add(ong_doc, text="  📄 Documents  ")
tableau_docs = creer_tableau(ong_doc, ("ID","Dossier","Type","Statut validation","Date upload"), [50,120,160,130,140])

def charger_documents():
    for r in tableau_docs.get_children(): tableau_docs.delete(r)
    db = connecter()
    if not db: return
    try:
        c = db.cursor()
        c.execute("""
            SELECT doc.id_document, d.numero_dossier,
                   doc.type_document, doc.statut_validation, doc.date_upload
            FROM document doc JOIN dossier d ON doc.id_dossier=d.id_dossier
        """)
        for i, l in enumerate(c.fetchall()):
            tableau_docs.insert("","end", values=l, tags=("even" if i%2==0 else "odd",))
        maj_stats()
    finally:
        db.close()

barre_doc = tk.Frame(ong_doc, bg=C["bg_card"])
barre_doc.pack(fill="x", padx=5, pady=4)
tk.Button(barre_doc, text="🔃 Actualiser", command=charger_documents,
    bg=C["accent2"], fg="white", font=("Segoe UI", 9, "bold"),
    relief="flat", cursor="hand2", padx=10).pack(side="left", ipady=4)

# ---- Onglet Demandes ----
ong_dem = tk.Frame(notebook, bg=C["bg_card"])
notebook.add(ong_dem, text="  💼 Demandes  ")
tableau_dem = creer_tableau(ong_dem, ("ID","N° Suivi","Dossier","Assureur","Montant réclamé","Statut"), [50,110,110,130,130,100])

def charger_demandes():
    for r in tableau_dem.get_children(): tableau_dem.delete(r)
    db = connecter()
    if not db: return
    try:
        c = db.cursor()
        c.execute("""
            SELECT di.id_demande, di.numero_suivi, d.numero_dossier,
                   CONCAT(a.prenom,' ',a.nom),
                   CONCAT(FORMAT(di.montant_reclame,0),' FCFA'), di.statut
            FROM demande_indemnisation di
            JOIN dossier d ON di.id_dossier=d.id_dossier
            JOIN acteur a ON di.id_assureur=a.id_acteur
        """)
        for i, l in enumerate(c.fetchall()):
            tableau_dem.insert("","end", values=l, tags=("even" if i%2==0 else "odd",))
    finally:
        db.close()

barre_dem = tk.Frame(ong_dem, bg=C["bg_card"])
barre_dem.pack(fill="x", padx=5, pady=4)
tk.Button(barre_dem, text="🔃 Actualiser", command=charger_demandes,
    bg=C["accent2"], fg="white", font=("Segoe UI", 9, "bold"),
    relief="flat", cursor="hand2", padx=10).pack(side="left", ipady=4)

# ============================================================
# BARRE DE STATUT + BOUTON CONNEXION
# ============================================================
barre_statut = tk.Label(fenetre, text="⚪  Non connecté",
    bd=0, anchor="w", bg="#0a1520", fg=C["text_muted"],
    font=("Segoe UI", 9), padx=12, pady=5)
barre_statut.pack(side="bottom", fill="x")

def tout_charger():
    db = connecter()
    if db:
        barre_statut.config(text="🟢  Connecté à MySQL — gestion_dossiers_victimes", fg=C["accent"])
        db.close()
        charger_acteurs(); charger_dossiers(); charger_documents(); charger_demandes()
        maj_stats()
    else:
        barre_statut.config(text="🔴  Échec de connexion à MySQL", fg=C["danger"])

tk.Button(header, text="🔌 Connecter & Charger", command=tout_charger,
    bg=C["bg_dark"], fg=C["accent"], font=("Segoe UI", 9, "bold"),
    relief="flat", cursor="hand2", padx=12).pack(side="right", padx=10, pady=10)

fenetre.after(800, tout_charger)
fenetre.mainloop()
