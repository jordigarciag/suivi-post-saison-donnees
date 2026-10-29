# Lecture du fichier — Sélection d’un état historique et comparaison de résultats enregistrés.
# On compare des observations datées, pas le NAS en direct. Une donnée absente de l’historique ne
# permet pas de reconstituer ce qui n’a jamais été enregistré.
#

"""Comparaison des états conservés. Lecture seule, sans accès au NAS ni SQL métier.

Le bilan (vignoble, pipeline, rapprochement) est l'unité indivisible. Aucun état
manquant n'est remplacé par une ligne courante. Les changements ne prouvent pas
une création/suppression physique, ni la cause d'une modification.
"""

# On diffère l’évaluation des annotations de type ; cette directive doit rester avant les autres
# imports.
from __future__ import annotations
# On décrit les champs d’un objet de données sans écrire toute sa construction à la main.
from dataclasses import dataclass, field
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On importe math. On utilise les contrôles ou calculs numériques définis dans ce module.
import math
# On importe pandas sous le nom pd. On prépare les tableaux de données et leurs calculs avec pandas.
import pandas as pd
# On rend disponibles _to_bool, _flatten_row, coalesce, format_time, prepare_acquisitions,
# prepare_passages, unique_acquisitions, yes depuis data_access, pour les appels de ce fichier.
from data_access import (
    _to_bool,
    _flatten_row,
    coalesce,
    format_scan_time as format_time,
    prepare_acquisitions,
    prepare_passages,
    unique_acquisitions,
    yes,
)
# On rend disponibles enrich_acquisitions, text depuis business_rules, pour les appels de ce fichier.
from business_rules import enrich_acquisitions, text

# On fixe META à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même réglage.
META = "reconciliation_vineyard_history"
# On regroupe dans HIST ces champs nommés ; on pourra les retrouver par leur clé plutôt que par leur
# position.
HIST = {
    # On associe la clé 'acquisition' à cette valeur dans cet objet.
    "acquisition": "reconciliation_acquisition_history",
    # On associe la clé 'passage' à cette valeur dans cet objet.
    "passage": "reconciliation_passage_history",
    # On associe la clé 'association' à cette valeur dans cet objet.
    "association": "reconciliation_association_history",
}
# On regroupe dans KEYS ces champs nommés ; on pourra les retrouver par leur clé plutôt que par leur
# position.
KEYS = {
    # On associe la clé 'acquisition' à cette valeur dans cet objet.
    "acquisition": ["acquisition_id_normalise"],
    # On associe la clé 'passage' à cette valeur dans cet objet.
    "passage": ["parcel_name", "passage_name"],
    # On associe la clé 'association' à cette valeur dans cet objet.
    "association": ["acquisition_id_normalise", "parcel_name", "passage_name"],
}
# On regroupe dans COUNTS ces champs nommés ; on pourra les retrouver par leur clé plutôt que par leur
# position.
COUNTS = {
    # On associe la clé 'acquisition' à cette valeur dans cet objet.
    "acquisition": "acquisition_count",
    # On associe la clé 'passage' à cette valeur dans cet objet.
    "passage": "passage_count",
    # On associe la clé 'association' à cette valeur dans cet objet.
    "association": "association_count",
}
# On rassemble dans IDENTITY les 3 éléments explicitement indiqués, en conservant leur structure.
IDENTITY = ["vineyard_key", "pipeline_execution_id", "reconciliation_run_id"]
# On rassemble dans BOOLS les 18 éléments explicitement indiqués, en conservant leur structure.
BOOLS = {
    "found_in_raw_live",
    "raw_has_full_size_image",
    "raw_has_full_size_both_sides",
    "found_in_processing_live",
    "processing_has_webp_images",
    "processing_has_webp_both_sides",
    "found_in_parcel_mapping",
    "found_in_passage_mapping",
    "parcel_mapping_consistent",
    "passage_created",
    "vitimap_created",
    "stocks_json_exists",
    "has_non_healthy_status",
    "vitiparcel_technical_criterion_satisfied",
    "treated_technical",
    "passage_outputs_verifiable",
    "has_technical_error",
    "vitiparcel_ready_verifiable",
}
# Explicit whitelist: timestamps, run IDs, source row numbers, filenames and hashes
# do not inflate the business change counters. Nothing from today's category is
# substituted for a stored historical value.
ACQ_FIELDS = [
    ("perimeter_normalized", "Catégorie déduite du suivi Excel", "Excel · catégories"),
    ("excel_status_display", "Statut dans le suivi Excel", "Excel · statuts"),
    ("excel_comment_display", "Commentaire du suivi Excel", "Excel · commentaires"),
    (
        "excel_acquisition_date",
        "Date d’acquisition · Excel",
        "Excel · autres informations",
    ),
    (
        "excel_exclusion_display",
        "Motif d’exclusion · Excel",
        "Excel · autres informations",
    ),
    ("found_in_raw_live", "Dossier Brut", "NAS · constats"),
    ("raw_has_full_size_image", "Image full size", "NAS · constats"),
    (
        "raw_has_full_size_both_sides",
        "Images full size LEFT et RIGHT",
        "NAS · constats",
    ),
    ("found_in_processing_live", "Dossier Processing", "NAS · constats"),
    ("processing_has_webp_images", "Images WEBP", "NAS · constats"),
    ("processing_has_webp_both_sides", "WEBP LEFT et RIGHT", "NAS · constats"),
    ("found_in_parcel_mapping", "ID dans le mapping des parcelles", "Rattachements"),
    ("found_in_passage_mapping", "ID dans le mapping des passages", "Rattachements"),
    ("parcel_mapping_consistent", "Cohérence des mappings", "Rattachements"),
    ("has_technical_error", "Erreur technique signalée", "Contrôles · vérifiabilité"),
    ("technical_errors", "Détail des erreurs techniques", "Contrôles · vérifiabilité"),
    ("raw_error", "Erreur de contrôle Brut", "Contrôles · vérifiabilité"),
    ("processing_error", "Erreur de contrôle Processing", "Contrôles · vérifiabilité"),
    (
        "passage_outputs_verifiable",
        "Sorties de passage vérifiables",
        "Contrôles · vérifiabilité",
    ),
]
# On rassemble dans PASSAGE_FIELDS les 11 éléments explicitement indiqués, en conservant leur
# structure.
PASSAGE_FIELDS = [
    ("passage_created", "Dossier de passage", "NAS · livrables"),
    ("vitimap_created", "Vitimap · GeoJSON", "NAS · livrables"),
    ("stocks_json_exists", "JSON de stocks", "NAS · livrables"),
    ("has_non_healthy_status", "Statut non sain détecté", "NAS · livrables"),
    ("stock_status_values", "Valeurs des statuts de stocks", "NAS · livrables"),
    (
        "vitiparcel_technical_criterion_satisfied",
        "Critère technique Vitiparcel satisfait",
        "NAS · livrables",
    ),
    ("passage_outputs_verifiable", "Sorties vérifiables", "Contrôles · vérifiabilité"),
    (
        "vitiparcel_ready_verifiable",
        "Critère Vitiparcel vérifiable",
        "Contrôles · vérifiabilité",
    ),
    ("passage_error", "Erreur de contrôle du passage", "Contrôles · vérifiabilité"),
    ("vitimap_error", "Erreur de contrôle Vitimap", "Contrôles · vérifiabilité"),
    ("vitiparcel_error", "Erreur de contrôle stocks", "Contrôles · vérifiabilité"),
]
# On rassemble dans DETAIL_COLUMNS les 19 éléments explicitement indiqués, en conservant leur
# structure.
DETAIL_COLUMNS = [
    "Vignoble",
    "Type",
    "Acquisition",
    "Parcelle",
    "Passage",
    "Famille",
    "Information",
    "Avant",
    "Après",
    "Lecture prudente",
    "Observation précédente",
    "Observation récente",
    "Rapprochement précédent",
    "Rapprochement récent",
    "Version Excel précédente",
    "Version Excel récente",
    "Référence précédente",
    "Référence récente",
    "_entity",
]


# On normalise la représentation temporelle utilisée par les comparaisons.
def stamp(value):
    # On fournit à l’appelant la conversion en dates avec les règles indiquées, notamment pour les
    # valeurs invalides.
    return pd.to_datetime(value, utc=True, errors="coerce")


# On prépare une représentation des champs structurés pour les traitements de comparaison.
def flatten(df):
    # On renvoie l’une des deux valeurs selon le test indiqué ; ce choix termine la fonction pour ce
    # cas.
    return (
        pd.DataFrame([_flatten_row(r) for r in df.to_dict("records")])
        if df is not None and not df.empty
        else pd.DataFrame()
    )


# On rassemble les métadonnées des lots historiques disponibles.
def metadata(frames):
    # On garde dans df une copie de frames.get(META, pd.DataFrame()) pour travailler sur cet objet
    # séparément.
    df = frames.get(META, pd.DataFrame()).copy()
    # Cette branche traite le cas où df est un tableau vide ou la condition set(IDENTITY +
    # ['vineyard_name', 'nas_checked_at', 'reconciled_at']) <= set(df) n’est pas remplie.
    if df.empty or not set(
        IDENTITY + ["vineyard_name", "nas_checked_at", "reconciled_at"]
    ) <= set(df):
        # On fournit à l’appelant un tableau pandas construit avec les données indiquées.
        return pd.DataFrame()
    # On garde dans df['_time'] les valeurs de df['reconciled_at'] transformées par la fonction ou la
    # correspondance indiquée.
    df["_time"] = df["reconciled_at"].map(stamp)
    # On garde dans df['_nas_time'] les valeurs de df['nas_checked_at'] transformées par la fonction ou
    # la correspondance indiquée.
    df["_nas_time"] = df["nas_checked_at"].map(stamp)
    # On garde dans df['_loaded'] les valeurs de df.get('reconciliation_loaded_at',
    # df['reconciled_at']) transformées par la fonction ou la correspondance indiquée.
    df["_loaded"] = df.get("reconciliation_loaded_at", df["reconciled_at"]).map(stamp)
    # On garde dans df les valeurs de df après retrait des données manquantes selon les options.
    df = df.dropna(subset=["_time", "_nas_time", *IDENTITY])
    # On retire les doublons selon les colonnes indiquées, pas selon une ressemblance visuelle entre
    # les lignes.
    return df.sort_values(["_time", "_loaded", *IDENTITY]).drop_duplicates(
        IDENTITY, keep="last"
    )


# On prépare l’état de comparaison selon les données disponibles dans ce contexte.
def reference(m):
    # On fournit à l’appelant le texte formé en réunissant les éléments avec ' / ' comme séparateur.
    return " / ".join(text(m.get(k)) for k in IDENTITY)


# On rassemble dans APPROVED_VINEYARDS les 8 éléments explicitement indiqués, en conservant leur
# structure.
APPROVED_VINEYARDS = {
    "DomaineDemoA",
    "DomaineDemoB",
    "DomaineDemoC",
    "DomaineDemoD",
    "DomaineDemoE",
    "DomaineDemoF",
    "DomaineDemoG",
    "DomaineDemoH",
}


def business_metadata(frames):
    """Hide pre-production tests, never delete their stored rows.

    Oct 14 is admitted only for the complete eight-vineyard execution.
    Subsequent partial runs remain visible, with explicit coverage warnings.
    The filter is applied BEFORE a user's vineyard filter.
    """
    # On garde dans df la valeur renvoyée par metadata.
    df = metadata(frames)
    # On traite à part le tableau df lorsqu’il est vide.
    if df.empty:
        # On remet le tableau de travail à l’appelant ; les étapes suivantes de cette fonction ne sont
        # plus parcourues.
        return df
    # On utilise les règles du fuseau demandé, notamment lors des changements d’heure.
    from zoneinfo import ZoneInfo

    # On prépare valid comme liste vide ; on la remplira au fil des opérations suivantes.
    valid = []
    # On parcourt df.groupby('pipeline_execution_id', sort=False) ; (run, group) désigne l’élément
    # courant à chaque passage dans la boucle.
    for run, group in df.groupby("pipeline_execution_id", sort=False):
        # On garde dans local_date la représentation ISO de
        # group['_nas_time'].min().tz_convert(ZoneInfo('Europe/Paris')).da….
        local_date = (
            group["_nas_time"]
            .min()
            .tz_convert(ZoneInfo("Europe/Paris"))
            .date()
            .isoformat()
        )
        # Cette branche traite le cas où local_date est supérieur au texte '2026-10-14' ou toutes les
        # conditions regroupées ici sont remplies.
        if local_date > "2026-10-14" or (
            local_date == "2026-10-14"
            # On exige aussi que group['_nas_time'].min() est au moins égal à
            # stamp('2026-10-14T12:49:00Z').
            and group["_nas_time"].min() >= stamp("2026-10-14T12:49:00Z")
            # On exige aussi que APPROVED_VINEYARDS ne dépasse pas set(group['vineyard_name']).
            and APPROVED_VINEYARDS <= set(group["vineyard_name"])
        ):
            # On ajoute run à la fin de valid ; les éléments précédents restent conservés.
            valid.append(run)
    # On fournit à l’appelant une copie de df[df['pipeline_execution_id'].isin(valid)] pour travailler
    # sur cet objet séparément.
    return df[df["pipeline_execution_id"].isin(valid)].copy()


# On prépare les choix de lots disponibles à partir des observations enregistrées.
def batch_options(frames, vineyard="__ALL__"):
    # On garde dans df les métadonnées métier associées à ces données.
    df = business_metadata(frames)
    # Cette branche traite le cas où le domaine concerné diffère du texte '__ALL__' et la condition
    # df.empty n’est pas remplie.
    if vineyard != "__ALL__" and not df.empty:
        # Keep full execution time ranges even for a vineyard subset.
        runs = set(df.loc[df["vineyard_name"].eq(vineyard), "pipeline_execution_id"])
        # On sélectionne dans df les éléments désignés par df['pipeline_execution_id'].isin(runs) ; df
        # recevra cette sélection.
        df = df[df["pipeline_execution_id"].isin(runs)]
    # On prépare rows comme liste vide ; on la remplira au fil des opérations suivantes.
    rows = []
    # Cette branche traite le cas où la condition df.empty n’est pas remplie.
    if not df.empty:
        # On parcourt df.groupby('pipeline_execution_id', sort=False) ; (run, group) désigne l’élément
        # courant à chaque passage dans la boucle.
        for run, group in df.groupby("pipeline_execution_id", sort=False):
            # On distribue ces valeurs entre start, end, dans l’ordre de l’affectation. Chaque nom
            # reçoit son propre élément.
            start, end = group["_nas_time"].min(), group["_nas_time"].max()
            # On garde dans label le résultat du remplacement demandé sur format_time(start).
            label = format_time(start).replace(" à ", " · ")
            # On vérifie ce cas avant la suite : start diffère de end.
            if start != end:
                # On ajoute '–' + (format_time(end).split(' à ')[-1] if format_time(start, True) ==
                # format_time(… à label et on conserve ce nouvel état pour la suite.
                label += "–" + (
                    format_time(end).split(" à ")[-1]
                    if format_time(start, True) == format_time(end, True)
                    else format_time(end).replace(" à ", " · ")
                )
            # On ajoute dict(value=run, label=label, time=group['_time'].max()) à la fin de rows ; les
            # éléments précédents restent conservés.
            rows.append(dict(value=run, label=label, time=group["_time"].max()))
    # On trie rows sur place avec la règle indiquée ; contrairement à sorted, cette opération modifie
    # la collection existante.
    rows.sort(key=lambda r: (r["time"], str(r["value"])), reverse=True)
    # On crée le dictionnaire vide seen pour y ranger ensuite les éléments par clé.
    seen = {}
    # On parcourt les lignes en gardant aussi sa position dans (i, r) ; le comptage commence à zéro.
    for i, r in enumerate(rows):
        # On récupère le libellé dans r et on le garde dans base pour la suite.
        base = r["label"]
        # On assemble ces deux éléments pour construire seen[base].
        seen[base] = seen.get(base, 0) + 1
        # On vérifie ce cas avant la suite : seen[base] est supérieur à 1.
        if seen[base] > 1:
            # On ajoute f' · exécution {seen[base]}' à r['label'] et on conserve ce nouvel état pour la
            # suite.
            r["label"] += f" · exécution {seen[base]}"
        # On vérifie ce cas avant la suite : i correspond à 0.
        if i == 0:
            # On ajoute ' ⇒ Dernier scan' à r['label'] et on conserve ce nouvel état pour la suite.
            r["label"] += " ⇒ Dernier scan"
    # On remet [{k: r[k] for k in ['label', 'value']} for r in rows] à l’appelant ; les étapes
    # suivantes de cette fonction ne sont plus parcourues.
    return [{k: r[k] for k in ["label", "value"]} for r in rows]


# On vérifie si le bilan actif correspond au dernier état disponible, sans le supposer.
def active_matches_latest(frames):
    # On garde dans options les options de sélection des lots disponibles.
    options = batch_options(frames)
    # On prévoit le cas où options est évalué comme faux, par exemple une valeur vide selon son type.
    if not options:
        # On renvoie False comme résultat explicite de cette branche.
        return False
    # On garde dans latest les métadonnées métier associées à ces données.
    latest = business_metadata(frames)
    # On retire les répétitions selon les colonnes choisies, pas selon une ressemblance visuelle.
    latest = latest[
        latest.pipeline_execution_id.eq(options[0]["value"])
    ].drop_duplicates("vineyard_key", keep="last")
    # On garde dans current le champ 'reconciliation_vineyard_current' de frames avec le repli indiqué
    # si la clé est absente.
    current = frames.get("reconciliation_vineyard_current", pd.DataFrame())
    # Cette branche traite le cas où current est un tableau vide ou la condition set(IDENTITY) <=
    # set(current) n’est pas remplie.
    if current.empty or not set(IDENTITY) <= set(current):
        # On renvoie False comme résultat explicite de cette branche.
        return False
    # On renvoie le booléen obtenu par cette comparaison : set(map(tuple,
    # current[IDENTITY].astype(str).values)) correspond à set(map(tuple,
    # latest[IDENTITY].astype(str).values)).
    return set(map(tuple, current[IDENTITY].astype(str).values)) == set(
        map(tuple, latest[IDENTITY].astype(str).values)
    )


# On prépare les états consultables et leurs libellés.
def snapshot_options(frames):
    # On garde dans options les options de sélection des lots disponibles.
    options = batch_options(frames)
    # Cette branche traite le cas où les options proposées est évalué comme vrai.
    if options:
        # On rassemble dans options les 2 éléments explicitement indiqués, en conservant leur
        # structure.
        options = [dict(options[0], value="__LATEST__"), *options[1:]]
    # On garde dans current le champ 'reconciliation_vineyard_current' de frames avec le repli indiqué
    # si la clé est absente.
    current = frames.get("reconciliation_vineyard_current", pd.DataFrame())
    # On garde dans eligible_active les métadonnées métier associées à ces données.
    eligible_active = business_metadata({META: current})
    # On calcule active_allowed avec ces conditions liées par and ; Python s’arrête dès qu’une valeur
    # est évaluée comme fausse.
    active_allowed = not current.empty and len(eligible_active) == len(current)
    # Cette branche traite le cas où active_allowed est évalué comme vrai et la condition
    # active_matches_latest(frames) n’est pas remplie.
    if active_allowed and not active_matches_latest(frames):
        # Never present mixed active pointers as one artificially dated run.
        options.append(
            {
                # On renseigne le libellé sous la clé 'label'.
                "label": "Bilans actifs · état distinct du dernier scan conservé",
                # On renseigne la valeur reçue sous la clé 'value'.
                "value": "__ACTIVE__",
            }
        )
    # On remet options or [{'label': 'Aucun état disponible', 'value': '__LATEST__'}] à l’appelant ;
    # les étapes suivantes de cette fonction ne sont plus parcourues.
    return options or [{"label": "Aucun état disponible", "value": "__LATEST__"}]


# On sélectionne les lignes correspondant à l’état demandé.
def rows_for(frames, m, kind):
    # On sélectionne dans HIST les éléments désignés par kind ; name recevra cette sélection.
    name = HIST[kind]
    # Une vue historique manquante ne doit pas être remplacée par les données d’aujourd’hui.
    if name not in frames:
        # On interrompt cette branche avec ValueError.
        raise ValueError(
            f"Vue {name} indisponible ; aucun état courant ne la remplace."
        )
    # On sélectionne dans frames les éléments désignés par name ; df recevra cette sélection.
    df = frames[name]
    # On traite à part le tableau df lorsqu’il est vide.
    if df.empty:
        # On garde dans result une copie de df pour travailler sur cet objet séparément.
        result = df.copy()
    # Cette branche traite le cas où la condition set(IDENTITY) <= set(df) n’est pas remplie.
    elif not set(IDENTITY) <= set(df):
        # On interrompt cette branche avec ValueError.
        raise ValueError(f"Identifiants de provenance incomplets dans {name}.")
    else:
        # On garde dans mask une série pandas avec les valeurs et l’index fournis.
        mask = pd.Series(True, index=df.index)
        # On parcourt IDENTITY ; k désigne l’élément courant à chaque passage dans la boucle.
        for k in IDENTITY:
            # On met à jour mask avec cette opération, plutôt que créer une variable séparée.
            mask &= df[k].astype(str).eq(str(m[k]))
        # On garde dans result une copie de df[mask] pour travailler sur cet objet séparément.
        result = df[mask].copy()
    # On garde dans result la valeur renvoyée par flatten.
    result = flatten(result)
    # On garde dans n la conversion en nombres avec le traitement d’erreur indiqué.
    n = pd.to_numeric(m.get(COUNTS[kind]), errors="coerce")
    # On garde dans declared la conversion en nombres avec le traitement d’erreur indiqué.
    declared = pd.to_numeric(m.get("declared_" + COUNTS[kind]), errors="coerce")
    # Le volume relu ne correspond pas au volume annoncé pour cet état historique.
    if pd.isna(n) or len(result) != n or (pd.notna(declared) and n != declared):
        # On interrompt cette branche avec ValueError.
        raise ValueError(
            f"{kind} : nombre de lignes historiques incohérent ou non documenté."
        )
    # Le lot ne confirme pas que toutes ses lignes sont présentes ; on ne peut pas le comparer comme
    # un état complet.
    if _to_bool(m.get("row_counts_match_declared")) is not True:
        # On interrompt cette branche avec ValueError : 'Le bilan historique ne confirme pas la
        # complétude de ses lignes.'.
        raise ValueError(
            "Le bilan historique ne confirme pas la complétude de ses lignes."
        )
    # Cette branche traite le cas où la condition result.empty n’est pas remplie.
    if not result.empty:
        # Cette branche traite le cas où la condition set(KEYS[kind]) <= set(result) n’est pas remplie.
        if not set(KEYS[kind]) <= set(result):
            # On interrompt cette branche avec ValueError.
            raise ValueError(f"Clés métier absentes pour {kind}.")
        # On doit résoudre ces doublons avant de compter ou de rapprocher les lignes.
        if result[KEYS[kind]].isna().any().any() or result.duplicated(KEYS[kind]).any():
            # On interrompt cette branche avec ValueError.
            raise ValueError(f"Clés métier absentes ou dupliquées pour {kind}.")
    # On vérifie ce cas avant la suite : kind correspond au texte 'acquisition'.
    if kind == "acquisition":
        # On garde dans result les acquisitions complétées avec les champs calculés de présentation.
        result = enrich_acquisitions(unique_acquisitions(prepare_acquisitions(result)))
    # On vérifie ce cas avant la suite : kind correspond au texte 'passage'.
    elif kind == "passage":
        # On garde dans result les passages préparés pour leur lecture dans le dashboard.
        result = prepare_passages(result)
    # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette fonction ne
    # sont plus parcourues.
    return result


# On rattache les liens utiles aux lignes de l’état historique reconstruit.
def _attach_links(aq, ps, links):
    # On distribue ces valeurs entre aq, ps, dans l’ordre de l’affectation. Chaque nom reçoit son
    # propre élément.
    aq, ps = aq.copy(), ps.copy()
    # Full exact snapshot associations override display fields; never zip two
    # independent multi-value strings into invented relationships.
    for idx, a in aq.iterrows():
        # On choisit la valeur de linked selon ce test : la condition links.empty n’est pas remplie.
        # Les deux résultats possibles restent définis explicitement ici.
        linked = (
            links[links["acquisition_id_normalise"].eq(a["acquisition_id_normalise"])]
            if not links.empty
            else links
        )
        # On choisit la valeur de pairs selon ce test : la condition linked.empty n’est pas remplie.
        # Les deux résultats possibles restent définis explicitement ici.
        pairs = (
            linked[["parcel_name", "passage_name"]].drop_duplicates().to_dict("records")
            if not linked.empty
            else []
        )
        # On prépare une représentation JSON ; les options ci-dessous fixent les détails de
        # sérialisation.
        aq.at[idx, "passage_links_json"] = json.dumps(pairs, ensure_ascii=False)
        # Cette branche traite le cas où pairs est évalué comme vrai.
        if pairs:
            # On garde dans aq.at[idx, 'parcel_name'] le texte formé en réunissant les éléments avec '
            # | ' comme séparateur.
            aq.at[idx, "parcel_name"] = " | ".join(
                sorted(
                    {text(p["parcel_name"]) for p in pairs if text(p["parcel_name"])}
                )
            )
            # On garde dans aq.at[idx, 'passage_name'] le texte formé en réunissant les éléments avec '
            # | ' comme séparateur.
            aq.at[idx, "passage_name"] = " | ".join(
                sorted(
                    {text(p["passage_name"]) for p in pairs if text(p["passage_name"])}
                )
            )
    # On parcourt ps.iterrows() ; (idx, p) désigne l’élément courant à chaque passage dans la boucle.
    for idx, p in ps.iterrows():
        # On choisit la valeur de linked selon ce test : la condition links.empty n’est pas remplie.
        # Les deux résultats possibles restent définis explicitement ici.
        linked = (
            links[
                links["parcel_name"].eq(p["parcel_name"])
                & links["passage_name"].eq(p["passage_name"])
            ]
            if not links.empty
            else links
        )
        # On choisit la valeur de ids selon ce test : la condition linked.empty n’est pas remplie. Les
        # deux résultats possibles restent définis explicitement ici.
        ids = (
            sorted(set(linked["acquisition_id_normalise"])) if not linked.empty else []
        )
        # On prépare une représentation JSON ; les options ci-dessous fixent les détails de
        # sérialisation.
        ps.at[idx, "acquisition_ids_json"] = json.dumps(ids, ensure_ascii=False)
    # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
    return aq, ps


# On reconstruit les tableaux consultables pour l’état historique demandé.
def historical_frames(frames, run):
    """Exact selected execution, not an as-of reconstruction of mutable pointers."""
    # On garde dans meta les métadonnées métier associées à ces données.
    meta = business_metadata(frames)
    # On choisit la valeur de chosen selon ce test : la condition meta.empty n’est pas remplie. Les
    # deux résultats possibles restent définis explicitement ici.
    chosen = meta[meta["pipeline_execution_id"].eq(run)] if not meta.empty else meta
    # Si cet état n’est pas disponible, on ne le remplace pas par le bilan courant.
    if chosen.empty:
        # On interrompt cette branche avec ValueError : 'Aucun bilan historique disponible pour cette
        # exécution.'.
        raise ValueError("Aucun bilan historique disponible pour cette exécution.")
    # On retire les répétitions selon les colonnes choisies, pas selon une ressemblance visuelle.
    chosen = chosen.drop_duplicates("vineyard_key", keep="last")
    # On prépare une liste distincte pour chacun de ces résultats : acqs, passages. Elles seront
    # alimentées au même rythme dans la boucle.
    acqs, passages = [], []
    # On parcourt chosen.iterrows() ; (_, m) désigne l’élément courant à chaque passage dans la boucle.
    for _, m in chosen.iterrows():
        # On distribue ces valeurs entre aq, ps, dans l’ordre de l’affectation. Chaque nom reçoit son
        # propre élément.
        aq, ps = rows_for(frames, m, "acquisition"), rows_for(frames, m, "passage")
        # On garde dans links la valeur renvoyée par rows_for.
        links = rows_for(frames, m, "association")
        # On répartit les valeurs renvoyées par _attach_links entre (aq, ps) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        aq, ps = _attach_links(aq, ps, links)
        # On ajoute aq à la fin de acqs ; les éléments précédents restent conservés.
        acqs.append(aq)
        # On ajoute ps à la fin de passages ; les éléments précédents restent conservés.
        passages.append(ps)
    # On garde dans out un nouveau dictionnaire construit avec les valeurs indiquées (la copie reste
    # superficielle).
    out = dict(frames)
    # On complète out avec les valeurs indiquées ; une clé déjà présente prendra la nouvelle valeur
    # fournie.
    out.update(
        reconciliation_acquisition_current=pd.concat(acqs, ignore_index=True),
        reconciliation_passage_current=pd.concat(passages, ignore_index=True),
        reconciliation_vineyard_current=chosen.drop(
            # On décrit les colonnes à présenter, distinctes des lignes de données.
            columns=["_time", "_nas_time", "_loaded"]
        ),
        reconciliation_freshness_current=chosen.drop(
            # On décrit les colonnes à présenter, distinctes des lignes de données.
            columns=["_time", "_nas_time", "_loaded"]
        ),
    )
    # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
    return out, chosen["vineyard_name"].tolist()


# On prépare une forme comparable des valeurs avant de rechercher des différences.
def canon(value, field):
    # On vérifie ce cas avant la suite : field appartient à BOOLS.
    if field in BOOLS:
        # On garde dans boolean l’état vrai, faux ou inconnu obtenu par la conversion métier.
        boolean = _to_bool(value)
        # On renvoie l’une des deux valeurs selon le test indiqué ; ce choix termine la fonction pour
        # ce cas.
        return (
            boolean
            if boolean is not None
            else (("Valeur non reconnue", text(value)) if text(value) else None)
        )
    # On réserve cette branche à value lorsqu’il est de type str.
    if isinstance(value, str):
        # On garde dans raw le texte value sans les caractères de bord indiqués, ou sans les espaces de
        # bord par défaut.
        raw = value.strip()
        # Cette branche traite le cas où raw commence par ('[', '{').
        if raw.startswith(("[", "{")):
            # On tente ce bloc et on traite séparément les erreurs prévues : ValueError.
            try:
                # On décodu texte JSON en objets Python ; les contrôles de structure viennent
                # ensuite, car un JSON lisible n’est pas forcément un lot valide.
                value = json.loads(raw)
            except ValueError:
                # On n’ajoute pas d’action dans cette branche ; le parcours continue après ce bloc.
                pass
    # On réserve cette branche à value lorsqu’il est de type list.
    if isinstance(value, list):
        # On fournit à l’appelant une séquence non modifiable construite à partir de sorted((canon(x,
        # '') for x in value), key=str).
        return tuple(sorted((canon(x, "") for x in value), key=str))
    # On réserve cette branche à value lorsqu’il est de type dict.
    if isinstance(value, dict):
        # On fournit à l’appelant une séquence non modifiable construite à partir de sorted(((str(k),
        # canon(v, '')) for k, v in value.items())).
        return tuple(sorted((str(k), canon(v, "")) for k, v in value.items()))
    # On fournit à l’appelant la forme textuelle préparée par text pour la valeur reçue.
    return text(value)


# On prépare une valeur lisible pour expliquer la différence constatée.
def show(value, field):
    # On vérifie ce cas avant la suite : field appartient à BOOLS.
    if field in BOOLS:
        # On garde dans b l’état vrai, faux ou inconnu obtenu par la conversion métier.
        b = _to_bool(value)
        # On renvoie l’une des deux valeurs selon le test indiqué ; ce choix termine la fonction pour
        # ce cas.
        return (
            "Oui"
            if b is True
            else "Non"
            if b is False
            else (
                "Non reconnu : " + text(value)
                if text(value)
                else "Non renseigné / non reconnu"
            )
        )
    # On remet text(value) or 'Non renseigné' à l’appelant ; les étapes suivantes de cette fonction ne
    # sont plus parcourues.
    return text(value) or "Non renseigné"


@dataclass
class Comparison:
    # On garde dans details la valeur du champ lue avec les règles définies dans ce module.
    details: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=DETAIL_COLUMNS)
    )
    # On garde dans timeline la valeur du champ lue avec les règles définies dans ce module.
    timeline: pd.DataFrame = field(default_factory=pd.DataFrame)
    # On garde dans coverage la valeur du champ lue avec les règles définies dans ce module.
    coverage: pd.DataFrame = field(default_factory=pd.DataFrame)
    # On garde dans messages la valeur du champ lue avec les règles définies dans ce module.
    messages: list[str] = field(default_factory=list)
    # On fixe comparable à 0 pour cette étape.
    comparable: int = 0
    # On fixe expected à 0 pour cette étape.
    expected: int = 0
    # On garde dans examined_entities la valeur du champ lue avec les règles définies dans ce module.
    examined_entities: set[str] = field(default_factory=set)

    # On calcule les compteurs de ce résultat de comparaison.
    def counts(self):
        # On garde self.details sous le nom df ; cette affectation ne copie pas à elle seule un objet
        # mutable.
        df = self.details
        # On traite à part le tableau df lorsqu’il est vide.
        if df.empty:
            # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver
            # chaque information par sa clé.
            return {
                # On renseigne les acquisitions sous la clé 'acquisitions'.
                "acquisitions": 0,
                # On renseigne les passages sous la clé 'passages'.
                "passages": 0,
                # On associe la clé 'comments' à cette valeur dans cet objet.
                "comments": 0,
                # On associe la clé 'processing' à cette valeur dans cet objet.
                "processing": 0,
                # On associe la clé 'relationships' à cette valeur dans cet objet.
                "relationships": 0,
                # On associe la clé 'changed' à cette valeur dans cet objet.
                "changed": 0,
                # On associe la clé 'examined' à cette valeur dans cet objet.
                "examined": self.examined_count(),
                # On associe la clé 'percentage' à cette valeur dans cet objet.
                "percentage": 0.0,
            }
        # On sélectionne dans df les éléments désignés par df['Type'].eq('Acquisition') ; aq recevra
        # cette sélection.
        aq = df[df["Type"].eq("Acquisition")]
        # On sélectionne dans df les éléments désignés par df['Type'].eq('Passage') ; ps recevra cette
        # sélection.
        ps = df[df["Type"].eq("Passage")]
        # On sélectionne dans aq les éléments désignés par aq['Famille'].eq('Excel · commentaires') ;
        # comments recevra cette sélection.
        comments = aq[aq["Famille"].eq("Excel · commentaires")]
        # On sélectionne dans df les éléments désignés par ~df['Famille'].eq('Excel · commentaires') ;
        # processing recevra cette sélection.
        processing = df[~df["Famille"].eq("Excel · commentaires")]
        # On garde dans n le nombre de valeurs distinctes de df['_entity'].
        n = df["_entity"].nunique()
        # On garde dans den la valeur renvoyée par self.examined_count.
        den = self.examined_count()
        # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
        # information par sa clé.
        return {
            # On renseigne les acquisitions sous la clé 'acquisitions'.
            "acquisitions": aq["_entity"].nunique(),
            # On renseigne les passages sous la clé 'passages'.
            "passages": ps["_entity"].nunique(),
            # On associe la clé 'comments' à cette valeur dans cet objet.
            "comments": comments["_entity"].nunique(),
            # On associe la clé 'processing' à cette valeur dans cet objet.
            "processing": processing["_entity"].nunique(),
            # On associe la clé 'relationships' à cette valeur dans cet objet.
            "relationships": df[df["Type"].eq("Rattachement")]["_entity"].nunique(),
            # On associe la clé 'changed' à cette valeur dans cet objet.
            "changed": n,
            # On associe la clé 'examined' à cette valeur dans cet objet.
            "examined": den,
            # On associe la clé 'percentage' à cette valeur dans cet objet.
            "percentage": round(100 * n / den, 1) if den else 0.0,
        }

    # On compte les éléments effectivement examinés dans ce périmètre.
    def examined_count(self):
        # Includes comparable acquisitions/passages + exact association keys;
        # counts shown separately for each grain in coverage, never sum volumes.
        return len(self.examined_entities)

    # On prépare le libellé de synthèse correspondant aux compteurs disponibles.
    def headline(self):
        # On garde dans c la valeur renvoyée par self.counts.
        c = self.counts()
        # Cette branche traite le cas où la condition self.expected n’est pas remplie.
        if not self.expected:
            # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
            return "Comparaison indisponible : il faut au moins deux observations pour un même vignoble."
        # Cette branche traite le cas où la condition self.comparable n’est pas remplie.
        if not self.comparable:
            # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
            return "Comparaison suspendue : données historiques insuffisantes ou incohérentes."
        # On traite à part le tableau self.details lorsqu’il est vide.
        if self.details.empty:
            # On utilise ce texte pour msg ; il ne dépend pas d’une valeur récupérée ailleurs à cet
            # endroit.
            msg = "Aucun changement détecté dans les informations métier comparées."
        else:
            # On prépare msg avec cette expression pour l’utiliser dans la suite du traitement.
            msg = f"{c['acquisitions']} acquisition(s) et {c['passages']} passage(s) présentent un changement."
            # Cette branche traite le cas où le test c['relationships'] est satisfait.
            if c["relationships"]:
                # On ajoute f" {c['relationships']} rattachement(s) modifié(s)." à msg et on conserve
                # ce nouvel état pour la suite.
                msg += f" {c['relationships']} rattachement(s) modifié(s)."
        # On vérifie ce cas avant la suite : self.comparable diffère de self.expected.
        if self.comparable != self.expected:
            # On ajoute ' Comparaison partielle : consulter les limites ci-dessous.' à msg et on
            # conserve ce nouvel état pour la suite.
            msg += " Comparaison partielle : consulter les limites ci-dessous."
        # On remet msg à l’appelant ; les étapes suivantes de cette fonction ne sont plus parcourues.
        return msg


# On compare les états enregistrés sans inventer de mesure pour un état non disponible.
def compare_history(frames, vineyard="__ALL__", selected=None, latest=True):
    # On garde dans meta les métadonnées métier associées à ces données.
    meta = business_metadata(frames)
    # On garde dans result la valeur renvoyée par Comparison.
    result = Comparison()
    # On traite à part le tableau meta lorsqu’il est vide.
    if meta.empty:
        # On ajoute 'Synthèse historique indisponible ; aucun changement ne peut être conclu.' à la fin
        # de result.messages ; les éléments précédents restent conservés.
        result.messages.append(
            "Synthèse historique indisponible ; aucun changement ne peut être conclu."
        )
        # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette fonction
        # ne sont plus parcourues.
        return result
    # Default is the two most recent executions, not two different NAS IDs.
    # A new Excel reconciliation of a reused NAS scan must still be compared.
    runs = (
        [o["value"] for o in batch_options(frames, vineyard)[:2]]
        if latest
        else list(dict.fromkeys(selected or []))
    )
    # On sélectionne dans meta les éléments désignés par meta['pipeline_execution_id'].isin(runs) ;
    # meta recevra cette sélection.
    meta = meta[meta["pipeline_execution_id"].isin(runs)]
    # On choisit la valeur de wanted selon ce test : le domaine concerné correspond au texte
    # '__ALL__'. Les deux résultats possibles restent définis explicitement ici.
    wanted = (
        set(business_metadata(frames)["vineyard_name"])
        if vineyard == "__ALL__"
        else {vineyard}
    )
    # On vérifie ce cas avant la suite : le domaine concerné diffère du texte '__ALL__'.
    if vineyard != "__ALL__":
        # On sélectionne dans meta les éléments désignés par meta['vineyard_name'].eq(vineyard) ; meta
        # recevra cette sélection.
        meta = meta[meta["vineyard_name"].eq(vineyard)]
    # On parcourt sorted(wanted - set(meta['vineyard_name'])) ; missing désigne l’élément courant à
    # chaque passage dans la boucle.
    for missing in sorted(wanted - set(meta["vineyard_name"])):
        # On ajoute len(KEYS) à result.expected et on conserve ce nouvel état pour la suite.
        result.expected += len(KEYS)
        # On ajoute f'{missing} : aucun état dans les exécutions sélectionnées ; non comparé.' à la fin
        # de result.messages ; les éléments précédents restent conservés.
        result.messages.append(
            f"{missing} : aucun état dans les exécutions sélectionnées ; non comparé."
        )
    # On vérifie ce cas avant la suite : len(runs) est inférieur à 2.
    if len(runs) < 2:
        # On ajoute 'Sélectionner au moins deux exécutions pour comparer les données.' à la fin de
        # result.messages ; les éléments précédents restent conservés.
        result.messages.append(
            "Sélectionner au moins deux exécutions pour comparer les données."
        )
        # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette fonction
        # ne sont plus parcourues.
        return result
    # On prépare une liste distincte pour chacun de ces résultats : timeline, coverage, details. Elles
    # seront alimentées au même rythme dans la boucle.
    timeline, coverage, details = [], [], []
    # On parcourt meta.groupby('vineyard_key', sort=True) ; (_, group) désigne l’élément courant à
    # chaque passage dans la boucle.
    for _, group in meta.groupby("vineyard_key", sort=True):
        # On garde dans group les lignes de group triées selon les colonnes indiquées.
        group = group.sort_values(["_time", "_loaded"])
        # On retire les répétitions selon les colonnes choisies, pas selon une ressemblance visuelle.
        group = group.drop_duplicates("pipeline_execution_id", keep="last")
        # On vérifie ce cas avant la suite : len(group) diffère de len(runs).
        if len(group) != len(runs):
            # On ajoute len(KEYS) à result.expected et on conserve ce nouvel état pour la suite.
            result.expected += len(KEYS)
            # On ajoute f"{group.iloc[-1]['vineyard_name']} : certaines exécutions sélectionnées ne
            # couvrent pas… à la fin de result.messages ; les éléments précédents restent conservés.
            result.messages.append(
                f"{group.iloc[-1]['vineyard_name']} : certaines exécutions sélectionnées ne couvrent pas ce vignoble ; les états disponibles ne sont pas reliés au travers de cet état manquant."
            )
        # On prépare states comme liste vide ; on la remplira au fil des opérations suivantes.
        states = []
        # On parcourt group.iterrows() ; (_, m) désigne l’élément courant à chaque passage dans la
        # boucle.
        for _, m in group.iterrows():
            # On ajoute (m, {}) à la fin de states ; les éléments précédents restent conservés.
            states.append((m, {}))
            # On crée le dictionnaire vide quantities pour y ranger ensuite les éléments par clé.
            quantities = {}
            # On parcourt KEYS ; kind désigne l’élément courant à chaque passage dans la boucle.
            for kind in KEYS:
                # On tente ce bloc et on traite séparément les erreurs prévues : ValueError.
                try:
                    # On garde dans rows la valeur renvoyée par rows_for.
                    rows = rows_for(frames, m, kind)
                    # On gardes lignes sous le nom states[-1][1][kind] ; cette affectation ne copie
                    # pas à elle seule un objet mutable.
                    states[-1][1][kind] = rows
                    # On vérifie ce cas avant la suite : kind correspond au texte 'acquisition'.
                    if kind == "acquisition":
                        # On complète quantities avec les valeurs indiquées ; une clé déjà présente
                        # prendra la nouvelle valeur fournie.
                        quantities.update(
                            Acquisitions=len(rows),
                            Production=int(
                                rows.get(
                                    "perimeter_normalized", pd.Series(dtype=object)
                                )
                                .eq("Production")
                                .sum()
                            ),
                            Tests=int(
                                rows.get(
                                    "perimeter_normalized", pd.Series(dtype=object)
                                )
                                .eq("Test")
                                .sum()
                            ),
                            **{
                                "Bloqué / en attente": int(
                                    rows.get(
                                        "perimeter_normalized", pd.Series(dtype=object)
                                    )
                                    .eq("Bloqué")
                                    .sum()
                                )
                            },
                            **{
                                "Production traitée": int(
                                    yes(rows, "treated_production").sum()
                                )
                            },
                        )
                    # On vérifie ce cas avant la suite : kind correspond au texte 'passage'.
                    if kind == "passage":
                        # On complète quantities avec les valeurs indiquées ; une clé déjà présente
                        # prendra la nouvelle valeur fournie.
                        quantities.update(
                            Vitimap=int(yes(rows, "vitimap_created").sum()),
                            Vitiparcel=int(
                                yes(
                                    rows, "vitiparcel_technical_criterion_satisfied"
                                ).sum()
                            ),
                            Passages=len(rows),
                        )
                except ValueError as exc:
                    # On ajoute f"{m['vineyard_name']} · {format_time(m['nas_checked_at'])} · {exc}" à
                    # la fin de result.messages ; les éléments précédents restent conservés.
                    result.messages.append(
                        f"{m['vineyard_name']} · {format_time(m['nas_checked_at'])} · {exc}"
                    )
            # On ajoute {'Vignoble': m['vineyard_name'], 'Observation NAS':
            # format_time(m['nas_checked_at']), 'Cr… à la fin de timeline ; les éléments précédents
            # restent conservés.
            timeline.append(
                {
                    # On associe la clé 'Vignoble' à cette valeur dans cet objet.
                    "Vignoble": m["vineyard_name"],
                    # On associe la clé 'Observation NAS' à cette valeur dans cet objet.
                    "Observation NAS": format_time(m["nas_checked_at"]),
                    # On associe la clé 'Croisement Excel / NAS' à cette valeur dans cet objet.
                    "Croisement Excel / NAS": format_time(m["reconciled_at"]),
                    # On associe la clé 'Version Excel' à cette valeur dans cet objet.
                    "Version Excel": text(m.get("excel_version_id")),
                    "Référence": reference(m),
                    # On associe la clé '_time' à cette valeur dans cet objet.
                    "_time": m["_nas_time"].isoformat(),
                    **quantities,
                }
            )
        # On vérifie ce cas avant la suite : len(states) est inférieur à 2.
        if len(states) < 2:
            # On ajoute len(KEYS) à result.expected et on conserve ce nouvel état pour la suite.
            result.expected += len(KEYS)
            # On ajoute f"{group.iloc[-1]['vineyard_name']} : moins de deux états sélectionnés ; non
            # comparé." à la fin de result.messages ; les éléments précédents restent conservés.
            result.messages.append(
                f"{group.iloc[-1]['vineyard_name']} : moins de deux états sélectionnés ; non comparé."
            )
        # On garde dans chronological une liste matérialisée à partir de reversed([o['value'] for o in
        # batch_options(frames) if o['value'] in runs….
        chronological = list(
            reversed([o["value"] for o in batch_options(frames) if o["value"] in runs])
        )
        # On parcourt ces collections en parallèle ; les éléments de même position seront comparés
        # ou associés dans le corps de la boucle.
        for (before, old), (after, new) in zip(states, states[1:]):
            # On vérifie ce cas avant la suite : chronological.index(after['pipeline_execution_id']) -
            # chronological.index… diffère de 1.
            if (
                chronological.index(after["pipeline_execution_id"])
                - chronological.index(before["pipeline_execution_id"])
                != 1
            ):
                # On ignore la suite de ce tour de boucle et on passe à l’élément suivant.
                continue
            # On parcourt KEYS ; kind désigne l’élément courant à chaque passage dans la boucle.
            for kind in KEYS:
                # On ajoute 1 à result.expected et on conserve ce nouvel état pour la suite.
                result.expected += 1
                # Cette branche traite le cas où kind ne figure pas dans old ou kind ne figure pas dans
                # new.
                if kind not in old or kind not in new:
                    # On ignore la suite de ce tour de boucle et on passe à l’élément suivant.
                    continue
                # On ajoute 1 à result.comparable et on conserve ce nouvel état pour la suite.
                result.comparable += 1
                # On sélectionne dans KEYS les éléments désignés par kind ; keys recevra cette
                # sélection.
                keys = KEYS[kind]
                # On indexe a par tuple((text(r.get(k)) for k in keys)) ; chaque clé sera associée à r.
                # Une même clé ne peut garder qu’une valeur.
                a = {
                    tuple(text(r.get(k)) for k in keys): r
                    for r in old[kind].to_dict("records")
                }
                # On indexe b par tuple((text(r.get(k)) for k in keys)) ; chaque clé sera associée à r.
                # Une même clé ne peut garder qu’une valeur.
                b = {
                    tuple(text(r.get(k)) for k in keys): r
                    for r in new[kind].to_dict("records")
                }
                # On garde dans union les éléments triés de set(a) | set(b) dans une nouvelle liste.
                union = sorted(set(a) | set(b))
                # On ajoute {'Vignoble': after['vineyard_name'], 'Type': kind, 'Observation
                # précédente': format_time(… à la fin de coverage ; les éléments précédents restent
                # conservés.
                coverage.append(
                    {
                        # On associe la clé 'Vignoble' à cette valeur dans cet objet.
                        "Vignoble": after["vineyard_name"],
                        # On associe la clé 'Type' à cette valeur dans cet objet.
                        "Type": kind,
                        "Observation précédente": format_time(before["nas_checked_at"]),
                        "Observation récente": format_time(after["nas_checked_at"]),
                        "Éléments comparés (union)": len(union),
                        # On associe la clé 'Avant' à cette valeur dans cet objet.
                        "Avant": len(a),
                        "Après": len(b),
                    }
                )
                # On parcourt union ; key désigne l’élément courant à chaque passage dans la boucle.
                for key in union:
                    # On distribue ces valeurs entre r0, r1, dans l’ordre de l’affectation. Chaque nom
                    # reçoit son propre élément.
                    r0, r1 = a.get(key), b.get(key)
                    # On rassemble dans ent les 3 éléments explicitement indiqués, en conservant leur
                    # structure.
                    ent = [text(after["vineyard_key"]), kind, *key]
                    # On ajoute json.dumps(ent, ensure_ascii=False) à result.examined_entities ; comme
                    # il s’agit d’un ensemble, une valeur déjà présente n’est pas comptée deux fois.
                    result.examined_entities.add(json.dumps(ent, ensure_ascii=False))
                    # On regroupe dans common ces champs nommés ; on pourra les retrouver par leur clé
                    # plutôt que par leur position.
                    common = {
                        # On associe la clé 'Vignoble' à cette valeur dans cet objet.
                        "Vignoble": after["vineyard_name"],
                        # On associe la clé 'Type' à cette valeur dans cet objet.
                        "Type": {
                            # On associe la clé 'acquisition' à cette valeur dans cet objet.
                            "acquisition": "Acquisition",
                            # On associe la clé 'passage' à cette valeur dans cet objet.
                            "passage": "Passage",
                            # On associe la clé 'association' à cette valeur dans cet objet.
                            "association": "Rattachement",
                        }[kind],
                        # On associe la clé 'Acquisition' à cette valeur dans cet objet.
                        "Acquisition": (r1 or r0).get("acquisition_id_normalise", ""),
                        # On associe la clé 'Parcelle' à cette valeur dans cet objet.
                        "Parcelle": (r1 or r0).get("parcel_name", "")
                        if kind != "acquisition"
                        else "",
                        # On associe la clé 'Passage' à cette valeur dans cet objet.
                        "Passage": (r1 or r0).get("passage_name", "")
                        if kind != "acquisition"
                        else "",
                        "Observation précédente": format_time(before["nas_checked_at"]),
                        "Observation récente": format_time(after["nas_checked_at"]),
                        "Rapprochement précédent": format_time(before["reconciled_at"]),
                        "Rapprochement récent": format_time(after["reconciled_at"]),
                        "Version Excel précédente": text(
                            before.get("excel_version_id")
                        ),
                        "Version Excel récente": text(after.get("excel_version_id")),
                        "Référence précédente": reference(before),
                        "Référence récente": reference(after),
                        # On associe la clé '_entity' à cette valeur dans cet objet.
                        "_entity": json.dumps(ent, ensure_ascii=False),
                    }
                    # Cette branche traite le cas où r0 vaut None ou r1 vaut None.
                    if r0 is None or r1 is None:
                        # On ajoute {**common, 'Famille': 'Rattachements' if kind == 'association' else
                        # 'Périmètre recensé',… à la fin de details ; les éléments précédents restent
                        # conservés.
                        details.append(
                            {
                                **common,
                                # On associe la clé 'Famille' à cette valeur dans cet objet.
                                "Famille": "Rattachements"
                                if kind == "association"
                                else "Périmètre recensé",
                                # On associe la clé 'Information' à cette valeur dans cet objet.
                                "Information": "Présence dans l’état enregistré",
                                # On associe la clé 'Avant' à cette valeur dans cet objet.
                                "Avant": "Recensé" if r0 else "Non recensé",
                                "Après": "Recensé" if r1 else "Non recensé",
                                # On associe la clé 'Lecture prudente' à cette valeur dans cet objet.
                                "Lecture prudente": "Entrée ou sortie du périmètre enregistré ; ne prouve ni création ni suppression physique.",
                            }
                        )
                        # On ignore la suite de ce tour de boucle et on passe à l’élément suivant.
                        continue
                    # On choisit la valeur de fields selon ce test : kind correspond au texte
                    # 'acquisition'. Les deux résultats possibles restent définis explicitement ici.
                    fields = (
                        ACQ_FIELDS
                        if kind == "acquisition"
                        else PASSAGE_FIELDS
                        if kind == "passage"
                        else []
                    )
                    # On parcourt les champs ; (f, label, family) désigne l’élément courant à chaque
                    # passage dans la boucle.
                    for f, label, family in fields:
                        # On vérifie ce cas avant la suite : canon(r0.get(f), f) diffère de
                        # canon(r1.get(f), f).
                        if canon(r0.get(f), f) != canon(r1.get(f), f):
                            # On utilise ce texte pour note ; il ne dépend pas d’une valeur récupérée
                            # ailleurs à cet endroit.
                            note = "Valeurs enregistrées ; cause du changement à confirmer."
                            # On vérifie ce cas avant la suite : f appartient à BOOLS.
                            if f in BOOLS:
                                # Cette branche traite le cas où _to_bool(r0.get(f)) vaut None ou
                                # _to_bool(r1.get(f)) vaut None.
                                if (
                                    _to_bool(r0.get(f)) is None
                                    # Ce cas est aussi retenu si _to_bool(r1.get(f)) vaut None.
                                    or _to_bool(r1.get(f)) is None
                                ):
                                    # On utilise ce texte pour note ; il ne dépend pas d’une valeur
                                    # récupérée ailleurs à cet endroit.
                                    note = "Changement de renseignement / vérifiabilité ; ne pas conclure à une apparition ou disparition."
                                else:
                                    # On utilise ce texte pour note ; il ne dépend pas d’une valeur
                                    # récupérée ailleurs à cet endroit.
                                    note = "Constat différent ; ni preuve de création/suppression à cette date ni validation de livraison."
                            # Cette branche traite le cas où au moins un élément satisfait le test
                            # indiqué.
                            if any(
                                text(r.get(e))
                                for r in [r0, r1]
                                for e in [
                                    "raw_error",
                                    "processing_error",
                                    "passage_error",
                                    "vitimap_error",
                                    "vitiparcel_error",
                                ]
                            ):
                                # On ajoute ' Erreur de contrôle renseignée : interprétation prudente
                                # requise.' à note et on conserve ce nouvel état pour la suite.
                                note += " Erreur de contrôle renseignée : interprétation prudente requise."
                            # On ajoute {**common, 'Famille': family, 'Information': label, 'Avant':
                            # show(r0.get(f), f), 'Après':… à la fin de details ; les éléments
                            # précédents restent conservés.
                            details.append(
                                {
                                    **common,
                                    # On associe la clé 'Famille' à cette valeur dans cet objet.
                                    "Famille": family,
                                    # On associe la clé 'Information' à cette valeur dans cet objet.
                                    "Information": label,
                                    # On associe la clé 'Avant' à cette valeur dans cet objet.
                                    "Avant": show(r0.get(f), f),
                                    "Après": show(r1.get(f), f),
                                    # On associe la clé 'Lecture prudente' à cette valeur dans cet
                                    # objet.
                                    "Lecture prudente": note,
                                }
                            )
    # On garde dans result.details un tableau pandas construit avec les données indiquées.
    result.details = pd.DataFrame(details, columns=DETAIL_COLUMNS)
    # On garde dans result.timeline un tableau pandas construit avec les données indiquées.
    result.timeline = pd.DataFrame(timeline)
    # On garde dans result.coverage un tableau pandas construit avec les données indiquées.
    result.coverage = pd.DataFrame(coverage)
    # Distinct entity union across the selected adjacent transitions (not sum).
    # Store exact union cardinality independently of per-transition coverage rows.
    result.messages = list(dict.fromkeys(result.messages))
    # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette fonction ne
    # sont plus parcourues.
    return result
