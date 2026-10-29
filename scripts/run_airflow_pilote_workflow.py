# Lecture du fichier — Lanceur Airflow du parcours limité à un domaine.
# On utilise les mêmes principes de précontrôle et de reçu, avec un périmètre plus réduit que le
# parcours principal.
#

"""Diagnostic Docker ou workflow DomaineDemoD manuel Airflow ; aucune programmation automatique."""

# On importe argparse. On décrit les options de la commande et on contrôle leur forme.
import argparse
# On rend disponibles datetime, timezone depuis datetime, pour les appels de ce fichier.
from datetime import datetime, timezone
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On importe re. On reconnaît ou transforme des motifs de texte avec les expressions régulières.
import re
# On rend disponibles uuid4 depuis uuid, pour les appels de ce fichier.
from uuid import uuid4

# On rend disponibles ROOT, RuntimeCheckError, check_runtime, receipt_path, write_receipt depuis
# airflow_workflow_runtime_check, pour les appels de ce fichier.
from airflow_workflow_runtime_check import (
    ROOT,
    RuntimeCheckError,
    check_runtime,
    receipt_path,
    write_receipt,
)


def main(argv=None):
    # On garde dans parser le lecteur des options de cette commande.
    parser = argparse.ArgumentParser(description=__doc__)
    # On déclare des options incompatibles entre elles : le parseur rejettera leur emploi simultané
    # avant le traitement.
    modes = parser.add_mutually_exclusive_group(required=True)
    # On appelle modes.add_argument avec '--diagnostic-only'.
    modes.add_argument("--diagnostic-only", action="store_true")
    # On appelle modes.add_argument avec '--run'.
    modes.add_argument("--run", action="store_true")
    # On appelle parser.add_argument avec '--allow-business-writes'.
    parser.add_argument("--allow-business-writes", action="store_true")
    # On appelle parser.add_argument avec '--confirm-nas-read-only'.
    parser.add_argument("--confirm-nas-read-only", action="store_true")
    # On appelle parser.add_argument avec '--receipt'.
    parser.add_argument("--receipt", type=Path)
    # On lit les options du parcours pilote ; le diagnostic reste distinct du lancement avec
    # écritures confirmées.
    args = parser.parse_args(argv)
    # Cette branche traite le cas où le test args.run est satisfait et la condition
    # args.allow_business_writes n’est pas remplie ou la condition args.confirm_nas_read_only n’est pas
    # remplie ou args.receipt vaut None.
    if args.run and (
        not args.allow_business_writes
        # Ce cas est aussi retenu si la condition args.confirm_nas_read_only n’est pas remplie.
        or not args.confirm_nas_read_only
        # Ce cas est aussi retenu si args.receipt vaut None.
        or args.receipt is None
    ):
        # On appelle parser.error avec '--run exige les deux confirmations et un recu local.'.
        parser.error("--run exige les deux confirmations et un recu local.")
    # Cette branche traite le cas où toutes les conditions regroupées ici sont remplies.
    if args.diagnostic_only and (
        args.allow_business_writes
        or args.confirm_nas_read_only
        # Ce cas est aussi retenu si args.receipt est renseigné (différent de None).
        or args.receipt is not None
    ):
        # On appelle parser.error avec 'Le diagnostic ne prend pas de confirmations de lancement.'.
        parser.error("Le diagnostic ne prend pas de confirmations de lancement.")
    # On vérifie ce cas avant la suite : args.receipt est renseigné (différent de None).
    if args.receipt is not None:
        # Cette branche traite le cas où au moins un des cas regroupés ici est rencontré.
        if (
            args.receipt.parent != ROOT / "logs/airflow_workflow"
            # Ce cas est aussi retenu si la condition args.receipt.name.startswith('execution_') n’est
            # pas remplie.
            or not args.receipt.name.startswith("execution_")
            # Ce cas est aussi retenu si args.receipt.suffix diffère du texte '.json'.
            or args.receipt.suffix != ".json"
        ):
            # On appelle parser.error avec 'Destination de recu non autorisee.'.
            parser.error("Destination de recu non autorisee.")
    # On utilise ce texte pour phase ; il ne dépend pas d’une valeur récupérée ailleurs à cet endroit.
    phase = "initial_imports"
    # On tente ce bloc et on traite séparément les erreurs prévues : Exception.
    try:
        # On rend disponibles load_business_configuration depuis workflow_business_config, pour les
        # appels de ce fichier.
        from workflow_business_config import load_business_configuration
        # On rend disponibles build_business_plan depuis workflow_business_wiring, pour les appels de
        # ce fichier.
        from workflow_business_wiring import build_business_plan
        # On rend disponibles diagnose_importer depuis run_workflow_business, pour les appels de ce
        # fichier.
        from run_workflow_business import diagnose_importer
        # On rend disponibles run_workflow, workflow_lock depuis workflow_runtime, pour les appels de
        # ce fichier.
        from workflow_runtime import run_workflow, workflow_lock

        # Pas de .env ; construction du meme plan et des memes huit callbacks.
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
            vineyards=["DomaineDemoD"],
            # Ce paramètre distingue le choix de tous les domaines d’une liste de sélection explicite.
            all_vineyards=False,
            # On transmet la saison à utiliser pour les contrôles et les chemins concernés.
            year=2026,
            # On fournit le délai maximal en secondes via le paramètre timeout_seconds de cet appel.
            timeout_seconds=1200,
        )
        # On initialise share à None : aucune valeur n’a encore été retenue ici.
        share = None

        # On réalise les contrôles préalables avant d’autoriser le lancement des étapes métier.
        def preflight(context):
            nonlocal share, phase
            # On utilise ce texte pour phase ; il ne dépend pas d’une valeur récupérée ailleurs à cet
            # endroit.
            phase = "runtime_preflight"
            # On garde dans share la valeur renvoyée par check_runtime.
            share = check_runtime(ROOT)
            # On utilise ce texte pour phase ; il ne dépend pas d’une valeur récupérée ailleurs à cet
            # endroit.
            phase = "postgres_preflight"
            # On appelle diagnose_importer avec config.
            diagnose_importer(config)
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
                # On regroupe dans receipt ces champs nommés ; on pourra les retrouver par leur clé
                # plutôt que par leur position.
                receipt = {
                    # On associe la clé 'kind' à cette valeur dans cet objet.
                    "kind": "diagnostic",
                    # On renseigne l’état du traitement sous la clé 'status'.
                    "status": "success",
                    # On associe la clé 'share_id' à cette valeur dans cet objet.
                    "share_id": share,
                    # On renseigne la date de l’événement sous la clé 'occurred_at'.
                    "occurred_at": datetime.now(timezone.utc).isoformat(),
                }
                # On garde dans path la valeur renvoyée par receipt_path.
                path = receipt_path(ROOT, "diagnostic")
                # On appelle write_receipt avec path.
                write_receipt(path, receipt)
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                "DIAGNOSTIC DOCKER : OK - montages RO, etat partage, sorties locales, Excel DomaineDemoD, lecture NAS ciblee et droits importeur."
            )
            # On affiche 'Recu local : logs/airflow_workflow/' + path.name dans la sortie du programme.
            print("Recu local : logs/airflow_workflow/" + path.name)
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                "Sondes locales creees puis supprimees ; recu conserve. Verrous SQL annules et verrou local libere."
            )
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                "Aucune ingestion, aucune ecriture SQL, aucun journal workflow. Deux JSON NAS lus, aucune ecriture NAS."
            )
            # On termine cette branche avec la valeur 0 ; à la sortie d’un main, elle sert de code de
            # retour.
            return 0
        # Exclusivement trigger_mode=airflow_manual ; le workflow n'est pas copie dans le DAG.
        phase = "workflow_call"
        # On lance les étapes assemblées avec le même contexte et leur journal ; le moteur ne
        # fournit pas de transaction globale couvrant tout le parcours.
        result = run_workflow(
            ROOT,
            plan.steps,
            # On fournit l’origine du déclenchement via le paramètre trigger_mode de cet appel.
            trigger_mode="airflow_manual",
            # On fournit le périmètre du traitement via le paramètre scope de cet appel.
            scope={
                # On renseigne la saison sous la clé 'year'.
                "year": 2026,
                # On renseigne les domaines sélectionnés sous la clé 'vineyards'.
                "vineyards": ["DomaineDemoD"],
                # On renseigne le choix de tous les domaines sous la clé 'all_vineyards'.
                "all_vineyards": False,
                # On associe la clé 'execution_kind' à cette valeur dans cet objet.
                "execution_kind": "business",
            },
            # On fournit le destinataire des événements du workflow ; ce n’est pas la base technique
            # des runs Airflow.
            journal_sink=plan.journal_sink,
            # On fournit le contrôle qui doit passer sous verrou avant le démarrage des étapes.
            preflight=preflight,
        )
        # On utilise ce texte pour phase ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        phase = "execution_receipt"
        # On regroupe dans receipt ces champs nommés ; on pourra les retrouver par leur clé plutôt que
        # par leur position.
        receipt = {
            # On associe la clé 'kind' à cette valeur dans cet objet.
            "kind": "execution",
            # On renseigne l’état du traitement sous la clé 'status'.
            "status": result["status"],
            # On associe la clé 'share_id' à cette valeur dans cet objet.
            "share_id": share,
            # On renseigne la date de l’événement sous la clé 'occurred_at'.
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            # On renseigne l’identifiant de l’exécution du workflow sous la clé
            # 'workflow_execution_id'.
            "workflow_execution_id": result["workflow_execution_id"],
            # On renseigne les étapes terminées sous la clé 'completed_steps'.
            "completed_steps": len(result["completed_steps"]),
            # On associe la clé 'journal_relative_path' à cette valeur dans cet objet.
            "journal_relative_path": result["journal_relative_path"],
            # On renseigne le code du problème rencontré sous la clé 'error_code'.
            "error_code": result["error_code"],
            # On renseigne l’identifiant du lot Excel sous la clé 'excel_publication_id'.
            "excel_publication_id": result.get("excel_publication_id"),
            # On renseigne l’identifiant du traitement NAS sous la clé 'pipeline_execution_id'.
            "pipeline_execution_id": result.get("pipeline_execution_id"),
            # On renseigne l’origine du déclenchement sous la clé 'trigger_mode'.
            "trigger_mode": "airflow_manual",
        }
        # On conserve le résultat de ce contrôle dans un reçu local ; il faudra encore vérifier sa
        # nature et son état avant d’en déduire une réussite métier.
        write_receipt(args.receipt, receipt)
        # On affiche 'Workflow : ' + result['workflow_execution_id'] dans la sortie du programme.
        print("Workflow : " + result["workflow_execution_id"])
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Etapes confirmees : %d/8 ; resultat : %s."
            % (len(result["completed_steps"]), result["status"])
        )
        # On renvoie l’une des deux valeurs selon le test indiqué ; ce choix termine la fonction pour
        # ce cas.
        return 0 if result["status"] == "success" else 1
    except Exception as exc:
        # On affiche 'PHASE DU LANCEUR : ' + phase dans la sortie du programme.
        print("PHASE DU LANCEUR : " + phase)
        # On réserve cette branche à exc lorsqu’il est de type ModuleNotFoundError.
        if isinstance(exc, ModuleNotFoundError):
            # On garde dans name l’attribut 'name' de exc avec le repli indiqué s’il est absent.
            name = getattr(exc, "name", None)
            # On choisit la valeur de safe_name selon ce test : le nom en cours est du type str et le
            # contrôle re.fullmatch('[A-Za-z_][A-Za-z0-9_.]{0,199}', name) est positif. Les deux
            # résultats possibles restent définis explicitement ici.
            safe_name = (
                name
                if isinstance(name, str)
                # On exige aussi que le contrôle re.fullmatch('[A-Za-z_][A-Za-z0-9_.]{0,199}', name)
                # est positif.
                and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]{0,199}", name)
                else "non_identifie"
            )
            # On affiche 'MODULE INTROUVABLE : ' + safe_name dans la sortie du programme.
            print("MODULE INTROUVABLE : " + safe_name)
            # On garde exc.__traceback__ sous le nom tb ; cette affectation ne copie pas à elle seule
            # un objet mutable.
            tb = exc.__traceback__
            # On répète ce bloc tant que tb est renseigné (différent de None). La condition sera
            # réévaluée à chaque tour.
            while tb is not None:
                # On garde dans frame_path un objet chemin local ; sa construction seule ne prouve pas
                # que le fichier existe.
                frame_path = Path(tb.tb_frame.f_code.co_filename)
                # On vérifie le périmètre du chemin résolu, pas un simple préfixe de texte : un
                # dossier voisin ou un lien symbolique ne doit pas permettre de sortir de la racine
                # autorisée.
                if frame_path.is_relative_to(ROOT):
                    # Aucun message d'exception, variable ou extrait de code.
                    print(
                        "CADRE PROJET : "
                        + frame_path.relative_to(ROOT).as_posix()
                        + ":"
                        + str(tb.tb_lineno)
                    )
                # On garde tb.tb_next sous le nom tb ; cette affectation ne copie pas à elle seule un
                # objet mutable.
                tb = tb.tb_next
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "EXECUTION NON CONFIRMEE : "
            + (str(exc) if isinstance(exc, RuntimeCheckError) else type(exc).__name__)
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Ne pas relancer automatiquement ; des etapes peuvent avoir ete commises. Aucun rollback global."
        )
        # On termine cette branche avec la valeur 1 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 1


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On termine le programme avec ce code de sortie pour que l’appelant puisse distinguer réussite et
    # échec.
    sys.exit(main())
