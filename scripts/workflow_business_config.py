# Lecture du fichier — Validation de la configuration utilisée par le workflow métier.
# On vérifie la racine locale et les paramètres attendus avant de construire les opérations. Avoir
# une configuration valide ne prouve pas que les services sont disponibles.
#

"""Configuration capturee pour le workflow metier ; aucun traitement a l'import."""

# On décrit les champs d’un objet de données sans écrire toute sa construction à la main.
from dataclasses import dataclass, field
# On calcule des empreintes de contenu pour détecter les différences ; ce ne sont pas des mots de
# passe chiffrés.
import hashlib
# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On rend disponibles MappingProxyType depuis types, pour les appels de ce fichier.
from types import MappingProxyType

# On rend disponibles database_config, MODE_VARIABLE depuis import_connection_config, pour les appels
# de ce fichier.
from import_connection_config import database_config, MODE_VARIABLE
# On rend disponibles nas_path depuis workflow_nas_executor, pour les appels de ce fichier.
from workflow_nas_executor import nas_path


class BusinessConfigurationError(ValueError):
    """Code stable, sans chemin sensible ni valeur de secret."""


@dataclass(frozen=True)
class BusinessConfiguration:
    # On déclare le champ root avec le type attendu Path ; sa valeur sera fournie lors de la
    # construction de l’objet.
    root: Path
    # On déclare le champ configuration_mode avec le type attendu str ; sa valeur sera fournie lors de
    # la construction de l’objet.
    configuration_mode: str
    # On garde dans nas_brut_root la valeur du champ lue avec les règles définies dans ce module.
    nas_brut_root: str = field(repr=False)
    # On garde dans nas_processing_root la valeur du champ lue avec les règles définies dans ce module.
    nas_processing_root: str = field(repr=False)
    # On garde dans importer la valeur du champ lue avec les règles définies dans ce module.
    importer: object = field(repr=False)


# On rassemble dans LOCAL_DIRECTORIES les 8 éléments explicitement indiqués, en conservant leur
# structure.
LOCAL_DIRECTORIES = (
    "data",
    "data/01_incoming/suivi_acquisitions",
    "data/02_raw_archive",
    "data/03_normalized",
    "data/04_rejected",
    "state",
    "config",
    "logs",
)
# On rassemble dans REQUIRED_FILES les 6 éléments explicitement indiqués, en conservant leur structure.
REQUIRED_FILES = (
    "config/tracking_files.yml",
    "src/suivi_traitements_post_saison/ingestion/tracking_versioning.py",
    "src/suivi_traitements_post_saison/ingestion/excel_reader.py",
    "src/suivi_traitements_post_saison/extraction/nas_live_evidence_extractor.py",
    "src/suivi_traitements_post_saison/extraction/workflow_nas_environment.py",
    "src/suivi_traitements_post_saison/reconciliation/excel_nas_live_reconciler.py",
)


def local_project(root):
    # On garde dans path un objet chemin local ; sa construction seule ne prouve pas que le fichier
    # existe.
    path = Path(root)
    # Cette branche traite le cas où str(path) commence par ('\\\\', '//').
    if str(path).startswith(("\\\\", "//")):
        # On interrompt cette branche avec BusinessConfigurationError : 'PROJECT_MUST_BE_LOCAL'.
        raise BusinessConfigurationError("PROJECT_MUST_BE_LOCAL")
    # On garde dans root le chemin absolu résolu de path, en tenant compte des liens symboliques.
    root = path.resolve()
    # Cette branche traite le cas où la condition root.is_dir() n’est pas remplie.
    if not root.is_dir():
        # On interrompt cette branche avec BusinessConfigurationError : 'PROJECT_MISSING'.
        raise BusinessConfigurationError("PROJECT_MISSING")
    # On parcourt (*LOCAL_DIRECTORIES, *REQUIRED_FILES, '.env') ; relative désigne l’élément courant à
    # chaque passage dans la boucle.
    for relative in (*LOCAL_DIRECTORIES, *REQUIRED_FILES, ".env"):
        # On garde la racine locale du projet sous le nom target ; cette affectation ne copie pas à
        # elle seule un objet mutable.
        target = root
        # On parcourt Path(relative).parts ; part désigne l’élément courant à chaque passage dans la
        # boucle.
        for part in Path(relative).parts:
            # On calcule ce quotient pour construire target.
            target = target / part
            # Cette branche traite le cas où le contrôle target.is_symlink() est positif ou le contrôle
            # hasattr(target, 'is_junction') est positif et le contrôle target.is_junction() est
            # positif.
            if target.is_symlink() or (
                hasattr(target, "is_junction") and target.is_junction()
            ):
                # On interrompt cette branche avec BusinessConfigurationError :
                # 'LOCAL_PATH_REDIRECTED'.
                raise BusinessConfigurationError("LOCAL_PATH_REDIRECTED")
        # On évite de charger un fichier de configuration extérieur par un chemin redirigé.
        if not target.resolve().is_relative_to(root):
            # On interrompt cette branche avec BusinessConfigurationError : 'LOCAL_PATH_REDIRECTED'.
            raise BusinessConfigurationError("LOCAL_PATH_REDIRECTED")
    # On parcourt REQUIRED_FILES ; relative désigne l’élément courant à chaque passage dans la boucle.
    for relative in REQUIRED_FILES:
        # Cette branche traite le cas où la condition (root / relative).is_file() n’est pas remplie.
        if not (root / relative).is_file():
            # On interrompt cette branche avec BusinessConfigurationError :
            # 'REQUIRED_SOURCE_OR_CONFIG_MISSING'.
            raise BusinessConfigurationError("REQUIRED_SOURCE_OR_CONFIG_MISSING")
    # On remet la racine locale du projet à l’appelant ; les étapes suivantes de cette fonction ne sont
    # plus parcourues.
    return root


# On charge et contrôle les paramètres nécessaires au parcours métier.
def load_business_configuration(root, *, configuration_mode="local"):
    # On garde dans root la valeur renvoyée par local_project.
    root = local_project(root)
    # On vérifie ce cas avant la suite : configuration_mode ne figure pas dans {'local',
    # 'environment'}.
    if configuration_mode not in {"local", "environment"}:
        # On interrompt cette branche avec BusinessConfigurationError : 'CONFIGURATION_MODE_INVALID'.
        raise BusinessConfigurationError("CONFIGURATION_MODE_INVALID")
    # On garde dans effective la valeur de la variable d’environnement demandée, ou son repli si elle
    # est absente.
    effective = os.environ.get(MODE_VARIABLE, "local")
    # On vérifie ce cas avant la suite : effective diffère de configuration_mode.
    if effective != configuration_mode:
        # On interrompt cette branche avec BusinessConfigurationError :
        # 'IMPORT_CONFIGURATION_MODE_MISMATCH'.
        raise BusinessConfigurationError("IMPORT_CONFIGURATION_MODE_MISMATCH")
    # On initialise before à None : aucune valeur n’a encore été retenue ici.
    before = None
    # On rassemble dans env_keys les 7 éléments explicitement indiqués, en conservant leur structure.
    env_keys = (
        "NAS_BRUT_ROOT",
        "NAS_PROCESSING_ROOT",
        MODE_VARIABLE,
        "PROJECT12_IMPORT_HOST",
        "PROJECT12_IMPORT_PORT",
        "PROJECT12_IMPORT_USER",
        "PROJECT12_IMPORT_PASSWORD",
    )
    # On choisit la valeur de env_before selon ce test : configuration_mode correspond au texte
    # 'environment'. Les deux résultats possibles restent définis explicitement ici.
    env_before = (
        {key: os.environ.get(key) for key in env_keys}
        if configuration_mode == "environment"
        else None
    )
    # On tente ce bloc et on traite séparément les erreurs prévues : BusinessConfigurationError,
    # Exception.
    try:
        # On vérifie ce cas avant la suite : configuration_mode correspond au texte 'local'.
        if configuration_mode == "local":
            # On rend disponibles dotenv_values depuis dotenv, pour les appels de ce fichier.
            from dotenv import dotenv_values

            # On construit source_path en assemblant les morceaux du chemin. L’opérateur / de
            # pathlib ne crée ni dossier ni fichier.
            source_path = root / ".env"
            # Cette branche traite le cas où la condition source_path.is_file() n’est pas remplie.
            if not source_path.is_file():
                # On interrompt cette branche avec BusinessConfigurationError :
                # 'LOCAL_CONFIGURATION_MISSING'.
                raise BusinessConfigurationError("LOCAL_CONFIGURATION_MISSING")
            # On garde l’empreinte du .env avant sa lecture pour vérifier ensuite que les réglages
            # n’ont pas été remplacés entre deux accès.
            before = hashlib.sha256(source_path.read_bytes()).digest()
            # On lit les réglages du fichier sans les injecter automatiquement dans l’environnement
            # global ; les secrets ne doivent pas être affichés.
            source = dotenv_values(source_path, encoding="utf-8-sig", interpolate=False)
        else:
            # On indexe le résultat par key, avec os.environ.get(key) comme valeur ; les contrôles
            # d’unicité sont importants car une même clé ne garde qu’une valeur dans un
            # dictionnaire.
            source = {
                key: os.environ.get(key)
                for key in ("NAS_BRUT_ROOT", "NAS_PROCESSING_ROOT")
            }
        # On récupère la racine des données brutes, séparément de la racine des traitements ; ces
        # deux emplacements n’ont pas le même rôle.
        brut = source.get("NAS_BRUT_ROOT")
        # On récupère la racine des sorties de traitement, où l’on cherchera notamment les fichiers
        # livrables.
        processing = source.get("NAS_PROCESSING_ROOT")
        # Ce contrôle valide la forme absolue de la racine brute. Il ne prouve pas que le NAS est
        # monté ni qu’on peut le lire.
        nas_path(brut)
        # On appelle nas_path avec processing.
        nas_path(processing)  # Forme du chemin, jamais son accessibilite.
    except BusinessConfigurationError:
        # On laisse remonter l’erreur déjà interceptée, sans la remplacer par une réussite ni en
        # fabriquer une autre.
        raise
    except Exception:
        # On interrompt cette branche avec BusinessConfigurationError : 'NAS_CONFIGURATION_INVALID'.
        raise BusinessConfigurationError("NAS_CONFIGURATION_INVALID") from None
    # On tente ce bloc et on traite séparément les erreurs prévues : BusinessConfigurationError,
    # Exception.
    try:
        # On garde dans importer les paramètres du compte PostgreSQL prévus par ce module.
        importer = database_config(
            root
        )  # Compte importer uniquement ; aucun repli admin.
        # On récupère importer['password'] et on le garde dans password pour la suite.
        password = importer["password"]
        # Cette branche traite le cas où au moins un élément satisfait le test indiqué.
        if any(c in password for c in ("\x00", "\r", "\n")):
            # On interrompt cette branche avec ValueError : 'invalid'.
            raise ValueError("invalid")
        # Cette branche traite le cas où env_before est renseigné (différent de None) et {key:
        # os.environ.get(key) for key in env_keys} diffère de env_before.
        if (
            env_before is not None
            # On exige aussi que {key: os.environ.get(key) for key in env_keys} diffère de env_before.
            and {key: os.environ.get(key) for key in env_keys} != env_before
        ):
            # On interrompt cette branche avec BusinessConfigurationError :
            # 'ENVIRONMENT_CONFIGURATION_CHANGED'.
            raise BusinessConfigurationError("ENVIRONMENT_CONFIGURATION_CHANGED")
        # On compare l’empreinte des octets actuels à celle du lot attendu ; une différence doit
        # bloquer le mélange de versions.
        if (
            before is not None
            # On exige aussi que hashlib.sha256((root / '.env').read_bytes()).digest() diffère de
            # l’état relevé avant l’opération.
            and hashlib.sha256((root / ".env").read_bytes()).digest() != before
        ):
            # On interrompt cette branche avec BusinessConfigurationError :
            # 'LOCAL_CONFIGURATION_CHANGED'.
            raise BusinessConfigurationError("LOCAL_CONFIGURATION_CHANGED")
    except BusinessConfigurationError:
        # On laisse remonter l’erreur déjà interceptée, sans la remplacer par une réussite ni en
        # fabriquer une autre.
        raise
    except Exception:
        # On interrompt cette branche avec BusinessConfigurationError : 'IMPORT_CONFIGURATION_INVALID'.
        raise BusinessConfigurationError("IMPORT_CONFIGURATION_INVALID") from None
    # Les autres variables du .env, dont admin/dashboard, ne sont pas conservees.
    return BusinessConfiguration(
        root, configuration_mode, brut, processing, MappingProxyType(dict(importer))
    )
