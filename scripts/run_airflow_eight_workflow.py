# Lecture du fichier — Lanceur du diagnostic ou de l’exécution principale dans l’environnement Airflow.
# On sépare les précontrôles, les étapes métier et le reçu final. En cas d’échec, des étapes
# antérieures peuvent déjà avoir été validées : pas de retour arrière global supposé.
#

"""Diagnostic ou workflow manuel ou programme des huit vignobles approuves ; programmation controlee."""

# On importe argparse. On décrit les options de la commande et on contrôle leur forme.
import argparse
# On rend disponibles datetime, timezone depuis datetime, pour les appels de ce fichier.
from datetime import datetime, timezone
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe re. On reconnaît ou transforme des motifs de texte avec les expressions régulières.
import re
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On rend disponibles uuid4 depuis uuid, pour les appels de ce fichier.
from uuid import uuid4
# On rend disponibles ROOT, SCOPE_ID, YEAR, VINEYARDS, CHILD_TIMEOUT, scope, require,
# validate_scheduled_time depuis airflow_eight_contract, pour les appels de ce fichier.
from airflow_eight_contract import (
    ROOT,
    SCOPE_ID,
    YEAR,
    VINEYARDS,
    CHILD_TIMEOUT,
    scope,
    require,
    validate_scheduled_time,
)


# On prépare un message d’échec limité plutôt que retransmettre une sortie brute potentiellement
# sensible.
def safe_error(exc, phase):
    # On affiche 'PHASE : ' + phase dans la sortie du programme.
    print("PHASE : " + phase)
    # On affiche 'TYPE : ' + type(exc).__name__ dans la sortie du programme.
    print("TYPE : " + type(exc).__name__)
    # On rend disponibles EightControlError depuis airflow_eight_contract, pour les appels de ce
    # fichier.
    from airflow_eight_contract import EightControlError

    # On réserve cette branche à exc lorsqu’il est de type EightControlError.
    if isinstance(exc, EightControlError):
        # On affiche 'CODE : ' + str(exc) dans la sortie du programme.
        print("CODE : " + str(exc))
    # On réserve cette branche à exc lorsqu’il est de type ModuleNotFoundError.
    if isinstance(exc, ModuleNotFoundError):
        # On garde dans name l’attribut 'name' de exc avec le repli indiqué s’il est absent.
        name = getattr(exc, "name", None)
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "MODULE : "
            + (
                name
                if isinstance(name, str)
                # On exige aussi que le contrôle re.fullmatch('[A-Za-z_][A-Za-z0-9_.]{0,199}', name)
                # est positif.
                and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]{0,199}", name)
                else "non_identifie"
            )
        )
    # On garde exc.__traceback__ sous le nom tb ; cette affectation ne copie pas à elle seule un objet
    # mutable.
    tb = exc.__traceback__
    # On répète ce bloc tant que tb est évalué comme vrai. La condition sera réévaluée à chaque tour.
    while tb:
        # On garde dans p un objet chemin local ; sa construction seule ne prouve pas que le fichier
        # existe.
        p = Path(tb.tb_frame.f_code.co_filename)
        # On vérifie le périmètre du chemin résolu, pas un simple préfixe de texte : un dossier
        # voisin ou un lien symbolique ne doit pas permettre de sortir de la racine autorisée.
        if p.is_relative_to(ROOT):
            # On affiche 'CADRE : ' + p.relative_to(ROOT).as_posix() + ':' + str(tb.tb_lineno) dans la
            # sortie du programme.
            print("CADRE : " + p.relative_to(ROOT).as_posix() + ":" + str(tb.tb_lineno))
        # On garde tb.tb_next sous le nom tb ; cette affectation ne copie pas à elle seule un objet
        # mutable.
        tb = tb.tb_next


def main(argv=None):
    # On garde dans parser le lecteur des options de cette commande.
    parser = argparse.ArgumentParser(description=__doc__)
    # On déclare des options incompatibles entre elles : le parseur rejettera leur emploi simultané
    # avant le traitement.
    modes = parser.add_mutually_exclusive_group(required=True)
    # Ce mode s’arrête aux contrôles préalables ; il ne demande pas de lancer les étapes métier.
    modes.add_argument("--diagnostic-only", action="store_true")
    # On appelle modes.add_argument avec '--run'.
    modes.add_argument("--run", action="store_true")
    # Ce drapeau demande un accord explicite pour les écritures métier ; il ne doit pas être activé
    # par défaut pour une simple vérification.
    parser.add_argument("--allow-business-writes", action="store_true")
    # On exige une confirmation du montage NAS en lecture seule ; ce drapeau ne remplace pas la
    # vérification des droits du montage.
    parser.add_argument("--confirm-nas-read-only", action="store_true")
    # On appelle parser.add_argument avec '--receipt'.
    parser.add_argument("--receipt", type=Path)
    # On appelle parser.add_argument avec '--trigger-mode'.
    parser.add_argument(
        "--trigger-mode",
        choices=("airflow_manual", "airflow_scheduled"),
        default="airflow_manual",
    )
    # On appelle parser.add_argument avec '--scheduled-for'.
    parser.add_argument("--scheduled-for")
    # On récupère le mode demandé pour les huit domaines ; un diagnostic et une exécution autorisée
    # ne doivent pas prendre la même branche.
    args = parser.parse_args(argv)
    # On initialise deadline à None : aucune valeur n’a encore été retenue ici.
    deadline = None
    # On vérifie ce cas avant la suite : args.trigger_mode correspond au texte 'airflow_scheduled'.
    if args.trigger_mode == "airflow_scheduled":
        # Cette branche traite le cas où la condition args.run n’est pas remplie ou la condition
        # args.scheduled_for n’est pas remplie.
        if not args.run or not args.scheduled_for:
            # On appelle parser.error avec 'Le mode programme exige --run et --scheduled-for.'.
            parser.error("Le mode programme exige --run et --scheduled-for.")
        # On tente ce bloc et on traite séparément les erreurs prévues : Exception.
        try:
            # On interprète la date ISO reçue ; les vérifications de fuseau et de cohérence restent
            # nécessaires après cette conversion.
            deadline = datetime.fromisoformat(args.scheduled_for)
            # On appelle validate_scheduled_time avec deadline.
            validate_scheduled_time(deadline)
        except Exception:
            # On affiche ce texte explicite dans la sortie du programme.
            print("HORAIRE REFUSE : aucun traitement lance ; aucun rattrapage.")
            # On termine cette branche avec la valeur 1 ; à la sortie d’un main, elle sert de code de
            # retour.
            return 1
    # Cette branche traite le cas où le test args.scheduled_for est satisfait.
    elif args.scheduled_for:
        # On appelle parser.error avec 'Une echeance est reservee au mode programme.'.
        parser.error("Une echeance est reservee au mode programme.")
    # Cette branche traite le cas où le test args.run est satisfait et la condition
    # args.allow_business_writes and args.confirm_nas_read_only and args.receipt n’est pas remplie.
    if args.run and not (
        args.allow_business_writes and args.confirm_nas_read_only and args.receipt
    ):
        # On appelle parser.error avec 'Le traitement exige les deux confirmations et un recu
        # explicite.'.
        parser.error("Le traitement exige les deux confirmations et un recu explicite.")
    # Cette branche traite le cas où toutes les conditions regroupées ici sont remplies.
    if args.diagnostic_only and (
        args.allow_business_writes or args.confirm_nas_read_only or args.receipt
    ):
        # On appelle parser.error avec 'Le diagnostic ne prend pas de confirmations de traitement.'.
        parser.error("Le diagnostic ne prend pas de confirmations de traitement.")
    # Cette branche traite le cas où le test args.receipt est satisfait et au moins un des cas
    # regroupés ici est rencontré.
    if args.receipt and (
        args.receipt.parent != ROOT / "logs/airflow_workflow"
        # Ce cas est aussi retenu si la condition
        # re.fullmatch('eight_execution_[0-9]{8}T[0-9]{6}_[0-9a-f]{32}\\.json', args.receipt.name)
        # n’est pas remplie.
        or not re.fullmatch(
            r"eight_execution_[0-9]{8}T[0-9]{6}_[0-9a-f]{32}\.json", args.receipt.name
        )
    ):
        # On appelle parser.error avec 'Destination du recu refusee.'.
        parser.error("Destination du recu refusee.")
    # On utilise ce texte pour phase ; il ne dépend pas d’une valeur récupérée ailleurs à cet endroit.
    phase = "imports"
    # On tente ce bloc et on traite séparément les erreurs prévues : Exception.
    try:
        # On rend disponibles load_business_configuration depuis workflow_business_config, pour les
        # appels de ce fichier.
        from workflow_business_config import load_business_configuration
        # On rend disponibles build_business_plan depuis workflow_business_wiring, pour les appels de
        # ce fichier.
        from workflow_business_wiring import build_business_plan
        # On rend disponibles workflow_lock, run_workflow depuis workflow_runtime, pour les appels de
        # ce fichier.
        from workflow_runtime import workflow_lock, run_workflow
        # On rend disponibles diagnose_importer depuis run_workflow_business, pour les appels de ce
        # fichier.
        from run_workflow_business import diagnose_importer
        # On rend disponibles write_receipt depuis airflow_workflow_runtime_check, pour les appels de
        # ce fichier.
        from airflow_workflow_runtime_check import write_receipt
        # On rend disponibles check_eight_sources, guarded_steps depuis airflow_eight_runtime, pour les
        # appels de ce fichier.
        from airflow_eight_runtime import check_eight_sources, guarded_steps

        # On utilise ce texte pour phase ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        phase = "configuration"
        # On capture les paramètres nécessaires au parcours ; ils seront passés explicitement aux
        # opérations qui les utilisent.
        config = load_business_configuration(ROOT, configuration_mode="environment")
        # On utilise ce texte pour phase ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        phase = "plan_construction"
        # On construit le plan des opérations réelles, sans encore exécuter les étapes qu’il
        # rassemble.
        plan = build_business_plan(
            config,
            # On transmet la sélection explicite des domaines concernés par cet appel.
            vineyards=list(VINEYARDS),
            # Ce paramètre distingue le choix de tous les domaines d’une liste de sélection explicite.
            all_vineyards=False,
            # On transmet la saison à utiliser pour les contrôles et les chemins concernés.
            year=YEAR,
            # On fournit le délai maximal en secondes via le paramètre timeout_seconds de cet appel.
            timeout_seconds=CHILD_TIMEOUT,
        )
        # On garde dans steps la valeur renvoyée par guarded_steps.
        steps = guarded_steps(plan)
        # On initialise share à None : aucune valeur n’a encore été retenue ici.
        share = None
        # On initialise publication à None : aucune valeur n’a encore été retenue ici.
        publication = None

        # On réalise les contrôles préalables avant d’autoriser le lancement des étapes métier.
        def preflight(context):
            nonlocal share, publication, phase
            # On utilise ce texte pour phase ; il ne dépend pas d’une valeur récupérée ailleurs à cet
            # endroit.
            phase = "eight_sources_preflight"
            # On répartit les valeurs renvoyées par check_eight_sources entre (share, publication) ;
            # leur ordre doit correspondre à celui prévu par cet appel.
            share, publication = check_eight_sources(ROOT)
            # On utilise ce texte pour phase ; il ne dépend pas d’une valeur récupérée ailleurs à cet
            # endroit.
            phase = "postgres_preflight"
            # On appelle diagnose_importer avec config.
            diagnose_importer(config)
            # On vérifie ce cas avant la suite : deadline est renseigné (différent de None).
            if deadline is not None:
                # On appelle validate_scheduled_time avec deadline.
                validate_scheduled_time(deadline)
            # On utilise ce texte pour phase ; il ne dépend pas d’une valeur récupérée ailleurs à cet
            # endroit.
            phase = "preflight_completed"

        # Cette branche s’arrête aux vérifications préalables ; elle ne passe pas à l’exécution des
        # étapes métier située après elle.
        if args.diagnostic_only:
            # On utilise workflow_lock(ROOT, str(uuid4())) dans son contexte de gestion ; les
            # opérations de sortie sont exécutées en quittant le bloc.
            with workflow_lock(ROOT, str(uuid4())):
                # On appelle preflight avec None.
                preflight(None)
                # On assemble ces deux éléments pour construire stamp.
                stamp = (
                    datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
                    + "_"
                    + uuid4().hex
                )
                # On assemble les morceaux du chemin path avec l’opérateur / de pathlib ; aucun fichier
                # n’est créé par cette construction.
                path = (
                    ROOT
                    / "logs/airflow_workflow"
                    / ("eight_diagnostic_" + stamp + ".json")
                )
                # On appelle write_receipt avec path.
                write_receipt(
                    path,
                    dict(
                        kind="diagnostic",
                        # On fournit l’état du traitement via le paramètre status de cet appel.
                        status="success",
                        scope_id=SCOPE_ID,
                        # On transmet la sélection explicite des domaines concernés par cet appel.
                        vineyards=list(VINEYARDS),
                        share_id=share,
                        # On fournit l’identifiant du lot Excel via le paramètre excel_publication_id
                        # de cet appel.
                        excel_publication_id=publication,
                        # On fournit la date de l’événement via le paramètre occurred_at de cet appel.
                        occurred_at=datetime.now(timezone.utc).isoformat(),
                    ),
                )
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                "DIAGNOSTIC HUIT VIGNOBLES : OK — sources Excel, reference 2026, NAS RO et diagnostic importeur."
            )
            # On affiche 'Perimetre : ' + ', '.join(VINEYARDS) dans la sortie du programme.
            print("Perimetre : " + ", ".join(VINEYARDS))
            # On affiche 'Recu local : logs/airflow_workflow/' + path.name dans la sortie du programme.
            print("Recu local : logs/airflow_workflow/" + path.name)
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                "Aucune ingestion, extraction metier, ecriture SQL ou journal workflow. Sondes/verrou locaux temporaires ; recu conserve."
            )
            # On termine cette branche avec la valeur 0 ; à la sortie d’un main, elle sert de code de
            # retour.
            return 0
        # On vérifie ce cas avant la suite : deadline est renseigné (différent de None).
        if deadline is not None:
            # On appelle validate_scheduled_time avec deadline.
            validate_scheduled_time(deadline)
        # On utilise ce texte pour phase ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        phase = "workflow_call"
        # On lance les étapes assemblées avec le même contexte et leur journal ; le moteur ne
        # fournit pas de transaction globale couvrant tout le parcours.
        result = run_workflow(
            ROOT,
            steps,
            # On fournit l’origine du déclenchement via le paramètre trigger_mode de cet appel.
            trigger_mode=args.trigger_mode,
            # On fournit le périmètre du traitement via le paramètre scope de cet appel.
            scope=scope(),
            # On fournit le destinataire des événements du workflow ; ce n’est pas la base technique
            # des runs Airflow.
            journal_sink=plan.journal_sink,
            # On fournit le contrôle qui doit passer sous verrou avant le démarrage des étapes.
            preflight=preflight,
        )
        # On utilise ce texte pour phase ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        phase = "execution_receipt"
        # On garde dans data un nouveau dictionnaire construit avec les valeurs indiquées.
        data = dict(
            kind="execution",
            # On fournit l’état du traitement via le paramètre status de cet appel.
            status=result["status"],
            scope_id=SCOPE_ID,
            # On transmet la sélection explicite des domaines concernés par cet appel.
            vineyards=list(VINEYARDS),
            share_id=share,
            # On fournit la date de l’événement via le paramètre occurred_at de cet appel.
            occurred_at=datetime.now(timezone.utc).isoformat(),
            # On fournit l’identifiant de l’exécution du workflow via le paramètre
            # workflow_execution_id de cet appel.
            workflow_execution_id=result["workflow_execution_id"],
            # On fournit les étapes terminées via le paramètre completed_steps de cet appel.
            completed_steps=len(result["completed_steps"]),
            journal_relative_path=result["journal_relative_path"],
            # On fournit le code du problème rencontré via le paramètre error_code de cet appel.
            error_code=result["error_code"],
            # On fournit l’identifiant du lot Excel via le paramètre excel_publication_id de cet appel.
            excel_publication_id=result.get("excel_publication_id"),
            # On fournit l’identifiant du traitement NAS via le paramètre pipeline_execution_id de cet
            # appel.
            pipeline_execution_id=result.get("pipeline_execution_id"),
            # On fournit l’origine du déclenchement via le paramètre trigger_mode de cet appel.
            trigger_mode=args.trigger_mode,
        )
        # On conserve le résultat de ce contrôle dans un reçu local ; il faudra encore vérifier sa
        # nature et son état avant d’en déduire une réussite métier.
        write_receipt(args.receipt, data)
        # On affiche 'Workflow : ' + result['workflow_execution_id'] dans la sortie du programme.
        print("Workflow : " + result["workflow_execution_id"])
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Etapes confirmees : %d/8 ; resultat : %s."
            % (len(result["completed_steps"]), result["status"])
        )
        # On affiche 'Recu local : logs/airflow_workflow/' + args.receipt.name dans la sortie du
        # programme.
        print("Recu local : logs/airflow_workflow/" + args.receipt.name)
        # On renvoie l’une des deux valeurs selon le test indiqué ; ce choix termine la fonction pour
        # ce cas.
        return 0 if result["status"] == "success" else 1
    except Exception as exc:
        # On appelle safe_error avec exc.
        safe_error(exc, phase)
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "EXECUTION NON CONFIRMEE. Aucune relance automatique ; des etapes peuvent avoir ete commises. Aucun rollback global."
        )
        # On termine cette branche avec la valeur 1 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 1


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On termine le programme avec ce code de sortie pour que l’appelant puisse distinguer réussite et
    # échec.
    sys.exit(main())
