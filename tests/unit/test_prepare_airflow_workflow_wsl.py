# Lecture du fichier — Tests de prepare airflow workflow wsl.
#

# On importe importlib.util. Ce module sera utilisé par les opérations de ce fichier.
import importlib.util
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe tempfile. On prépare des fichiers ou dossiers temporaires pour les cas isolés.
import tempfile
# On importe unittest. On décrit les scénarios et les vérifications de la suite de tests.
import unittest
# On rend disponibles patch depuis unittest.mock, pour les appels de ce fichier.
from unittest.mock import patch
# On rend disponibles uuid4 depuis uuid, pour les appels de ce fichier.
from uuid import uuid4

# On assemble les morceaux du chemin FILE avec l’opérateur / de pathlib ; aucun fichier n’est créé par
# cette construction.
FILE = Path(__file__).resolve().parents[2] / "scripts/prepare_airflow_workflow_wsl.py"
# On garde dans spec la valeur renvoyée par importlib.util.spec_from_file_location pour
# 'wsl_preparation_tested'.
spec = importlib.util.spec_from_file_location("wsl_preparation_tested", FILE)
# On garde dans m la valeur renvoyée par importlib.util.module_from_spec.
m = importlib.util.module_from_spec(spec)
# On appelle spec.loader.exec_module avec m.
spec.loader.exec_module(m)


class TestPrepareAirflowWorkflowWsl(unittest.TestCase):
    def setUp(self):
        # On garde dans self.temp un dossier temporaire distinct des données du projet.
        self.temp = tempfile.TemporaryDirectory()
        # On enregistre cette opération de nettoyage pour qu’elle soit appelée après le test, même si
        # celui-ci échoue.
        self.addCleanup(self.temp.cleanup)
        # On garde dans self.root un objet chemin local ; sa construction seule ne prouve pas que le
        # fichier existe.
        self.root = Path(self.temp.name)
        # On parcourt ('src', 'scripts', 'config', 'docker', 'data', 'state', 'logs', 'state/wo… ;
        # relative désigne l’élément courant de ce scénario.
        for relative in (
            "src",
            "scripts",
            "config",
            "docker",
            "data",
            "state",
            "logs",
            "state/workflow_execution",
            "logs/airflow_workflow",
            "data/01_incoming/suivi_acquisitions",
            "data/02_raw_archive",
            "data/03_normalized",
            "data/04_rejected",
        ):
            # On prépare le dossier self.root / relative avec les règles de création indiquées ; aucun
            # résultat métier n’est encore produit par cette création.
            (self.root / relative).mkdir(parents=True, exist_ok=True)
        # On parcourt ('scripts/prepare_airflow_workflow.py', 'scripts/run_airflow_pilote_workf… ;
        # relative désigne l’élément courant de ce scénario.
        for relative in (
            "scripts/prepare_airflow_workflow.py",
            "scripts/run_airflow_pilote_workflow.py",
            "config/tracking_files.yml",
            "docker/docker-compose.airflow-workflow.yml",
        ):
            # On écrit le contenu préparé dans self.root / relative ; cette opération remplace le
            # contenu du fichier s’il existe déjà.
            (self.root / relative).write_text("original content\n")
        # On garde dans self.share_id la représentation textuelle de uuid4().
        self.share_id = str(uuid4())
        # On assemble les morceaux du chemin self.marker avec l’opérateur / de pathlib ; aucun fichier
        # n’est créé par cette construction.
        self.marker = self.root / "state/workflow_execution/airflow_share_identity.json"
        # On écrit le contenu préparé dans self.marker ; cette opération remplace le contenu du fichier
        # s’il existe déjà.
        self.marker.write_text(json.dumps({"share_id": self.share_id}))
        # On écrit le contenu préparé dans self.root / '.env' ; cette opération remplace le contenu du
        # fichier s’il existe déjà.
        (self.root / ".env").write_text("ADMIN_PASSWORD=private-do-not-copy\n")
        # On écrit le contenu préparé dans self.root / '.env.airflow.workflow.local' ; cette opération
        # remplace le contenu du fichier s’il existe déjà.
        (self.root / ".env.airflow.workflow.local").write_text(
            "Windows source configuration\n"
        )
        # On écrit le contenu préparé dans self.root / '.gitignore' ; cette opération remplace le
        # contenu du fichier s’il existe déjà.
        (self.root / ".gitignore").write_text("/logs/\n/data/\n")

    def test_expected_sources_and_same_identity(self):
        # On garde dans before les octets lus depuis self.marker, avant toute conversion en texte.
        # Les contrôles de contenu pourront ainsi repartir de cette lecture.
        before = self.marker.read_bytes()
        # On vérifie que m.prepare_wsl(self.root) correspond à self.share_id.
        self.assertEqual(m.prepare_wsl(self.root), self.share_id)
        # On garde dans text le texte lu depuis self.root / m.TARGET avec l’encodage indiqué.
        text = (self.root / m.TARGET).read_text()
        # On vérifie que "PROJECT12_WORKFLOW_NAS_SOURCE='/mnt/demo-data'" figure dans text.
        self.assertIn("PROJECT12_WORKFLOW_NAS_SOURCE='/mnt/demo-data'", text)
        # On vérifie que 'PROJECT12_WORKFLOW_BRUT_SOURCE' ne figure pas dans text.
        self.assertNotIn("PROJECT12_WORKFLOW_BRUT_SOURCE", text)
        # On vérifie que self.share_id figure dans text.
        self.assertIn(self.share_id, text)
        # On vérifie que self.marker.read_bytes() correspond à before.
        self.assertEqual(self.marker.read_bytes(), before)
        # On vérifie que 'private-do-not-copy' ne figure pas dans text.
        self.assertNotIn("private-do-not-copy", text)

    def test_original_files_unchanged(self):
        # On construit originals comme une liste à partir de self.root / p, pour chaque p de ('.env',
        # '.env.airflow.workflow.local', 'scripts/prepare_airflow….
        originals = [
            self.root / p
            for p in (
                ".env",
                ".env.airflow.workflow.local",
                "scripts/prepare_airflow_workflow.py",
                "docker/docker-compose.airflow-workflow.yml",
            )
        ]
        # On indexe before par p ; chaque clé sera associée à p.read_bytes(). Une même clé ne peut
        # garder qu’une valeur.
        before = {p: p.read_bytes() for p in originals}
        # On appelle m.prepare_wsl avec self.root.
        m.prepare_wsl(self.root)
        # On vérifie que before correspond à {p: p.read_bytes() for p in originals}.
        self.assertEqual(before, {p: p.read_bytes() for p in originals})

    def test_idempotent_without_duplicate_ignore_rule(self):
        # On appelle m.prepare_wsl avec self.root.
        m.prepare_wsl(self.root)
        # On garde dans before les octets lus depuis self.root / m.TARGET, avant toute conversion en
        # texte. Les contrôles de contenu pourront ainsi repartir de cette lecture.
        before = (self.root / m.TARGET).read_bytes()
        # On appelle m.prepare_wsl avec self.root.
        m.prepare_wsl(self.root)
        # On vérifie que before correspond à (self.root / m.TARGET).read_bytes().
        self.assertEqual(before, (self.root / m.TARGET).read_bytes())
        # On vérifie que (self.root / '.gitignore').read_text().splitlines().count(m.TARGET) correspond
        # à 1.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            (self.root / ".gitignore").read_text().splitlines().count(m.TARGET), 1
        )

    def test_existing_different_target_not_overwritten(self):
        # On calcule ce quotient pour construire target.
        target = self.root / m.TARGET
        # On écrit le contenu préparé dans target ; cette opération remplace le contenu du fichier s’il
        # existe déjà.
        target.write_text("different\n")
        # On garde dans ignore les octets lus depuis self.root / '.gitignore', avant toute
        # conversion en texte. Les contrôles de contenu pourront ainsi repartir de cette lecture.
        ignore = (self.root / ".gitignore").read_bytes()
        # On attend m.WslPreparationError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(m.WslPreparationError):
            # On appelle m.prepare_wsl avec self.root.
            m.prepare_wsl(self.root)
        # On vérifie que target.read_text() correspond à 'different\n'.
        self.assertEqual(target.read_text(), "different\n")
        # On vérifie que (self.root / '.gitignore').read_bytes() correspond à ignore.
        self.assertEqual((self.root / ".gitignore").read_bytes(), ignore)

    def test_lock_blocks_before_configuration_creation(self):
        # On écrit le contenu préparé dans self.root / 'state/workflow_execution/workflow.lock' ; cette
        # opération remplace le contenu du fichier s’il existe déjà.
        (self.root / "state/workflow_execution/workflow.lock").write_text("busy")
        # On attend m.WslPreparationError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(m.WslPreparationError):
            # On appelle m.prepare_wsl avec self.root.
            m.prepare_wsl(self.root)
        # On attend que (self.root / m.TARGET).exists() soit évalué comme faux pour ce cas de test.
        self.assertFalse((self.root / m.TARGET).exists())

    def test_missing_marker_not_regenerated(self):
        # On supprime ce fichier local selon le chemin préparé ; on ne nettoie pas arbitrairement
        # d’autres fichiers.
        self.marker.unlink()
        # On attend m.WslPreparationError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(m.WslPreparationError):
            # On appelle m.prepare_wsl avec self.root.
            m.prepare_wsl(self.root)
        # On attend que self.marker.exists() soit évalué comme faux pour ce cas de test.
        self.assertFalse(self.marker.exists())
        # On attend que (self.root / m.TARGET).exists() soit évalué comme faux pour ce cas de test.
        self.assertFalse((self.root / m.TARGET).exists())

    def test_wrong_marker_shape_rejected(self):
        # On écrit le contenu préparé dans self.marker ; cette opération remplace le contenu du fichier
        # s’il existe déjà.
        self.marker.write_text(json.dumps({"share_id": self.share_id, "extra": True}))
        # On attend m.WslPreparationError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(m.WslPreparationError):
            # On appelle m.prepare_wsl avec self.root.
            m.prepare_wsl(self.root)

    def test_invalid_marker_uuid_rejected(self):
        # On écrit le contenu préparé dans self.marker ; cette opération remplace le contenu du fichier
        # s’il existe déjà.
        self.marker.write_text(json.dumps({"share_id": "bad"}))
        # On attend m.WslPreparationError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(m.WslPreparationError):
            # On appelle m.prepare_wsl avec self.root.
            m.prepare_wsl(self.root)

    def test_missing_local_directory_rejected(self):
        # On appelle (self.root / 'data/04_rejected').rmdir sans argument positionnel.
        (self.root / "data/04_rejected").rmdir()
        # On attend m.WslPreparationError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(m.WslPreparationError):
            # On appelle m.prepare_wsl avec self.root.
            m.prepare_wsl(self.root)
        # On attend que (self.root / m.TARGET).exists() soit évalué comme faux pour ce cas de test.
        self.assertFalse((self.root / m.TARGET).exists())

    def test_missing_compose_rejected(self):
        # On supprime ce fichier local selon le chemin préparé ; on ne nettoie pas arbitrairement
        # d’autres fichiers.
        (self.root / "docker/docker-compose.airflow-workflow.yml").unlink()
        # On attend m.WslPreparationError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(m.WslPreparationError):
            # On appelle m.prepare_wsl avec self.root.
            m.prepare_wsl(self.root)

    def test_ignore_without_final_newline_preserved(self):
        # On écrit le contenu préparé dans self.root / '.gitignore' ; cette opération remplace le
        # contenu du fichier s’il existe déjà.
        (self.root / ".gitignore").write_text("/logs/")
        # On appelle m.prepare_wsl avec self.root.
        m.prepare_wsl(self.root)
        # On vérifie que (self.root / '.gitignore').read_text() correspond à '/logs/\n' + m.TARGET +
        # '\n'.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            (self.root / ".gitignore").read_text(), "/logs/\n" + m.TARGET + "\n"
        )

    def test_source_files_and_env_not_required_to_be_read(self):
        # On garde m.Path.read_text sous le nom original ; cette affectation ne copie pas à elle seule
        # un objet mutable.
        original = m.Path.read_text

        def read(path, *args, **kwargs):
            # On vérifie ce cas avant la suite : path.name correspond au texte '.env'.
            if path.name == ".env":
                # On interrompt cette branche avec AssertionError : 'Business secrets must not be
                # read'.
                raise AssertionError("Business secrets must not be read")
            # On fournit à l’appelant la valeur renvoyée par original.
            return original(path, *args, **kwargs)

        # On remplace temporairement m.Path dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with patch.object(m.Path, "read_text", read):
            # On appelle m.prepare_wsl avec self.root.
            m.prepare_wsl(self.root)

    def test_redirect_refused_without_symlink_privilege(self):
        # On remplace temporairement m.Path dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with patch.object(m.Path, "is_symlink", return_value=True):
            # On attend m.WslPreparationError dans ce bloc ; si aucune erreur n’est levée, le test doit
            # échouer.
            with self.assertRaises(m.WslPreparationError):
                # On appelle m.prepare_wsl avec self.root.
                m.prepare_wsl(self.root)

    def test_nas_paths_not_accessed(self):
        # On garde m.Path.resolve sous le nom original ; cette affectation ne copie pas à elle seule un
        # objet mutable.
        original = m.Path.resolve

        def resolve(path, *args, **kwargs):
            # Cette branche traite le cas où str(path) commence par le texte '/mnt/demo-data'.
            if str(path).startswith("/mnt/demo-data"):
                # On interrompt cette branche avec AssertionError : 'No NAS access allowed during
                # preparation'.
                raise AssertionError("No NAS access allowed during preparation")
            # On fournit à l’appelant la valeur renvoyée par original.
            return original(path, *args, **kwargs)

        # On remplace temporairement m.Path dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with patch.object(m.Path, "resolve", resolve):
            # On appelle m.prepare_wsl avec self.root.
            m.prepare_wsl(self.root)


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On confie la découverte et l’exécution des tests de ce fichier au lanceur unittest.
    unittest.main()
