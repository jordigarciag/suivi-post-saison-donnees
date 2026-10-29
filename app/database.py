# Lecture du fichier — Accès PostgreSQL du dashboard avec un compte destiné à la consultation.
# On prépare les paramètres localement, puis les méthodes de lecture ouvrent leurs connexions. Cette
# base métier est distincte de la base technique d’Airflow.
#

# On diffère l’évaluation des annotations de type ; cette directive doit rester avant les autres
# imports.
from __future__ import annotations

# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On rend disponibles Any, Iterable, Sequence depuis typing, pour les appels de ce fichier.
from typing import Any, Iterable, Sequence


# On signale la dépendance manquante avec une indication d’installation plutôt que masquer l’échec.
def _require_dependency(name: str, exc: Exception) -> None:
    # On interrompt cette branche avec RuntimeError. La cause initiale reste attachée grâce à from.
    raise RuntimeError(
        f"La dépendance '{name}' est requise. Installe requirements-dashboard.txt."
    ) from exc


# On regroupe dans DEFAULT_DB_CONFIG ces champs nommés ; on pourra les retrouver par leur clé plutôt
# que par leur position.
DEFAULT_DB_CONFIG = {
    # On associe la clé 'host' à cette valeur dans cet objet.
    "host": "127.0.0.1",
    # On associe la clé 'port' à cette valeur dans cet objet.
    "port": 5433,
    # On associe la clé 'dbname' à cette valeur dans cet objet.
    "dbname": "suivi_acquisitions",
    # On associe la clé 'user_env' à cette valeur dans cet objet.
    "user_env": "PROJECT12_DASHBOARD_USER",
    # On associe la clé 'password_env' à cette valeur dans cet objet.
    "password_env": "PROJECT12_DASHBOARD_PASSWORD",
}


# On retrouve la racine du projet à partir de la configuration ou de l’emplacement des fichiers.
def locate_project_root(explicit_root: str | None = None) -> Path:
    # Cette branche traite le cas où explicit_root est évalué comme vrai.
    if explicit_root:
        # On fournit à l’appelant le chemin absolu résolu de Path(explicit_root).expanduser(), en
        # tenant compte des liens symboliques.
        return Path(explicit_root).expanduser().resolve()
    # On garde dans env_root la valeur renvoyée par os.getenv pour 'DASHBOARD_PROJECT_ROOT'.
    env_root = os.getenv("DASHBOARD_PROJECT_ROOT")
    # Cette branche traite le cas où env_root est évalué comme vrai.
    if env_root:
        # On fournit à l’appelant le chemin absolu résolu de Path(env_root).expanduser(), en tenant
        # compte des liens symboliques.
        return Path(env_root).expanduser().resolve()
    # On garde Path(__file__).resolve().parent sous le nom here ; cette affectation ne copie pas à elle
    # seule un objet mutable.
    here = Path(__file__).resolve().parent
    # On parcourt [here.parent, *here.parents] ; candidate désigne l’élément courant à chaque passage
    # dans la boucle.
    for candidate in [here.parent, *here.parents]:
        # Cette branche traite le cas où candidate / '.env' existe.
        if (candidate / ".env").exists():
            # On remet candidate à l’appelant ; les étapes suivantes de cette fonction ne sont plus
            # parcourues.
            return candidate
    # On remet here.parent à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return here.parent


# On lit les paramètres locaux du projet ; les valeurs sensibles ne doivent pas être affichées ni
# publiées.
def load_dotenv_values(project_root: Path) -> dict[str, str]:
    # On construit env_path en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée
    # ni dossier ni fichier.
    env_path = project_root / ".env"
    # Cette branche traite le cas où la condition env_path.exists() n’est pas remplie.
    if not env_path.exists():
        # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
        # information par sa clé.
        return {}
    # On tente ce bloc et on traite séparément les erreurs prévues : Exception.
    try:
        # On rend disponibles dotenv_values depuis dotenv, pour les appels de ce fichier.
        from dotenv import dotenv_values
    except Exception as exc:  # pragma: no cover - dependency path
        # On appelle _require_dependency avec 'python-dotenv'.
        _require_dependency("python-dotenv", exc)
    # On lit les réglages du fichier sans les injecter automatiquement dans l’environnement global ;
    # les secrets ne doivent pas être affichés.
    values = dotenv_values(env_path, encoding="utf-8-sig", interpolate=False)
    # On remet {k: v for k, v in values.items() if isinstance(v, str)} à l’appelant ; les étapes
    # suivantes de cette fonction ne sont plus parcourues.
    return {k: v for k, v in values.items() if isinstance(v, str)}


# On prépare les paramètres PostgreSQL sans afficher les valeurs sensibles.
def build_connection_kwargs(project_root: Path | None = None) -> dict[str, Any]:
    # On garde dans root la valeur renvoyée par locate_project_root.
    root = locate_project_root(str(project_root) if project_root else None)
    # On garde dans env_values la valeur renvoyée par load_dotenv_values.
    env_values = load_dotenv_values(root)
    # On retient pour user la première valeur évaluée comme vraie dans cette chaîne de replis ; une
    # valeur vide fera donc passer à la suivante.
    user = os.getenv(DEFAULT_DB_CONFIG["user_env"]) or env_values.get(
        DEFAULT_DB_CONFIG["user_env"], "projet12_dashboard"
    )
    # On retient pour password la première valeur évaluée comme vraie dans cette chaîne de replis ; une
    # valeur vide fera donc passer à la suivante.
    password = os.getenv(DEFAULT_DB_CONFIG["password_env"]) or env_values.get(
        DEFAULT_DB_CONFIG["password_env"], ""
    )
    # On n’essaie pas de connexion sans le secret du compte de consultation.
    if not password:
        # On interrompt cette branche avec RuntimeError.
        raise RuntimeError(
            "Le mot de passe dashboard est introuvable dans les variables d'environnement ou le .env du projet."
        )
    # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
    # information par sa clé.
    return {
        # On associe la clé 'host' à cette valeur dans cet objet.
        "host": DEFAULT_DB_CONFIG["host"],
        # On associe la clé 'port' à cette valeur dans cet objet.
        "port": DEFAULT_DB_CONFIG["port"],
        # On associe la clé 'dbname' à cette valeur dans cet objet.
        "dbname": DEFAULT_DB_CONFIG["dbname"],
        # On associe la clé 'user' à cette valeur dans cet objet.
        "user": user,
        # On associe la clé 'password' à cette valeur dans cet objet.
        "password": password,
        # On associe la clé 'connect_timeout' à cette valeur dans cet objet.
        "connect_timeout": 5,
    }


class DatabaseClient:
    def __init__(self, project_root: Path | None = None):
        # On garde dans self.project_root la valeur renvoyée par locate_project_root.
        self.project_root = locate_project_root(
            str(project_root) if project_root else None
        )
        # On garde dans self.connection_kwargs la valeur renvoyée par build_connection_kwargs.
        self.connection_kwargs = build_connection_kwargs(self.project_root)

    # On ouvre la connexion PostgreSQL avec les paramètres préparés pour cet accès.
    def _connect(self):
        # On tente ce bloc et on traite séparément les erreurs prévues : Exception.
        try:
            # On importe psycopg. On utilise le pilote de connexion PostgreSQL ; l’import seul n’ouvre
            # pas de connexion.
            import psycopg
            # On rend disponibles dict_row depuis psycopg.rows, pour les appels de ce fichier.
            from psycopg.rows import dict_row
        except Exception as exc:  # pragma: no cover - dependency path
            # On appelle _require_dependency avec 'psycopg'.
            _require_dependency("psycopg", exc)
        # Cette instruction ouvre réellement une connexion PostgreSQL avec les paramètres préparés ;
        # ce n’est plus une simple validation de configuration.
        return psycopg.connect(row_factory=dict_row, **self.connection_kwargs)

    # On applique la configuration de session prévue pour la consultation.
    def _prepare_connection(self, connection) -> None:
        # On envoie cette requête à connection avec ses paramètres ; son résultat sera contrôlé
        # séparément.
        connection.execute("SET TRANSACTION READ ONLY")
        # On applique ce réglage à la transaction courante ; il ne s’agit pas de modifier
        # durablement la configuration du serveur PostgreSQL.
        connection.execute("SET LOCAL jit = off")
        # On envoie cette requête à connection avec ses paramètres ; son résultat sera contrôlé
        # séparément.
        connection.execute("SET LOCAL statement_timeout = '120s'")
        # On envoie cette requête à connection avec ses paramètres ; son résultat sera contrôlé
        # séparément.
        connection.execute("SET LOCAL lock_timeout = '5s'")

    # On récupère les vues prévues et on garde la trace de celles qui ne sont pas disponibles.
    def fetch_bundle(self, required, optional):
        """All data views see one PostgreSQL snapshot; optional failures isolated.

        No DDL/DML, no role changes, no commits. SAVEPOINT only recovers a
        failed optional SELECT while keeping the read-only snapshot stable.
        """
        # On distribue ces valeurs entre frames, missing, dans l’ordre de l’affectation. Chaque nom
        # reçoit son propre élément.
        frames, missing = {}, []
        # On utilise self._connect() dans son contexte de gestion ; les opérations de sortie sont
        # exécutées en quittant le bloc.
        with self._connect() as connection:
            # On envoie cette requête à connection avec ses paramètres ; son résultat sera contrôlé
            # séparément.
            connection.execute(
                "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
            )
            # On applique ce réglage à la transaction courante ; il ne s’agit pas de modifier
            # durablement la configuration du serveur PostgreSQL.
            connection.execute("SET LOCAL jit = off")
            # On envoie cette requête à connection avec ses paramètres ; son résultat sera contrôlé
            # séparément.
            connection.execute("SET LOCAL statement_timeout = '120s'")
            # On envoie cette requête à connection avec ses paramètres ; son résultat sera contrôlé
            # séparément.
            connection.execute("SET LOCAL lock_timeout = '5s'")
            # On parcourt required ; name désigne l’élément courant à chaque passage dans la boucle.
            for name in required:
                # On construit frames[name] comme une liste à partir de dict(r), pour chaque r de
                # connection.execute(f'SELECT * FROM "mart"."{name}"').fetchall().
                frames[name] = [
                    dict(r)
                    for r in connection.execute(
                        f'SELECT * FROM "mart"."{name}"'
                    ).fetchall()
                ]
            # On parcourt optional ; name désigne l’élément courant à chaque passage dans la boucle.
            for name in optional:
                # On envoie cette requête à connection avec ses paramètres ; son résultat sera contrôlé
                # séparément.
                connection.execute("SAVEPOINT optional_history")
                # On tente ce bloc et on traite séparément les erreurs prévues : Exception.
                try:
                    # On construit frames[name] comme une liste à partir de dict(r), pour chaque r de
                    # connection.execute(f'SELECT * FROM "mart"."{name}"').fetchall().
                    frames[name] = [
                        dict(r)
                        for r in connection.execute(
                            f'SELECT * FROM "mart"."{name}"'
                        ).fetchall()
                    ]
                except Exception:
                    # On envoie cette requête à connection avec ses paramètres ; son résultat sera
                    # contrôlé séparément.
                    connection.execute("ROLLBACK TO SAVEPOINT optional_history")
                    # On ajoute name à la fin de missing ; les éléments précédents restent conservés.
                    missing.append(name)
                # On envoie cette requête à connection avec ses paramètres ; son résultat sera contrôlé
                # séparément.
                connection.execute("RELEASE SAVEPOINT optional_history")
            # On annule les écritures non validées dans cette transaction, sans prétendre annuler les
            # opérations déjà commises ailleurs.
            connection.rollback()
        # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
        return frames, missing

    # On lit les colonnes disponibles pour adapter la consultation à la structure réellement
    # présente.
    def list_columns(self, view_name: str, schema: str = "mart") -> list[str]:
        # On utilise ce texte pour sql ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        sql = """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """
        # On utilise self._connect() dans son contexte de gestion ; les opérations de sortie sont
        # exécutées en quittant le bloc.
        with self._connect() as connection:
            # On appelle self._prepare_connection avec connection.
            self._prepare_connection(connection)
            # On récupère toutes les lignes du résultat SQL en mémoire avant des comparer ou de
            # les présenter.
            rows = connection.execute(sql, (schema, view_name)).fetchall()
            # On annule les écritures non validées dans cette transaction, sans prétendre annuler les
            # opérations déjà commises ailleurs.
            connection.rollback()
        # On remet [row['column_name'] for row in rows] à l’appelant ; les étapes suivantes de cette
        # fonction ne sont plus parcourues.
        return [row["column_name"] for row in rows]

    # On lit les lignes demandées à travers les paramètres internes de cet accès.
    def fetch_rows(
        self,
        view_name: str,
        schema: str = "mart",
        limit: int | None = None,
        where_sql: str | None = None,
        params: Sequence[Any] | None = None,
        order_by: str | None = None,
    ) -> list[dict[str, Any]]:
        # On rassemble dans parts les 1 éléments explicitement indiqués, en conservant leur structure.
        parts = [f'SELECT * FROM "{schema}"."{view_name}"']
        # Cette branche traite le cas où where_sql est évalué comme vrai.
        if where_sql:
            # On ajoute f'WHERE {where_sql}' à la fin de parts ; les éléments précédents restent
            # conservés.
            parts.append(f"WHERE {where_sql}")
        # Cette branche traite le cas où order_by est évalué comme vrai.
        if order_by:
            # On ajoute f'ORDER BY {order_by}' à la fin de parts ; les éléments précédents restent
            # conservés.
            parts.append(f"ORDER BY {order_by}")
        # On vérifie ce cas avant la suite : limit est renseigné (différent de None).
        if limit is not None:
            # On ajoute 'LIMIT %s' à la fin de parts ; les éléments précédents restent conservés.
            parts.append("LIMIT %s")
        # On garde dans sql le texte formé en réunissant les éléments avec ' ' comme séparateur.
        sql = " ".join(parts)
        # On garde dans final_params une liste matérialisée à partir de params or [].
        final_params: list[Any] = list(params or [])
        # On vérifie ce cas avant la suite : limit est renseigné (différent de None).
        if limit is not None:
            # On ajoute limit à la fin de final_params ; les éléments précédents restent conservés.
            final_params.append(limit)
        # On utilise self._connect() dans son contexte de gestion ; les opérations de sortie sont
        # exécutées en quittant le bloc.
        with self._connect() as connection:
            # On appelle self._prepare_connection avec connection.
            self._prepare_connection(connection)
            # On récupère toutes les lignes du résultat SQL en mémoire avant des comparer ou de
            # les présenter.
            rows = connection.execute(sql, final_params).fetchall()
            # On annule les écritures non validées dans cette transaction, sans prétendre annuler les
            # opérations déjà commises ailleurs.
            connection.rollback()
        # On remet [dict(row) for row in rows] à l’appelant ; les étapes suivantes de cette fonction ne
        # sont plus parcourues.
        return [dict(row) for row in rows]

    # On vérifie la réponse et l’identité de la connexion, sans en déduire la validité de tous les
    # résultats métier.
    def healthcheck(self) -> dict[str, Any]:
        # On utilise self._connect() dans son contexte de gestion ; les opérations de sortie sont
        # exécutées en quittant le bloc.
        with self._connect() as connection:
            # On appelle self._prepare_connection avec connection.
            self._prepare_connection(connection)
            # On récupère une seule ligne du résultat SQL ; les contrôles suivants vérifient les
            # valeurs attendues.
            row = connection.execute(
                "SELECT current_database() AS database_name, current_user AS current_user, session_user AS session_user"
            ).fetchone()
            # On annule les écritures non validées dans cette transaction, sans prétendre annuler les
            # opérations déjà commises ailleurs.
            connection.rollback()
        # On fournit à l’appelant un nouveau dictionnaire construit avec les valeurs indiquées (la
        # copie reste superficielle).
        return dict(row)
