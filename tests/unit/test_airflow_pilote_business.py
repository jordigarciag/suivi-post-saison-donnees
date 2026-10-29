# Lecture du fichier — Tests de airflow pilote business.
#

"""Tests locaux : aucun Docker, NAS, Airflow reel ou connexion SQL."""

# On importe contextlib. Ce module sera utilisé par les opérations de ce fichier.
import contextlib
# On rend disponibles datetime, timezone depuis datetime, pour les appels de ce fichier.
from datetime import datetime, timezone
# On importe importlib.util. Ce module sera utilisé par les opérations de ce fichier.
import importlib.util
# On importe io. On peut fournir des flux en mémoire aux lecteurs et aux captures de sortie.
import io
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe subprocess. On lance et surveille les programmes enfants lorsqu’un parcours l’exige.
import subprocess
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On importe tempfile. On prépare des fichiers ou dossiers temporaires pour les cas isolés.
import tempfile
# On importe types. Ce module sera utilisé par les opérations de ce fichier.
import types
# On importe unittest. On décrit les scénarios et les vérifications de la suite de tests.
import unittest
# On rend disponibles patch depuis unittest.mock, pour les appels de ce fichier.
from unittest.mock import patch
# On rend disponibles uuid4 depuis uuid, pour les appels de ce fichier.
from uuid import uuid4

# On récupère Path(__file__).resolve().parents[2] et on le garde dans ROOT pour la suite.
ROOT = Path(__file__).resolve().parents[2]


def load(name):
    # On garde dans spec la valeur renvoyée par importlib.util.spec_from_file_location.
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    # On garde dans module la valeur renvoyée par importlib.util.module_from_spec.
    module = importlib.util.module_from_spec(spec)
    # On appelle spec.loader.exec_module avec module.
    spec.loader.exec_module(module)
    # On remet module à l’appelant ; les étapes suivantes de cette fonction ne sont plus parcourues.
    return module


# On garde dans prep les données retournées par le chargeur utilisé à cet endroit.
prep = load("prepare_airflow_workflow")
# On garde dans rt les données retournées par le chargeur utilisé à cet endroit.
rt = load("airflow_workflow_runtime_check")
# On garde dans task les données retournées par le chargeur utilisé à cet endroit.
task = load("airflow_pilote_task")


class PreparationTests(unittest.TestCase):
    def tree(self, root):
        # On écrit le contenu préparé dans root / '.env' ; cette opération remplace le contenu du
        # fichier s’il existe déjà.
        (root / ".env").write_text(
            "NAS_BRUT_ROOT=C:/NAS/brute_v2025\nNAS_PROCESSING_ROOT=C:/NAS/data_processing_2025\nPROJECT12_POSTGRES_PASSWORD=secret-admin\nPROJECT12_IMPORT_PASSWORD=secret-importer\n"
        )
        # On écrit le contenu préparé dans root / '.gitignore' ; cette opération remplace le contenu du
        # fichier s’il existe déjà.
        (root / ".gitignore").write_text("data/\nstate/\nlogs/\n")

    def test_only_mount_sources_copied(self):
        # On utilise un dossier temporaire pour cet essai ; les fichiers produits ici ne sont pas ceux
        # de la production.
        with tempfile.TemporaryDirectory() as d:
            # On garde dans root un objet chemin local ; sa construction seule ne prouve pas que le
            # fichier existe.
            root = Path(d)
            # On appelle self.tree avec root.
            self.tree(root)
            # On appelle prep.prepare avec root.
            prep.prepare(root)
            # On garde dans data le texte lu depuis root / '.env.airflow.workflow.local' avec
            # l’encodage indiqué.
            data = (root / ".env.airflow.workflow.local").read_text()
            # On vérifie que 'secret' ne figure pas dans data.
            self.assertNotIn("secret", data)
            # On vérifie que 'PASSWORD' ne figure pas dans data.
            self.assertNotIn("PASSWORD", data)
            # On vérifie que "PROJECT12_WORKFLOW_NAS_SOURCE='C:/NAS'" figure dans data.
            self.assertIn("PROJECT12_WORKFLOW_NAS_SOURCE='C:/NAS'", data)
            # On vérifie que 'PROJECT12_WORKFLOW_BRUT_SOURCE' ne figure pas dans data.
            self.assertNotIn("PROJECT12_WORKFLOW_BRUT_SOURCE", data)

    def test_repeat_preserves_marker_and_configuration(self):
        # On utilise un dossier temporaire pour cet essai ; les fichiers produits ici ne sont pas ceux
        # de la production.
        with tempfile.TemporaryDirectory() as d:
            # On garde dans root un objet chemin local ; sa construction seule ne prouve pas que le
            # fichier existe.
            root = Path(d)
            # On appelle self.tree avec root.
            self.tree(root)
            # On garde dans first la valeur renvoyée par prep.prepare.
            first = prep.prepare(root)
            # On garde dans content les octets lus depuis root / '.env.airflow.workflow.local',
            # avant toute conversion en texte. Les contrôles de contenu pourront ainsi repartir de
            # cette lecture.
            content = (root / ".env.airflow.workflow.local").read_bytes()
            # On vérifie que first correspond à prep.prepare(root).
            self.assertEqual(first, prep.prepare(root))
            # On vérifie que content correspond à (root / '.env.airflow.workflow.local').read_bytes().
            self.assertEqual(
                # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
                content, (root / ".env.airflow.workflow.local").read_bytes()
            )
            # On vérifie que (root / '.gitignore').read_text().count('.env.airflow.workflow.local')
            # correspond à 1.
            self.assertEqual(
                # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
                (root / ".gitignore").read_text().count(".env.airflow.workflow.local"),
                # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
                1,
            )

    def test_existing_different_config_not_overwritten(self):
        # On utilise un dossier temporaire pour cet essai ; les fichiers produits ici ne sont pas ceux
        # de la production.
        with tempfile.TemporaryDirectory() as d:
            # On garde dans root un objet chemin local ; sa construction seule ne prouve pas que le
            # fichier existe.
            root = Path(d)
            # On appelle self.tree avec root.
            self.tree(root)
            # On assemble les morceaux du chemin target avec l’opérateur / de pathlib ; aucun fichier
            # n’est créé par cette construction.
            target = root / ".env.airflow.workflow.local"
            # On écrit le contenu préparé dans target ; cette opération remplace le contenu du fichier
            # s’il existe déjà.
            target.write_text("different")
            # On attend prep.PreparationError dans ce bloc ; si aucune erreur n’est levée, le test doit
            # échouer.
            with self.assertRaises(prep.PreparationError):
                # On appelle prep.prepare avec root.
                prep.prepare(root)
            # On vérifie que target.read_text() correspond à 'different'.
            self.assertEqual(target.read_text(), "different")

    def test_active_workflow_blocks_preparation(self):
        # On utilise un dossier temporaire pour cet essai ; les fichiers produits ici ne sont pas ceux
        # de la production.
        with tempfile.TemporaryDirectory() as d:
            # On garde dans root un objet chemin local ; sa construction seule ne prouve pas que le
            # fichier existe.
            root = Path(d)
            # On appelle self.tree avec root.
            self.tree(root)
            # On assemble les morceaux du chemin lock avec l’opérateur / de pathlib ; aucun fichier
            # n’est créé par cette construction.
            lock = root / "state/workflow_execution/workflow.lock"
            # On prépare le dossier lock.parent avec les règles de création indiquées ; aucun résultat
            # métier n’est encore produit par cette création.
            lock.parent.mkdir(parents=True)
            # On écrit le contenu préparé dans lock ; cette opération remplace le contenu du fichier
            # s’il existe déjà.
            lock.write_text("existing")
            # On attend prep.PreparationError dans ce bloc ; si aucune erreur n’est levée, le test doit
            # échouer.
            with self.assertRaises(prep.PreparationError):
                # On appelle prep.prepare avec root.
                prep.prepare(root)
            # On attend que (root / '.env.airflow.workflow.local').exists() soit évalué comme faux pour
            # ce cas de test.
            self.assertFalse((root / ".env.airflow.workflow.local").exists())

    def test_sources_are_absolute(self):
        # On parcourt ('relative/path', '', None, 'C:/NAS\npassword', "C:/NAS'bad") ; value désigne
        # l’élément courant de ce scénario.
        for value in ("relative/path", "", None, "C:/NAS\npassword", "C:/NAS'bad"):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(value=value), self.assertRaises(prep.PreparationError):
                # On appelle prep.source_value avec value.
                prep.source_value(value)

    def test_windows_unc_and_posix_sources_accepted(self):
        # On parcourt ('C:/NAS/Brut', '\\\\server\\share\\Brut', '/mnt/nas/Brut') ; value désigne
        # l’élément courant de ce scénario.
        for value in ("C:/NAS/Brut", r"\\server\share\Brut", "/mnt/nas/Brut"):
            # On vérifie que prep.source_value(value) correspond à value.replace('\\', '/').
            self.assertEqual(prep.source_value(value), value.replace("\\", "/"))

    def test_missing_source_blocks_before_new_file(self):
        # On utilise un dossier temporaire pour cet essai ; les fichiers produits ici ne sont pas ceux
        # de la production.
        with tempfile.TemporaryDirectory() as d:
            # On garde dans root un objet chemin local ; sa construction seule ne prouve pas que le
            # fichier existe.
            root = Path(d)
            # On écrit le contenu préparé dans root / '.env' ; cette opération remplace le contenu du
            # fichier s’il existe déjà.
            (root / ".env").write_text("NAS_BRUT_ROOT=C:/NAS/Brut\n")
            # On attend prep.PreparationError dans ce bloc ; si aucune erreur n’est levée, le test doit
            # échouer.
            with self.assertRaises(prep.PreparationError):
                # On appelle prep.prepare avec root.
                prep.prepare(root)
            # On attend que (root / '.env.airflow.workflow.local').exists() soit évalué comme faux pour
            # ce cas de test.
            self.assertFalse((root / ".env.airflow.workflow.local").exists())

    def test_local_env_preserved(self):
        # On utilise un dossier temporaire pour cet essai ; les fichiers produits ici ne sont pas ceux
        # de la production.
        with tempfile.TemporaryDirectory() as d:
            # On garde dans root un objet chemin local ; sa construction seule ne prouve pas que le
            # fichier existe.
            root = Path(d)
            # On appelle self.tree avec root.
            self.tree(root)
            # On garde dans old les octets lus depuis root / '.env', avant toute conversion en
            # texte. Les contrôles de contenu pourront ainsi repartir de cette lecture.
            old = (root / ".env").read_bytes()
            # On appelle prep.prepare avec root.
            prep.prepare(root)
            # On vérifie que old correspond à (root / '.env').read_bytes().
            self.assertEqual(old, (root / ".env").read_bytes())

    def test_host_receipt_and_shared_id_checked(self):
        # On utilise un dossier temporaire pour cet essai ; les fichiers produits ici ne sont pas ceux
        # de la production.
        with tempfile.TemporaryDirectory() as d:
            # On garde dans root un objet chemin local ; sa construction seule ne prouve pas que le
            # fichier existe.
            root = Path(d)
            # On appelle self.tree avec root.
            self.tree(root)
            # On garde dans identity la valeur renvoyée par prep.prepare.
            identity = prep.prepare(root)
            # On assemble les morceaux du chemin path avec l’opérateur / de pathlib ; aucun fichier
            # n’est créé par cette construction.
            path = root / "logs/airflow_workflow/diagnostic_test.json"
            # On écrit le contenu préparé dans path ; cette opération remplace le contenu du fichier
            # s’il existe déjà.
            path.write_text(
                json.dumps(
                    dict(
                        kind="diagnostic",
                        # On fournit l’état du traitement via le paramètre status de cet appel.
                        status="success",
                        share_id=identity["share_id"],
                        # On fournit la date de l’événement via le paramètre occurred_at de cet appel.
                        occurred_at=datetime.now(timezone.utc).isoformat(),
                    )
                )
            )
            # On vérifie que prep.check_diagnostic(root) correspond à path.name.
            self.assertEqual(prep.check_diagnostic(root), path.name)
            # On garde dans r les objets Python décodés depuis le JSON fourni.
            r = json.loads(path.read_text())
            # On garde dans r['share_id'] la représentation textuelle de uuid4().
            r["share_id"] = str(uuid4())
            # On écrit le contenu préparé dans path ; cette opération remplace le contenu du fichier
            # s’il existe déjà.
            path.write_text(json.dumps(r))
            # On attend prep.PreparationError dans ce bloc ; si aucune erreur n’est levée, le test doit
            # échouer.
            with self.assertRaises(prep.PreparationError):
                # On appelle prep.check_diagnostic avec root.
                prep.check_diagnostic(root)

    def test_host_receipt_required(self):
        # On utilise un dossier temporaire pour cet essai ; les fichiers produits ici ne sont pas ceux
        # de la production.
        with tempfile.TemporaryDirectory() as d:
            # On garde dans root un objet chemin local ; sa construction seule ne prouve pas que le
            # fichier existe.
            root = Path(d)
            # On appelle self.tree avec root.
            self.tree(root)
            # On appelle prep.prepare avec root.
            prep.prepare(root)
            # On attend prep.PreparationError dans ce bloc ; si aucune erreur n’est levée, le test doit
            # échouer.
            with self.assertRaises(prep.PreparationError):
                # On appelle prep.check_diagnostic avec root.
                prep.check_diagnostic(root)


class MountTests(unittest.TestCase):
    def mounts(self):
        # On prépare lines comme liste vide ; on la remplira au fil des opérations suivantes.
        lines = []
        # On contrôle chaque montage qui doit rester en lecture seule, dont la racine du NAS.
        for i, p in enumerate(rt.RO_MOUNTS + rt.RW_MOUNTS):
            # On choisit la valeur de mode selon ce test : p appartient à rt.RO_MOUNTS. Les deux
            # résultats possibles restent définis explicitement ici.
            mode = "ro" if p in rt.RO_MOUNTS else "rw"
            # On ajoute f'{i + 1} 1 0:1 / {p} {mode},relatime - ext4 fake rw' à la fin de lines ; les
            # éléments précédents restent conservés.
            lines.append(f"{i + 1} 1 0:1 / {p} {mode},relatime - ext4 fake rw")
        # On fournit à l’appelant le texte formé en réunissant les éléments avec '\n' comme séparateur.
        return "\n".join(lines)

    def test_readonly_mounts_accepted(self):
        # On appelle rt.validate_mounts avec self.mounts().
        rt.validate_mounts(self.mounts())

    # On remplace ro par rw dans le montage fictif. Le diagnostic doit détecter que le NAS peut être
    # modifié.
    def test_writable_nas_rejected(self):
        # On garde dans content le résultat du remplacement demandé sur self.mounts().
        content = self.mounts().replace("/opt/nas ro,", "/opt/nas rw,")
        # On attend rt.RuntimeCheckError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(rt.RuntimeCheckError):
            # On appelle rt.validate_mounts avec content.
            rt.validate_mounts(content)

    # Le chemin peut exister sans être le montage attendu. Ici, on retire le montage des
    # informations Linux simulées.
    def test_missing_nas_mount_rejected(self):
        # On garde dans content le texte formé en réunissant les éléments avec '\n' comme séparateur.
        content = "\n".join(
            l for l in self.mounts().splitlines() if "/opt/nas " not in l
        )
        # On attend rt.RuntimeCheckError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(rt.RuntimeCheckError):
            # On appelle rt.validate_mounts avec content.
            rt.validate_mounts(content)

    def test_readonly_shared_state_rejected(self):
        # On attend rt.RuntimeCheckError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(rt.RuntimeCheckError):
            # On appelle rt.validate_mounts avec self.mounts().replace('/opt/project/state rw,',
            # '/opt/project/state ro,').
            rt.validate_mounts(
                self.mounts().replace(
                    "/opt/project/state rw,", "/opt/project/state ro,"
                )
            )

    def test_duplicate_mount_rejected(self):
        # On attend rt.RuntimeCheckError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(rt.RuntimeCheckError):
            # On appelle rt.validate_mounts avec self.mounts() + '\n' + self.mounts().splitlines()[0].
            rt.validate_mounts(self.mounts() + "\n" + self.mounts().splitlines()[0])

    def test_escape_decoding(self):
        # On utilise ce texte pour content ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        content = r"1 0 0:1 / /a\040b ro - ext4 fake rw"
        # On vérifie que '/a b' figure dans rt.mount_options(content).
        self.assertIn("/a b", rt.mount_options(content))

    def test_windows_runtime_refused_without_nas_access(self):
        # On remplace temporairement rt.os dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with (
            patch.object(rt.os, "name", "nt"),
            patch.object(rt.Path, "read_text") as read,
        ):
            # On attend rt.RuntimeCheckError dans ce bloc ; si aucune erreur n’est levée, le test doit
            # échouer.
            with self.assertRaises(rt.RuntimeCheckError):
                # On appelle rt.check_runtime sans argument positionnel.
                rt.check_runtime()
            # On vérifie que read n’a pas été appelé : le refus doit intervenir avant cette
            # opération.
            read.assert_not_called()


class TaskTests(unittest.TestCase):
    def environment(self):
        # On fournit à l’appelant un nouveau dictionnaire construit avec les valeurs indiquées.
        return dict(
            PROJECT12_IMPORT_CONNECTION_MODE="environment",
            PROJECT12_IMPORT_HOST="projet12-suivi-postgres-1",
            PROJECT12_IMPORT_PORT="5432",
            PROJECT12_IMPORT_USER="projet12_importer",
            PROJECT12_IMPORT_PASSWORD="fake-importer-secret",
            PROJECT12_NAS_CONNECTION_MODE="environment",
            NAS_BRUT_ROOT="/opt/nas/brute_v2025",
            NAS_PROCESSING_ROOT="/opt/nas/data_processing_2025",
            PROJECT12_WORKFLOW_DOCKER="1",
            PROJECT12_WORKFLOW_SHARE_ID=str(uuid4()),
            AIRFLOW__API_AUTH__JWT_SECRET="fake-jwt",
            PROJECT12_POSTGRES_PASSWORD="fake-admin",
            PROJECT12_DASHBOARD_PASSWORD="fake-reader",
            OTHER_SECRET="other",
        )

    def params(self):
        # On fournit à l’appelant un nouveau dictionnaire construit avec les valeurs indiquées.
        return dict(
            # On fournit le domaine concerné via le paramètre vineyard de cet appel.
            vineyard="DomaineDemoD", allow_business_writes=True, confirm_nas_read_only=True
        )

    def test_valid_manual_trigger(self):
        # On appelle task.validate_trigger avec 'manual'.
        task.validate_trigger("manual", self.params())

    def test_scheduled_and_backfill_refused(self):
        # On parcourt ('scheduled', 'backfill', None) ; kind désigne l’élément courant de ce scénario.
        for kind in ("scheduled", "backfill", None):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(kind=kind), self.assertRaises(task.TaskControlError):
                # On appelle task.validate_trigger avec kind.
                task.validate_trigger(kind, self.params())

    def test_false_missing_and_string_confirmations_refused(self):
        # On parcourt (False, 'true', 1, None) ; value désigne l’élément courant de ce scénario.
        for value in (False, "true", 1, None):
            # On garde dans p la valeur renvoyée par self.params.
            p = self.params()
            # On garde la valeur reçue sous le nom p['allow_business_writes'] ; cette affectation ne
            # copie pas à elle seule un objet mutable.
            p["allow_business_writes"] = value
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(value=value), self.assertRaises(task.TaskControlError):
                # On appelle task.validate_trigger avec 'manual'.
                task.validate_trigger("manual", p)

    def test_other_vineyard_refused(self):
        # On garde dans p la valeur renvoyée par self.params.
        p = self.params()
        # On utilise ce texte pour p['vineyard'] ; il ne dépend pas d’une valeur récupérée ailleurs à
        # cet endroit.
        p["vineyard"] = "Achille"
        # On attend task.TaskControlError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(task.TaskControlError):
            # On appelle task.validate_trigger avec 'manual'.
            task.validate_trigger("manual", p)

    # Le processus métier doit recevoir le secret importeur, mais pas les secrets d’administration
    # ou d’Airflow.
    def test_child_does_not_inherit_other_secrets(self):
        # On garde dans parent les variables d’environnement préparées pour ce scénario.
        parent = self.environment()
        # On garde dans copy une copie de parent pour travailler sur cet objet séparément.
        copy = parent.copy()
        # On garde dans child la valeur renvoyée par task.child_environment.
        child = task.child_environment(parent)
        # On vérifie que parent correspond à copy.
        self.assertEqual(parent, copy)
        # On vérifie que 'AIRFLOW__API_AUTH__JWT_SECRET' ne figure pas dans child.
        self.assertNotIn("AIRFLOW__API_AUTH__JWT_SECRET", child)
        # On vérifie que 'PROJECT12_POSTGRES_PASSWORD' ne figure pas dans child.
        self.assertNotIn("PROJECT12_POSTGRES_PASSWORD", child)
        # On vérifie que 'PROJECT12_DASHBOARD_PASSWORD' ne figure pas dans child.
        self.assertNotIn("PROJECT12_DASHBOARD_PASSWORD", child)
        # On vérifie que 'OTHER_SECRET' ne figure pas dans child.
        self.assertNotIn("OTHER_SECRET", child)
        # On vérifie que child['PROJECT12_IMPORT_PASSWORD'] correspond à 'fake-importer-secret'.
        self.assertEqual(child["PROJECT12_IMPORT_PASSWORD"], "fake-importer-secret")

    def test_missing_child_password_refused(self):
        # On garde dans e les variables d’environnement préparées pour ce scénario.
        e = self.environment()
        # On retire e['PROJECT12_IMPORT_PASSWORD'] de son emplacement ; la suite ne doit plus s’appuyer
        # sur cette entrée.
        del e["PROJECT12_IMPORT_PASSWORD"]
        # On attend task.TaskControlError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(task.TaskControlError):
            # On appelle task.child_environment avec e.
            task.child_environment(e)

    def test_local_configuration_refused(self):
        # On garde dans e les variables d’environnement préparées pour ce scénario.
        e = self.environment()
        # On utilise ce texte pour e['PROJECT12_IMPORT_CONNECTION_MODE'] ; il ne dépend pas d’une
        # valeur récupérée ailleurs à cet endroit.
        e["PROJECT12_IMPORT_CONNECTION_MODE"] = "local"
        # On attend task.TaskControlError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(task.TaskControlError):
            # On appelle task.child_environment avec e.
            task.child_environment(e)

    def test_noncontainer_nas_roots_refused(self):
        # On garde dans e les variables d’environnement préparées pour ce scénario.
        e = self.environment()
        # On utilise ce texte pour e['NAS_BRUT_ROOT'] ; il ne dépend pas d’une valeur récupérée
        # ailleurs à cet endroit.
        e["NAS_BRUT_ROOT"] = "C:/NAS/Brut"
        # On attend task.TaskControlError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(task.TaskControlError):
            # On appelle task.child_environment avec e.
            task.child_environment(e)

    def test_receipt_success(self):
        # On garde dans e les variables d’environnement préparées pour ce scénario.
        e = self.environment()
        # On garde dans wid la représentation textuelle de uuid4().
        wid = str(uuid4())
        # On garde dans data un nouveau dictionnaire construit avec les valeurs indiquées.
        data = dict(
            kind="execution",
            # On fournit l’état du traitement via le paramètre status de cet appel.
            status="success",
            # On fournit l’origine du déclenchement via le paramètre trigger_mode de cet appel.
            trigger_mode="airflow_manual",
            # On fournit les étapes terminées via le paramètre completed_steps de cet appel.
            completed_steps=8,
            share_id=e["PROJECT12_WORKFLOW_SHARE_ID"],
            # On fournit l’identifiant de l’exécution du workflow via le paramètre
            # workflow_execution_id de cet appel.
            workflow_execution_id=wid,
            # On fournit l’identifiant du lot Excel via le paramètre excel_publication_id de cet appel.
            excel_publication_id="pub",
            # On fournit l’identifiant du traitement NAS via le paramètre pipeline_execution_id de cet
            # appel.
            pipeline_execution_id="nas",
            journal_relative_path="data/03_normalized/workflow_runs/"
            + wid.replace("-", "")
            + "/events.jsonl",
        )
        # On utilise un dossier temporaire pour cet essai ; les fichiers produits ici ne sont pas ceux
        # de la production.
        with tempfile.TemporaryDirectory() as d:
            # On assemble les morceaux du chemin p avec l’opérateur / de pathlib ; aucun fichier n’est
            # créé par cette construction.
            p = Path(d) / "receipt.json"
            # On écrit le contenu préparé dans p ; cette opération remplace le contenu du fichier s’il
            # existe déjà.
            p.write_text(json.dumps(data))
            # On garde dans r la valeur renvoyée par task.receipt_result.
            r = task.receipt_result(p, e)
            # On vérifie que r['status'] correspond à 'success'.
            self.assertEqual(r["status"], "success")
            # On vérifie que 'share_id' ne figure pas dans r.
            self.assertNotIn("share_id", r)
            # On utilise ce texte pour data['status'] ; il ne dépend pas d’une valeur récupérée
            # ailleurs à cet endroit.
            data["status"] = "failed"
            # On écrit le contenu préparé dans p ; cette opération remplace le contenu du fichier s’il
            # existe déjà.
            p.write_text(json.dumps(data))
            # On attend task.TaskControlError dans ce bloc ; si aucune erreur n’est levée, le test doit
            # échouer.
            with self.assertRaises(task.TaskControlError):
                # On appelle task.receipt_result avec p.
                task.receipt_result(p, e)

    def test_process_group_stopped_on_timeout(self):
        # On garde dans fake un objet simple portant les attributs indiqués.
        fake = types.SimpleNamespace(pid=123, wait=lambda timeout: None)
        # On remplace temporairement task.os dans ce bloc de test ; le réglage initial sera rétabli à
        # sa sortie.
        with (
            patch.object(task.os, "killpg", create=True) as kill,
            patch.object(task.signal, "SIGKILL", 9, create=True),
        ):
            # On appelle task.stop_group avec fake.
            task.stop_group(fake)
        # On vérifie que kill.call_count correspond à 2.
        self.assertEqual(kill.call_count, 2)

    def test_missing_group_already_stopped(self):
        # On garde dans fake un objet simple portant les attributs indiqués.
        fake = types.SimpleNamespace(pid=123, wait=lambda timeout: None)
        # On remplace temporairement task.os dans ce bloc de test ; le réglage initial sera rétabli à
        # sa sortie.
        with patch.object(
            # On définit le comportement simulé de l’appel, qui peut notamment lever une erreur ou
            # suivre une fonction de test.
            task.os, "killpg", side_effect=ProcessLookupError, create=True
        ) as kill:
            # On appelle task.stop_group avec fake.
            task.stop_group(fake)
        # On vérifie que kill.call_count correspond à 1.
        self.assertEqual(kill.call_count, 1)

    def test_rejection_happens_before_process_creation(self):
        # Le lancement du processus est remplacé pour observer ses paramètres sans démarrer le
        # programme métier.
        with patch.object(task.subprocess, "Popen") as popen:
            # On attend task.TaskControlError dans ce bloc ; si aucune erreur n’est levée, le test doit
            # échouer.
            with self.assertRaises(task.TaskControlError):
                # On appelle task.execute_pilote avec 'scheduled'.
                task.execute_pilote("scheduled", self.params())
            # On vérifie que popen n’a pas été appelé : le refus doit intervenir avant cette
            # opération.
            popen.assert_not_called()


class DagTests(unittest.TestCase):
    def test_manual_dag_with_zero_retries_and_confirmations(self):
        # On crée le dictionnaire vide settings pour y ranger ensuite les éléments par clé.
        settings = {}
        # On prépare tasks comme liste vide ; on la remplira au fil des opérations suivantes.
        tasks = []

        def dag(**kw):
            # On complète settings avec les valeurs indiquées ; une clé déjà présente prendra la
            # nouvelle valeur fournie.
            settings.update(kw)
            # On remet lambda function: function à l’appelant ; les étapes suivantes de cette fonction
            # ne sont plus parcourues.
            return lambda function: function

        def decorator(**kw):
            def wrap(f):
                # On ajoute (f, kw) à la fin de tasks ; les éléments précédents restent conservés.
                tasks.append((f, kw))
                # On remet lambda: None à l’appelant ; les étapes suivantes de cette fonction ne sont
                # plus parcourues.
                return lambda: None

            # On remet wrap à l’appelant ; les étapes suivantes de cette fonction ne sont plus
            # parcourues.
            return wrap

        # On garde dans sdk la valeur renvoyée par types.ModuleType pour 'airflow.sdk'.
        sdk = types.ModuleType("airflow.sdk")
        # On garde dag sous le nom sdk.dag ; cette affectation ne copie pas à elle seule un objet
        # mutable.
        sdk.dag = dag
        # On garde decorator sous le nom sdk.task ; cette affectation ne copie pas à elle seule un
        # objet mutable.
        sdk.task = decorator
        # On prépare pour sdk.Param une fonction courte ; elle ne sera exécutée que lorsqu’elle sera
        # appelée, pas lors de cette affectation.
        sdk.Param = lambda v, **kw: (v, kw)
        # On garde dans pendulum la valeur renvoyée par types.ModuleType pour 'pendulum'.
        pendulum = types.ModuleType("pendulum")
        # On prépare pour pendulum.datetime une fonction courte ; elle ne sera exécutée que lorsqu’elle
        # sera appelée, pas lors de cette affectation.
        pendulum.datetime = lambda *a, **kw: "date"
        # On garde dans airflow la valeur renvoyée par types.ModuleType pour 'airflow'.
        airflow = types.ModuleType("airflow")
        # On garde sdk sous le nom airflow.sdk ; cette affectation ne copie pas à elle seule un objet
        # mutable.
        airflow.sdk = sdk
        # On remplace temporairement sys.modules dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.dict(
            sys.modules, {"airflow": airflow, "airflow.sdk": sdk, "pendulum": pendulum}
        ):
            # On garde dans spec la valeur renvoyée par importlib.util.spec_from_file_location pour
            # 'dag_pilote_test'.
            spec = importlib.util.spec_from_file_location(
                "dag_pilote_test", ROOT / "dags/project12_pilote_business.py"
            )
            # On garde dans m la valeur renvoyée par importlib.util.module_from_spec.
            m = importlib.util.module_from_spec(spec)
            # On appelle spec.loader.exec_module avec m.
            spec.loader.exec_module(m)
        # On attend None pour settings['schedule'] : aucune valeur n’est confirmée dans ce cas.
        self.assertIsNone(settings["schedule"])
        # On attend que settings['catchup'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(settings["catchup"])
        # On vérifie que settings['max_active_runs'] correspond à 1.
        self.assertEqual(settings["max_active_runs"], 1)
        # On vérifie que settings['default_args']['retries'] correspond à 0.
        self.assertEqual(settings["default_args"]["retries"], 0)
        # On attend que settings['params']['allow_business_writes'][0] soit évalué comme faux pour ce
        # cas de test.
        self.assertFalse(settings["params"]["allow_business_writes"][0])
        # On vérifie que len(tasks) correspond à 1.
        self.assertEqual(len(tasks), 1)
        # On vérifie que settings['params']['vineyard'][1]['enum'] correspond à ['DomaineDemoD'].
        self.assertEqual(settings["params"]["vineyard"][1]["enum"], ["DomaineDemoD"])


class ChildExecutionTests(unittest.TestCase):
    def test_real_launcher_contract_with_fake_child(self):
        # On garde dans e la valeur renvoyée par TaskTests().environment.
        e = TaskTests().environment()
        # On garde dans parameters la valeur renvoyée par TaskTests().params.
        parameters = TaskTests().params()
        # On utilise un dossier temporaire pour cet essai ; les fichiers produits ici ne sont pas ceux
        # de la production.
        with tempfile.TemporaryDirectory() as d:
            # On garde dans root un objet chemin local ; sa construction seule ne prouve pas que le
            # fichier existe.
            root = Path(d)
            # On prépare le dossier root / 'scripts' avec les règles de création indiquées ; aucun
            # résultat métier n’est encore produit par cette création.
            (root / "scripts").mkdir()
            # On écrit le contenu préparé dans root / 'scripts/run_airflow_pilote_workflow.py' ; cette
            # opération remplace le contenu du fichier s’il existe déjà.
            (root / "scripts/run_airflow_pilote_workflow.py").write_text("# fake")
            # On prépare le dossier root / 'logs/airflow_workflow' avec les règles de création
            # indiquées ; aucun résultat métier n’est encore produit par cette création.
            (root / "logs/airflow_workflow").mkdir(parents=True)
            # On crée le dictionnaire vide captured pour y ranger ensuite les éléments par clé.
            captured = {}
            # On garde dans wid la représentation textuelle de uuid4().
            wid = str(uuid4())

            def popen(command, **kw):
                # On complète captured avec les valeurs indiquées ; une clé déjà présente prendra la
                # nouvelle valeur fournie.
                captured.update(command=command, **kw)
                # On garde dans receipt un objet chemin local ; sa construction seule ne prouve pas que
                # le fichier existe.
                receipt = Path(command[-1])
                # On écrit le contenu préparé dans receipt ; cette opération remplace le contenu du
                # fichier s’il existe déjà.
                receipt.write_text(
                    json.dumps(
                        dict(
                            kind="execution",
                            # On fournit l’état du traitement via le paramètre status de cet appel.
                            status="success",
                            # On fournit l’origine du déclenchement via le paramètre trigger_mode de
                            # cet appel.
                            trigger_mode="airflow_manual",
                            # On fournit les étapes terminées via le paramètre completed_steps de cet
                            # appel.
                            completed_steps=8,
                            share_id=e["PROJECT12_WORKFLOW_SHARE_ID"],
                            # On fournit l’identifiant de l’exécution du workflow via le paramètre
                            # workflow_execution_id de cet appel.
                            workflow_execution_id=wid,
                            # On fournit l’identifiant du lot Excel via le paramètre
                            # excel_publication_id de cet appel.
                            excel_publication_id="pub",
                            # On fournit l’identifiant du traitement NAS via le paramètre
                            # pipeline_execution_id de cet appel.
                            pipeline_execution_id="nas",
                            journal_relative_path="data/03_normalized/workflow_runs/"
                            + wid.replace("-", "")
                            + "/events.jsonl",
                        )
                    )
                )
                # On écrit 'local fake payload; no forwarding' dans kw['stdout'] ; le mode d’ouverture
                # du flux détermine s’il s’agit d’un ajout ou d’un remplacement.
                kw["stdout"].write("local fake payload; no forwarding")
                # On fournit à l’appelant un objet simple portant les attributs indiqués.
                return types.SimpleNamespace(pid=123, wait=lambda timeout: 0)

            # On garde dans out un flux texte en mémoire, utilisable comme un fichier par le lecteur
            # CSV.
            out = io.StringIO()
            # Le lancement du processus est remplacé pour observer ses paramètres sans démarrer le
            # programme métier.
            with (
                patch.object(task, "IS_POSIX", True),
                patch.object(task, "ROOT", root),
                patch.object(task, "BUSINESS_PYTHON", Path(sys.executable)),
                patch.dict(task.os.environ, e, clear=True),
                patch.object(task.subprocess, "Popen", side_effect=popen),
                contextlib.redirect_stdout(out),
            ):
                # On garde dans result la valeur renvoyée par task.execute_pilote pour 'manual'.
                result = task.execute_pilote("manual", parameters)
            # On vérifie que result['workflow_execution_id'] correspond à wid.
            self.assertEqual(result["workflow_execution_id"], wid)
            # On attend que captured['start_new_session'] soit évalué comme vrai pour ce cas de test.
            self.assertTrue(captured["start_new_session"])
            # On attend que captured['shell'] soit évalué comme faux pour ce cas de test.
            self.assertFalse(captured["shell"])
            # On vérifie que 'local fake payload' ne figure pas dans out.getvalue().
            self.assertNotIn("local fake payload", out.getvalue())
            # On vérifie que 'fake-importer-secret' ne figure pas dans out.getvalue().
            self.assertNotIn("fake-importer-secret", out.getvalue())
            # On vérifie que 'AIRFLOW__API_AUTH__JWT_SECRET' ne figure pas dans captured['env'].
            self.assertNotIn("AIRFLOW__API_AUTH__JWT_SECRET", captured["env"])

    # La sortie de l’enfant contient volontairement un secret fictif. On vérifie qu’elle n’est pas
    # retransmise telle quelle.
    def test_child_failure_does_not_forward_output(self):
        # On garde dans e la valeur renvoyée par TaskTests().environment.
        e = TaskTests().environment()
        # On utilise un dossier temporaire pour cet essai ; les fichiers produits ici ne sont pas ceux
        # de la production.
        with tempfile.TemporaryDirectory() as d:
            # On garde dans root un objet chemin local ; sa construction seule ne prouve pas que le
            # fichier existe.
            root = Path(d)
            # On prépare le dossier root / 'scripts' avec les règles de création indiquées ; aucun
            # résultat métier n’est encore produit par cette création.
            (root / "scripts").mkdir()
            # On écrit le contenu préparé dans root / 'scripts/run_airflow_pilote_workflow.py' ; cette
            # opération remplace le contenu du fichier s’il existe déjà.
            (root / "scripts/run_airflow_pilote_workflow.py").write_text("# fake")
            # On prépare le dossier root / 'logs/airflow_workflow' avec les règles de création
            # indiquées ; aucun résultat métier n’est encore produit par cette création.
            (root / "logs/airflow_workflow").mkdir(parents=True)

            def popen(command, **kw):
                # On écrit e['PROJECT12_IMPORT_PASSWORD'] dans kw['stdout'] ; le mode d’ouverture du
                # flux détermine s’il s’agit d’un ajout ou d’un remplacement.
                kw["stdout"].write(e["PROJECT12_IMPORT_PASSWORD"])
                # On fournit à l’appelant un objet simple portant les attributs indiqués.
                return types.SimpleNamespace(pid=123, wait=lambda timeout: 1)

            # On garde dans out un flux texte en mémoire, utilisable comme un fichier par le lecteur
            # CSV.
            out = io.StringIO()
            # Le lancement du processus est remplacé pour observer ses paramètres sans démarrer le
            # programme métier.
            with (
                patch.object(task, "IS_POSIX", True),
                patch.object(task, "ROOT", root),
                patch.object(task, "BUSINESS_PYTHON", Path(sys.executable)),
                patch.dict(task.os.environ, e, clear=True),
                patch.object(task.subprocess, "Popen", side_effect=popen),
                patch.object(task, "stop_group") as stop,
                contextlib.redirect_stdout(out),
            ):
                # On attend task.TaskControlError dans ce bloc ; si aucune erreur n’est levée, le test
                # doit échouer.
                with self.assertRaises(task.TaskControlError):
                    # On appelle task.execute_pilote avec 'manual'.
                    task.execute_pilote("manual", TaskTests().params())
                # On attend un seul appel à stop dans ce scénario, ni zéro ni plusieurs.
                stop.assert_called_once()
            # On vérifie que e['PROJECT12_IMPORT_PASSWORD'] ne figure pas dans out.getvalue().
            self.assertNotIn(e["PROJECT12_IMPORT_PASSWORD"], out.getvalue())

    # Le processus simulé dépasse son délai : l’arrêt doit aussi viser son groupe, pas seulement
    # l’attente du parent.
    def test_timeout_stops_child_group(self):
        # On garde dans e la valeur renvoyée par TaskTests().environment.
        e = TaskTests().environment()
        # On utilise un dossier temporaire pour cet essai ; les fichiers produits ici ne sont pas ceux
        # de la production.
        with tempfile.TemporaryDirectory() as d:
            # On garde dans root un objet chemin local ; sa construction seule ne prouve pas que le
            # fichier existe.
            root = Path(d)
            # On prépare le dossier root / 'scripts' avec les règles de création indiquées ; aucun
            # résultat métier n’est encore produit par cette création.
            (root / "scripts").mkdir()
            # On écrit le contenu préparé dans root / 'scripts/run_airflow_pilote_workflow.py' ; cette
            # opération remplace le contenu du fichier s’il existe déjà.
            (root / "scripts/run_airflow_pilote_workflow.py").write_text("# fake")
            # On prépare le dossier root / 'logs/airflow_workflow' avec les règles de création
            # indiquées ; aucun résultat métier n’est encore produit par cette création.
            (root / "logs/airflow_workflow").mkdir(parents=True)
            # On garde dans process un objet simple portant les attributs indiqués.
            process = types.SimpleNamespace(
                pid=123,
                wait=lambda timeout: (_ for _ in ()).throw(
                    subprocess.TimeoutExpired("fake", timeout)
                ),
            )
            # Le lancement du processus est remplacé pour observer ses paramètres sans démarrer le
            # programme métier.
            with (
                patch.object(task, "IS_POSIX", True),
                patch.object(task, "ROOT", root),
                patch.object(task, "BUSINESS_PYTHON", Path(sys.executable)),
                patch.dict(task.os.environ, e, clear=True),
                patch.object(task.subprocess, "Popen", return_value=process),
                patch.object(task, "stop_group") as stop,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                # On attend task.TaskControlError dans ce bloc ; si aucune erreur n’est levée, le test
                # doit échouer.
                with self.assertRaises(task.TaskControlError):
                    # On appelle task.execute_pilote avec 'manual'.
                    task.execute_pilote("manual", TaskTests().params())
                # On vérifie que ce double a reçu un seul appel avec exactement les arguments indiqués
                # ; une valeur correcte obtenue par le mauvais appel ne suffirait pas.
                stop.assert_called_once_with(process)


class AssemblyTests(unittest.TestCase):
    def modules(self, captured, root):
        # On garde dans cfg la valeur renvoyée par types.ModuleType pour 'workflow_business_config'.
        cfg = types.ModuleType("workflow_business_config")
        # On prépare pour cfg.load_business_configuration une fonction courte ; elle ne sera exécutée
        # que lorsqu’elle sera appelée, pas lors de cette affectation.
        cfg.load_business_configuration = lambda root, **kw: ("config", kw)
        # On garde dans wiring la valeur renvoyée par types.ModuleType pour 'workflow_business_wiring'.
        wiring = types.ModuleType("workflow_business_wiring")

        # On assemble les éléments de présentation prévus par ce bloc local.
        def build(config, **kw):
            # On garde kw sous le nom captured['plan'] ; cette affectation ne copie pas à elle seule un
            # objet mutable.
            captured["plan"] = kw
            # On fournit à l’appelant un objet simple portant les attributs indiqués.
            return types.SimpleNamespace(
                # On fournit les étapes du workflow via le paramètre steps de cet appel.
                steps=("same-steps",), journal_sink="same-sink"
            )

        # On garde build sous le nom wiring.build_business_plan ; cette affectation ne copie pas à elle
        # seule un objet mutable.
        wiring.build_business_plan = build
        # On garde dans entry la valeur renvoyée par types.ModuleType pour 'run_workflow_business'.
        entry = types.ModuleType("run_workflow_business")
        # On prépare pour entry.diagnose_importer une fonction courte ; elle ne sera exécutée que
        # lorsqu’elle sera appelée, pas lors de cette affectation.
        entry.diagnose_importer = lambda config: captured.setdefault("diagnose", True)
        # On garde dans runtime la valeur renvoyée par types.ModuleType pour 'workflow_runtime'.
        runtime = types.ModuleType("workflow_runtime")
        # On prépare pour runtime.workflow_lock une fonction courte ; elle ne sera exécutée que
        # lorsqu’elle sera appelée, pas lors de cette affectation.
        runtime.workflow_lock = lambda *a: contextlib.nullcontext()

        def run(root, steps, **kw):
            # On complète captured avec les valeurs indiquées ; une clé déjà présente prendra la
            # nouvelle valeur fournie.
            captured.update(root=root, steps=steps, **kw)
            # On appelle kw['preflight'] avec None.
            kw["preflight"](None)
            # On garde dans wid la représentation textuelle de uuid4().
            wid = str(uuid4())
            # On fournit à l’appelant un nouveau dictionnaire construit avec les valeurs indiquées.
            return dict(
                # On fournit l’état du traitement via le paramètre status de cet appel.
                status="success",
                # On fournit l’identifiant de l’exécution du workflow via le paramètre
                # workflow_execution_id de cet appel.
                workflow_execution_id=wid,
                # On fournit les étapes terminées via le paramètre completed_steps de cet appel.
                completed_steps=list(range(8)),
                journal_relative_path="data/03_normalized/workflow_runs/"
                + wid.replace("-", "")
                + "/events.jsonl",
                # On fournit le code du problème rencontré via le paramètre error_code de cet appel.
                error_code=None,
                # On fournit l’identifiant du lot Excel via le paramètre excel_publication_id de cet
                # appel.
                excel_publication_id="pub",
                # On fournit l’identifiant du traitement NAS via le paramètre pipeline_execution_id de
                # cet appel.
                pipeline_execution_id="nas",
            )

        # On garde run sous le nom runtime.run_workflow ; cette affectation ne copie pas à elle seule
        # un objet mutable.
        runtime.run_workflow = run
        # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
        # information par sa clé.
        return {
            # On associe la clé 'airflow_workflow_runtime_check' à cette valeur dans les données de ce
            # scénario.
            "airflow_workflow_runtime_check": rt,
            # On associe la clé 'workflow_business_config' à cette valeur dans les données de ce
            # scénario.
            "workflow_business_config": cfg,
            # On associe la clé 'workflow_business_wiring' à cette valeur dans les données de ce
            # scénario.
            "workflow_business_wiring": wiring,
            # On associe la clé 'run_workflow_business' à cette valeur dans les données de ce scénario.
            "run_workflow_business": entry,
            # On associe la clé 'workflow_runtime' à cette valeur dans les données de ce scénario.
            "workflow_runtime": runtime,
        }

    def test_same_callbacks_and_airflow_mode_used(self):
        # On utilise un dossier temporaire pour cet essai ; les fichiers produits ici ne sont pas ceux
        # de la production.
        with tempfile.TemporaryDirectory() as d:
            # On garde dans root un objet chemin local ; sa construction seule ne prouve pas que le
            # fichier existe.
            root = Path(d)
            # On prépare le dossier root / 'logs/airflow_workflow' avec les règles de création
            # indiquées ; aucun résultat métier n’est encore produit par cette création.
            (root / "logs/airflow_workflow").mkdir(parents=True)
            # On crée le dictionnaire vide captured pour y ranger ensuite les éléments par clé.
            captured = {}
            # On remplace temporairement sys.modules dans ce bloc de test ; le réglage initial sera
            # rétabli à sa sortie.
            with patch.dict(sys.modules, self.modules(captured, root)):
                # On garde dans runner les données retournées par le chargeur utilisé à cet endroit.
                runner = load("run_airflow_pilote_workflow")
                # On remplace temporairement runner dans ce bloc de test ; le réglage initial sera
                # rétabli à sa sortie.
                with (
                    patch.object(runner, "ROOT", root),
                    patch.object(runner, "check_runtime", return_value="share"),
                    contextlib.redirect_stdout(io.StringIO()),
                ):
                    # On garde dans result la valeur renvoyée par runner.main.
                    result = runner.main(
                        [
                            "--run",
                            "--allow-business-writes",
                            "--confirm-nas-read-only",
                            "--receipt",
                            str(root / "logs/airflow_workflow/execution_test.json"),
                        ]
                    )
            # On vérifie que result correspond à 0.
            self.assertEqual(result, 0)
            # On vérifie que captured['trigger_mode'] correspond à 'airflow_manual'.
            self.assertEqual(captured["trigger_mode"], "airflow_manual")
            # On vérifie que captured['scope']['vineyards'] correspond à ['DomaineDemoD'].
            self.assertEqual(captured["scope"]["vineyards"], ["DomaineDemoD"])
            # On attend que captured['plan']['all_vineyards'] soit évalué comme faux pour ce cas de
            # test.
            self.assertFalse(captured["plan"]["all_vineyards"])
            # On vérifie que captured['steps'] correspond à ('same-steps',).
            self.assertEqual(captured["steps"], ("same-steps",))
            # On vérifie que captured['journal_sink'] correspond à 'same-sink'.
            self.assertEqual(captured["journal_sink"], "same-sink")
            # On attend que captured['diagnose'] soit évalué comme vrai pour ce cas de test.
            self.assertTrue(captured["diagnose"])

    def test_diagnostic_does_not_execute_steps(self):
        # On utilise un dossier temporaire pour cet essai ; les fichiers produits ici ne sont pas ceux
        # de la production.
        with tempfile.TemporaryDirectory() as d:
            # On garde dans root un objet chemin local ; sa construction seule ne prouve pas que le
            # fichier existe.
            root = Path(d)
            # On prépare le dossier root / 'logs/airflow_workflow' avec les règles de création
            # indiquées ; aucun résultat métier n’est encore produit par cette création.
            (root / "logs/airflow_workflow").mkdir(parents=True)
            # On crée le dictionnaire vide captured pour y ranger ensuite les éléments par clé.
            captured = {}
            # On remplace temporairement sys.modules dans ce bloc de test ; le réglage initial sera
            # rétabli à sa sortie.
            with patch.dict(sys.modules, self.modules(captured, root)):
                # On garde dans runner les données retournées par le chargeur utilisé à cet endroit.
                runner = load("run_airflow_pilote_workflow")
                # On remplace temporairement runner dans ce bloc de test ; le réglage initial sera
                # rétabli à sa sortie.
                with (
                    patch.object(runner, "ROOT", root),
                    patch.object(runner, "check_runtime", return_value="share"),
                    contextlib.redirect_stdout(io.StringIO()),
                ):
                    # On garde dans result la valeur renvoyée par runner.main.
                    result = runner.main(["--diagnostic-only"])
            # On vérifie que result correspond à 0.
            self.assertEqual(result, 0)
            # On attend que captured['diagnose'] soit évalué comme vrai pour ce cas de test.
            self.assertTrue(captured["diagnose"])
            # On vérifie que 'steps' ne figure pas dans captured.
            self.assertNotIn("steps", captured)
            # On vérifie que len(list((root / 'logs/airflow_workflow').glob('diagnostic_*.json')))
            # correspond à 1.
            self.assertEqual(
                # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
                len(list((root / "logs/airflow_workflow").glob("diagnostic_*.json"))), 1
            )

    def test_confirmation_refused_before_configuration(self):
        # On remplace temporairement sys.modules dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.dict(sys.modules, {"airflow_workflow_runtime_check": rt}):
            # On garde dans runner les données retournées par le chargeur utilisé à cet endroit.
            runner = load("run_airflow_pilote_workflow")
        # On attend SystemExit dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            # On appelle runner.main avec ['--run'].
            runner.main(["--run"])


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On confie la découverte et l’exécution des tests de ce fichier au lanceur unittest.
    unittest.main()
