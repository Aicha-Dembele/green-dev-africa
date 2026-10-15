"""Fabrication du PDF d'un rapport — le dessin, et rien d'autre.

Même principe que `collecteur.py` : ce fichier ne touche jamais à la base.
On lui passe un Rapport déjà chargé, il rend des octets. Le modèle
`Rapport.generer_pdf()` se contente de l'appeler, et la vue se contente de
servir ces octets. Chacun son métier.

Choix de mise en page : **fond blanc**. Un PDF au fond bleu nuit couvrirait
la page d'encre à l'impression — difficile à défendre pour un outil qui
mesure la sobriété. La charte reste dans le bandeau et les accents.
"""

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# --- la charte, reprise de static/css/greendev.css -------------------------

NUIT = colors.HexColor("#0b1e2d")
TURQUOISE = colors.HexColor("#2dd4a7")
TEXTE = colors.HexColor("#0b1e2d")
TEXTE_DOUX = colors.HexColor("#5a7183")
FILET = colors.HexColor("#d7e1e8")
FOND_DOUX = colors.HexColor("#f2f7f9")

#: Les mêmes seuils que la jauge à l'écran (templates/partiels/score.html),
#: mais en versions assombries : le turquoise clair est illisible sur blanc.
SCORE_BON = colors.HexColor("#108a68")
SCORE_MOYEN = colors.HexColor("#b07d0e")
SCORE_MAUVAIS = colors.HexColor("#d13a51")

#: Couleurs de gravité, assombries elles aussi pour l'impression.
GRAVITES = {
    "critique": colors.HexColor("#d13a51"),
    "elevee": colors.HexColor("#c26a1d"),
    "moyenne": colors.HexColor("#a8841f"),
    "faible": colors.HexColor("#3f7f9f"),
}

MARGE = 18 * mm
HAUTEUR_BANDEAU = 26 * mm


# --- petits utilitaires ----------------------------------------------------


def _nombre(valeur, decimales=0):
    """12345.678 -> « 12 345,7 » : séparateur de milliers et virgule française."""
    if valeur is None:
        return "—"
    texte = f"{valeur:,.{decimales}f}"
    # La f-string donne « 12,345.7 » : on échange les deux séparateurs.
    return texte.replace(",", " ").replace(".", ",")


def _texte(valeur, longueur_max=None):
    """Prépare un texte venu de la base pour un Paragraph ReportLab.

    ReportLab lit ses paragraphes comme du mini-HTML : une adresse qui
    contient « & » ou un titre qui contient « < » ferait échouer l'analyse
    et donc la génération entière du PDF. On échappe avant d'insérer.
    """
    texte = escape(str(valeur or ""))
    if longueur_max is not None and len(texte) > longueur_max:
        texte = texte[:longueur_max] + "…"
    return texte


def _valeur(valeur, decimales=0, unite=""):
    """La valeur suivie de son unité — et un simple tiret si elle manque.

    Sans ce garde-fou, une mesure absente s'afficherait « — Ko ».
    """
    if valeur is None:
        return "—"
    return f"{_nombre(valeur, decimales)} {unite}".strip()


def _couleur_du_score(score):
    """Les seuils de templates/partiels/score.html : 70 et 40."""
    if score is None:
        return TEXTE_DOUX
    if score >= 70:
        return SCORE_BON
    if score >= 40:
        return SCORE_MOYEN
    return SCORE_MAUVAIS


def _styles():
    """Les styles de texte du document, construits une fois pour toutes."""
    base = ParagraphStyle(
        "base",
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        textColor=TEXTE,
    )
    return {
        "base": base,
        "titre": ParagraphStyle(
            "titre", parent=base, fontName="Helvetica-Bold", fontSize=18, leading=22
        ),
        "sous_titre": ParagraphStyle(
            "sous_titre", parent=base, fontSize=9.5, textColor=TEXTE_DOUX, leading=13
        ),
        "section": ParagraphStyle(
            "section",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=16,
            textColor=NUIT,
        ),
        "probleme": ParagraphStyle(
            "probleme",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=14,
        ),
        "petit": ParagraphStyle(
            "petit", parent=base, fontSize=8.5, leading=11.5, textColor=TEXTE_DOUX
        ),
        # La note en gros : l'interligne doit suivre la taille, sinon le
        # chiffre déborde sur la ligne du dessous.
        "note": ParagraphStyle(
            "note",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=30,
            leading=34,
            alignment=1,
        ),
        "note_libelle": ParagraphStyle(
            "note_libelle",
            parent=base,
            fontSize=7.5,
            leading=10,
            textColor=TEXTE_DOUX,
            alignment=1,
        ),
        "puce": ParagraphStyle(
            "puce", parent=base, fontSize=9, leading=12.5, leftIndent=10
        ),
        # Les exemples de code : en chasse fixe, sur un fond discret, pour
        # qu'on voie d'un coup d'oeil que ce n'est pas de la prose.
        "code": ParagraphStyle(
            "code",
            parent=base,
            fontName="Courier",
            fontSize=8,
            leading=11,
            leftIndent=20,
            rightIndent=6,
            spaceBefore=3,
            spaceAfter=4,
            backColor=FOND_DOUX,
            borderPadding=5,
            textColor=colors.HexColor("#1d3b4d"),
        ),
    }


# --- bandeau et pied de page, redessinés sur chaque page -------------------


def _habillage(canevas, document, nom_projet):
    """Appelé par ReportLab sur chaque page, par-dessus le contenu."""
    canevas.saveState()
    largeur, hauteur = A4

    # Bandeau bleu nuit en haut.
    canevas.setFillColor(NUIT)
    canevas.rect(
        0, hauteur - HAUTEUR_BANDEAU, largeur, HAUTEUR_BANDEAU, stroke=0, fill=1
    )

    ligne = hauteur - 15 * mm
    canevas.setFont("Helvetica-Bold", 14)
    canevas.setFillColor(colors.white)
    canevas.drawString(MARGE, ligne, "Green")
    decalage = canevas.stringWidth("Green ", "Helvetica-Bold", 14)
    canevas.setFillColor(TURQUOISE)
    canevas.drawString(MARGE + decalage, ligne, "Dev")
    decalage += canevas.stringWidth("Dev ", "Helvetica-Bold", 14)
    canevas.setFillColor(colors.white)
    canevas.drawString(MARGE + decalage, ligne, "Africa")

    canevas.setFont("Helvetica", 8.5)
    canevas.setFillColor(colors.HexColor("#9db6c4"))
    canevas.drawRightString(
        largeur - MARGE, ligne, "Rapport d'analyse de sobriété numérique"
    )

    # Filet et mentions en pied de page.
    canevas.setStrokeColor(FILET)
    canevas.setLineWidth(0.5)
    canevas.line(MARGE, 13 * mm, largeur - MARGE, 13 * mm)

    canevas.setFont("Helvetica", 7.5)
    canevas.setFillColor(TEXTE_DOUX)
    canevas.drawString(MARGE, 9 * mm, nom_projet[:70])
    canevas.drawRightString(largeur - MARGE, 9 * mm, f"Page {document.page}")
    canevas.restoreState()


# --- les blocs de contenu --------------------------------------------------


def _bloc_score(rapport, styles, largeur_utile):
    """La note sur 100 dans son cadre, le nom du projet et la jauge."""
    score = rapport.green_score
    couleur = _couleur_du_score(score)
    note = _nombre(score, 0) if score is not None else "—"

    largeur_note = 34 * mm
    reste = largeur_utile - largeur_note

    cadre_note = Table(
        [
            [
                Paragraph(
                    f'<font color="#{couleur.hexval()[2:]}">{note}</font>',
                    styles["note"],
                )
            ],
            [Paragraph("GREEN SCORE / 100", styles["note_libelle"])],
        ],
        colWidths=[largeur_note],
    )
    cadre_note.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BACKGROUND", (0, 0), (-1, -1), FOND_DOUX),
                ("BOX", (0, 0), (-1, -1), 0.75, couleur),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
                ("TOPPADDING", (0, 1), (-1, 1), 0),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 9),
            ]
        )
    )

    # La jauge : un rail gris sur toute la largeur, rempli jusqu'au score.
    largeur_jauge = reste - 6 * mm
    part = max(0.0, min(1.0, (score or 0) / 100))
    if score is None:
        jauge = Paragraph("Pas encore de score.", styles["petit"])
    else:
        remplie = largeur_jauge * part
        jauge = Table(
            [["", ""]],
            colWidths=[remplie, largeur_jauge - remplie],
            rowHeights=[4.5 * mm],
        )
        jauge.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, 0), couleur),
                    ("BACKGROUND", (1, 0), (1, 0), FILET),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )

    colonne_droite = Table(
        [
            [Paragraph(_texte(rapport.analyse.projet.nom), styles["titre"])],
            [Paragraph(_texte(rapport.analyse.projet.url), styles["sous_titre"])],
            [jauge],
        ],
        colWidths=[largeur_jauge],
    )
    colonne_droite.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )

    bloc = Table([[cadre_note, colonne_droite]], colWidths=[largeur_note, reste])
    bloc.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("LEFTPADDING", (1, 0), (1, 0), 6 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return bloc


def _tableau_chiffres(rapport, largeur_utile):
    """Les quatre grandeurs clés du rapport, en tableau."""
    lignes = [
        ["Indicateur", "Valeur mesurée"],
        ["Poids total de la page", _valeur(rapport.poids_total, 1, "Ko")],
        ["Nombre de requêtes", _valeur(rapport.nombre_requetes, 0)],
        ["Temps de chargement", _valeur(rapport.temps_chargement, 2, "s")],
        ["Données transférées", _valeur(rapport.donnees_transferees, 2, "Mo")],
    ]
    tableau = Table(lignes, colWidths=[largeur_utile * 0.62, largeur_utile * 0.38])
    tableau.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NUIT),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                ("TEXTCOLOR", (0, 1), (-1, -1), TEXTE),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, FOND_DOUX]),
                ("GRID", (0, 0), (-1, -1), 0.4, FILET),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return tableau


def _bloc_probleme(probleme, styles):
    """Un problème et ses recommandations, gardés d'un seul tenant.

    KeepTogether empêche ReportLab de couper le bloc entre deux pages : on ne
    veut pas d'un titre de problème seul en bas de page.
    """
    couleur = f"#{GRAVITES.get(probleme.gravite, TEXTE_DOUX).hexval()[2:]}"
    morceaux = [
        Paragraph(
            f'<font color="{couleur}">■</font> {_texte(probleme.titre)}'
            f' <font size="8" color="{couleur}">'
            f"[{probleme.get_gravite_display().upper()}]</font>",
            styles["probleme"],
        ),
        Paragraph(_texte(probleme.description), styles["base"]),
    ]

    if probleme.ressource_id:
        morceaux.append(
            Paragraph(
                "Principal fichier en cause : "
                f"{_texte(probleme.ressource.url, 220)} "
                f"({_nombre(probleme.ressource.taille, 1)} Ko)",
                styles["petit"],
            )
        )
    elif probleme.localisation:
        morceaux.append(
            Paragraph(_texte(probleme.localisation, 300), styles["petit"])
        )

    for recommandation in probleme.recommandations.all():
        morceaux.append(
            Paragraph(
                f"→ <b>{_texte(recommandation.titre)}</b> — "
                f"{_texte(recommandation.description)}",
                styles["puce"],
            )
        )
        if recommandation.conseil.exemple_code:
            morceaux.append(
                Paragraph(
                    _texte(recommandation.conseil.exemple_code).replace(
                        "\n", "<br/>"
                    ),
                    styles["code"],
                )
            )
    morceaux.append(Spacer(1, 5 * mm))
    return KeepTogether(morceaux)


# --- la fonction publique --------------------------------------------------


def construire_pdf(rapport):
    """Rend le rapport sous forme d'octets PDF, prêts à être servis.

    On reçoit le Rapport, pas un identifiant : le chargement et le
    cloisonnement des données restent l'affaire de la vue.
    """
    tampon = BytesIO()
    styles = _styles()
    analyse = rapport.analyse
    projet = analyse.projet

    document = SimpleDocTemplate(
        tampon,
        pagesize=A4,
        leftMargin=MARGE,
        rightMargin=MARGE,
        topMargin=HAUTEUR_BANDEAU + 10 * mm,
        bottomMargin=18 * mm,
        title=f"Rapport Green Dev Africa — {projet.nom}",
        author="Green Dev Africa",
        subject="Analyse de sobriété numérique",
    )
    largeur_utile = document.width

    histoire = [
        _bloc_score(rapport, styles, largeur_utile),
        Spacer(1, 6 * mm),
        Paragraph(
            f"Analyse du {analyse.date_analyse:%d/%m/%Y à %H:%M} · "
            f"rapport généré le {rapport.date_generation:%d/%m/%Y}",
            styles["sous_titre"],
        ),
        Spacer(1, 7 * mm),
        Paragraph("Les chiffres clés", styles["section"]),
        Spacer(1, 2.5 * mm),
        _tableau_chiffres(rapport, largeur_utile),
        Spacer(1, 9 * mm),
    ]

    problemes = list(
        analyse.problemes.select_related("regle", "ressource").prefetch_related(
            "recommandations__conseil"
        )
    )
    histoire.append(
        Paragraph(f"Problèmes détectés ({len(problemes)})", styles["section"])
    )
    histoire.append(Spacer(1, 3 * mm))

    if problemes:
        for probleme in problemes:
            histoire.append(_bloc_probleme(probleme, styles))
    else:
        histoire.append(
            Paragraph(
                "Aucun problème détecté : tous les indicateurs mesurés restent "
                "sous les seuils des règles actives.",
                styles["base"],
            )
        )

    histoire.append(Spacer(1, 4 * mm))
    histoire.append(
        Paragraph(
            "L'outil mesure la page telle qu'elle arrive du serveur ; les fichiers "
            "ajoutés ensuite par JavaScript ne sont pas comptés. Les résultats "
            "aident à repérer des pistes de sobriété, ils ne constituent pas un "
            "calcul d'empreinte carbone.",
            styles["petit"],
        )
    )

    def habillage(canevas, doc):
        _habillage(canevas, doc, projet.nom)

    document.build(histoire, onFirstPage=habillage, onLaterPages=habillage)
    return tampon.getvalue()
