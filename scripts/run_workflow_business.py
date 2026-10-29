# Lecture du fichier — Entrée du workflow avec ses dépendances métier configurées.
# On distingue le diagnostic d’une exécution autorisée à charger des résultats. Les contrôles
# précédant le lancement ne garantissent pas l’absence d’erreur en cours de traitement.
#

"""Entree metier explicite : diagnostic seul ou lancement confirme d'un vignoble.
Ne pas lancer --run avant validation du perimetre et des chemins sur la machine autorisee.
"""

# On importe argparse. On décrit les options de la commande et on contrôle leur forme.
import argparse
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On rend disponibles uuid4 depuis uuid, pour les appels de ce fichier.
from uuid import uuid4

# On rend disponibles load_business_configuration, BusinessConfigurationError depuis
# workflow_business_config, pour les appels de ce fichier.
from workflow_business_config import (
    load_business_configuration,
    BusinessConfigurationError,
)
# On rend disponibles build_business_plan depuis workflow_business_wiring, pour les appels de ce
# fichier.
from workflow_business_wiring import build_business_plan
# On rend disponibles _project_module depuis workflow_excel_adapter, pour les appels de ce fichier.
from workflow_excel_adapter import _project_module
# On rend disponibles run_workflow, workflow_lock, WorkflowBusy depuis workflow_runtime, pour les
# appels de ce fichier.
from workflow_runtime import run_workflow, workflow_lock, WorkflowBusy


class ImporterDiagnosticError(RuntimeError):
    # Cette classe marque un type d’erreur distinct, sans ajouter de comportement à sa classe parente.
    pass


# On prépare la connexion réservée au diagnostic avec les paramètres contrôlés.
def diagnostic_connection(configuration):
    # On importe psycopg. On utilise le pilote de connexion PostgreSQL ; l’import seul n’ouvre pas de
    # connexion.
    import psycopg

    # Cette instruction ouvre réellement une connexion PostgreSQL avec les paramètres préparés ; ce
    # n’est plus une simple validation de configuration.
    return psycopg.connect(**dict(configuration.importer), autocommit=False)


def diagnose_importer(configuration):
    """SELECT et verrous seulement, diagnostic existant, ROLLBACK garanti."""
    # On charge le module check_import_connection de cette copie ; le helper contrôle son
    # emplacement pour ne pas mélanger deux projets présents sur le poste.
    checker = _project_module(
        configuration.root,
        "check_import_connection",
        "scripts/check_import_connection.py",
    )
    # On tente ce bloc et on traite séparément les erreurs prévues : Exception.
    try:
        # On utilise diagnostic_connection(configuration) dans son contexte de gestion ; les opérations
        # de sortie sont exécutées en quittant le bloc.
        with diagnostic_connection(configuration) as connection:
            # On encadre cette opération pour que le bloc finally soit exécuté même si elle échoue.
            try:
                # On lance le diagnostic des droits et des états attendus sur cette connexion ; ce
                # contrôle ne réalise pas les chargements du pipeline.
                counts = checker.check(connection)
            finally:
                # On annule les écritures non validées dans cette transaction, sans prétendre annuler
                # les opérations déjà commises ailleurs.
                connection.rollback()
        # Cette branche traite le cas où le type reçu ne correspond pas à tuple ou len(counts) diffère
        # de 3 ou au moins un élément satisfait le test indiqué.
        if (
            not isinstance(counts, tuple)
            # Ce cas est aussi retenu si len(counts) diffère de 3.
            or len(counts) != 3
            # Ce cas est aussi retenu si au moins un élément satisfait le test indiqué.
            or any(type(n) is not int or n < 0 for n in counts)
        ):
            # On interrompt cette branche avec ValueError : 'Diagnostic non confirme.'.
            raise ValueError("Diagnostic non confirme.")
        # On remet les compteurs à l’appelant ; les étapes suivantes de cette fonction ne sont plus
        # parcourues.
        return counts
    except Exception:
        # On interrompt cette branche avec ImporterDiagnosticError : 'IMPORT_DIAGNOSTIC_FAILED'.
        raise ImporterDiagnosticError("IMPORT_DIAGNOSTIC_FAILED") from None


# On contrôle le domaine choisi avant de préparer le parcours limité à ce périmètre.
def validate_one_vineyard(vineyard):
    # Cette branche traite le cas où le type reçu ne correspond pas à str ou la condition
    # vineyard.strip() n’est pas remplie ou au moins un élément satisfait le test indiqué.
    if (
        not isinstance(vineyard, str)
        # Ce cas est aussi retenu si la condition vineyard.strip() n’est pas remplie.
        or not vineyard.strip()
        # Ce cas est aussi retenu si au moins un élément satisfait le test indiqué.
        or any(c in vineyard for c in ("\x00", "\r", "\n", "/", "\\"))
    ):
        # On interrompt cette branche avec ValueError : 'Un vignoble explicite valide est requis.'.
        raise ValueError("Un vignoble explicite valide est requis.")
    # On fournit à l’appelant le texte vineyard sans les caractères de bord indiqués, ou sans les
    # espaces de bord par défaut.
    return vineyard.strip()


def execute_business(
    configuration,
    plan,
    *,
    vineyard,
    year=2026,
    allow_business_writes=False,
    confirm_nas_read_only=False,
):
    """Meme socle et callbacks ; aucun retry ou rollback global entre les etapes."""
    # Cette branche traite le cas où allow_business_writes n’est pas exactement la valeur vraie (True)
    # ou confirm_nas_read_only n’est pas exactement la valeur vraie (True).
    if allow_business_writes is not True or confirm_nas_read_only is not True:
        # On interrompt cette branche avec ValueError : 'Les deux confirmations explicites sont
        # requises.'.
        raise ValueError("Les deux confirmations explicites sont requises.")
    # On nettoie et contrôle le nom du domaine avant du comparer au périmètre du plan.
    name = validate_one_vineyard(vineyard)
    # Cette branche traite le cas où type(year) n’est pas exactement int ou la saison diffère de 2026.
    if type(year) is not int or year != 2026:
        # On interrompt cette branche avec ValueError : 'Cette entree pilote est limitee a la saison
        # 2026.'.
        raise ValueError("Cette entree pilote est limitee a la saison 2026.")
    # Cette branche traite le cas où plan.all_vineyards n’est pas exactement la valeur fausse (False)
    # ou plan.vineyards diffère de (name,) ou plan.year diffère de la saison.
    if (
        plan.all_vineyards is not False
        # Ce cas est aussi retenu si plan.vineyards diffère de (name,).
        or plan.vineyards != (name,)
        # Ce cas est aussi retenu si plan.year diffère de la saison.
        or plan.year != year
    ):
        # On interrompt cette branche avec ValueError : 'Plan different du perimetre unique autorise.'.
        raise ValueError("Plan different du perimetre unique autorise.")
    # Cette fois, on lance le moteur avec les étapes du plan. Le diagnostic importeur sera refait
    # sous verrou avant le journal et les étapes métier.
    return run_workflow(
        configuration.root,
        plan.steps,
        # On fournit l’origine du déclenchement via le paramètre trigger_mode de cet appel.
        trigger_mode="manual_script",
        # On fournit le périmètre du traitement via le paramètre scope de cet appel.
        scope={
            # On renseigne la saison sous la clé 'year'.
            "year": year,
            # On renseigne les domaines sélectionnés sous la clé 'vineyards'.
            "vineyards": [name],
            # On renseigne le choix de tous les domaines sous la clé 'all_vineyards'.
            "all_vineyards": False,
            # On associe la clé 'execution_kind' à cette valeur dans cet objet.
            "execution_kind": "business",
        },
        # On fournit le destinataire des événements du workflow ; ce n’est pas la base technique des
        # runs Airflow.
        journal_sink=plan.journal_sink,
        # On fournit le contrôle qui doit passer sous verrou avant le démarrage des étapes.
        preflight=lambda context: diagnose_importer(configuration),
    )


def main(argv=None):
    # On garde dans parser le lecteur des options de cette commande.
    parser = argparse.ArgumentParser(description=__doc__)
    # On déclare des options incompatibles entre elles : le parseur rejettera leur emploi simultané
    # avant le traitement.
    mode = parser.add_mutually_exclusive_group(required=True)
    # On appelle mode.add_argument avec '--diagnostic-only'.
    mode.add_argument("--diagnostic-only", action="store_true")
    # On appelle mode.add_argument avec '--run'.
    mode.add_argument("--run", action="store_true")
    # On garde dans selection la valeur renvoyée par parser.add_mutually_exclusive_group.
    selection = parser.add_mutually_exclusive_group(required=True)
    # On appelle selection.add_argument avec '--vineyard'.
    selection.add_argument("--vineyard")
    # On appelle selection.add_argument avec '--all-vineyards'.
    selection.add_argument("--all-vineyards", action="store_true")
    # On appelle parser.add_argument avec '--allow-business-writes'.
    parser.add_argument("--allow-business-writes", action="store_true")
    # On appelle parser.add_argument avec '--confirm-nas-read-only'.
    parser.add_argument("--confirm-nas-read-only", action="store_true")
    # On appelle parser.add_argument avec '--configuration-mode'.
    parser.add_argument(
        "--configuration-mode", choices=["local", "environment"], default="local"
    )
    # On appelle parser.add_argument avec '--project-root'.
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    # On appelle parser.add_argument avec '--year'.
    parser.add_argument("--year", type=int, choices=[2026], default=2026)
    # On appelle parser.add_argument avec '--child-timeout'.
    parser.add_argument("--child-timeout", type=int, default=3600)
    # On récupère les options de l’entrée métier. Le lancement exige ensuite les confirmations
    # explicites ; un diagnostic n’exécute pas le plan.
    args = parser.parse_args(argv)
    # Refuser AVANT lecture de configuration ou connexion.
    if args.run and (
        args.all_vineyards
        # Ce cas est aussi retenu si la condition args.allow_business_writes n’est pas remplie.
        or not args.allow_business_writes
        # Ce cas est aussi retenu si la condition args.confirm_nas_read_only n’est pas remplie.
        or not args.confirm_nas_read_only
    ):
        # On appelle parser.error avec '--run exige un seul --vineyard, --allow-business-writes et
        # --confirm-nas-read-only.'.
        parser.error(
            "--run exige un seul --vineyard, --allow-business-writes et --confirm-nas-read-only."
        )
    # Cette branche traite le cas où le test args.diagnostic_only est satisfait et le test
    # args.allow_business_writes est satisfait ou le test args.confirm_nas_read_only est satisfait.
    if args.diagnostic_only and (
        args.allow_business_writes or args.confirm_nas_read_only
    ):
        # On appelle parser.error avec 'Les confirmations de lancement ne concernent pas
        # --diagnostic-only.'.
        parser.error(
            "Les confirmations de lancement ne concernent pas --diagnostic-only."
        )
    # On tente ce bloc et on traite séparément les erreurs prévues : WorkflowBusy,
    # ImporterDiagnosticError, BusinessConfigurationError, KeyboardInterrupt, Exception.
    try:
        # On nettoie et contrôle le nom du domaine avant du comparer au périmètre du plan.
        name = (
            validate_one_vineyard(args.vineyard) if args.vineyard is not None else None
        )
        # On capture les paramètres nécessaires au parcours ; ils seront passés explicitement aux
        # opérations qui les utilisent.
        config = load_business_configuration(
            args.project_root, configuration_mode=args.configuration_mode
        )
        # On prépare les opérations en utilisant la configuration capturée ; la branche diagnostic
        # peut ainsi contrôler l’environnement sans exécuter le plan.
        plan = build_business_plan(
            config,
            # On transmet la sélection explicite des domaines concernés par cet appel.
            vineyards=[name] if name else None,
            # Ce paramètre distingue le choix de tous les domaines d’une liste de sélection explicite.
            all_vineyards=args.all_vineyards,
            # On transmet la saison à utiliser pour les contrôles et les chemins concernés.
            year=args.year,
            # On fournit le délai maximal en secondes via le paramètre timeout_seconds de cet appel.
            timeout_seconds=args.child_timeout,
        )
        # Cette branche s’arrête aux vérifications préalables ; elle ne passe pas à l’exécution des
        # étapes métier située après elle.
        if args.diagnostic_only:
            # Meme verrou local que les lancements reels, jamais de journal SQL/local.
            with workflow_lock(config.root, str(uuid4())):
                # On garde dans counts la valeur renvoyée par diagnose_importer.
                counts = diagnose_importer(config)
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                "Connexion et droits importeur verifies depuis l entree metier ; verrous SQL liberes par ROLLBACK."
            )
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                "Bilans actifs : %d | lignes Excel conservees : %d | acquisitions historiques : %d"
                % counts
            )
            # On affiche le bilan de ce contrôle ; le code de retour qui suit reste nécessaire pour un
            # appel depuis un autre outil.
            print("RESULTAT : OK — diagnostic de l entree metier reussi.")
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                "Aucune ingestion, consultation NAS, ecriture SQL ou creation de journal workflow."
            )
            # On affiche ce texte explicite dans la sortie du programme.
            print("Verrou local acquis puis libere ; aucune execution des huit etapes.")
            # On termine cette branche avec la valeur 0 ; à la sortie d’un main, elle sert de code de
            # retour.
            return 0
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "MODE METIER CONFIRME : ecritures locales et PostgreSQL autorisees ; NAS en lecture seule."
        )
        # Après les confirmations explicites, on exécute le plan. Des étapes peuvent déjà avoir
        # validé leurs écritures si une étape ultérieure échoue.
        result = execute_business(
            config,
            plan,
            # On fournit le domaine concerné via le paramètre vineyard de cet appel.
            vineyard=name,
            # On transmet la saison à utiliser pour les contrôles et les chemins concernés.
            year=args.year,
            allow_business_writes=args.allow_business_writes,
            confirm_nas_read_only=args.confirm_nas_read_only,
        )
        # On affiche 'Workflow : ' + result['workflow_execution_id'] dans la sortie du programme.
        print("Workflow : " + result["workflow_execution_id"])
        # On affiche 'Etapes confirmees : ' + str(len(result['completed_steps'])) + '/8' dans la sortie
        # du programme.
        print("Etapes confirmees : " + str(len(result["completed_steps"])) + "/8")
        # On affiche 'Journal local : ' + result['journal_relative_path'] dans la sortie du programme.
        print("Journal local : " + result["journal_relative_path"])
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "RESULTAT METIER : "
            + result["status"]
            + (" ; code=" + result["error_code"] if result["error_code"] else "")
        )
        # On garde l’échec explicite : certaines étapes peuvent déjà être validées et ne doivent pas
        # être relancées comme si rien ne s’était passé.
        if result["status"] != "success":
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                "Arreter : des etapes peuvent avoir ete commises. Pas de rollback global ni reprise automatique."
            )
        # Le code 0 est réservé à la réussite confirmée ; un outil appelant peut ainsi distinguer un
        # affichage de résultat d’un traitement réussi.
        return 0 if result["status"] == "success" else 1
    except WorkflowBusy:
        # On affiche cette information de suivi dans la sortie du programme.
        print("ENTREE BLOQUEE : WORKFLOW_BUSY ; aucun nettoyage automatique du verrou.")
        # On termine cette branche avec la valeur 1 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 1
    except ImporterDiagnosticError:
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "ENTREE BLOQUEE : IMPORT_DIAGNOSTIC_FAILED ; aucune ingestion ni ecriture journal/metier commencee."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Utiliser le diagnostic existant pour preciser le blocage ; ne pas elargir les droits."
        )
        # On termine cette branche avec la valeur 1 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 1
    except BusinessConfigurationError as exc:
        # On affiche 'ENTREE BLOQUEE : ' + str(exc) dans la sortie du programme.
        print("ENTREE BLOQUEE : " + str(exc))
        # On termine cette branche avec la valeur 1 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 1
    except KeyboardInterrupt:
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "ENTREE INTERROMPUE ; aucun succes annonce. Examiner les traces avant toute relance."
        )
        # On termine cette branche avec la valeur 130 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 130
    except Exception as exc:
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "ENTREE NON CONFIRMEE : "
            + type(exc).__name__
            + " ; details sensibles non affiches."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Arreter et examiner les traces locales ; ne pas supposer les operations precedentes annulees."
        )
        # On termine cette branche avec la valeur 1 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 1


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On termine ce programme avec le résultat du point d’entrée ; un import du module ne doit pas
    # lancer ce bloc.
    raise SystemExit(main())
