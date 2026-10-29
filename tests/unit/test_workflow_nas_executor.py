# Lecture du fichier — Tests de workflow nas executor.
#

"""Scripts factices et mocks uniquement : aucune lecture du vrai NAS."""

# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On importe shutil. On réalise les copies et nettoyages de fichiers explicitement prévus.
import shutil
# On importe subprocess. On lance et surveille les programmes enfants lorsqu’un parcours l’exige.
import subprocess
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On importe tempfile. On prépare des fichiers ou dossiers temporaires pour les cas isolés.
import tempfile
# On importe unittest. On décrit les scénarios et les vérifications de la suite de tests.
import unittest
# On rend disponibles Mock, patch depuis unittest.mock, pour les appels de ce fichier.
from unittest.mock import Mock, patch

# On récupère Path(__file__).resolve().parents[2] et on le garde dans ROOT pour la suite.
ROOT = Path(__file__).resolve().parents[2]
# On ajoute ce dossier aux chemins de recherche Python pour rendre les modules locaux importables dans
# ce contexte.
sys.path.insert(0, str(ROOT / "scripts"))
# On importe workflow_nas_executor sous le nom executor. Ce module sera utilisé par les opérations de
# ce fichier.
import workflow_nas_executor as executor

# On fixe PROBE à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même réglage.
PROBE = """import os,json,sys
from pathlib import Path
from workflow_nas_environment import configure_nas_environment
PROJECT_ROOT = Path(__file__).resolve().parents[3]
def load_dotenv(*args):
    raise AssertionError('Le fichier dotenv ne doit pas etre lu.')
def main():
    configure_nas_environment(PROJECT_ROOT, local_loader=load_dotenv)
    print(json.dumps(dict(os.environ)))
main()
"""


class TestWorkflowNasExecutor(unittest.TestCase):
    def setUp(self):
        # On garde dans temp un dossier temporaire distinct des données du projet.
        temp = tempfile.TemporaryDirectory()
        # On enregistre cette opération de nettoyage pour qu’elle soit appelée après le test, même si
        # celui-ci échoue.
        self.addCleanup(temp.cleanup)
        # On garde dans self.base un objet chemin local ; sa construction seule ne prouve pas que le
        # fichier existe.
        self.base = Path(temp.name)
        # On assemble les morceaux du chemin self.root avec l’opérateur / de pathlib ; aucun fichier
        # n’est créé par cette construction.
        self.root = self.base / "projet test"
        # On prépare le dossier self.root avec les règles de création indiquées ; aucun résultat métier
        # n’est encore produit par cette création.
        self.root.mkdir()
        # On parcourt ((executor.EXTRACTOR, PROBE), (executor.RECONCILER, 'print("LOCAL_RECONCI… ;
        # (relative, content) désigne l’élément courant de ce scénario.
        for relative, content in (
            (executor.EXTRACTOR, PROBE),
            (executor.RECONCILER, 'print("LOCAL_RECONCILIATION")\n'),
        ):
            # On calcule ce quotient pour construire p.
            p = self.root / relative
            # On prépare le dossier p.parent avec les règles de création indiquées ; aucun résultat
            # métier n’est encore produit par cette création.
            p.parent.mkdir(parents=True, exist_ok=True)
            # On écrit le contenu préparé dans p ; cette opération remplace le contenu du fichier s’il
            # existe déjà.
            p.write_text(content, encoding="utf-8")
        # On appelle shutil.copyfile avec ROOT / executor.HELPER.
        shutil.copyfile(ROOT / executor.HELPER, self.root / executor.HELPER)
        # On écrit le contenu préparé dans self.root / '.env' ; cette opération remplace le contenu du
        # fichier s’il existe déjà.
        (self.root / ".env").write_text(
            # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas être
            # décodé selon un réglage implicite du poste.
            "PROJECT12_IMPORT_PASSWORD=private-sentinel", encoding="utf-8"
        )
        # On utilise ce texte pour self.execution ; il ne dépend pas d’une valeur récupérée ailleurs à
        # cet endroit.
        self.execution = "20261013_abcd1234"
        # On assemble les morceaux du chemin self.state avec l’opérateur / de pathlib ; aucun fichier
        # n’est créé par cette construction.
        self.state = self.root / "data/03_normalized/pipeline_runs" / self.execution
        # On prépare le dossier self.state avec les règles de création indiquées ; aucun résultat
        # métier n’est encore produit par cette création.
        self.state.mkdir(parents=True)
        # On assemble les morceaux du chemin self.reference avec l’opérateur / de pathlib ; aucun
        # fichier n’est créé par cette construction.
        self.reference = self.state / "tracking_reference_snapshot.csv"
        # On écrit le contenu préparé dans self.reference ; cette opération remplace le contenu du
        # fichier s’il existe déjà.
        self.reference.write_text("fake", encoding="utf-8")
        # On assemble les morceaux du chemin self.output avec l’opérateur / de pathlib ; aucun fichier
        # n’est créé par cette construction.
        self.output = (
            self.root
            / "data/03_normalized/nas_live_evidence/runs"
            / self.execution
            / "v01"
        )
        # On prépare le dossier self.output avec les règles de création indiquées ; aucun résultat
        # métier n’est encore produit par cette création.
        self.output.mkdir(parents=True)
        # On assemble les morceaux du chemin self.log avec l’opérateur / de pathlib ; aucun fichier
        # n’est créé par cette construction.
        self.log = self.state / "v01_extraction.log"
        # On rassemble dans self.command les 10 éléments explicitement indiqués pour ce cas d’essai.
        self.command = [
            sys.executable,
            str(self.root / executor.EXTRACTOR),
            "--vineyard",
            "Synthetic",
            "--year",
            "2026",
            "--reference",
            str(self.reference),
            "--output-dir",
            str(self.output),
        ]
        # On garde dans self.parent un nouveau dictionnaire construit avec les valeurs indiquées (la
        # copie reste superficielle).
        self.parent = dict(
            os.environ,
            PROJECT12_IMPORT_PASSWORD="private-sentinel",
            AIRFLOW__CORE__FERNET_KEY="private-sentinel",
            PGPASSWORD="private-sentinel",
            PYTHONPATH="inherited-wrong",
            NAS_BRUT_ROOT="inherited-wrong",
        )
        # On garde dans self.brut la représentation textuelle de self.base / 'nas_absent_brut'.
        self.brut = str(self.base / "nas_absent_brut")
        # On garde dans self.processing la représentation textuelle de self.base /
        # 'nas_absent_processing'.
        self.processing = str(self.base / "nas_absent_processing")

    def factory(self, **kwargs):
        # On garde dans options un nouveau dictionnaire construit avec les valeurs indiquées.
        options = dict(
            # On passe la racine des données brutes explicitement, sans la deviner depuis le poste.
            nas_brut_root=self.brut,
            # On passe séparément la racine des résultats de traitement.
            nas_processing_root=self.processing,
            parent_environment=self.parent,
        )
        # On complète options avec les valeurs indiquées ; une clé déjà présente prendra la nouvelle
        # valeur fournie.
        options.update(kwargs)
        # On fournit à l’appelant la valeur renvoyée par executor.build_nas_executor.
        return executor.build_nas_executor(self.root, **options)

    def test_minimal_environment_removes_application_secrets_and_overrides_paths(self):
        # On garde dans env la valeur renvoyée par executor.minimal_environment.
        env = executor.minimal_environment(
            self.root,
            # On passe la racine des données brutes explicitement, sans la deviner depuis le poste.
            nas_brut_root=self.brut,
            # On passe séparément la racine des résultats de traitement.
            nas_processing_root=self.processing,
            temp_dir=self.state,
            parent=self.parent,
        )
        # On parcourt ('PROJECT12_IMPORT_PASSWORD', 'AIRFLOW__CORE__FERNET_KEY', 'PGPASSWORD',… ; key
        # désigne l’élément courant de ce scénario.
        for key in (
            "PROJECT12_IMPORT_PASSWORD",
            "AIRFLOW__CORE__FERNET_KEY",
            "PGPASSWORD",
            "PATH",
        ):
            # On vérifie que key ne figure pas dans env.
            self.assertNotIn(key, env)
        # On vérifie que 'private-sentinel' ne figure pas dans env.values().
        self.assertNotIn("private-sentinel", env.values())
        # On vérifie que env['PYTHONPATH'] correspond à str(self.root / 'src').
        self.assertEqual(env["PYTHONPATH"], str(self.root / "src"))
        # On vérifie que env['NAS_BRUT_ROOT'] correspond à self.brut.
        self.assertEqual(env["NAS_BRUT_ROOT"], self.brut)
        # On vérifie que env['PROJECT12_NAS_CONNECTION_MODE'] correspond à 'environment'.
        self.assertEqual(env["PROJECT12_NAS_CONNECTION_MODE"], "environment")
        # On vérifie que self.parent['PGPASSWORD'] correspond à 'private-sentinel'.
        self.assertEqual(self.parent["PGPASSWORD"], "private-sentinel")

    def test_windows_os_variable_names_are_case_insensitive(self):
        # On regroupe dans parent ces champs nommés ; on pourra les retrouver par leur clé plutôt que
        # par leur position.
        parent = {
            # On associe la clé 'SYSTEMROOT' à cette valeur dans les données de ce scénario.
            "SYSTEMROOT": str(self.base / "Windows"),
            # On associe la clé 'WINDIR' à cette valeur dans les données de ce scénario.
            "WINDIR": str(self.base / "Windows"),
        }
        # On garde dans env la valeur renvoyée par executor.minimal_environment.
        env = executor.minimal_environment(
            self.root,
            # On passe la racine des données brutes explicitement, sans la deviner depuis le poste.
            nas_brut_root=self.brut,
            # On passe séparément la racine des résultats de traitement.
            nas_processing_root=self.processing,
            temp_dir=self.state,
            parent=parent,
        )
        # On vérifie que env['SystemRoot'] correspond à parent['SYSTEMROOT'].
        self.assertEqual(env["SystemRoot"], parent["SYSTEMROOT"])

    def test_factory_does_not_launch_or_create_child_logs(self):
        # Le lancement du processus est remplacé pour observer ses paramètres sans démarrer le
        # programme métier.
        with patch.object(executor.subprocess, "Popen") as popen:
            # On appelle self.factory sans argument positionnel.
            self.factory()
        # On vérifie que popen n’a pas été appelé dans ce scénario.
        popen.assert_not_called()
        # On attend que self.log.exists() soit évalué comme faux pour ce cas de test.
        self.assertFalse(self.log.exists())
        # On attend que (self.state / 'child_tmp').exists() soit évalué comme faux pour ce cas de test.
        self.assertFalse((self.state / "child_tmp").exists())
        # On attend que Path(self.brut).exists() soit évalué comme faux pour ce cas de test.
        self.assertFalse(Path(self.brut).exists())

    def test_real_fake_child_receives_no_secret_and_never_loads_dotenv(self):
        # On garde dans run la valeur renvoyée par self.factory.
        run = self.factory()
        # On vérifie que run(self.command, self.root, self.log) correspond à 0.
        self.assertEqual(run(self.command, self.root, self.log), 0)
        # On garde dans lines les lignes de self.log.read_text(encoding='utf-8') séparées sans dépendre
        # du type de fin de ligne.
        lines = self.log.read_text(encoding="utf-8").splitlines()
        # On garde dans env les objets Python décodés depuis le JSON fourni.
        env = json.loads(lines[-1])
        # On vérifie que 'PROJECT12_IMPORT_PASSWORD' ne figure pas dans env.
        self.assertNotIn("PROJECT12_IMPORT_PASSWORD", env)
        # On vérifie que 'PGPASSWORD' ne figure pas dans env.
        self.assertNotIn("PGPASSWORD", env)
        # On vérifie que 'private-sentinel' ne figure pas dans '\n'.join(lines).
        self.assertNotIn("private-sentinel", "\n".join(lines))
        # On vérifie que env['PROJECT12_NAS_CONNECTION_MODE'] correspond à 'environment'.
        self.assertEqual(env["PROJECT12_NAS_CONNECTION_MODE"], "environment")
        # On attend que Path(env['TMPDIR']).is_relative_to(self.state) soit évalué comme vrai pour ce
        # cas de test.
        self.assertTrue(Path(env["TMPDIR"]).is_relative_to(self.state))
        # On attend que Path(self.brut).exists() soit évalué comme faux pour ce cas de test.
        self.assertFalse(Path(self.brut).exists())

    def test_no_shell_and_output_redirected_to_local_log(self):
        # On garde dans process un double de test dont les réponses et les appels pourront être
        # contrôlés.
        process = Mock()
        # On fixe process.wait.return_value à 0 pour cette étape du scénario de test.
        process.wait.return_value = 0
        # Le lancement du processus est remplacé pour observer ses paramètres sans démarrer le
        # programme métier.
        with patch.object(executor.subprocess, "Popen", return_value=process) as popen:
            # On vérifie que self.factory()(self.command, self.root, self.log) correspond à 0.
            self.assertEqual(self.factory()(self.command, self.root, self.log), 0)
        # On garde popen.call_args.kwargs sous le nom options ; cette affectation ne copie pas à elle
        # seule un objet mutable.
        options = popen.call_args.kwargs
        # On vérifie l’identité de options['shell'] avec False, et pas seulement une égalité de
        # valeur.
        self.assertIs(options["shell"], False)
        # On vérifie que options['cwd'] correspond à self.root.
        self.assertEqual(options["cwd"], self.root)
        # On vérifie que options['stderr'] correspond à subprocess.STDOUT.
        self.assertEqual(options["stderr"], subprocess.STDOUT)
        # On vérifie que 'PGPASSWORD' ne figure pas dans options['env'].
        self.assertNotIn("PGPASSWORD", options["env"])

    def test_nonzero_child_code_preserved(self):
        # On garde dans process un double de test dont les réponses et les appels pourront être
        # contrôlés.
        process = Mock()
        # On fixe process.wait.return_value à 7 pour cette étape du scénario de test.
        process.wait.return_value = 7
        # Le lancement du processus est remplacé pour observer ses paramètres sans démarrer le
        # programme métier.
        with patch.object(executor.subprocess, "Popen", return_value=process):
            # On vérifie que self.factory()(self.command, self.root, self.log) correspond à 7.
            self.assertEqual(self.factory()(self.command, self.root, self.log), 7)

    def test_relative_nas_path_refused(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.factory sans argument positionnel.
            self.factory(nas_brut_root="relative")

    def test_overlapping_nas_and_project_refused(self):
        # On parcourt (str(self.root), str(self.root / 'data'), str(self.base)) ; value désigne
        # l’élément courant de ce scénario.
        for value in (str(self.root), str(self.root / "data"), str(self.base)):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(value=value):
                # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit
                # échouer.
                with self.assertRaises(ValueError):
                    # On appelle self.factory sans argument positionnel.
                    self.factory(nas_brut_root=value)

    def test_unknown_executable_refused_before_launch(self):
        # On garde dans command une liste matérialisée à partir de self.command.
        command = list(self.command)
        # On utilise ce texte pour command[0] ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        command[0] = "python"
        # Le lancement du processus est remplacé pour observer ses paramètres sans démarrer le
        # programme métier.
        with patch.object(executor.subprocess, "Popen") as popen:
            # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaises(ValueError):
                # On appelle self.factory() avec command.
                self.factory()(command, self.root, self.log)
        # On vérifie que popen n’a pas été appelé dans ce scénario.
        popen.assert_not_called()

    def test_unknown_script_refused_before_launch(self):
        # On assemble les morceaux du chemin other avec l’opérateur / de pathlib ; aucun fichier n’est
        # créé par cette construction.
        other = self.root / "other.py"
        # On écrit le contenu préparé dans other ; cette opération remplace le contenu du fichier s’il
        # existe déjà.
        other.write_text("print(1)")
        # On garde dans command une liste matérialisée à partir de self.command.
        command = list(self.command)
        # On garde dans command[1] la représentation textuelle de other.
        command[1] = str(other)
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.factory() avec command.
            self.factory()(command, self.root, self.log)

    def test_extra_or_duplicate_flag_refused(self):
        # On parcourt (['--password', 'private-sentinel'], ['--year', '2026']) ; addition désigne
        # l’élément courant de ce scénario.
        for addition in (["--password", "private-sentinel"], ["--year", "2026"]):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(addition=addition):
                # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit
                # échouer.
                with self.assertRaises(ValueError):
                    # On appelle self.factory() avec self.command + addition.
                    self.factory()(self.command + addition, self.root, self.log)

    def test_missing_flag_refused(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.factory() avec self.command[:-2].
            self.factory()(self.command[:-2], self.root, self.log)

    def test_wrong_project_refused(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.factory() avec self.command.
            self.factory()(self.command, self.base, self.log)

    def test_reference_from_other_run_refused(self):
        # On assemble les morceaux du chemin other avec l’opérateur / de pathlib ; aucun fichier n’est
        # créé par cette construction.
        other = self.root / "data/other.csv"
        # On écrit le contenu préparé dans other ; cette opération remplace le contenu du fichier s’il
        # existe déjà.
        other.write_text("fake")
        # On garde dans command une liste matérialisée à partir de self.command.
        command = list(self.command)
        # On garde dans command[7] la représentation textuelle de other.
        command[7] = str(other)
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.factory() avec command.
            self.factory()(command, self.root, self.log)

    def test_output_outside_project_refused(self):
        # On garde dans command une liste matérialisée à partir de self.command.
        command = list(self.command)
        # On garde dans command[-1] la représentation textuelle de self.base.
        command[-1] = str(self.base)
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.factory() avec command.
            self.factory()(command, self.root, self.log)

    def test_wrong_output_run_refused(self):
        # On garde dans command une liste matérialisée à partir de self.command.
        command = list(self.command)
        # On garde dans command[-1] la représentation textuelle de self.state.
        command[-1] = str(self.state)
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.factory() avec command.
            self.factory()(command, self.root, self.log)

    def test_log_outside_project_refused(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.factory() avec self.command.
            self.factory()(self.command, self.root, self.base / "v01_extraction.log")

    def test_existing_log_never_overwritten(self):
        # On écrit le contenu préparé dans self.log ; cette opération remplace le contenu du fichier
        # s’il existe déjà.
        self.log.write_text("keep", encoding="utf-8")
        # Le lancement du processus est remplacé pour observer ses paramètres sans démarrer le
        # programme métier.
        with patch.object(executor.subprocess, "Popen") as popen:
            # On attend FileExistsError dans ce bloc ; si aucune erreur n’est levée, le test doit
            # échouer.
            with self.assertRaises(FileExistsError):
                # On appelle self.factory() avec self.command.
                self.factory()(self.command, self.root, self.log)
        # On vérifie que self.log.read_text(encoding='utf-8') correspond à 'keep'.
        self.assertEqual(self.log.read_text(encoding="utf-8"), "keep")
        # On vérifie que popen n’a pas été appelé dans ce scénario.
        popen.assert_not_called()

    def test_unpatched_extractor_refused(self):
        # On écrit le contenu préparé dans self.root / executor.EXTRACTOR ; cette opération remplace le
        # contenu du fichier s’il existe déjà.
        (self.root / executor.EXTRACTOR).write_text(
            # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas être
            # décodé selon un réglage implicite du poste.
            'from dotenv import load_dotenv\nload_dotenv(".env")\n', encoding="utf-8"
        )
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.factory sans argument positionnel.
            self.factory()

    def test_source_changed_after_preparation_refused(self):
        # On garde dans run la valeur renvoyée par self.factory.
        run = self.factory()
        # On écrit le contenu préparé dans self.root / executor.HELPER ; cette opération remplace le
        # contenu du fichier s’il existe déjà.
        (self.root / executor.HELPER).write_text("# changed", encoding="utf-8")
        # Le lancement du processus est remplacé pour observer ses paramètres sans démarrer le
        # programme métier.
        with patch.object(executor.subprocess, "Popen") as popen:
            # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaises(ValueError):
                # On appelle run avec self.command.
                run(self.command, self.root, self.log)
        # On vérifie que popen n’a pas été appelé dans ce scénario.
        popen.assert_not_called()

    def test_timeout_stops_child_and_reports_failure(self):
        # On garde dans process un double de test dont les réponses et les appels pourront être
        # contrôlés.
        process = Mock()
        # On initialise process.poll.return_value à None : aucune valeur n’a encore été retenue ici.
        process.poll.return_value = None
        # On rassemble dans process.wait.side_effect les 2 éléments explicitement indiqués pour ce cas
        # d’essai.
        process.wait.side_effect = [subprocess.TimeoutExpired("fake", 1), 0]
        # Le lancement du processus est remplacé pour observer ses paramètres sans démarrer le
        # programme métier.
        with patch.object(executor.subprocess, "Popen", return_value=process):
            # On attend executor.NasChildTimeout dans ce bloc ; si aucune erreur n’est levée, le test
            # doit échouer.
            with self.assertRaises(executor.NasChildTimeout):
                # On appelle self.factory(timeout_seconds=1) avec self.command.
                self.factory(timeout_seconds=1)(self.command, self.root, self.log)
        # On attend un seul appel à process.terminate dans ce scénario, ni zéro ni plusieurs.
        process.terminate.assert_called_once()

    def test_interrupt_stops_child_and_is_not_success(self):
        # On garde dans process un double de test dont les réponses et les appels pourront être
        # contrôlés.
        process = Mock()
        # On initialise process.poll.return_value à None : aucune valeur n’a encore été retenue ici.
        process.poll.return_value = None
        # On rassemble dans process.wait.side_effect les 2 éléments explicitement indiqués pour ce cas
        # d’essai.
        process.wait.side_effect = [KeyboardInterrupt, 0]
        # Le lancement du processus est remplacé pour observer ses paramètres sans démarrer le
        # programme métier.
        with patch.object(executor.subprocess, "Popen", return_value=process):
            # On attend KeyboardInterrupt dans ce bloc ; si aucune erreur n’est levée, le test doit
            # échouer.
            with self.assertRaises(KeyboardInterrupt):
                # On appelle self.factory() avec self.command.
                self.factory()(self.command, self.root, self.log)
        # On attend un seul appel à process.terminate dans ce scénario, ni zéro ni plusieurs.
        process.terminate.assert_called_once()

    def test_stop_falls_back_to_kill(self):
        # On garde dans process un double de test dont les réponses et les appels pourront être
        # contrôlés.
        process = Mock()
        # On initialise process.poll.return_value à None : aucune valeur n’a encore été retenue ici.
        process.poll.return_value = None
        # On rassemble dans process.wait.side_effect les 2 éléments explicitement indiqués pour ce cas
        # d’essai.
        process.wait.side_effect = [subprocess.TimeoutExpired("fake", 5), 0]
        # On appelle executor.stop_child avec process.
        executor.stop_child(process)
        # On attend un seul appel à process.terminate dans ce scénario, ni zéro ni plusieurs.
        process.terminate.assert_called_once()
        # On attend un seul appel à process.kill dans ce scénario, ni zéro ni plusieurs.
        process.kill.assert_called_once()

    def test_invalid_timeout_refused(self):
        # On parcourt (True, 0, float('inf'), float('nan'), 90000) ; value désigne l’élément courant de
        # ce scénario.
        for value in (True, 0, float("inf"), float("nan"), 90000):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(value=value):
                # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit
                # échouer.
                with self.assertRaises(ValueError):
                    # On appelle self.factory sans argument positionnel.
                    self.factory(timeout_seconds=value)

    def test_reconciliation_requires_local_evidence_from_same_run(self):
        # On assemble les morceaux du chemin out avec l’opérateur / de pathlib ; aucun fichier n’est
        # créé par cette construction.
        out = (
            self.root
            / "data/03_normalized/reconciliations/nas_live/runs"
            / self.execution
            / "v01"
        )
        # On prépare le dossier out avec les règles de création indiquées ; aucun résultat métier n’est
        # encore produit par cette création.
        out.mkdir(parents=True)
        # On prépare paths comme liste vide ; on la remplira au fil des opérations suivantes.
        paths = []
        # On parcourt ('evidence', 'associations', 'passages') ; name désigne l’élément courant de ce
        # scénario.
        for name in ("evidence", "associations", "passages"):
            # On assemble les morceaux du chemin path avec l’opérateur / de pathlib ; aucun fichier
            # n’est créé par cette construction.
            path = self.output / (name + ".csv")
            # On écrit le contenu préparé dans path ; cette opération remplace le contenu du fichier
            # s’il existe déjà.
            path.write_text("fake")
            # On ajoute str(path) à la fin de paths ; les éléments précédents restent conservés.
            paths.append(str(path))
        # On rassemble dans command les 14 éléments explicitement indiqués pour ce cas d’essai.
        command = [
            sys.executable,
            str(self.root / executor.RECONCILER),
            "--vineyard",
            "Synthetic",
            "--reference",
            str(self.reference),
            "--evidence",
            paths[0],
            "--associations",
            paths[1],
            "--passages",
            paths[2],
            "--output-dir",
            str(out),
        ]
        # On assemble les morceaux du chemin log avec l’opérateur / de pathlib ; aucun fichier n’est
        # créé par cette construction.
        log = self.state / "v01_reconciliation.log"
        # On vérifie que self.factory()(command, self.root, log) correspond à 0.
        self.assertEqual(self.factory()(command, self.root, log), 0)
        # On garde dans command[7] la représentation textuelle de self.reference.
        command[7] = str(self.reference)
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.factory() avec command.
            self.factory()(command, self.root, log)

    def test_existing_pilot_commands_accepted_with_simulated_children(self):
        # On importe test_run_local_pipeline sous le nom pilot_fixture. Ce module sera utilisé par les
        # opérations de ce fichier.
        import test_run_local_pipeline as pilot_fixture

        # On garde dans f la valeur renvoyée par pilot_fixture.TestRunLocalPipeline.
        f = pilot_fixture.TestRunLocalPipeline()
        # On initialise les ressources du scénario f avec sa méthode setUp.
        f.setUp()
        # On encadre cette opération pour que le bloc finally soit exécuté même si elle échoue.
        try:
            # On écrit le contenu préparé dans f.root / executor.EXTRACTOR ; cette opération remplace
            # le contenu du fichier s’il existe déjà.
            (f.root / executor.EXTRACTOR).write_text(PROBE, encoding="utf-8")
            # On écrit le contenu préparé dans f.root / executor.RECONCILER ; cette opération remplace
            # le contenu du fichier s’il existe déjà.
            (f.root / executor.RECONCILER).write_text('print("fake")', encoding="utf-8")
            # On appelle shutil.copyfile avec ROOT / executor.HELPER.
            shutil.copyfile(ROOT / executor.HELPER, f.root / executor.HELPER)
            # On garde dans run la valeur renvoyée par executor.build_nas_executor.
            run = executor.build_nas_executor(
                f.root,
                # On passe la racine des données brutes explicitement, sans la deviner depuis le poste.
                nas_brut_root=self.brut,
                # On passe séparément la racine des résultats de traitement.
                nas_processing_root=self.processing,
                parent_environment=self.parent,
            )

            def simulated(command, **kwargs):
                # On garde dans code la valeur renvoyée par f.fake.
                code = f.fake(command, f.root, f.root / "fake_process.log")
                # On garde dans process un double de test dont les réponses et les appels pourront être
                # contrôlés.
                process = Mock()
                # On gardu code de retour sous le nom process.wait.return_value ; cette affectation
                # ne copie pas à elle seule un objet mutable.
                process.wait.return_value = code
                # On remet le processus enfant à l’appelant ; les étapes suivantes de cette fonction ne
                # sont plus parcourues.
                return process

            # Le lancement du processus est remplacé pour observer ses paramètres sans démarrer le
            # programme métier.
            with patch.object(executor.subprocess, "Popen", side_effect=simulated):
                # On répartit les valeurs renvoyées par f.execute entre (code, manifest) ; leur ordre
                # doit correspondre à celui prévu par cet appel.
                code, manifest = f.execute(executor=run)
            # On vérifie que code correspond à 0.
            self.assertEqual(code, 0)
            # On vérifie que json.loads(manifest.read_text(encoding='utf-8'))['status'] correspond à
            # 'success'.
            self.assertEqual(
                # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
                json.loads(manifest.read_text(encoding="utf-8"))["status"], "success"
            )
            # On vérifie que len(f.calls) correspond à 2.
            self.assertEqual(len(f.calls), 2)
        finally:
            # On appelle f.doCleanups sans argument positionnel.
            f.doCleanups()

    def test_parent_changes_do_not_inject_secrets_after_factory(self):
        # On garde dans run la valeur renvoyée par self.factory.
        run = self.factory()
        # On utilise ce texte pour self.parent['NEW_SECRET'] ; il ne dépend pas d’une valeur récupérée
        # ailleurs à cet endroit.
        self.parent["NEW_SECRET"] = "private-sentinel"
        # On vérifie que run(self.command, self.root, self.log) correspond à 0.
        self.assertEqual(run(self.command, self.root, self.log), 0)
        # On vérifie que 'NEW_SECRET' ne figure pas dans self.log.read_text(encoding='utf-8').
        self.assertNotIn("NEW_SECRET", self.log.read_text(encoding="utf-8"))
