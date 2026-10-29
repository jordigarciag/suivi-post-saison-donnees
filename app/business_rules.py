# Lecture du fichier — Règles utilisées pour interpréter les acquisitions et préparer les listes du dashboard.
# On part de tableaux déjà chargés. On calcule des catégories, des liens et des filtres ; on ne lance
# pas de lecture du NAS.
#

"""Lecture explicite des données existantes : aucun accès NAS, aucune écriture SQL."""

# On diffère l’évaluation des annotations de type ; cette directive doit rester avant les autres
# imports.
from __future__ import annotations
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On importe re. On reconnaît ou transforme des motifs de texte avec les expressions régulières.
import re
# On importe unicodedata. On peut distinguer les lettres et leurs marques d’accent pour normaliser le
# texte.
import unicodedata
# On importe pandas sous le nom pd. On prépare les tableaux de données et leurs calculs avec pandas.
import pandas as pd
# On rend disponibles _to_bool, boolean, coalesce, no, yes, parse_json, passage_linked depuis
# data_access, pour les appels de ce fichier.
from data_access import _to_bool, boolean, coalesce, no, yes, parse_json, passage_linked


def text(value):
    # On réserve cette branche à value lorsqu’il est de type (dict, list, tuple).
    if isinstance(value, (dict, list, tuple)):
        # On prévoit le cas où value est évalué comme faux, par exemple une valeur vide selon son type.
        if not value:
            # On renvoie un texte vide pour ce cas, plutôt que d’afficher None ou une valeur manquante.
            return ""
        # On prépare une représentation JSON des données ; ce format permettra des relire sans
        # dépendre des objets Python en mémoire.
        return json.dumps(value, ensure_ascii=False, default=str)
    # On vérifie ce cas avant la suite : la valeur reçue vaut None.
    if value is None:
        # On renvoie un texte vide pour ce cas, plutôt que d’afficher None ou une valeur manquante.
        return ""
    # On tente ce bloc et on traite séparément les erreurs prévues : (TypeError, ValueError).
    try:
        # On reconnaît aussi les valeurs manquantes propres à pandas, comme NaN ; elles ne doivent pas
        # s’afficher comme le texte "nan".
        if pd.isna(value):
            # On renvoie un texte vide pour ce cas, plutôt que d’afficher None ou une valeur manquante.
            return ""
    except (TypeError, ValueError):
        # Si pandas ne sait pas traiter cette valeur comme un scalaire, on laisse la conversion
        # textuelle située après le bloc prendre le relais.
        pass
    # On fournit à l’appelant le texte str(value) sans les caractères de bord indiqués, ou sans les
    # espaces de bord par défaut.
    return str(value).strip()


# On prépare une forme comparable du texte en conservant la valeur d’origine ailleurs.
def normal(value):
    # On recompose le texte normalisé sans les marques d’accent. Par exemple, deux écritures qui ne
    # diffèrent que par les accents pourront ainsi être comparées sur la même base.
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", text(value).casefold())
        if not unicodedata.combining(c)
    )


# On complète les acquisitions avec les indicateurs utilisés par les vues du dashboard.
def enrich_acquisitions(aq):
    # On traite à part le tableau aq lorsqu’il est vide.
    if aq.empty:
        # On fournit à l’appelant une copie de aq pour travailler sur cet objet séparément.
        return aq.copy()
    # On garde dans df une copie de aq pour travailler sur cet objet séparément.
    df = aq.copy()
    # On garde dans df['excel_status_display'] les valeurs retenues dans les colonnes candidates par
    # ordre de priorité, puis converties par la fonction indiquée.
    df["excel_status_display"] = coalesce(
        df,
        [
            "recorded_excel_pipeline_status",
            "excel_pipeline_status",
            "extractor_excel_pipeline_status",
        ],
    ).map(text)
    # On garde dans df['excel_perimeter_display'] les valeurs retenues dans les colonnes candidates par
    # ordre de priorité, puis converties par la fonction indiquée.
    df["excel_perimeter_display"] = coalesce(
        df, ["recorded_excel_perimeter", "excel_perimeter", "perimeter"]
    ).map(text)
    # On garde dans df['excel_comment_display'] les valeurs retenues dans les colonnes candidates par
    # ordre de priorité, puis converties par la fonction indiquée.
    df["excel_comment_display"] = coalesce(df, ["excel_comments"]).map(text)
    # On garde dans df['excel_exclusion_display'] les valeurs retenues dans les colonnes candidates par
    # ordre de priorité, puis converties par la fonction indiquée.
    df["excel_exclusion_display"] = coalesce(df, ["excel_exclusion_reason"]).map(text)
    # On garde dans df['decision_reason_display'] les valeurs retenues dans les colonnes candidates par
    # ordre de priorité, puis converties par la fonction indiquée.
    df["decision_reason_display"] = coalesce(df, ["decision_reason"]).map(text)
    # On garde dans df['classification_note_display'] les valeurs retenues dans les colonnes candidates
    # par ordre de priorité, puis converties par la fonction indiquée.
    df["classification_note_display"] = coalesce(df, ["classification_note"]).map(text)
    # On rassemble dans fields les 5 éléments explicitement indiqués, en conservant leur structure.
    fields = [
        (
            "excel_needs_review",
            "Suivi Excel",
            "Le pipeline a marqué les informations du suivi Excel comme nécessitant un examen. Le champ ne précise pas à lui seul la cause.",
        ),
        (
            "excel_acquisition_timestamp_issue",
            "Suivi Excel",
            "Le pipeline a relevé un problème sur la date ou l’heure de l’acquisition dans le suivi Excel.",
        ),
        (
            "raw_evidence_review_required",
            "Contrôle NAS · Brut",
            "Le contrôle du dossier Brut demande un examen. Le motif détaillé est repris lorsqu’il est renseigné.",
        ),
        (
            "processing_decision_required",
            "Règle de traitement du pipeline",
            "La règle de traitement demande une décision ; ce drapeau seul ne permet pas d’affirmer un désaccord Excel / NAS.",
        ),
        (
            "has_technical_error",
            "Contrôle technique du pipeline",
            "Une erreur technique a été enregistrée. Elle ne prouve pas l’absence des fichiers attendus.",
        ),
    ]
    # On prépare une liste distincte pour chacun de ces résultats : origins, reasons, sources,
    # observed, bases. Elles seront alimentées au même rythme dans la boucle.
    origins, reasons, sources, observed, bases = [], [], [], [], []
    # On parcourt df.iterrows() ; (_, row) désigne l’élément courant à chaque passage dans la boucle.
    for _, row in df.iterrows():
        # On prépare une liste distincte pour chacun de ces résultats : origin, reason, source. Elles
        # seront alimentées au même rythme dans la boucle.
        origin, reason, source = [], [], []
        # On garde dans production le résultat de cette comparaison : row['perimeter_normalized']
        # correspond au texte 'Production'.
        production = row["perimeter_normalized"] == "Production"
        # On parcourt les champs ; (flag, where, why) désigne l’élément courant à chaque passage dans
        # la boucle.
        for flag, where, why in fields:
            # Cette branche traite le cas où _to_bool(row.get(flag)) n’est pas exactement la valeur
            # vraie (True) ou flag diffère du texte 'has_technical_error' et la condition production
            # n’est pas remplie.
            if _to_bool(row.get(flag)) is not True or (
                flag != "has_technical_error" and not production
            ):
                # On ignore la suite de ce tour de boucle et on passe à l’élément suivant.
                continue
            # On commence detail avec un texte vide, à compléter uniquement si la suite apporte une
            # information.
            detail = ""
            # On vérifie ce cas avant la suite : flag correspond au texte
            # 'processing_decision_required'.
            if flag == "processing_decision_required":
                # On garde dans category la forme textuelle préparée par text pour
                # row.get('processing_business_category').
                category = text(row.get("processing_business_category"))
                # On vérifie ce cas avant la suite : le texte 'divergence' appartient à
                # normal(category).
                if "divergence" in normal(category):
                    # On utilise ce texte pour where ; il ne dépend pas d’une valeur récupérée ailleurs
                    # à cet endroit.
                    where = "Croisement Excel / NAS"
                # On garde category sous le nom detail ; cette affectation ne copie pas à elle seule un
                # objet mutable.
                detail = category
                # Cette branche traite le cas où le contrôle text(row.get('processing_next_action'))
                # est positif.
                if text(row.get("processing_next_action")):
                    # On ajoute (' ; ' if detail else '') + text(row.get('processing_next_action')) à
                    # detail et on conserve ce nouvel état pour la suite.
                    detail += (" ; " if detail else "") + text(
                        row.get("processing_next_action")
                    )
            # On vérifie ce cas avant la suite : flag correspond au texte 'has_technical_error'.
            elif flag == "has_technical_error":
                # On garde dans detail la forme textuelle préparée par text pour
                # row.get('technical_errors').
                detail = text(row.get("technical_errors"))
            # On vérifie ce cas avant la suite : flag correspond au texte
            # 'raw_evidence_review_required'.
            elif flag == "raw_evidence_review_required":
                # On garde dans detail la forme textuelle préparée par text pour row.get('raw_error').
                detail = text(row.get("raw_error"))
            # On ajoute where à la fin de origin ; les éléments précédents restent conservés.
            origin.append(where)
            # On ajoute why + (' Détail enregistré : ' + detail if detail else '') à la fin de reason ;
            # les éléments précédents restent conservés.
            reason.append(why + (" Détail enregistré : " + detail if detail else ""))
            # On ajoute flag à la fin de source ; les éléments précédents restent conservés.
            source.append(flag)
        # On ajoute ' ; '.join(dict.fromkeys(origin)) à la fin de origins ; les éléments précédents
        # restent conservés.
        origins.append(" ; ".join(dict.fromkeys(origin)))
        # On ajoute '\n'.join(reason) à la fin de reasons ; les éléments précédents restent conservés.
        reasons.append("\n".join(reason))
        # On ajoute ', '.join(source) à la fin de sources ; les éléments précédents restent conservés.
        sources.append(", ".join(source))
        # On garde dans df.at[row.name, 'needs_verification'] la valeur de vérité Python de la source ;
        # ce test ne distingue pas à lui seul tous les états métier.
        df.at[row.name, "needs_verification"] = bool(source)
        # On prépare observations comme liste vide ; on la remplira au fil des opérations suivantes.
        observations = []
        # On parcourt [('found_in_raw_live', 'Dossier Brut'), ('raw_has_full_size_image', 'Imag… ;
        # (name, title) désigne l’élément courant à chaque passage dans la boucle.
        for name, title in [
            ("found_in_raw_live", "Dossier Brut"),
            ("raw_has_full_size_image", "Image full size"),
            ("found_in_processing_live", "Dossier Processing"),
            ("processing_has_webp_images", "Images WEBP"),
            ("found_in_parcel_mapping", "ID dans le mapping des parcelles"),
            ("found_in_passage_mapping", "ID dans le mapping des passages"),
        ]:
            # On garde dans value l’état vrai, faux ou inconnu obtenu par la conversion métier.
            value = _to_bool(row.get(name))
            # On répartit les valeurs renvoyées par {'raw_has_full_size_image': ('présente', 'absente',
            # 'non renseignée'), 'processing_has_webp_images': ('présentes', 'absentes', 'non
            # renseignées')}.get entre (present, absent, unknown) ; leur ordre doit correspondre à
            # celui prévu par cet appel.
            present, absent, unknown = {
                # On renseigne la présence d’une image pleine taille sous la clé
                # 'raw_has_full_size_image'.
                "raw_has_full_size_image": ("présente", "absente", "non renseignée"),
                # On renseigne la présence d’images WEBP sous la clé 'processing_has_webp_images'.
                "processing_has_webp_images": (
                    "présentes",
                    "absentes",
                    "non renseignées",
                ),
            }.get(name, ("présent", "absent", "non renseigné"))
            # On ajoute title + ' : ' + (present if value is True else absent if value is False else
            # unknown) à la fin de observations ; les éléments précédents restent conservés.
            observations.append(
                title
                + " : "
                + (present if value is True else absent if value is False else unknown)
            )
        # Presentation only. Keep recorded statuses and make control errors visible
        # alongside them; do not change eligibility or missing/unknown masks.
        for field, title in [
            ("raw_error", "Erreur de contrôle Brut"),
            ("processing_error", "Erreur de contrôle Processing"),
            ("technical_errors", "Erreur technique enregistrée"),
        ]:
            # On garde dans detail la forme textuelle préparée par text pour row.get(field).
            detail = text(row.get(field))
            # Cette branche traite le cas où detail est évalué comme vrai et normal(detail) ne figure
            # pas dans {'none', 'nan', 'false', '0', '[]', '{}'}.
            if detail and normal(detail) not in {
                "none",
                "nan",
                "false",
                "0",
                "[]",
                "{}",
            }:
                # On ajoute title + ' : ' + detail à la fin de observations ; les éléments précédents
                # restent conservés.
                observations.append(title + " : " + detail)
        # Cette branche traite le cas où _to_bool(row.get('has_technical_error')) est exactement la
        # valeur vraie (True) et la condition text(row.get('technical_errors')) n’est pas remplie.
        if _to_bool(row.get("has_technical_error")) is True and not text(
            row.get("technical_errors")
        ):
            # On ajoute 'Erreur technique enregistrée : signalée, détail non renseigné' à la fin de
            # observations ; les éléments précédents restent conservés.
            observations.append(
                "Erreur technique enregistrée : signalée, détail non renseigné"
            )
        # On ajoute '\n'.join(observations) à la fin de observed ; les éléments précédents restent
        # conservés.
        observed.append("\n".join(observations))
        # On garde dans src le prochain élément de (f for f in ['perimeter_normalized',
        # 'recorded_excel_perimeter', 'excel_p… ou la valeur de repli indiquée si l’itérateur est
        # épuisé.
        src = next(
            (
                f
                for f in [
                    "perimeter_normalized",
                    "recorded_excel_perimeter",
                    "excel_perimeter",
                    "perimeter",
                ]
                if text(row.get(f))
            ),
            None,
        )
        # perimeter_normalized is itself prepared from the Excel-derived fields.
        basis = (
            "Catégorie "
            + row["perimeter_normalized"]
            + " issue du suivi Excel normalisé."
        )
        # Cette branche traite le cas où le test row['excel_perimeter_display'] est satisfait.
        if row["excel_perimeter_display"]:
            # On ajoute ' Valeur de périmètre conservée : ' + row['excel_perimeter_display'] + '.' à
            # basis et on conserve ce nouvel état pour la suite.
            basis += (
                " Valeur de périmètre conservée : "
                + row["excel_perimeter_display"]
                + "."
            )
        # Cette branche traite le cas où le test row['excel_status_display'] est satisfait.
        if row["excel_status_display"]:
            # On ajoute ' Statut Excel conservé : ' + row['excel_status_display'] + '.' à basis et on
            # conserve ce nouvel état pour la suite.
            basis += " Statut Excel conservé : " + row["excel_status_display"] + "."
        else:
            # On ajoute ' Statut Excel détaillé non renseigné.' à basis et on conserve ce nouvel état
            # pour la suite.
            basis += " Statut Excel détaillé non renseigné."
        # Cette branche traite le cas où le test row['excel_exclusion_display'] est satisfait.
        if row["excel_exclusion_display"]:
            # On ajoute ' Motif d’exclusion conservé : ' + row['excel_exclusion_display'] + '.' à basis
            # et on conserve ce nouvel état pour la suite.
            basis += (
                " Motif d’exclusion conservé : " + row["excel_exclusion_display"] + "."
            )
        # On ajoute basis à la fin de bases ; les éléments précédents restent conservés.
        bases.append(basis)
    # On distribue ces valeurs entre df['review_origin'], df['review_reason'],
    # df['review_source_fields'], dans l’ordre de l’affectation. Chaque nom reçoit son propre élément.
    df["review_origin"], df["review_reason"], df["review_source_fields"] = (
        origins,
        reasons,
        sources,
    )
    # On distribue ces valeurs entre df['nas_observations_display'], df['classification_explanation'],
    # dans l’ordre de l’affectation. Chaque nom reçoit son propre élément.
    df["nas_observations_display"], df["classification_explanation"] = observed, bases
    # On remet le tableau de travail à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return df


# On recherche les champs d’erreur prévus sur une ligne, sans assimiler un inconnu à une erreur
# confirmée.
def row_has_error(row, names):
    # On fournit à l’appelant un booléen indiquant si au moins un élément satisfait le test de
    # (normal(row.get(f)) not in {'', 'none', 'nan', 'false', '0', '[]', '{}'} for f in names).
    return any(
        normal(row.get(f)) not in {"", "none", "nan", "false", "0", "[]", "{}"}
        for f in names
    )


# On repère les lignes qui portent les erreurs recherchées par ce calcul.
def has_error(df, names):
    # On renvoie l’une des deux valeurs selon le test indiqué ; ce choix termine la fonction pour ce
    # cas.
    return (
        df.apply(lambda r: row_has_error(r, names), axis=1).astype(bool)
        if not df.empty
        else pd.Series(False, index=df.index)
    )


# On sélectionne les passages qui appartiennent au périmètre de ce calcul.
def eligible_passages(ps, aq):
    # On traite à part le tableau ps lorsqu’il est vide.
    if ps.empty:
        # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
        return ps.copy(), ps.copy()
    # On choisit la valeur de prod selon ce test : la condition aq.empty n’est pas remplie. Les deux
    # résultats possibles restent définis explicitement ici.
    prod = aq[aq["perimeter_normalized"].eq("Production")] if not aq.empty else aq
    # On prépare une liste distincte pour chacun de ces résultats : eligible, unknown. Elles seront
    # alimentées au même rythme dans la boucle.
    eligible, unknown = [], []
    # On parcourt ps.iterrows() ; (i, row) désigne l’élément courant à chaque passage dans la boucle.
    for i, row in ps.iterrows():
        # On garde dans n la conversion en nombres avec le traitement d’erreur indiqué.
        n = pd.to_numeric(row.get("eligible_acquisitions_count"), errors="coerce")
        # On garde dans category la forme textuelle normalisée utilisée pour les comparaisons.
        category = normal(row.get("passage_business_category"))
        # Cette branche traite le cas où le contrôle pd.notna(n) est positif.
        if pd.notna(n):
            # On ajoute i à la fin de eligible if n > 0 else [] ; les éléments précédents restent
            # conservés.
            (eligible if n > 0 else []).append(i)
        # Cette branche traite le cas où category appartient à {'production', 'prod'} ou le contrôle
        # passage_linked(row, prod) est positif.
        elif category in {"production", "prod"} or passage_linked(row, prod):
            # On ajoute i à la fin de eligible ; les éléments précédents restent conservés.
            eligible.append(i)
        # Cette branche traite le cas où toutes les conditions regroupées ici sont remplies.
        elif (
            "test" not in category
            # On exige aussi que le texte 'hors' ne figure pas dans category.
            and "hors" not in category
            # On exige aussi que le texte 'attente' ne figure pas dans category.
            and "attente" not in category
            # On exige aussi que le texte 'bloqu' ne figure pas dans category.
            and "bloqu" not in category
        ):
            # On ajoute i à la fin de unknown ; les éléments précédents restent conservés.
            unknown.append(i)
    # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
    return ps.loc[eligible].copy(), ps.loc[unknown].copy()


# On rassemble dans FOCUS_SPECS les 10 éléments explicitement indiqués, en conservant leur structure.
FOCUS_SPECS = [
    (
        "raw",
        "Prise en compte à confirmer",
        "acq",
        "Dossier d’acquisition absent du Brut. La liste porte uniquement sur les acquisitions de production connues dans les données enregistrées.",
    ),
    (
        "backup",
        "Sauvegarde à compléter",
        "acq",
        "Dossier Brut présent, mais aucune image full size observée. Les dossiers Brut absents sont comptés séparément dans « Prise en compte ».",
    ),
    (
        "mapping",
        "Rattachement à une parcelle à compléter",
        "acq",
        "Identifiant de l’acquisition non trouvé dans le JSON de mapping des parcelles.",
    ),
    (
        "processing",
        "Traitement à compléter",
        "acq",
        "Dossier Processing absent ou images WEBP absentes explicitement. Un statut non renseigné n’est pas assimilé à une absence.",
    ),
    (
        "link",
        "Rattachement à un passage à compléter",
        "acq",
        "Identifiant de l’acquisition non trouvé dans le mapping des passages. Aucun nombre de passages à créer n’est inventé.",
    ),
    (
        "passage",
        "Passages identifiés dont le dossier est absent",
        "passage",
        "Passages recensés et liés à la production, dont le dossier est explicitement absent selon le contrôle enregistré. La nécessité de le créer reste à confirmer.",
    ),
    (
        "vitimap",
        "Vitimap à produire",
        "passage",
        "Passage lié à la production, dossier présent et GeoJSON Vitimap explicitement absent, sans erreur de contrôle signalée.",
    ),
    (
        "stocks",
        "JSON de stocks à produire",
        "passage",
        "Passage lié à la production, dossier présent et JSON de stocks explicitement absent, sans erreur de contrôle signalée.",
    ),
    (
        "status",
        "Vitiparcel · critère non satisfait, à interpréter",
        "passage",
        "JSON de stocks présent, mais aucun statut non sain détecté. Ce constat n’est pas une preuve qu’un livrable reste à produire ; l’attente métier est à confirmer.",
    ),
    (
        "both",
        "Passages sans Vitimap ni JSON de stocks",
        "passage",
        "Passages liés à la production, dont le dossier est présent, mais le GeoJSON Vitimap et le JSON de stocks sont explicitement absents, sans erreur de contrôle signalée. Ces passages figurent déjà dans les deux listes précédentes. Ne pas additionner les compteurs.",
    ),
]


# On prépare les populations utiles aux listes de points à vérifier.
def focus_sections(aq, ps):
    # On choisit la valeur de prod selon ce test : la condition aq.empty n’est pas remplie. Les deux
    # résultats possibles restent définis explicitement ici.
    prod = (
        aq[aq["perimeter_normalized"].eq("Production")].copy()
        if not aq.empty
        else aq.copy()
    )
    # On répartit les valeurs renvoyées par eligible_passages entre (eligible, unknown_scope) ; leur
    # ordre doit correspondre à celui prévu par cet appel.
    eligible, unknown_scope = eligible_passages(ps, aq)
    # On crée le dictionnaire vide results pour y ranger ensuite les éléments par clé.
    results = {}
    # On parcourt FOCUS_SPECS ; (key, title, grain, rule) désigne l’élément courant à chaque passage
    # dans la boucle.
    for key, title, grain, rule in FOCUS_SPECS:
        # On choisit la valeur de df selon ce test : grain correspond au texte 'acq'. Les deux
        # résultats possibles restent définis explicitement ici.
        df = prod if grain == "acq" else eligible
        # On traite à part le tableau df lorsqu’il est vide.
        if df.empty:
            # On garde dans results[key] un nouveau dictionnaire construit avec les valeurs indiquées.
            results[key] = dict(
                title=title,
                grain=grain,
                rule=rule,
                missing=df.copy(),
                unknown=df.copy(),
                eligible=0,
            )
            # On ignore la suite de ce tour de boucle et on passe à l’élément suivant.
            continue
        # On vérifie ce cas avant la suite : grain correspond au texte 'acq'.
        if grain == "acq":
            # On rassemble dans error_fields les 1 éléments explicitement indiqués, en conservant leur
            # structure.
            error_fields = ["has_technical_error"]
            # On vérifie ce cas avant la suite : la clé de l’élément appartient à {'raw', 'backup'}.
            if key in {"raw", "backup"}:
                # On ajoute ['raw_error'] à error_fields et on conserve ce nouvel état pour la suite.
                error_fields += ["raw_error"]
            # On vérifie ce cas avant la suite : la clé de l’élément correspond au texte
            # 'processing'.
            if key == "processing":
                # On ajoute ['processing_error'] à error_fields et on conserve ce nouvel état pour la
                # suite.
                error_fields += ["processing_error"]
            # On garde dans errors la valeur renvoyée par has_error.
            errors = has_error(df, error_fields)
            # On vérifie ce cas avant la suite : la clé de l’élément correspond au texte 'raw'.
            if key == "raw":
                # On distribue ces valeurs entre missing, known, dans l’ordre de l’affectation. Chaque
                # nom reçoit son propre élément.
                missing, known = (
                    no(df, "found_in_raw_live"),
                    boolean(df, "found_in_raw_live").notna(),
                )
            # On vérifie ce cas avant la suite : la clé de l’élément correspond au texte 'backup'.
            elif key == "backup":
                # On combine ces masques avec & pour construire missing ; les parenthèses gardent les
                # comparaisons regroupées.
                missing = yes(df, "found_in_raw_live") & no(
                    df, "raw_has_full_size_image"
                )
                # On réunit ces masques avec | pour construire known ; les parenthèses gardent les
                # comparaisons regroupées.
                known = no(df, "found_in_raw_live") | (
                    yes(df, "found_in_raw_live")
                    & boolean(df, "raw_has_full_size_image").notna()
                )
            # On vérifie ce cas avant la suite : la clé de l’élément correspond au texte 'mapping'.
            elif key == "mapping":
                # On distribue ces valeurs entre missing, known, dans l’ordre de l’affectation. Chaque
                # nom reçoit son propre élément.
                missing, known = (
                    no(df, "found_in_parcel_mapping"),
                    boolean(df, "found_in_parcel_mapping").notna(),
                )
            # On vérifie ce cas avant la suite : la clé de l’élément correspond au texte 'link'.
            elif key == "link":
                # On distribue ces valeurs entre missing, known, dans l’ordre de l’affectation. Chaque
                # nom reçoit son propre élément.
                missing, known = (
                    no(df, "found_in_passage_mapping"),
                    boolean(df, "found_in_passage_mapping").notna(),
                )
            else:
                # On réunit ces masques avec | pour construire missing ; les parenthèses gardent les
                # comparaisons regroupées.
                missing = no(df, "found_in_processing_live") | no(
                    df, "processing_has_webp_images"
                )
                # On réunit ces masques avec | pour construire known ; les parenthèses gardent les
                # comparaisons regroupées.
                known = missing | (
                    yes(df, "found_in_processing_live")
                    & yes(df, "processing_has_webp_images")
                )
        else:
            # On garde dans errors la valeur renvoyée par has_error.
            errors = has_error(
                df,
                ["passage_error"]
                + (
                    ["vitimap_error"]
                    if key == "vitimap"
                    else ["vitiparcel_error"]
                    if key in {"stocks", "status"}
                    else ["vitimap_error", "vitiparcel_error"]
                ),
            )
            # On garde dans created les valeurs reconnues comme vraies par le helper métier.
            created = yes(df, "passage_created")
            # On vérifie ce cas avant la suite : la clé de l’élément correspond au texte 'passage'.
            if key == "passage":
                # On distribue ces valeurs entre missing, known, dans l’ordre de l’affectation. Chaque
                # nom reçoit son propre élément.
                missing, known = (
                    no(df, "passage_created"),
                    boolean(df, "passage_created").notna(),
                )
            # On vérifie ce cas avant la suite : la clé de l’élément correspond au texte 'vitimap'.
            elif key == "vitimap":
                # On combine ces masques avec & pour construire missing ; les parenthèses gardent les
                # comparaisons regroupées.
                missing = created & no(df, "vitimap_created")
                # On réunit ces masques avec | pour construire known ; les parenthèses gardent les
                # comparaisons regroupées.
                known = no(df, "passage_created") | (
                    created & boolean(df, "vitimap_created").notna()
                )
            # On vérifie ce cas avant la suite : la clé de l’élément correspond au texte 'stocks'.
            elif key == "stocks":
                # On combine ces masques avec & pour construire missing ; les parenthèses gardent les
                # comparaisons regroupées.
                missing = created & no(df, "stocks_json_exists")
                # On réunit ces masques avec | pour construire known ; les parenthèses gardent les
                # comparaisons regroupées.
                known = no(df, "passage_created") | (
                    created & boolean(df, "stocks_json_exists").notna()
                )
            # On vérifie ce cas avant la suite : la clé de l’élément correspond au texte 'status'.
            elif key == "status":
                # On combine ces masques avec & pour construire missing ; les parenthèses gardent les
                # comparaisons regroupées.
                missing = (
                    created
                    & yes(df, "stocks_json_exists")
                    & no(df, "has_non_healthy_status")
                )
                # On réunit ces masques avec | pour construire known ; les parenthèses gardent les
                # comparaisons regroupées.
                known = no(df, "passage_created") | (
                    created
                    & (
                        no(df, "stocks_json_exists")
                        | (
                            yes(df, "stocks_json_exists")
                            & boolean(df, "has_non_healthy_status").notna()
                        )
                    )
                )
            else:
                # On combine ces masques avec & pour construire missing ; les parenthèses gardent les
                # comparaisons regroupées.
                missing = (
                    created & no(df, "vitimap_created") & no(df, "stocks_json_exists")
                )
                # On réunit ces masques avec | pour construire known ; les parenthèses gardent les
                # comparaisons regroupées.
                known = no(df, "passage_created") | (
                    created
                    & boolean(df, "vitimap_created").notna()
                    & boolean(df, "stocks_json_exists").notna()
                )
        # On garde dans missing_df une copie de df[missing & ~errors] pour travailler sur cet objet
        # séparément.
        missing_df = df[missing & ~errors].copy()
        # On garde rule sous le nom missing_df['focus_reason'] ; cette affectation ne copie pas à elle
        # seule un objet mutable.
        missing_df["focus_reason"] = rule
        # On garde dans results[key] un nouveau dictionnaire construit avec les valeurs indiquées.
        results[key] = dict(
            title=title,
            grain=grain,
            rule=rule,
            missing=missing_df,
            unknown=df[~known | errors].copy(),
            eligible=len(df),
        )
    # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
    return results, unknown_scope


def tokens(value):
    """Split explicit multi-name display fields; never split the date in a name."""
    # On garde dans raw la forme textuelle préparée par text pour la valeur reçue.
    raw = text(value)
    # On prévoit le cas où raw est évalué comme faux, par exemple une valeur vide selon son type.
    if not raw:
        # On renvoie ces 0 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
        return []
    # On remet [p.strip() for p in raw.split('|') if p.strip()] à l’appelant ; les étapes suivantes de
    # cette fonction ne sont plus parcourues.
    return [p.strip() for p in raw.split("|") if p.strip()]


# On prépare les liens permettant de retrouver les acquisitions associées.
def acquisition_links(row):
    # On garde dans links le contenu interprété par le lecteur JSON du projet.
    links = parse_json(row.get("passage_links_json"))
    # On prépare result comme liste vide ; on la remplira au fil des opérations suivantes.
    result = []
    # On réserve cette branche à links lorsqu’il est de type list.
    if isinstance(links, list):
        # On parcourt links ; link désigne l’élément courant à chaque passage dans la boucle.
        for link in links:
            # Cette branche traite le cas où link est du type dict et le contrôle
            # text(link.get('parcel_name')) est positif et le contrôle text(link.get('passage_name'))
            # est positif.
            if (
                isinstance(link, dict)
                # On exige aussi que le contrôle text(link.get('parcel_name')) est positif.
                and text(link.get("parcel_name"))
                # On exige aussi que le contrôle text(link.get('passage_name')) est positif.
                and text(link.get("passage_name"))
            ):
                # On ajoute (text(link['parcel_name']), text(link['passage_name'])) à la fin de result
                # ; les éléments précédents restent conservés.
                result.append((text(link["parcel_name"]), text(link["passage_name"])))
    # On distribue ces valeurs entre parcels, passages, dans l’ordre de l’affectation. Chaque nom
    # reçoit son propre élément.
    parcels, passages = tokens(row.get("parcel_name")), tokens(row.get("passage_name"))
    # Equal-length arrays are not assumed to be aligned. Only a one-to-one
    # display field is accepted without explicit JSON relationships.
    if len(parcels) == 1 and len(passages) == 1:
        # On ajoute (parcels[0], passages[0]) à la fin de result ; les éléments précédents restent
        # conservés.
        result.append((parcels[0], passages[0]))
    # On fournit à l’appelant une liste matérialisée à partir de dict.fromkeys(result).
    return list(dict.fromkeys(result))


# On rassemble les noms de parcelles associés aux éléments consultés.
def parcel_names(row):
    # On garde dans result la valeur renvoyée par tokens.
    result = tokens(row.get("parcel_name"))
    # On garde dans values le contenu interprété par le lecteur JSON du projet.
    values = parse_json(row.get("parcel_names_json"))
    # On réserve cette branche à values lorsqu’il est de type list.
    if isinstance(values, list):
        # On parcourt les valeurs ; v désigne l’élément courant à chaque passage dans la boucle.
        for v in values:
            # On réserve cette branche à v lorsqu’il est de type str.
            if isinstance(v, str):
                # On ajoute v à la fin de result ; les éléments précédents restent conservés.
                result.append(v)
            # Cette branche traite le cas où v est du type dict et le contrôle
            # text(v.get('parcel_name')) est positif.
            elif isinstance(v, dict) and text(v.get("parcel_name")):
                # On ajoute text(v['parcel_name']) à la fin de result ; les éléments précédents restent
                # conservés.
                result.append(text(v["parcel_name"]))
    # On ajoute [parcel for parcel, passage in acquisition_links(row)] à result et on conserve ce
    # nouvel état pour la suite.
    result += [parcel for parcel, passage in acquisition_links(row)]
    # On fournit à l’appelant une liste matérialisée à partir de dict.fromkeys(result).
    return list(dict.fromkeys(result))


# On rassemble les éléments consultables dans le catalogue de recherche.
def catalog(aq, ps):
    # On garde dans entries un ensemble vide, qui servira à repérer les valeurs déjà rencontrées.
    entries = set()
    # On parcourt aq.iterrows() ; (_, a) désigne l’élément courant à chaque passage dans la boucle.
    for _, a in aq.iterrows():
        # On distribue ces valeurs entre v, identifier, dans l’ordre de l’affectation. Chaque nom
        # reçoit son propre élément.
        v, identifier = (
            text(a.get("vineyard_name")),
            text(a.get("acquisition_id_normalise")),
        )
        # Cette branche traite le cas où identifier est évalué comme vrai.
        if identifier:
            # On ajoute ('acquisition', v, '', identifier) à entries ; comme il s’agit d’un ensemble,
            # une valeur déjà présente n’est pas comptée deux fois.
            entries.add(("acquisition", v, "", identifier))
        # On parcourt parcel_names(a) ; parcel désigne l’élément courant à chaque passage dans la
        # boucle.
        for parcel in parcel_names(a):
            # On ajoute ('parcel', v, '', parcel) à entries ; comme il s’agit d’un ensemble, une valeur
            # déjà présente n’est pas comptée deux fois.
            entries.add(("parcel", v, "", parcel))
        # On parcourt acquisition_links(a) ; (parcel, passage) désigne l’élément courant à chaque
        # passage dans la boucle.
        for parcel, passage in acquisition_links(a):
            # On ajoute ('passage', v, parcel, passage) à entries ; comme il s’agit d’un ensemble, une
            # valeur déjà présente n’est pas comptée deux fois.
            entries.add(("passage", v, parcel, passage))
    # On parcourt ps.iterrows() ; (_, row) désigne l’élément courant à chaque passage dans la boucle.
    for _, row in ps.iterrows():
        # On distribue ces valeurs entre v, parcel, passage, dans l’ordre de l’affectation. Chaque nom
        # reçoit son propre élément.
        v, parcel, passage = (
            text(row.get("vineyard_name")),
            text(row.get("parcel_name")),
            text(row.get("passage_name")),
        )
        # Cette branche traite le cas où parcel est évalué comme vrai.
        if parcel:
            # On ajoute ('parcel', v, '', parcel) à entries ; comme il s’agit d’un ensemble, une valeur
            # déjà présente n’est pas comptée deux fois.
            entries.add(("parcel", v, "", parcel))
        # Cette branche traite le cas où passage est évalué comme vrai.
        if passage:
            # On ajoute ('passage', v, parcel, passage) à entries ; comme il s’agit d’un ensemble, une
            # valeur déjà présente n’est pas comptée deux fois.
            entries.add(("passage", v, parcel, passage))
    # On prépare rows comme liste vide ; on la remplira au fil des opérations suivantes.
    rows = []
    # On regroupe dans kinds ces champs nommés ; on pourra les retrouver par leur clé plutôt que par
    # leur position.
    kinds = {"acquisition": "Acquisition", "parcel": "Parcelle", "passage": "Passage"}
    # On parcourt sorted(entries) ; (kind, vineyard, parcel, name) désigne l’élément courant à chaque
    # passage dans la boucle.
    for kind, vineyard, parcel, name in sorted(entries):
        # On ajoute {'kind': kind, 'Type': kinds[kind], 'Vignoble': vineyard, 'Parcelle': parcel,
        # 'Identifian… à la fin de rows ; les éléments précédents restent conservés.
        rows.append(
            {
                # On associe la clé 'kind' à cette valeur dans cet objet.
                "kind": kind,
                # On associe la clé 'Type' à cette valeur dans cet objet.
                "Type": kinds[kind],
                # On associe la clé 'Vignoble' à cette valeur dans cet objet.
                "Vignoble": vineyard,
                # On associe la clé 'Parcelle' à cette valeur dans cet objet.
                "Parcelle": parcel,
                # On associe la clé 'Identifiant ou nom' à cette valeur dans cet objet.
                "Identifiant ou nom": name,
                # On associe la clé 'entity_key' à cette valeur dans cet objet.
                "entity_key": json.dumps(
                    # On choisit ici si les caractères accentués doivent être échappés dans le JSON.
                    [kind, vineyard, parcel, name], ensure_ascii=False
                ),
            }
        )
    # On fournit à l’appelant un tableau pandas construit avec les données indiquées.
    return pd.DataFrame(
        rows,
        # On décrit les colonnes à présenter, distinctes des lignes de données.
        columns=[
            "kind",
            "Type",
            "Vignoble",
            "Parcelle",
            "Identifiant ou nom",
            "entity_key",
        ],
    )


# On cherche dans le catalogue préparé, pas directement sur le NAS.
def search_catalog(aq, ps, query, kind="all", vineyard="__ALL__"):
    # On garde dans df la valeur renvoyée par catalog.
    df = catalog(aq, ps)
    # On garde dans words les morceaux de normal(query) séparés selon la règle indiquée.
    words = normal(query).split()
    # On prévoit le cas où words est évalué comme faux, par exemple une valeur vide selon son type.
    if not words:
        # On remet df.iloc[:0] à l’appelant ; les étapes suivantes de cette fonction ne sont plus
        # parcourues.
        return df.iloc[:0]
    # On vérifie ce cas avant la suite : kind diffère du texte 'all'.
    if kind != "all":
        # On sélectionne dans df les éléments désignés par df['kind'].eq(kind) ; df recevra cette
        # sélection.
        df = df[df["kind"].eq(kind)]
    # On vérifie ce cas avant la suite : le domaine concerné diffère du texte '__ALL__'.
    if vineyard != "__ALL__":
        # On sélectionne dans df les éléments désignés par df['Vignoble'].eq(vineyard) ; df recevra
        # cette sélection.
        df = df[df["Vignoble"].eq(vineyard)]
    # On garde dans hay le résultat de la fonction appliquée aux éléments ou à l’axe indiqué de df.
    hay = df.apply(
        lambda r: normal(
            " ".join(
                text(r[c])
                for c in ["Type", "Vignoble", "Parcelle", "Identifiant ou nom"]
            )
        ),
        # On indique l’axe de l’opération : sa valeur distingue le travail sur les lignes ou sur les
        # colonnes.
        axis=1,
    )
    # On remet df[hay.map(lambda h: all((re.search('(?<!\\w)' + re.escape(w) + '(?!\\w)'… à l’appelant
    # ; les étapes suivantes de cette fonction ne sont plus parcourues.
    return df[
        hay.map(
            lambda h: all(
                (re.search(r"(?<!\w)" + re.escape(w) + r"(?!\w)", h) is not None)
                if len(w) <= 2
                else w in h
                for w in words
            )
        )
    ]


# On retrouve les éléments liés à la sélection à partir des tableaux déjà disponibles.
def related(entity_key, aq, ps):
    # On décodu texte JSON en objets Python ; les contrôles de structure viennent ensuite, car un
    # JSON lisible n’est pas forcément un lot valide.
    kind, vineyard, parcel, name = json.loads(entity_key)
    # On choisit la valeur de a selon ce test : la condition aq.empty n’est pas remplie. Les deux
    # résultats possibles restent définis explicitement ici.
    a = aq[aq["vineyard_name"].eq(vineyard)].copy() if not aq.empty else aq.copy()
    # On choisit la valeur de p selon ce test : la condition ps.empty n’est pas remplie. Les deux
    # résultats possibles restent définis explicitement ici.
    p = ps[ps["vineyard_name"].eq(vineyard)].copy() if not ps.empty else ps.copy()
    # On vérifie ce cas avant la suite : kind correspond au texte 'acquisition'.
    if kind == "acquisition":
        # On choisit la valeur de a selon ce test : la condition a.empty n’est pas remplie. Les deux
        # résultats possibles restent définis explicitement ici.
        a = a[a["acquisition_id_normalise"].eq(name)] if not a.empty else a
        # On choisit la valeur de p selon ce test : la condition p.empty n’est pas remplie. Les deux
        # résultats possibles restent définis explicitement ici.
        p = p[p.apply(lambda r: passage_linked(r, a), axis=1)] if not p.empty else p
    # On vérifie ce cas avant la suite : kind correspond au texte 'parcel'.
    elif kind == "parcel":
        # On choisit la valeur de a selon ce test : la condition a.empty n’est pas remplie. Les deux
        # résultats possibles restent définis explicitement ici.
        a = a[a.apply(lambda r: name in parcel_names(r), axis=1)] if not a.empty else a
        # On choisit la valeur de p selon ce test : la condition p.empty n’est pas remplie et le texte
        # 'parcel_name' appartient à p. Les deux résultats possibles restent définis explicitement ici.
        p = (
            p[p["parcel_name"].eq(name)]
            if not p.empty and "parcel_name" in p
            else p.iloc[:0]
        )
    else:
        # On choisit la valeur de p selon ce test : la condition p.empty n’est pas remplie et
        # {'parcel_name', 'passage_name'} ne dépasse pas set(p). Les deux résultats possibles restent
        # définis explicitement ici.
        p = (
            p[p["passage_name"].eq(name) & p["parcel_name"].eq(parcel)]
            if not p.empty and {"parcel_name", "passage_name"} <= set(p)
            else p.iloc[:0]
        )
        # Cette branche traite le cas où la condition a.empty n’est pas remplie.
        if not a.empty:
            # On sélectionne dans a les éléments désignés par a.apply(lambda r: (parcel, name) in
            # acquisition_links(r) or (not p.empty and any((pas… ; a recevra cette sélection.
            a = a[
                a.apply(
                    lambda r: (parcel, name) in acquisition_links(r)
                    or (
                        not p.empty
                        # On exige aussi que au moins un élément satisfait le test indiqué.
                        and any(
                            passage_linked(pr, r.to_frame().T) for _, pr in p.iterrows()
                        )
                    ),
                    # On indique l’axe de l’opération : sa valeur distingue le travail sur les lignes
                    # ou sur les colonnes.
                    axis=1,
                )
            ]
    # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
    return a, p
