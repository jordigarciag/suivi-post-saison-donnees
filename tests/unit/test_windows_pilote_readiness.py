# Lecture du fichier — Tests de windows pilote readiness.
#

# On importe importlib.util. Ce module sera utilisé par les opérations de ce fichier.
import importlib.util
# On importe io. On peut fournir des flux en mémoire aux lecteurs et aux captures de sortie.
import io
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On importe tempfile. On prépare des fichiers ou dossiers temporaires pour les cas isolés.
import tempfile
# On rend disponibles SimpleNamespace, ModuleType depuis types, pour les appels de ce fichier.
from types import SimpleNamespace, ModuleType
# On importe unittest. On décrit les scénarios et les vérifications de la suite de tests.
import unittest
# On rend disponibles patch depuis unittest.mock, pour les appels de ce fichier.
from unittest.mock import patch
# On importe zipfile. Ce module sera utilisé par les opérations de ce fichier.
import zipfile
# On rend disponibles contextmanager, redirect_stdout depuis contextlib, pour les appels de ce fichier.
from contextlib import contextmanager, redirect_stdout

# On assemble les morceaux du chemin SCRIPT avec l’opérateur / de pathlib ; aucun fichier n’est créé
# par cette construction.
SCRIPT = (
    Path(__file__).resolve().parents[2] / "scripts/check_windows_pilote_readiness.py"
)
# On garde dans spec la valeur renvoyée par importlib.util.spec_from_file_location pour
# 'windows_readiness_tested'.
spec = importlib.util.spec_from_file_location("windows_readiness_tested", SCRIPT)
# On garde dans m la valeur renvoyée par importlib.util.module_from_spec.
m = importlib.util.module_from_spec(spec)
# On appelle spec.loader.exec_module avec m.
spec.loader.exec_module(m)


class TestWindowsDomaineDemoDReadiness(unittest.TestCase):
    def setUp(self):
        # On garde dans self.tmp un dossier temporaire distinct des données du projet.
        self.tmp = tempfile.TemporaryDirectory()
        # On enregistre cette opération de nettoyage pour qu’elle soit appelée après le test, même si
        # celui-ci échoue.
        self.addCleanup(self.tmp.cleanup)
        # On garde dans self.root un objet chemin local ; sa construction seule ne prouve pas que le
        # fichier existe.
        self.root = Path(self.tmp.name)
        # On assemble les morceaux du chemin self.incoming avec l’opérateur / de pathlib ; aucun
        # fichier n’est créé par cette construction.
        self.incoming = self.root / "data/01_incoming/suivi_acquisitions"
        # On prépare le dossier self.incoming avec les règles de création indiquées ; aucun résultat
        # métier n’est encore produit par cette création.
        self.incoming.mkdir(parents=True)
        # On assemble les morceaux du chemin self.brut avec l’opérateur / de pathlib ; aucun fichier
        # n’est créé par cette construction.
        self.brut = self.root / "fake_nas_brut"
        # On assemble les morceaux du chemin self.processing avec l’opérateur / de pathlib ; aucun
        # fichier n’est créé par cette construction.
        self.processing = self.root / "fake_nas_processing"
        # On prépare le dossier self.brut / 'DomaineDemoD/2026' avec les règles de création indiquées ;
        # aucun résultat métier n’est encore produit par cette création.
        (self.brut / "DomaineDemoD/2026").mkdir(parents=True)
        # On prépare le dossier self.processing / 'DomaineDemoD/acquisitions/2026' avec les règles de
        # création indiquées ; aucun résultat métier n’est encore produit par cette création.
        (self.processing / "DomaineDemoD/acquisitions/2026").mkdir(parents=True)
        # On assemble les morceaux du chemin parcels avec l’opérateur / de pathlib ; aucun fichier
        # n’est créé par cette construction.
        parcels = self.processing / "DomaineDemoD/parcels"
        # On prépare le dossier parcels avec les règles de création indiquées ; aucun résultat métier
        # n’est encore produit par cette création.
        parcels.mkdir(parents=True)
        # On écrit le contenu préparé dans parcels / 'DomaineDemoD_parcels_acquisitions_map.json' ;
        # cette opération remplace le contenu du fichier s’il existe déjà.
        (parcels / "DomaineDemoD_parcels_acquisitions_map.json").write_text("{}")
        # On assemble les morceaux du chemin passages avec l’opérateur / de pathlib ; aucun fichier
        # n’est créé par cette construction.
        passages = self.processing / "DomaineDemoD/passages"
        # On prépare le dossier passages avec les règles de création indiquées ; aucun résultat métier
        # n’est encore produit par cette création.
        passages.mkdir(parents=True)
        # On écrit le contenu préparé dans passages /
        # 'DomaineDemoD_parcels_passages_acquisitions_map.json' ; cette opération remplace le contenu
        # du fichier s’il existe déjà.
        (passages / "DomaineDemoD_parcels_passages_acquisitions_map.json").write_text("{}")
        # On garde dans self.config un objet de test regroupant les attributs fournis.
        self.config = SimpleNamespace(
            # On fournit la racine locale du projet via le paramètre root de cet appel.
            root=self.root,
            # On passe la racine des données brutes explicitement, sans la deviner depuis le poste.
            nas_brut_root=str(self.brut),
            # On passe séparément la racine des résultats de traitement.
            nas_processing_root=str(self.processing),
        )
        # On assemble les morceaux du chemin self.excel avec l’opérateur / de pathlib ; aucun fichier
        # n’est créé par cette construction.
        self.excel = self.incoming / "Suivi_acquisition_DomaineDemoD_2026.xlsx"
        # On utilise zipfile.ZipFile(self.excel, 'w') dans son contexte de gestion ; les opérations de
        # sortie sont exécutées en quittant le bloc.
        with zipfile.ZipFile(self.excel, "w") as book:
            # On appelle book.writestr avec 'xl/workbook.xml'.
            book.writestr("xl/workbook.xml", "<workbook/>")

    def call_main(self, *, failure=None, platform="win32"):
        # On garde dans configmod la valeur renvoyée par ModuleType pour 'workflow_business_config'.
        configmod = ModuleType("workflow_business_config")
        # On prépare pour configmod.local_project une fonction courte ; elle ne sera exécutée que
        # lorsqu’elle sera appelée, pas lors de cette affectation.
        configmod.local_project = lambda root: self.root
        # On prépare pour configmod.load_business_configuration une fonction courte ; elle ne sera
        # exécutée que lorsqu’elle sera appelée, pas lors de cette affectation.
        configmod.load_business_configuration = lambda *a, **k: self.config
        # On garde dans runtime la valeur renvoyée par ModuleType pour 'workflow_runtime'.
        runtime = ModuleType("workflow_runtime")
        # On fixe self.lock_entries à 0 pour cette étape du scénario de test.
        self.lock_entries = 0
        # On initialise self.lock_released à False ; les branches suivantes pourront modifier cet état.
        self.lock_released = False

        @contextmanager
        def lock(*args):
            # On ajoute 1 à self.lock_entries et on conserve ce nouvel état pour la suite.
            self.lock_entries += 1
            # On encadre cette opération pour que le bloc finally soit exécuté même si elle échoue.
            try:
                # On fournit cette valeur à l’appelant et on suspend la fonction ici ; elle reprendra
                # après ce point si son itération continue.
                yield
            finally:
                # On initialise self.lock_released à True ; les branches suivantes pourront modifier
                # cet état.
                self.lock_released = True

        # On garde lock sous le nom runtime.workflow_lock ; cette affectation ne copie pas à elle seule
        # un objet mutable.
        runtime.workflow_lock = lock
        # On garde dans entry la valeur renvoyée par ModuleType pour 'run_workflow_business'.
        entry = ModuleType("run_workflow_business")
        # On fixe self.sql_calls à 0 pour cette étape du scénario de test.
        self.sql_calls = 0

        def sql(config):
            # On ajoute 1 à self.sql_calls et on conserve ce nouvel état pour la suite.
            self.sql_calls += 1
            # Cette branche traite le cas où failure est évalué comme vrai.
            if failure:
                # On lève cette exception au lieu de continuer avec un résultat non confirmé.
                raise failure
            # On affiche le texte 'private-output-must-not-leak' dans la sortie du programme.
            print("private-output-must-not-leak")
            # On renvoie ces 3 éléments ensemble ; l’appelant doit respecter leur ordre s’il les
            # décompose.
            return (8, 1044, 488)

        # On garde sql sous le nom entry.diagnose_importer ; cette affectation ne copie pas à elle
        # seule un objet mutable.
        entry.diagnose_importer = sql
        # On garde dans output un flux texte en mémoire, utilisable comme un fichier par le lecteur
        # CSV.
        output = io.StringIO()
        # On remplace temporairement m.sys dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with (
            patch.object(m.sys, "platform", platform),
            patch.dict(
                sys.modules,
                {
                    # On associe la clé 'workflow_business_config' à cette valeur dans les données de
                    # ce scénario.
                    "workflow_business_config": configmod,
                    # On associe la clé 'workflow_runtime' à cette valeur dans les données de ce
                    # scénario.
                    "workflow_runtime": runtime,
                    # On associe la clé 'run_workflow_business' à cette valeur dans les données de ce
                    # scénario.
                    "run_workflow_business": entry,
                },
            ),
            redirect_stdout(output),
        ):
            # On garde dans result la valeur renvoyée par m.main.
            result = m.main(["--project-root", str(self.root)])
        # On garde dans files une liste matérialisée à partir de (self.root /
        # 'logs/windows_scheduler_checks').glob('*.jsonl').
        files = list((self.root / "logs/windows_scheduler_checks").glob("*.jsonl"))
        # On choisit la valeur de records selon ce test : files est évalué comme vrai. Les deux
        # résultats possibles restent définis explicitement ici.
        records = (
            [json.loads(line) for line in files[0].read_text().splitlines()]
            if files
            else []
        )
        # On renvoie ces 3 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
        return result, output.getvalue(), records

    def test_sources_valid(self):
        # On appelle m.check_sources avec self.config.
        m.check_sources(self.config)

    def test_missing_excel_rejected(self):
        # On supprime ce fichier local selon le chemin préparé ; on ne nettoie pas arbitrairement
        # d’autres fichiers.
        self.excel.unlink()
        # On attend m.ReadinessError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(m.ReadinessError):
            # On appelle m.check_sources avec self.config.
            m.check_sources(self.config)

    def test_two_excel_rejected(self):
        # On écrit le contenu préparé dans self.incoming / 'DomaineDemoD_copy.xlsx' ; cette opération
        # remplace le contenu du fichier s’il existe déjà.
        (self.incoming / "DomaineDemoD_copy.xlsx").write_bytes(self.excel.read_bytes())
        # On attend m.ReadinessError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(m.ReadinessError):
            # On appelle m.check_sources avec self.config.
            m.check_sources(self.config)

    def test_excel_temporary_file_ignored(self):
        # On écrit le contenu préparé dans self.incoming / '~$DomaineDemoD.xlsx' ; cette opération
        # remplace le contenu du fichier s’il existe déjà.
        (self.incoming / "~$DomaineDemoD.xlsx").write_bytes(b"not-a-workbook")
        # On appelle m.check_sources avec self.config.
        m.check_sources(self.config)

    def test_invalid_excel_rejected(self):
        # On écrit le contenu préparé dans self.excel ; cette opération remplace le contenu du fichier
        # s’il existe déjà.
        self.excel.write_bytes(b"bad")
        # On attend zipfile.BadZipFile dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(zipfile.BadZipFile):
            # On appelle m.check_sources avec self.config.
            m.check_sources(self.config)

    def test_missing_nas_scope_rejected(self):
        # On appelle (self.brut / 'DomaineDemoD/2026').rmdir sans argument positionnel.
        (self.brut / "DomaineDemoD/2026").rmdir()
        # On attend OSError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(OSError):
            # On appelle m.check_sources avec self.config.
            m.check_sources(self.config)

    def test_passage_mapping_is_read_from_passages_not_parcels(self):
        # On assemble les morceaux du chemin passage avec l’opérateur / de pathlib ; aucun fichier
        # n’est créé par cette construction.
        passage = (
            self.processing
            / "DomaineDemoD/passages/DomaineDemoD_parcels_passages_acquisitions_map.json"
        )
        # On supprime ce fichier local selon le chemin préparé ; on ne nettoie pas arbitrairement
        # d’autres fichiers.
        passage.unlink()
        # On assemble les morceaux du chemin decoy avec l’opérateur / de pathlib ; aucun fichier n’est
        # créé par cette construction.
        decoy = (
            self.processing
            / "DomaineDemoD/parcels/DomaineDemoD_parcels_passages_acquisitions_map.json"
        )
        # On écrit le contenu préparé dans decoy ; cette opération remplace le contenu du fichier s’il
        # existe déjà.
        decoy.write_text("{}")
        # On attend FileNotFoundError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(FileNotFoundError):
            # On appelle m.check_sources avec self.config.
            m.check_sources(self.config)

    def test_invalid_mapping_rejected(self):
        # On écrit le contenu préparé dans self.processing /
        # 'DomaineDemoD/parcels/DomaineDemoD_parcels_ac… ; cette opération remplace le contenu du
        # fichier s’il existe déjà.
        (
            self.processing / "DomaineDemoD/parcels/DomaineDemoD_parcels_acquisitions_map.json"
        ).write_text("broken")
        # On attend json.JSONDecodeError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(json.JSONDecodeError):
            # On appelle m.check_sources avec self.config.
            m.check_sources(self.config)

    def test_mapping_scalar_rejected(self):
        # On écrit le contenu préparé dans self.processing /
        # 'DomaineDemoD/parcels/DomaineDemoD_parcels_ac… ; cette opération remplace le contenu du
        # fichier s’il existe déjà.
        (
            self.processing / "DomaineDemoD/parcels/DomaineDemoD_parcels_acquisitions_map.json"
        ).write_text("true")
        # On attend m.ReadinessError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(m.ReadinessError):
            # On appelle m.check_sources avec self.config.
            m.check_sources(self.config)

    def test_reading_does_not_change_source_bytes(self):
        # On rassemble dans files les 2 éléments explicitement indiqués pour ce cas d’essai.
        files = [self.excel, *self.processing.rglob("*.json")]
        # On indexe before par p ; chaque clé sera associée à p.read_bytes(). Une même clé ne peut
        # garder qu’une valeur.
        before = {p: p.read_bytes() for p in files}
        # On appelle m.check_sources avec self.config.
        m.check_sources(self.config)
        # On vérifie que before correspond à {p: p.read_bytes() for p in files}.
        self.assertEqual(before, {p: p.read_bytes() for p in files})

    def test_success_report_and_zero_workflow(self):
        # On répartit les valeurs renvoyées par self.call_main entre (result, output, records) ; leur
        # ordre doit correspondre à celui prévu par cet appel.
        result, output, records = self.call_main()
        # On vérifie que result correspond à 0.
        self.assertEqual(result, 0)
        # On vérifie que records[-1]['status'] correspond à 'success'.
        self.assertEqual(records[-1]["status"], "success")
        # On vérifie que records[-1]['workflow_steps_executed'] correspond à 0.
        self.assertEqual(records[-1]["workflow_steps_executed"], 0)
        # On vérifie que self.sql_calls correspond à 1.
        self.assertEqual(self.sql_calls, 1)
        # On attend que self.lock_released soit évalué comme vrai pour ce cas de test.
        self.assertTrue(self.lock_released)
        # On vérifie que 'private-output-must-not-leak' ne figure pas dans output.
        self.assertNotIn("private-output-must-not-leak", output)

    def test_sql_failure_does_not_leak_secret(self):
        # On répartit les valeurs renvoyées par self.call_main entre (result, output, records) ; leur
        # ordre doit correspondre à celui prévu par cet appel.
        result, output, records = self.call_main(
            failure=RuntimeError("secret-password-NAS-path")
        )
        # On vérifie que result correspond à 1.
        self.assertEqual(result, 1)
        # On vérifie que records[-1]['status'] correspond à 'failed'.
        self.assertEqual(records[-1]["status"], "failed")
        # On attend que self.lock_released soit évalué comme vrai pour ce cas de test.
        self.assertTrue(self.lock_released)
        # On vérifie que 'secret-password' ne figure pas dans output + json.dumps(records).
        self.assertNotIn("secret-password", output + json.dumps(records))

    def test_sources_failure_prevents_sql(self):
        # On supprime ce fichier local selon le chemin préparé ; on ne nettoie pas arbitrairement
        # d’autres fichiers.
        self.excel.unlink()
        # On répartit les valeurs renvoyées par self.call_main entre (result, _, records) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        result, _, records = self.call_main()
        # On vérifie que result correspond à 1.
        self.assertEqual(result, 1)
        # On vérifie que self.sql_calls correspond à 0.
        self.assertEqual(self.sql_calls, 0)
        # On vérifie que records[-2]['step'] correspond à 'sources_read'.
        self.assertEqual(records[-2]["step"], "sources_read")
        # On attend que self.lock_released soit évalué comme vrai pour ce cas de test.
        self.assertTrue(self.lock_released)

    def test_non_windows_refused_without_log(self):
        # On répartit les valeurs renvoyées par self.call_main entre (result, _, records) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        result, _, records = self.call_main(platform="linux")
        # On vérifie que result correspond à 1.
        self.assertEqual(result, 1)
        # On vérifie que records correspond à [].
        self.assertEqual(records, [])
        # On vérifie que self.sql_calls correspond à 0.
        self.assertEqual(self.sql_calls, 0)

    def test_report_has_unique_name(self):
        # On répartit les valeurs renvoyées par m.create_report entre (relative1, handle1) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        relative1, handle1 = m.create_report(self.root)
        # On ferme handle1 pour libérer la ressource associée après son utilisation.
        handle1.close()
        # On répartit les valeurs renvoyées par m.create_report entre (relative2, handle2) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        relative2, handle2 = m.create_report(self.root)
        # On ferme handle2 pour libérer la ressource associée après son utilisation.
        handle2.close()
        # On vérifie que relative1 diffère de relative2.
        self.assertNotEqual(relative1, relative2)

    def test_report_redirect_rejected(self):
        # Simuler la redirection : aucun privilege de lien symbolique requis sous Windows.
        with patch.object(m.Path, "is_symlink", return_value=True):
            # On attend m.ReadinessError dans ce bloc ; si aucune erreur n’est levée, le test doit
            # échouer.
            with self.assertRaises(m.ReadinessError):
                # On appelle m.create_report avec self.root.
                m.create_report(self.root)

    def test_run_argument_refused(self):
        # On remplace temporairement m.sys dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with (
            redirect_stdout(io.StringIO()),
            patch.object(m.sys, "stderr", io.StringIO()),
        ):
            # On attend SystemExit dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaises(SystemExit) as caught:
                # On appelle m.main avec ['--run'].
                m.main(["--run"])
        # On vérifie que caught.exception.code correspond à 2.
        self.assertEqual(caught.exception.code, 2)


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On confie la découverte et l’exécution des tests de ce fichier au lanceur unittest.
    unittest.main()
