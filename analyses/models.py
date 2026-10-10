"""Le cœur de Green Dev Africa : l'analyse d'une URL et tout ce qu'elle produit.

Les 12 classes du diagramme qui tournent autour de « Analyse » :

    Analyse ─┬─<>─ ConfigurationAnalyse   (comment on audite)
             ├─<>─ UtilisateurContexte    (avec quel appareil / quel réseau)
             ├─<>─ Indicateur             (les métriques mesurées)
             ├─<>─ RessourceWeb           (les fichiers téléchargés)
             ├─<>─ ProblemeDetecte ─<>─ Recommandation ──> ConseilOptimisation
             │          └──> RegleAnalyse
             └─<>─ Rapport ─<>─ PartageRapport

    ComparaisonAnalyse ──> deux Analyses (avant / après)

Le losange du diagramme (composition) se traduit en Django par
on_delete=models.CASCADE : si l'analyse disparaît, ses pièces disparaissent.
"""

import secrets

from django.db import models
from django.utils import timezone

from projets.models import Projet


def nombre_francais(valeur):
    """1850.0 → « 1850 », 230.82 → « 230,82 ».

    Ces nombres partent dans des titres enregistrés en base, que les filtres
    de gabarit ne retoucheront plus : on écrit donc la virgule décimale ici.
    """
    return f"{valeur:g}".replace(".", ",")


# ---------------------------------------------------------------------------
#  Les référentiels : des tables de paramétrage, remplies une fois pour toutes
# ---------------------------------------------------------------------------


class RegleAnalyse(models.Model):
    """Classe RegleAnalyse : « au-delà de ce seuil, c'est un problème ».

    C'est l'administrateur qui règle les seuils (cas d'utilisation
    « Régler les seuils des règles d'analyse »).

    Convention du projet : le `code` de la règle porte le même nom que
    l'indicateur qu'elle surveille (la règle « poids_total » surveille
    l'indicateur « poids_total »).
    """

    class Categorie(models.TextChoices):
        POIDS = "poids", "Poids des pages"
        REQUETES = "requetes", "Nombre de requêtes"
        IMAGES = "images", "Images"
        CODE = "code", "Code (JS / CSS)"
        RESEAU = "reseau", "Réseau et cache"
        ACCESSIBILITE = "accessibilite", "Accessibilité"

    code = models.SlugField("code de la règle", max_length=60, unique=True)
    description = models.TextField("description")
    categorie = models.CharField("catégorie", max_length=20, choices=Categorie.choices)
    seuil = models.FloatField("seuil à ne pas dépasser")
    active = models.BooleanField("règle active", default=True)

    class Meta:
        verbose_name = "règle d'analyse"
        verbose_name_plural = "règles d'analyse"
        ordering = ["categorie", "code"]

    def __str__(self):
        return f"{self.code} (seuil : {self.seuil})"

    # --- opérations du diagramme ---

    def verifier_seuil(self, valeur):
        """verifierSeuil(): boolean — True si la valeur dépasse le seuil."""
        return valeur is not None and valeur > self.seuil

    def est_regle_de_comptage(self):
        """Vrai si la règle compte des occurrences au lieu de surveiller un plafond.

        Convention du projet : **un seuil à 0 désigne une règle de comptage**,
        c'est-à-dire une règle où toute occurrence est déjà un défaut
        (`images_sans_alternative`, `images_non_optimisees`).

        La distinction compte pour la gravité : « dépasser le seuil de 3 fois »
        a un sens pour un poids de page, aucun pour un nombre d'images sans
        texte alternatif. Voir `ProblemeDetecte.evaluer_gravite()`.
        """
        return self.seuil == 0

    def intitule_probleme(self, indicateur):
        """Le titre lisible du problème que cette règle vient de détecter."""
        mesure = nombre_francais(indicateur.valeur)
        if self.est_regle_de_comptage():
            return f"{self.get_categorie_display()} : {mesure} cas relevés"
        return (
            f"{self.get_categorie_display()} : {mesure} {indicateur.unite} "
            f"(maximum {nombre_francais(self.seuil)} {indicateur.unite})"
        )

    def activer(self):
        """activer() : la règle sera prise en compte aux prochaines analyses."""
        self.active = True
        self.save(update_fields=["active"])

    def desactiver(self):
        """desactiver() : on cesse de signaler ce type de problème."""
        self.active = False
        self.save(update_fields=["active"])


class ConseilOptimisation(models.Model):
    """Classe ConseilOptimisation : la fiche « comment corriger ça ».

    Une même fiche sert à toutes les recommandations de sa catégorie :
    on l'écrit une fois, on la réutilise partout.
    """

    titre = models.CharField("titre", max_length=200)
    explication = models.TextField("explication simple")
    solution_technique = models.TextField("solution technique")
    gain_attendu = models.CharField("gain attendu", max_length=200)
    categorie = models.CharField(
        "catégorie", max_length=20, choices=RegleAnalyse.Categorie.choices
    )

    class Meta:
        verbose_name = "conseil d'optimisation"
        verbose_name_plural = "conseils d'optimisation"
        ordering = ["categorie", "titre"]

    def __str__(self):
        return self.titre

    # --- opérations du diagramme ---

    def fournir_conseil(self):
        """fournirConseil(): String — le texte à afficher à l'utilisateur."""
        return f"{self.explication}\n\nÀ faire : {self.solution_technique}"

    def adapter_au_probleme(self, probleme):
        """adapterAuProbleme() : le même conseil, mais en citant l'endroit visé."""
        texte = self.fournir_conseil()
        if probleme.localisation:
            texte += f"\n\nConcerne : {probleme.localisation}"
        return texte

    @classmethod
    def pour_categorie(cls, categorie):
        """Le conseil à rattacher à un problème de cette catégorie (ou None)."""
        return cls.objects.filter(categorie=categorie).first()


# ---------------------------------------------------------------------------
#  L'analyse et ses pièces
# ---------------------------------------------------------------------------


class Analyse(models.Model):
    """Classe Analyse : un passage de l'outil d'audit sur l'URL d'un projet.

    Relation du diagramme : Projet 1 <>-- 0..* Analyse.
    """

    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        EN_COURS = "en_cours", "En cours"
        TERMINEE = "terminee", "Terminée"
        ECHOUEE = "echouee", "Échouée"

    projet = models.ForeignKey(
        Projet,
        on_delete=models.CASCADE,
        related_name="analyses",
        verbose_name="projet",
    )
    date_analyse = models.DateTimeField("date de l'analyse", default=timezone.now)
    statut = models.CharField(
        "statut", max_length=10, choices=Statut.choices, default=Statut.EN_ATTENTE
    )
    score_global = models.FloatField("score global (Green Score)", null=True, blank=True)

    class Meta:
        verbose_name = "analyse"
        verbose_name_plural = "analyses"
        ordering = ["-date_analyse"]

    def __str__(self):
        return f"Analyse de {self.projet.nom} du {self.date_analyse:%d/%m/%Y %H:%M}"

    # --- création ---

    @classmethod
    def creer_pour(cls, projet, configuration=None, contexte=None):
        """Crée l'analyse avec sa configuration et son contexte utilisateur.

        Le diagramme impose à chaque analyse au moins une configuration
        (1..*) et exactement un contexte (1..1) : on les crée donc ici, en
        même temps que l'analyse. `configuration` et `contexte` sont des
        dictionnaires de réglages, par exemple {"mode_analyse": "approfondi"}.
        """
        analyse = cls.objects.create(projet=projet)
        ConfigurationAnalyse.objects.create(analyse=analyse, **(configuration or {}))
        UtilisateurContexte.objects.create(analyse=analyse, **(contexte or {}))
        return analyse

    # --- opérations du diagramme ---

    def collecter_mesures(self):
        """Interroge le site et enregistre ses mesures et ses fichiers.

        C'est le pont avec l'acteur « Outil d'audit web » : le travail réseau
        est fait par `analyses/collecteur.py`, qui ne connaît pas la base.
        C'est ici qu'on lit la configuration choisie par l'utilisateur pour
        décider d'auditer une seule page ou de parcourir le site.
        """
        from .collecteur import collecter, collecter_site, unites_et_categories

        configuration = self.configurations.first()
        plafonds = ConfigurationAnalyse.plafonds_de(configuration)
        options = {
            "inclure_medias": configuration.inclure_medias if configuration else True,
            "inclure_javascript": (
                configuration.inclure_javascript if configuration else True
            ),
            "max_ressources": plafonds["max_ressources"],
        }

        if configuration and configuration.type_audit == (
            ConfigurationAnalyse.TypeAudit.SITE_COMPLET
        ):
            resultat = collecter_site(
                self.projet.url, max_pages=plafonds["max_pages"], **options
            )
        else:
            resultat = collecter(self.projet.url, **options)

        Indicateur.objects.bulk_create(
            Indicateur(analyse=self, **mesure)
            for mesure in unites_et_categories(resultat["mesures"])
        )
        RessourceWeb.objects.bulk_create(
            RessourceWeb(analyse=self, **ressource)
            for ressource in resultat["ressources"]
        )
        return resultat["mesures"]

    def executer_analyse(self, collecter=True):
        """executerAnalyse() : enchaîne les étapes d'une analyse complète.

        Si aucune mesure n'a été saisie à la main, on va d'abord les chercher
        sur le site lui-même. Passer `collecter=False` force le mode manuel.
        """
        self.statut = self.Statut.EN_COURS
        self.save(update_fields=["statut"])
        try:
            if collecter and not self.indicateurs.exists():
                self.collecter_mesures()
            self.detecter_problemes()
            self.calculer_score()
            Rapport.construire_depuis(self)
        except Exception:
            self.statut = self.Statut.ECHOUEE
            self.save(update_fields=["statut"])
            raise
        self.statut = self.Statut.TERMINEE
        self.save(update_fields=["statut"])
        self._prevenir_utilisateur()
        return self

    def detecter_problemes(self):
        """detecterProblemes(): List — confronte chaque indicateur aux règles.

        Pour chaque règle active, on cherche l'indicateur du même nom : si sa
        valeur dépasse le seuil, on crée un problème détecté, puis sa
        recommandation si un conseil existe pour cette catégorie.
        """
        indicateurs = {i.nom: i for i in self.indicateurs.all()}
        problemes = []
        for regle in RegleAnalyse.objects.filter(active=True):
            indicateur = indicateurs.get(regle.code)
            if indicateur is None or not regle.verifier_seuil(indicateur.valeur):
                continue
            probleme = ProblemeDetecte.objects.create(
                analyse=self,
                regle=regle,
                titre=regle.intitule_probleme(indicateur),
                description=regle.description,
                localisation=self.projet.url,
            )
            probleme.evaluer_gravite(indicateur.valeur)
            probleme.proposer_recommandation()
            problemes.append(probleme)
        return problemes

    def calculer_score(self):
        """calculerScore(): float — le Green Score, sur 100.

        On part de 100 et on retire des points selon la gravité de chaque
        problème. Le barème est volontairement regroupé ici : c'est le seul
        endroit à modifier si l'équipe veut une autre pondération.
        """
        penalites = {
            ProblemeDetecte.Gravite.FAIBLE: 2,
            ProblemeDetecte.Gravite.MOYENNE: 5,
            ProblemeDetecte.Gravite.ELEVEE: 10,
            ProblemeDetecte.Gravite.CRITIQUE: 20,
        }
        total = sum(penalites.get(p.gravite, 0) for p in self.problemes.all())
        self.score_global = max(0.0, 100.0 - total)
        self.save(update_fields=["score_global"])
        return self.score_global

    # --- interne ---

    def _prevenir_utilisateur(self):
        """Notifie le propriétaire du projet (cas « Notifier l'utilisateur »)."""
        from comptes.models import Notification

        Notification.envoyer(
            self.projet.utilisateur,
            f"L'analyse de « {self.projet.nom} » est terminée : "
            f"Green Score {self.score_global}/100.",
            type=Notification.Type.ANALYSE_TERMINEE,
        )


class ConfigurationAnalyse(models.Model):
    """Classe ConfigurationAnalyse : les réglages choisis avant de lancer.

    Relation du diagramme : Analyse 1 <>-- 1..* ConfigurationAnalyse.
    """

    class TypeAudit(models.TextChoices):
        PAGE_UNIQUE = "page_unique", "Une seule page"
        SITE_COMPLET = "site_complet", "Site complet"

    class Mode(models.TextChoices):
        RAPIDE = "rapide", "Rapide"
        APPROFONDI = "approfondi", "Approfondi"

    #: Ce que « rapide » et « approfondi » changent concrètement : jusqu'où
    #: l'outil d'audit va avant de s'arrêter. Sans ces plafonds, un gros site
    #: ferait tourner l'analyse pendant plusieurs minutes.
    PLAFONDS = {
        Mode.RAPIDE: {"max_pages": 5, "max_ressources": 30},
        Mode.APPROFONDI: {"max_pages": 15, "max_ressources": 60},
    }

    analyse = models.ForeignKey(
        Analyse,
        on_delete=models.CASCADE,
        related_name="configurations",
        verbose_name="analyse",
    )
    type_audit = models.CharField(
        "type d'audit",
        max_length=15,
        choices=TypeAudit.choices,
        default=TypeAudit.PAGE_UNIQUE,
    )
    inclure_medias = models.BooleanField("inclure les images et vidéos", default=True)
    inclure_javascript = models.BooleanField("inclure le JavaScript", default=True)
    mode_analyse = models.CharField(
        "mode d'analyse", max_length=12, choices=Mode.choices, default=Mode.RAPIDE
    )

    class Meta:
        verbose_name = "configuration d'analyse"
        verbose_name_plural = "configurations d'analyse"

    def __str__(self):
        return f"{self.get_type_audit_display()} / {self.get_mode_analyse_display()}"

    # --- opérations du diagramme ---

    @classmethod
    def plafonds_de(cls, configuration):
        """Les limites de l'audit, même si aucune configuration n'existe."""
        if configuration is None:
            return cls.PLAFONDS[cls.Mode.RAPIDE]
        return cls.PLAFONDS.get(configuration.mode_analyse, cls.PLAFONDS[cls.Mode.RAPIDE])

    def valider_configuration(self):
        """validerConfiguration(): boolean — un audit qui ne mesure rien n'a pas de sens."""
        return self.inclure_medias or self.inclure_javascript

    def modifier_parametres(self, **parametres):
        """modifierParametres() : change les réglages avant exécution."""
        for champ, valeur in parametres.items():
            setattr(self, champ, valeur)
        self.save()
        return self


class UtilisateurContexte(models.Model):
    """Classe UtilisateurContexte : dans quelles conditions on simule la visite.

    C'est le point fort du projet pour l'Afrique : un site « léger » sur
    fibre peut rester inutilisable sur un téléphone d'entrée de gamme en 3G.
    Relation du diagramme : Analyse 1 <>-- 1 UtilisateurContexte.
    """

    class Appareil(models.TextChoices):
        MOBILE_BAS = "mobile_bas", "Téléphone d'entrée de gamme"
        MOBILE_HAUT = "mobile_haut", "Téléphone récent"
        ORDINATEUR = "ordinateur", "Ordinateur"

    class Connexion(models.TextChoices):
        G2 = "2g", "2G"
        G3 = "3g", "3G"
        G4 = "4g", "4G"
        FIBRE = "fibre", "Fibre / ADSL"

    class Forfait(models.TextChoices):
        LIMITE = "limite", "Forfait limité (quelques Mo)"
        MOYEN = "moyen", "Forfait moyen"
        ILLIMITE = "illimite", "Illimité"

    #: Poids de page (en Ko) au-delà duquel la visite devient pénible, par connexion.
    PLAFONDS_KO = {
        Connexion.G2: 300,
        Connexion.G3: 800,
        Connexion.G4: 2000,
        Connexion.FIBRE: 5000,
    }

    analyse = models.OneToOneField(
        Analyse,
        on_delete=models.CASCADE,
        related_name="contexte",
        verbose_name="analyse",
    )
    type_appareil = models.CharField(
        "type d'appareil",
        max_length=12,
        choices=Appareil.choices,
        default=Appareil.MOBILE_BAS,
    )
    qualite_connexion = models.CharField(
        "qualité de connexion",
        max_length=6,
        choices=Connexion.choices,
        default=Connexion.G3,
    )
    forfait_data = models.CharField(
        "forfait data", max_length=10, choices=Forfait.choices, default=Forfait.LIMITE
    )

    class Meta:
        verbose_name = "contexte utilisateur"
        verbose_name_plural = "contextes utilisateur"

    def __str__(self):
        return (
            f"{self.get_type_appareil_display()} "
            f"en {self.get_qualite_connexion_display()}"
        )

    # --- opérations du diagramme ---

    def evaluer_compatibilite(self):
        """evaluerCompatibilite(): boolean — le site passe-t-il dans ce contexte ?

        Renvoie None tant qu'aucun rapport n'a chiffré le poids de la page.
        """
        rapport = getattr(self.analyse, "rapport", None)
        if rapport is None or rapport.poids_total is None:
            return None
        return rapport.poids_total <= self.PLAFONDS_KO[self.qualite_connexion]

    def proposer_optimisation(self):
        """proposerOptimisation() : la phrase à afficher sous le score."""
        compatible = self.evaluer_compatibilite()
        if compatible is None:
            return "Lancez une analyse pour connaître la compatibilité."
        if compatible:
            return "Le site reste utilisable dans ce contexte."
        plafond = self.PLAFONDS_KO[self.qualite_connexion]
        return (
            f"Trop lourd pour ce contexte : visez moins de {plafond} Ko "
            f"en {self.get_qualite_connexion_display()}."
        )


class Indicateur(models.Model):
    """Classe Indicateur : une métrique mesurée pendant l'analyse.

    Exemples : poids_total = 1450 Ko, nombre_requetes = 87, temps_chargement = 6.2 s.
    Relation du diagramme : Analyse 1 <>-- 1..* Indicateur.
    """

    analyse = models.ForeignKey(
        Analyse,
        on_delete=models.CASCADE,
        related_name="indicateurs",
        verbose_name="analyse",
    )
    nom = models.SlugField("nom de l'indicateur", max_length=60)
    valeur = models.FloatField("valeur mesurée")
    unite = models.CharField("unité", max_length=20)
    categorie = models.CharField(
        "catégorie", max_length=20, choices=RegleAnalyse.Categorie.choices
    )

    class Meta:
        verbose_name = "indicateur"
        verbose_name_plural = "indicateurs"
        ordering = ["categorie", "nom"]
        constraints = [
            models.UniqueConstraint(
                fields=["analyse", "nom"], name="un_indicateur_par_nom_et_analyse"
            )
        ]

    def __str__(self):
        return f"{self.nom} = {self.valeur} {self.unite}"

    # --- opérations du diagramme ---

    def mesurer(self):
        """mesurer(): float — la valeur relevée par l'outil d'audit."""
        return self.valeur

    def evaluer(self):
        """evaluer() : les règles actives que cette valeur fait dépasser."""
        return [
            regle
            for regle in RegleAnalyse.objects.filter(active=True, code=self.nom)
            if regle.verifier_seuil(self.valeur)
        ]


class RessourceWeb(models.Model):
    """Classe RessourceWeb : un fichier que le navigateur a dû télécharger.

    Relations du diagramme :
      - Analyse 1 <>-- 0..* RessourceWeb
      - RessourceWeb 0..1 -- 0..* ProblemeDetecte
    """

    class Type(models.TextChoices):
        IMAGE = "image", "Image"
        SCRIPT = "script", "Script JavaScript"
        STYLE = "style", "Feuille de style"
        POLICE = "police", "Police de caractères"
        VIDEO = "video", "Vidéo"
        HTML = "html", "Document HTML"
        AUTRE = "autre", "Autre"

    #: Au-dessus de cette taille (en Ko), le fichier est jugé optimisable.
    SEUILS_KO = {Type.IMAGE: 150, Type.SCRIPT: 100, Type.STYLE: 50, Type.VIDEO: 1000}

    analyse = models.ForeignKey(
        Analyse,
        on_delete=models.CASCADE,
        related_name="ressources",
        verbose_name="analyse",
    )
    url = models.URLField("URL de la ressource", max_length=1000)
    type = models.CharField("type", max_length=10, choices=Type.choices)
    taille = models.FloatField("taille (Ko)")
    optimisable = models.BooleanField("optimisable", default=False)

    class Meta:
        verbose_name = "ressource web"
        verbose_name_plural = "ressources web"
        ordering = ["-taille"]

    def __str__(self):
        return f"{self.get_type_display()} — {self.taille} Ko"

    # --- opérations du diagramme ---

    def calculer_poids(self):
        """calculerPoids(): float — la part de cette ressource dans le poids total (%)."""
        total = self.analyse.ressources.aggregate(t=models.Sum("taille"))["t"] or 0
        if not total:
            return 0.0
        return round(self.taille * 100 / total, 2)

    def verifier_optimisation(self):
        """verifierOptimisation(): boolean — ce fichier peut-il être allégé ?"""
        self.optimisable = self.taille > self.SEUILS_KO.get(self.type, 200)
        self.save(update_fields=["optimisable"])
        return self.optimisable


# ---------------------------------------------------------------------------
#  Ce que l'analyse révèle : problèmes et recommandations
# ---------------------------------------------------------------------------


class ProblemeDetecte(models.Model):
    """Classe ProblemeDetecte : une règle dépassée, à un endroit précis.

    Relations du diagramme :
      - Analyse 1 <>-- 0..* ProblemeDetecte
      - ProblemeDetecte 0..* -- 1 RegleAnalyse
      - RessourceWeb 0..1 -- 0..* ProblemeDetecte
    """

    class Gravite(models.TextChoices):
        FAIBLE = "faible", "Faible"
        MOYENNE = "moyenne", "Moyenne"
        ELEVEE = "elevee", "Élevée"
        CRITIQUE = "critique", "Critique"

    class Statut(models.TextChoices):
        OUVERT = "ouvert", "Ouvert"
        EN_COURS = "en_cours", "En cours de correction"
        CORRIGE = "corrige", "Corrigé"
        IGNORE = "ignore", "Ignoré"

    analyse = models.ForeignKey(
        Analyse,
        on_delete=models.CASCADE,
        related_name="problemes",
        verbose_name="analyse",
    )
    regle = models.ForeignKey(
        RegleAnalyse,
        on_delete=models.PROTECT,
        related_name="problemes",
        verbose_name="règle enfreinte",
    )
    ressource = models.ForeignKey(
        RessourceWeb,
        on_delete=models.SET_NULL,
        related_name="problemes",
        verbose_name="ressource concernée",
        null=True,
        blank=True,
    )
    titre = models.CharField("titre", max_length=200)
    description = models.TextField("description")
    gravite = models.CharField(
        "gravité", max_length=10, choices=Gravite.choices, default=Gravite.MOYENNE
    )
    localisation = models.CharField("localisation", max_length=500, blank=True)
    statut = models.CharField(
        "statut", max_length=10, choices=Statut.choices, default=Statut.OUVERT
    )

    class Meta:
        verbose_name = "problème détecté"
        verbose_name_plural = "problèmes détectés"
        ordering = ["gravite", "titre"]

    def __str__(self):
        return f"{self.titre} ({self.get_gravite_display()})"

    # --- opérations du diagramme ---

    #: Règle de plafond : on juge le rapport « valeur mesurée / seuil ».
    #: Une page de 1500 Ko pour un maximum de 500 Ko dépasse de 3 fois.
    PALIERS_DEPASSEMENT = [
        (3, Gravite.CRITIQUE),
        (2, Gravite.ELEVEE),
        (1.5, Gravite.MOYENNE),
    ]

    #: Règle de comptage (seuil 0) : on juge le nombre d'occurrences.
    #: Deux images sans texte alternatif, c'est un oubli ; vingt, c'est que le
    #: site a été construit sans y penser du tout.
    PALIERS_COMPTAGE = [
        (20, Gravite.CRITIQUE),
        (10, Gravite.ELEVEE),
        (3, Gravite.MOYENNE),
    ]

    def evaluer_gravite(self, valeur_mesuree):
        """evaluerGravite(): String — la gravité dépend de la nature de la règle.

        Deux barèmes, parce que les deux sortes de règles ne se mesurent pas
        pareil (voir `RegleAnalyse.est_regle_de_comptage()`) :

        - règle de plafond : combien de fois on dépasse le seuil ;
        - règle de comptage : combien de cas ont été relevés.

        Sans cette distinction, 3 images sans texte alternatif ressortaient
        « Critique », au même niveau qu'une page quatre fois trop lourde.
        """
        if self.regle.est_regle_de_comptage():
            paliers, mesure = self.PALIERS_COMPTAGE, valeur_mesuree
        else:
            paliers, mesure = self.PALIERS_DEPASSEMENT, valeur_mesuree / self.regle.seuil

        self.gravite = next(
            (gravite for minimum, gravite in paliers if mesure >= minimum),
            self.Gravite.FAIBLE,
        )
        self.save(update_fields=["gravite"])
        return self.gravite

    def changer_statut(self, statut):
        """changerStatut() : le développeur suit la correction."""
        self.statut = statut
        self.save(update_fields=["statut"])
        return self.statut

    def proposer_recommandation(self):
        """Crée la recommandation attachée à ce problème (si un conseil existe).

        Le diagramme impose un conseil par recommandation : sans fiche conseil
        pour cette catégorie, on ne crée rien.
        """
        conseil = ConseilOptimisation.pour_categorie(self.regle.categorie)
        if conseil is None:
            return None
        return Recommandation.objects.create(
            probleme=self,
            conseil=conseil,
            titre=conseil.titre,
            description=conseil.adapter_au_probleme(self),
            priorite=Recommandation.PRIORITE_PAR_GRAVITE[self.gravite],
            categorie=self.regle.categorie,
        )


class Recommandation(models.Model):
    """Classe Recommandation : ce que l'utilisateur doit faire, ici et maintenant.

    Relations du diagramme :
      - ProblemeDetecte 1 <>-- 1..* Recommandation
      - Recommandation 0..* -- 1 ConseilOptimisation
    """

    class Priorite(models.TextChoices):
        BASSE = "basse", "Basse"
        MOYENNE = "moyenne", "Moyenne"
        HAUTE = "haute", "Haute"
        URGENTE = "urgente", "Urgente"

    class Statut(models.TextChoices):
        A_FAIRE = "a_faire", "À faire"
        FAITE = "faite", "Faite"
        REPORTEE = "reportee", "Reportée"

    #: Une recommandation hérite de l'urgence de son problème.
    PRIORITE_PAR_GRAVITE = {
        ProblemeDetecte.Gravite.FAIBLE: Priorite.BASSE,
        ProblemeDetecte.Gravite.MOYENNE: Priorite.MOYENNE,
        ProblemeDetecte.Gravite.ELEVEE: Priorite.HAUTE,
        ProblemeDetecte.Gravite.CRITIQUE: Priorite.URGENTE,
    }

    probleme = models.ForeignKey(
        ProblemeDetecte,
        on_delete=models.CASCADE,
        related_name="recommandations",
        verbose_name="problème détecté",
    )
    conseil = models.ForeignKey(
        ConseilOptimisation,
        on_delete=models.PROTECT,
        related_name="recommandations",
        verbose_name="conseil appliqué",
    )
    titre = models.CharField("titre", max_length=200)
    description = models.TextField("description")
    priorite = models.CharField(
        "priorité", max_length=10, choices=Priorite.choices, default=Priorite.MOYENNE
    )
    categorie = models.CharField(
        "catégorie", max_length=20, choices=RegleAnalyse.Categorie.choices
    )
    statut = models.CharField(
        "statut", max_length=10, choices=Statut.choices, default=Statut.A_FAIRE
    )

    class Meta:
        verbose_name = "recommandation"
        verbose_name_plural = "recommandations"
        ordering = ["priorite", "titre"]

    def __str__(self):
        return f"{self.titre} [{self.get_priorite_display()}]"

    # --- opérations du diagramme ---

    def afficher(self):
        """afficher() : le bloc d'informations prêt pour le gabarit HTML."""
        return {
            "titre": self.titre,
            "priorite": self.get_priorite_display(),
            "categorie": self.get_categorie_display(),
            "description": self.description,
            "gain_attendu": self.conseil.gain_attendu,
        }

    def marquer_comme_faite(self):
        """marquerCommeFaite() : la reco est traitée, le problème suit."""
        self.statut = self.Statut.FAITE
        self.save(update_fields=["statut"])
        if not self.probleme.recommandations.exclude(statut=self.Statut.FAITE).exists():
            self.probleme.changer_statut(ProblemeDetecte.Statut.CORRIGE)
        return self


# ---------------------------------------------------------------------------
#  Ce qu'on en sort : rapport, partage, comparaison
# ---------------------------------------------------------------------------


class Rapport(models.Model):
    """Classe Rapport : la synthèse chiffrée d'une analyse.

    Relation du diagramme : Analyse 1 <>-- 1 Rapport.
    Les champs reprennent les grandeurs clés de la sobriété numérique.
    """

    analyse = models.OneToOneField(
        Analyse,
        on_delete=models.CASCADE,
        related_name="rapport",
        verbose_name="analyse",
    )
    date_generation = models.DateTimeField("date de génération", default=timezone.now)
    green_score = models.FloatField("Green Score (/100)", null=True, blank=True)
    poids_total = models.FloatField("poids total (Ko)", null=True, blank=True)
    nombre_requetes = models.IntegerField("nombre de requêtes", null=True, blank=True)
    temps_chargement = models.FloatField(
        "temps de chargement (s)", null=True, blank=True
    )
    donnees_transferees = models.FloatField(
        "données transférées (Mo)", null=True, blank=True
    )

    class Meta:
        verbose_name = "rapport"
        verbose_name_plural = "rapports"
        ordering = ["-date_generation"]

    def __str__(self):
        return f"Rapport du {self.date_generation:%d/%m/%Y} — {self.green_score}/100"

    # --- construction ---

    @classmethod
    def construire_depuis(cls, analyse):
        """Remplit le rapport à partir des indicateurs de l'analyse.

        Les noms d'indicateurs attendus suivent la convention du projet :
        poids_total, nombre_requetes, temps_chargement, donnees_transferees.
        """
        mesures = dict(analyse.indicateurs.values_list("nom", "valeur"))
        nombre = mesures.get("nombre_requetes")
        rapport, _ = cls.objects.update_or_create(
            analyse=analyse,
            defaults={
                "date_generation": timezone.now(),
                "green_score": analyse.score_global,
                "poids_total": mesures.get("poids_total"),
                # En audit « site complet », la moyenne tombe rarement juste
                # (27,5 requêtes) : on arrondit plutôt que de tronquer.
                "nombre_requetes": round(nombre) if nombre is not None else None,
                "temps_chargement": mesures.get("temps_chargement"),
                "donnees_transferees": mesures.get("donnees_transferees"),
            },
        )
        return rapport

    # --- opérations du diagramme ---

    def exporter_json(self):
        """exporterJSON() : le rapport sous forme de dictionnaire sérialisable."""
        return {
            "projet": self.analyse.projet.nom,
            "url": self.analyse.projet.url,
            "date": self.date_generation.isoformat(),
            "green_score": self.green_score,
            "poids_total_ko": self.poids_total,
            "nombre_requetes": self.nombre_requetes,
            "temps_chargement_s": self.temps_chargement,
            "donnees_transferees_mo": self.donnees_transferees,
            "problemes": [
                {
                    "titre": p.titre,
                    "gravite": p.get_gravite_display(),
                    "recommandations": [r.titre for r in p.recommandations.all()],
                }
                for p in self.analyse.problemes.all()
            ],
        }

    def generer_pdf(self):
        """genererPDF() : à brancher sur la vue d'export (étape suivante).

        Le PDF sera produit depuis le gabarit HTML du rapport ; la méthode
        reste ici pour respecter le diagramme et être remplie ensuite.
        """
        raise NotImplementedError(
            "Export PDF à implémenter avec la vue rapport (étape suivante)."
        )

    def partager(self, duree_jours=30):
        """partager() : crée un lien public temporaire vers ce rapport."""
        return PartageRapport.generer_lien(self, duree_jours=duree_jours)


class PartageRapport(models.Model):
    """Classe PartageRapport : un lien public, limité dans le temps.

    Relation du diagramme : Rapport 1 <>-- 0..* PartageRapport.
    Le jeton remplace l'identifiant dans l'URL : impossible de tomber sur le
    rapport d'un autre projet en changeant un numéro.
    """

    rapport = models.ForeignKey(
        Rapport,
        on_delete=models.CASCADE,
        related_name="partages",
        verbose_name="rapport",
    )
    jeton = models.CharField("jeton du lien", max_length=64, unique=True)
    date_creation = models.DateTimeField("date de création", default=timezone.now)
    date_expiration = models.DateTimeField("date d'expiration")
    actif = models.BooleanField("lien actif", default=True)

    class Meta:
        verbose_name = "partage de rapport"
        verbose_name_plural = "partages de rapport"
        ordering = ["-date_creation"]

    def __str__(self):
        etat = "actif" if self.actif else "révoqué"
        return f"Lien {self.jeton[:8]}… ({etat})"

    # --- opérations du diagramme ---

    @classmethod
    def generer_lien(cls, rapport, duree_jours=30):
        """genererLien(): String — crée le partage et renvoie l'objet porteur du jeton."""
        return cls.objects.create(
            rapport=rapport,
            jeton=secrets.token_urlsafe(32),
            date_expiration=timezone.now() + timezone.timedelta(days=duree_jours),
        )

    def revoquer_lien(self):
        """revoquerLien() : le lien ne fonctionne plus, même avant expiration."""
        self.actif = False
        self.save(update_fields=["actif"])

    def verifier_validite(self):
        """verifierValidite(): boolean — ce lien peut-il encore être ouvert ?"""
        return self.actif and self.date_expiration > timezone.now()


class ComparaisonAnalyse(models.Model):
    """Classe ComparaisonAnalyse : l'avant / après d'une optimisation.

    Le diagramme relie la comparaison à Analyse ; le cas d'utilisation
    « Comparer deux analyses (avant / après) » demande deux analyses : on a
    donc deux liens, analyse_avant et analyse_apres.
    """

    analyse_avant = models.ForeignKey(
        Analyse,
        on_delete=models.CASCADE,
        related_name="comparaisons_comme_avant",
        verbose_name="analyse de départ",
    )
    analyse_apres = models.ForeignKey(
        Analyse,
        on_delete=models.CASCADE,
        related_name="comparaisons_comme_apres",
        verbose_name="analyse d'arrivée",
    )
    date_comparaison = models.DateTimeField("date de comparaison", default=timezone.now)
    score_avant = models.FloatField("score avant", null=True, blank=True)
    score_apres = models.FloatField("score après", null=True, blank=True)
    ecart_poids = models.FloatField("écart de poids (Ko)", null=True, blank=True)
    evolution = models.FloatField("évolution du score (points)", null=True, blank=True)
    taux_amelioration = models.FloatField(
        "taux d'amélioration (%)", null=True, blank=True
    )

    class Meta:
        verbose_name = "comparaison d'analyses"
        verbose_name_plural = "comparaisons d'analyses"
        ordering = ["-date_comparaison"]

    def __str__(self):
        if self.evolution is None:
            return f"Comparaison du {self.date_comparaison:%d/%m/%Y} (non calculée)"
        return f"Comparaison du {self.date_comparaison:%d/%m/%Y} ({self.evolution:+} pts)"

    # --- opérations du diagramme ---

    def comparer_resultats(self):
        """comparerResultats() : relève les deux scores et l'écart de poids."""
        self.score_avant = self.analyse_avant.score_global
        self.score_apres = self.analyse_apres.score_global

        poids_avant = self._poids(self.analyse_avant)
        poids_apres = self._poids(self.analyse_apres)
        if poids_avant is not None and poids_apres is not None:
            self.ecart_poids = round(poids_apres - poids_avant, 2)

        self.calculer_evolution()
        return self

    def calculer_evolution(self):
        """calculerEvolution(): float — combien de points le score a gagné."""
        if self.score_avant is None or self.score_apres is None:
            self.evolution = None
            self.taux_amelioration = None
        else:
            self.evolution = round(self.score_apres - self.score_avant, 2)
            self.taux_amelioration = (
                round(self.evolution * 100 / self.score_avant, 2)
                if self.score_avant
                else None
            )
        self.save()
        return self.evolution

    @staticmethod
    def _poids(analyse):
        """Le poids total relevé par le rapport de cette analyse, s'il existe."""
        rapport = getattr(analyse, "rapport", None)
        return rapport.poids_total if rapport else None
