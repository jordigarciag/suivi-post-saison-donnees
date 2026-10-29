# Lecture du fichier — Point d’entrée du diagnostic métier.
# On transmet les options au parcours de contrôle ; on garde ce lancement distinct d’une exécution
# d’ingestion.
#

"""Controle LOCAL du raccordement metier. Aucun --run, NAS ou PostgreSQL."""

# On importe argparse. On décrit les options de la commande et on contrôle leur forme.
import argparse
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On rend disponibles load_business_configuration, BusinessConfigurationError depuis
# workflow_business_config, pour les appels de ce fichier.
from workflow_business_config import (
    load_business_configuration,
    BusinessConfigurationError,
)
# On rend disponibles build_business_plan depuis workflow_business_wiring, pour les appels de ce
# fichier.
from workflow_business_wiring import build_business_plan


def main(argv=None):
    # On garde dans parser le lecteur des options de cette commande.
    parser = argparse.ArgumentParser(description=__doc__)
    # On appelle parser.add_argument avec '--check-only'.
    parser.add_argument("--check-only", action="store_true", required=True)
    # On appelle parser.add_argument avec '--configuration-mode'.
    parser.add_argument(
        "--configuration-mode", choices=["local", "environment"], default="local"
    )
    # On appelle parser.add_argument avec '--project-root'.
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    # On déclare des options incompatibles entre elles : le parseur rejettera leur emploi simultané
    # avant le traitement.
    group = parser.add_mutually_exclusive_group(required=True)
    # On appelle group.add_argument avec '--vineyard'.
    group.add_argument("--vineyard", action="append")
    # On appelle group.add_argument avec '--all-vineyards'.
    group.add_argument("--all-vineyards", action="store_true")
    # On appelle parser.add_argument avec '--year'.
    parser.add_argument("--year", type=int, default=2026)
    # On appelle parser.add_argument avec '--child-timeout'.
    parser.add_argument("--child-timeout", type=int, default=3600)
    # On lit les options du contrôle local. Cette commande ne possède pas de mode
    # permettant de lancer les huit étapes métier.
    args = parser.parse_args(argv)
    # On tente ce bloc et on traite séparément les erreurs prévues : BusinessConfigurationError,
    # Exception.
    try:
        # On charge la configuration explicitement ; valider ses valeurs ne démontre pas encore que
        # PostgreSQL et le NAS sont accessibles.
        config = load_business_configuration(
            args.project_root, configuration_mode=args.configuration_mode
        )
        # On construit le plan pour vérifier son assemblage sans déclencher les fonctions métier
        # qu’il contient.
        plan = build_business_plan(
            config,
            # On transmet la sélection explicite des domaines concernés par cet appel.
            vineyards=args.vineyard,
            # Ce paramètre distingue le choix de tous les domaines d’une liste de sélection explicite.
            all_vineyards=args.all_vineyards,
            # On transmet la saison à utiliser pour les contrôles et les chemins concernés.
            year=args.year,
            # On fournit le délai maximal en secondes via le paramètre timeout_seconds de cet appel.
            timeout_seconds=args.child_timeout,
        )
        # On affiche ce texte explicite dans la sortie du programme.
        print("CONTROLE LOCAL : mode de configuration et compte importeur prepares.")
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Chemins NAS : forme absolue verifiee ; accessibilite NON testee ; valeurs non affichees."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Executor a environnement minimal raccorde ; mode NAS environment impose aux enfants."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print("Huit etapes raccordees : " + ", ".join(name for name, _ in plan.steps))
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Journal PostgreSQL prepare avec une connexion dediee ; aucune connexion ouverte."
        )
        # On affiche le bilan de ce contrôle ; le code de retour qui suit reste nécessaire pour un
        # appel depuis un autre outil.
        print("RESULTAT : OK — raccordement construit, aucune etape executee.")
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Aucune ingestion, consultation NAS, ecriture SQL, creation de verrou/journal ou modification de configuration."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Les donnees sources, droits/connectivite SQL, partage de state et DAG complet restent a valider."
        )
        # On termine cette branche avec la valeur 0 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 0
    except BusinessConfigurationError as exc:
        # On affiche 'CONTROLE LOCAL BLOQUE : ' + str(exc) dans la sortie du programme.
        print("CONTROLE LOCAL BLOQUE : " + str(exc))  # Codes fixes uniquement.
        # On termine cette branche avec la valeur 1 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 1
    except Exception as exc:
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "CONTROLE LOCAL NON CONFIRME : "
            + type(exc).__name__
            + " ; ne pas lancer de traitement reel."
        )
        # On termine cette branche avec la valeur 1 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 1


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On termine ce programme avec le résultat du point d’entrée ; un import du module ne doit pas
    # lancer ce bloc.
    raise SystemExit(main())
