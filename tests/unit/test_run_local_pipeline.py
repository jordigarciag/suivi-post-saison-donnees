# Lecture du fichier — Tests de run local pipeline.
#

"""Tests du pilote avec processus simulés : aucun accès au NAS."""

# On importe contextlib. Ce module sera utilisé par les opérations de ce fichier.
import contextlib
# On importe csv. On transforme les tableaux entre lignes Python et fichiers CSV.
import csv
# On importe importlib.util. Ce module sera utilisé par les opérations de ce fichier.
import importlib.util
# On importe io. On peut fournir des flux en mémoire aux lecteurs et aux captures de sortie.
import io
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On importe tempfile. On prépare des fichiers ou dossiers temporaires pour les cas isolés.
import tempfile
# On importe unittest. On décrit les scénarios et les vérifications de la suite de tests.
import unittest
# On rend disponibles Path, PureWindowsPath depuis pathlib, pour les appels de ce fichier.
from pathlib import Path, PureWindowsPath

# On récupère Path(__file__).resolve().parents[2] et on le garde dans PROJECT_ROOT pour la suite.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# On garde dans SPEC la valeur renvoyée par importlib.util.spec_from_file_location pour
# 'local_pipeline_under_test'.
SPEC = importlib.util.spec_from_file_location(
    "local_pipeline_under_test", PROJECT_ROOT / "scripts/run_local_pipeline.py"
)
# On garde dans p la valeur renvoyée par importlib.util.module_from_spec.
p = importlib.util.module_from_spec(SPEC)
# On appelle SPEC.loader.exec_module avec p.
SPEC.loader.exec_module(p)


def csv_file(path, rows, fields=None):
    # On retient pour fields la première valeur évaluée comme vraie dans cette chaîne de replis ; une
    # valeur vide fera donc passer à la suivante.
    fields = fields or list(rows[0])
    # On prépare le dossier path.parent avec les règles de création indiquées ; aucun résultat métier
    # n’est encore produit par cette création.
    path.parent.mkdir(parents=True, exist_ok=True)
    # On ouvre cette sortie en écriture ; le contenu précédent serait remplacé. La fermeture du
    # fichier est gérée à la sortie du bloc.
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        # On garde dans writer un outil d’écriture CSV avec les noms de colonnes explicitement
        # indiqués.
        writer = csv.DictWriter(stream, fieldnames=fields)
        # On appelle writer.writeheader sans argument positionnel.
        writer.writeheader()
        # On appelle writer.writerows avec rows.
        writer.writerows(rows)


class TestRunLocalPipeline(unittest.TestCase):
    def setUp(self):
        # On garde dans self.temp un dossier temporaire distinct des données du projet.
        self.temp = tempfile.TemporaryDirectory()
        # On enregistre cette opération de nettoyage pour qu’elle soit appelée après le test, même si
        # celui-ci échoue.
        self.addCleanup(self.temp.cleanup)
        # On garde dans self.root un objet chemin local ; sa construction seule ne prouve pas que le
        # fichier existe.
        self.root = Path(self.temp.name)
        # On calcule ce quotient pour construire self.reference.
        self.reference = self.root / p.REFERENCE_PATH
        # On appelle csv_file avec self.reference.
        csv_file(
            self.reference,
            [
                {
                    # On renseigne le domaine concerné sous la clé 'Vineyard'.
                    "Vineyard": "DomaineDemoD",
                    # On renseigne l’identifiant normalisé de l’acquisition sous la clé
                    # 'Acquisition_ID_normalise'.
                    "Acquisition_ID_normalise": "DomaineDemoD_C01_V1_2026-07-15T10-00-00",
                },
                {
                    # On renseigne le domaine concerné sous la clé 'Vineyard'.
                    "Vineyard": "DomaineDemoB",
                    # On renseigne l’identifiant normalisé de l’acquisition sous la clé
                    # 'Acquisition_ID_normalise'.
                    "Acquisition_ID_normalise": "DomaineDemoB_C01_V1_2026-06-01T10-00-00",
                },
                {
                    # On renseigne le domaine concerné sous la clé 'Vineyard'.
                    "Vineyard": "Ancien",
                    # On renseigne l’identifiant normalisé de l’acquisition sous la clé
                    # 'Acquisition_ID_normalise'.
                    "Acquisition_ID_normalise": "Ancien_C01_V1_2025-06-01T10-00-00",
                },
            ],
        )
        # On parcourt ('extraction/nas_live_evidence_extractor.py', 'reconciliation/excel_nas_l… ; name
        # désigne l’élément courant de ce scénario.
        for name in (
            "extraction/nas_live_evidence_extractor.py",
            "reconciliation/excel_nas_live_reconciler.py",
        ):
            # On calcule ce quotient pour construire file.
            file = self.root / p.PACKAGE_PATH / name
            # On prépare le dossier file.parent avec les règles de création indiquées ; aucun résultat
            # métier n’est encore produit par cette création.
            file.parent.mkdir(parents=True, exist_ok=True)
            # On écrit le contenu préparé dans file ; cette opération remplace le contenu du fichier
            # s’il existe déjà.
            file.write_text("# script simulé", encoding="utf-8")
        # On prépare self.calls comme liste vide ; on la remplira au fil des opérations suivantes.
        self.calls = []

    def fake(self, command, root, log):
        # On ajoute command à la fin de self.calls ; les éléments précédents restent conservés.
        self.calls.append(command)
        # On écrit le contenu préparé dans log ; cette opération remplace le contenu du fichier s’il
        # existe déjà.
        log.write_text("Log synthétique", encoding="utf-8")
        # On sélectionne dans command les éléments désignés par command.index('--vineyard') + 1 ;
        # vineyard recevra cette sélection.
        vineyard = command[command.index("--vineyard") + 1]
        # On garde dans folder un objet chemin local ; sa construction seule ne prouve pas que le
        # fichier existe.
        folder = Path(command[command.index("--output-dir") + 1])
        # On vérifie ce cas avant la suite : le texte 'nas_live_evidence_extractor.py' appartient à
        # command[1].
        if "nas_live_evidence_extractor.py" in command[1]:
            # On prépare prefix avec cette expression pour l’utiliser dans la suite du traitement.
            prefix = f"{p.safe_stem(vineyard)}_live_nas_"
            # On garde p.LABELS sous le nom labels ; cette affectation ne copie pas à elle seule un
            # objet mutable.
            labels = p.LABELS
            # On utilise ce texte pour timestamp ; il ne dépend pas d’une valeur récupérée ailleurs à
            # cet endroit.
            timestamp = "2026-10-06T09-00-00Z"
        else:
            # On prépare prefix avec cette expression pour l’utiliser dans la suite du traitement.
            prefix = f"{p.safe_stem(vineyard)}_excel_nas_live_"
            # On garde p.OUTPUT_LABELS sous le nom labels ; cette affectation ne copie pas à elle seule
            # un objet mutable.
            labels = p.OUTPUT_LABELS
            # On utilise ce texte pour timestamp ; il ne dépend pas d’une valeur récupérée ailleurs à
            # cet endroit.
            timestamp = "2026-10-06T09-00-01-123456Z"
        # On parcourt labels ; label désigne l’élément courant de ce scénario.
        for label in labels:
            # On appelle csv_file avec folder / f'{prefix}{label}_{timestamp}.csv'.
            csv_file(
                folder / f"{prefix}{label}_{timestamp}.csv",
                [
                    {
                        # On renseigne le domaine concerné sous la clé 'Vineyard'.
                        "Vineyard": vineyard,
                        # On associe la clé 'project_year' à cette valeur dans les données de ce
                        # scénario.
                        "project_year": "2026",
                        # On renseigne la date du contrôle sous la clé 'checked_at'.
                        "checked_at": "2026-10-06T09:00:00.123456+00:00",
                        # On renseigne l’erreur de lecture des données brutes sous la clé 'raw_error'.
                        "raw_error": "",
                    }
                ],
            )
        # On termine cette branche avec la valeur 0.
        return 0

    def execute(self, vineyards=None, executor=None, stop=False):
        # On utilise contextlib.redirect_stdout(io.StringIO()) dans son contexte de gestion ; les
        # opérations de sortie sont exécutées en quittant le bloc.
        with contextlib.redirect_stdout(io.StringIO()):
            # On fournit à l’appelant la valeur renvoyée par p.execute_pipeline.
            return p.execute_pipeline(
                self.root,
                self.reference,
                vineyards or ["DomaineDemoD"],
                2026,
                # On décide si le parcours s’arrête dès la première erreur, au lieu de laisser ce choix
                # implicite.
                stop_on_error=stop,
                executor=executor or self.fake,
            )

    def test_success_passes_exact_three_paths_without_manual_run_id(self):
        # On répartit les valeurs renvoyées par self.execute entre (code, manifest_path) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        code, manifest_path = self.execute()
        # On vérifie que code correspond à 0.
        self.assertEqual(code, 0)
        # On vérifie que len(self.calls) correspond à 2.
        self.assertEqual(len(self.calls), 2)
        # On garde dans manifest les objets Python décodés depuis le JSON fourni.
        manifest = json.loads(manifest_path.read_text())
        # On récupère manifest['vineyards'][0] et on le garde dans item pour la suite.
        item = manifest["vineyards"][0]
        # On vérifie que item['extraction_run_id'] correspond à '2026-10-06T09-00-00Z'.
        self.assertEqual(item["extraction_run_id"], "2026-10-06T09-00-00Z")
        # On vérifie que '--run-id' ne figure pas dans self.calls[1].
        self.assertNotIn("--run-id", self.calls[1])
        # On parcourt (('--evidence', 'evidence'), ('--associations', 'associations'), ('--pass… ;
        # (option, label) désigne l’élément courant de ce scénario.
        for option, label in (
            ("--evidence", "evidence"),
            ("--associations", "associations"),
            ("--passages", "passages"),
        ):
            # On vérifie que self.calls[1][self.calls[1].index(option) + 1] correspond à
            # item['evidence_outputs'][label].
            self.assertEqual(
                # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
                self.calls[1][self.calls[1].index(option) + 1],
                # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
                item["evidence_outputs"][label],
            )
        # On vérifie que self.calls[0][0] correspond à sys.executable.
        self.assertEqual(self.calls[0][0], sys.executable)
        # On vérifie que manifest['status'] correspond à 'success'.
        self.assertEqual(manifest["status"], "success")

    def test_reference_is_snapshotted_and_original_unchanged(self):
        # On garde dans before les octets lus depuis self.reference, avant toute conversion en
        # texte. Les contrôles de contenu pourront ainsi repartir de cette lecture.
        before = self.reference.read_bytes()
        # On répartit les valeurs renvoyées par self.execute entre (_, path) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        _, path = self.execute()
        # On garde dans manifest les objets Python décodés depuis le JSON fourni.
        manifest = json.loads(path.read_text())
        # On vérifie que Path(manifest['reference_snapshot']).read_bytes() correspond à before.
        self.assertEqual(Path(manifest["reference_snapshot"]).read_bytes(), before)
        # On vérifie que self.reference.read_bytes() correspond à before.
        self.assertEqual(self.reference.read_bytes(), before)
        # On parcourt self.calls ; command désigne l’élément courant de ce scénario.
        for command in self.calls:
            # On vérifie que command[command.index('--reference') + 1] correspond à
            # manifest['reference_snapshot'].
            self.assertEqual(
                # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
                command[command.index("--reference") + 1],
                # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
                manifest["reference_snapshot"],
            )

    def test_new_runs_have_isolated_directories(self):
        # On répartit les valeurs renvoyées par self.execute entre (_, first) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        _, first = self.execute()
        # On répartit les valeurs renvoyées par self.execute entre (_, second) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        _, second = self.execute()
        # On vérifie que first.parent diffère de second.parent.
        self.assertNotEqual(first.parent, second.parent)
        # On vérifie que self.calls[0][self.calls[0].index('--output-dir') + 1] diffère de
        # self.calls[2][self.calls[2].index('--output-dir') + 1].
        self.assertNotEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            self.calls[0][self.calls[0].index("--output-dir") + 1],
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            self.calls[2][self.calls[2].index("--output-dir") + 1],
        )

    def test_failed_extraction_does_not_launch_reconciler(self):
        # On répartit les valeurs renvoyées par self.execute entre (code, path) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        code, path = self.execute(executor=lambda *args: 2)
        # On vérifie que code correspond à 1.
        self.assertEqual(code, 1)
        # On récupère json.loads(path.read_text())['vineyards'][0] et on le garde dans item pour la
        # suite.
        item = json.loads(path.read_text())["vineyards"][0]
        # On vérifie que item['status'] correspond à 'failed'.
        self.assertEqual(item["status"], "failed")
        # On vérifie que 'reconciliation_returncode' ne figure pas dans item.
        self.assertNotIn("reconciliation_returncode", item)

    def test_old_global_files_are_never_used(self):
        # On assemble les morceaux du chemin old avec l’opérateur / de pathlib ; aucun fichier n’est
        # créé par cette construction.
        old = self.root / "data/03_normalized/nas_live_evidence"
        # On prépare le dossier old avec les règles de création indiquées ; aucun résultat métier n’est
        # encore produit par cette création.
        old.mkdir(parents=True)
        # On parcourt p.LABELS ; label désigne l’élément courant de ce scénario.
        for label in p.LABELS:
            # On écrit le contenu préparé dans old /
            # f'pilote_live_nas_{label}_2026-10-06T09-00-00Z.csv' ; cette opération remplace le contenu
            # du fichier s’il existe déjà.
            (old / f"pilote_live_nas_{label}_2026-10-06T09-00-00Z.csv").write_text(
                "old"
            )
        # On répartit les valeurs renvoyées par self.execute entre (code, path) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        code, path = self.execute(executor=lambda *args: 0)
        # On vérifie que code correspond à 1.
        self.assertEqual(code, 1)
        # On vérifie que 'exactement un CSV' figure dans
        # json.loads(path.read_text())['vineyards'][0]['error'].
        self.assertIn(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            "exactement un CSV", json.loads(path.read_text())["vineyards"][0]["error"]
        )

    def test_extraction_failure_continues_next_vineyard_by_default(self):
        def executor(command, root, log):
            # On vérifie ce cas avant la suite : command[command.index('--vineyard') + 1] correspond à
            # le texte 'DomaineDemoD'.
            if command[command.index("--vineyard") + 1] == "DomaineDemoD":
                # On termine cette branche avec la valeur 2.
                return 2
            # On fournit à l’appelant la valeur renvoyée par self.fake.
            return self.fake(command, root, log)

        # On répartit les valeurs renvoyées par self.execute entre (code, path) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        code, path = self.execute(["DomaineDemoD", "DomaineDemoB"], executor)
        # On vérifie que code correspond à 1.
        self.assertEqual(code, 1)
        # On vérifie que [row['status'] for row in json.loads(path.read_text())['vineyards']]
        # correspond à ['failed', 'success'].
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            [row["status"] for row in json.loads(path.read_text())["vineyards"]],
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            ["failed", "success"],
        )

    def test_stop_on_error_skips_next_vineyard(self):
        # On répartit les valeurs renvoyées par self.execute entre (code, path) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        code, path = self.execute(["DomaineDemoD", "DomaineDemoB"], lambda *args: 2, stop=True)
        # On vérifie que code correspond à 1.
        self.assertEqual(code, 1)
        # On vérifie que [row['status'] for row in json.loads(path.read_text())['vineyards']]
        # correspond à ['failed', 'skipped'].
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            [row["status"] for row in json.loads(path.read_text())["vineyards"]],
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            ["failed", "skipped"],
        )

    def test_failed_reconciliation_is_not_success(self):
        def executor(command, root, log):
            # On renvoie l’une des deux valeurs selon le test indiqué ; ce choix termine la fonction
            # pour ce cas.
            return (
                self.fake(command, root, log)
                if "nas_live_evidence_extractor.py" in command[1]
                else 3
            )

        # On répartit les valeurs renvoyées par self.execute entre (code, path) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        code, path = self.execute(executor=executor)
        # On vérifie que code correspond à 1.
        self.assertEqual(code, 1)
        # On vérifie que json.loads(path.read_text())['vineyards'][0]['stage'] correspond à
        # 'reconciliation'.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            json.loads(path.read_text())["vineyards"][0]["stage"], "reconciliation"
        )

    def test_missing_reconciliation_outputs_is_failure(self):
        def executor(command, root, log):
            # On renvoie l’une des deux valeurs selon le test indiqué ; ce choix termine la fonction
            # pour ce cas.
            return (
                self.fake(command, root, log)
                if "nas_live_evidence_extractor.py" in command[1]
                else 0
            )

        # On répartit les valeurs renvoyées par self.execute entre (code, _) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        code, _ = self.execute(executor=executor)
        # On vérifie que code correspond à 1.
        self.assertEqual(code, 1)

    def test_all_vineyards_filters_year_and_sorts(self):
        # On vérifie que p.select_vineyards(self.reference, [], True, 2026) correspond à
        # ['DomaineDemoB', 'DomaineDemoD'].
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            p.select_vineyards(self.reference, [], True, 2026), ["DomaineDemoB", "DomaineDemoD"]
        )

    def test_selection_is_case_insensitive_and_deduplicated(self):
        # On vérifie que p.select_vineyards(self.reference, [' domainedemod ', 'DomaineDemoD'], Fals…
        # correspond à ['DomaineDemoD'].
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            p.select_vineyards(self.reference, [" domainedemod ", "DomaineDemoD"], False, 2026),
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            ["DomaineDemoD"],
        )

    def test_unknown_vineyard_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle p.select_vineyards avec self.reference.
            p.select_vineyards(self.reference, ["Inconnu"], False, 2026)

    def test_output_outside_local_data_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle p.local_data_path avec self.root.
            p.local_data_path(self.root, self.root / "outside")

    def test_mixed_triplet_timestamps_rejected(self):
        # On assemble les morceaux du chemin folder avec l’opérateur / de pathlib ; aucun fichier n’est
        # créé par cette construction.
        folder = self.root / "triplet"
        # On prépare le dossier folder avec les règles de création indiquées ; aucun résultat métier
        # n’est encore produit par cette création.
        folder.mkdir()
        # On parcourt p.LABELS en gardant aussi sa position dans (index, label) ; le comptage commence
        # à zéro.
        for index, label in enumerate(p.LABELS):
            # On écrit le contenu préparé dans folder /
            # f'pilote_live_nas_{label}_2026-10-06T09-00-0{index}Z.c… ; cette opération remplace le
            # contenu du fichier s’il existe déjà.
            (
                folder / f"pilote_live_nas_{label}_2026-10-06T09-00-0{index}Z.csv"
            ).write_text("unused")
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle p.collect_triplet avec folder.
            p.collect_triplet(folder, "DomaineDemoD", "extraction")

    def test_observation_errors_are_counted_not_hidden_or_treated_as_process_failure(
        self,
    ):
        def executor(command, root, log):
            # On garde dans result la valeur renvoyée par self.fake.
            result = self.fake(command, root, log)
            # On vérifie ce cas avant la suite : le texte 'nas_live_evidence_extractor.py' appartient à
            # command[1].
            if "nas_live_evidence_extractor.py" in command[1]:
                # On garde dans folder un objet chemin local ; sa construction seule ne prouve pas que
                # le fichier existe.
                folder = Path(command[command.index("--output-dir") + 1])
                # On garde dans file le prochain élément de folder.glob('*_evidence_*.csv').
                file = next(folder.glob("*_evidence_*.csv"))
                # On répartit les valeurs renvoyées par p.read_csv entre (fields, rows) ; leur ordre
                # doit correspondre à celui prévu par cet appel.
                fields, rows = p.read_csv(file)
                # On utilise ce texte pour rows[0]['raw_error'] ; il ne dépend pas d’une valeur
                # récupérée ailleurs à cet endroit.
                rows[0]["raw_error"] = "Accès refusé"
                # On appelle csv_file avec file.
                csv_file(file, rows, fields)
            # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette
            # fonction ne sont plus parcourues.
            return result

        # On répartit les valeurs renvoyées par self.execute entre (code, path) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        code, path = self.execute(executor=executor)
        # On vérifie que code correspond à 0.
        self.assertEqual(code, 0)
        # On vérifie que json.loads(path.read_text())['vineyards'][0]['observations']['rows_with_obs…
        # correspond à 1.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            json.loads(path.read_text())["vineyards"][0]["observations"][
                "rows_with_observation_errors"
            ]["evidence"],
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            1,
        )

    def test_wrong_vineyard_in_extraction_blocks_reconciliation(self):
        def executor(command, root, log):
            # On garde dans result la valeur renvoyée par self.fake.
            result = self.fake(command, root, log)
            # On garde dans folder un objet chemin local ; sa construction seule ne prouve pas que le
            # fichier existe.
            folder = Path(command[command.index("--output-dir") + 1])
            # On parcourt folder.glob('*.csv') ; file désigne l’élément courant de ce scénario.
            for file in folder.glob("*.csv"):
                # On répartit les valeurs renvoyées par p.read_csv entre (fields, rows) ; leur ordre
                # doit correspondre à celui prévu par cet appel.
                fields, rows = p.read_csv(file)
                # On utilise ce texte pour rows[0]['Vineyard'] ; il ne dépend pas d’une valeur
                # récupérée ailleurs à cet endroit.
                rows[0]["Vineyard"] = "Autre"
                # On appelle csv_file avec file.
                csv_file(file, rows, fields)
            # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette
            # fonction ne sont plus parcourues.
            return result

        # On répartit les valeurs renvoyées par self.execute entre (code, path) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        code, path = self.execute(executor=executor)
        # On vérifie que code correspond à 1.
        self.assertEqual(code, 1)
        # On vérifie que len(self.calls) correspond à 1.
        self.assertEqual(len(self.calls), 1)

    def test_keyboard_interrupt_is_recorded(self):
        # On traite l’interruption pour ne pas laisser le processus enfant poursuivre sans son
        # parent.
        def interrupted(*args):
            # On interrompt cette branche avec KeyboardInterrupt.
            raise KeyboardInterrupt()

        # On répartit les valeurs renvoyées par self.execute entre (code, path) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        code, path = self.execute(["DomaineDemoD", "DomaineDemoB"], executor=interrupted)
        # On vérifie que code correspond à 130.
        self.assertEqual(code, 130)
        # On garde dans manifest les objets Python décodés depuis le JSON fourni.
        manifest = json.loads(path.read_text())
        # On vérifie que manifest['status'] correspond à 'interrupted'.
        self.assertEqual(manifest["status"], "interrupted")
        # On vérifie que [row['status'] for row in manifest['vineyards']] correspond à ['interrupted',
        # 'skipped'].
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            [row["status"] for row in manifest["vineyards"]], ["interrupted", "skipped"]
        )

    def test_short_folder_names_keep_windows_chateau_path_within_budget(self):
        # On répartit les valeurs renvoyées par self.execute entre (code, manifest_path) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        code, manifest_path = self.execute()
        # On vérifie que code correspond à 0.
        self.assertEqual(code, 0)
        # On garde dans manifest les objets Python décodés depuis le JSON fourni.
        manifest = json.loads(manifest_path.read_text())
        # On récupère l’identifiant du traitement NAS dans manifest et on le garde dans execution_id
        # pour la suite.
        execution_id = manifest["pipeline_execution_id"]
        # On vérifie que len(execution_id) correspond à 17.
        self.assertEqual(len(execution_id), 17)
        # On vérifie que manifest['vineyards'][0]['directory_name'] correspond à 'v01'.
        self.assertEqual(manifest["vineyards"][0]["directory_name"], "v01")
        # On garde dans windows_root une représentation de chemin Windows, sans ouvrir ce chemin.
        windows_root = PureWindowsPath(
            r"C:\Users\utilisateur\Documents\GitHub\demo-data-stats\suivi_traitements_post_saison"
        )
        # On assemble les morceaux du chemin planned avec l’opérateur / de pathlib ; aucun fichier
        # n’est créé par cette construction.
        planned = (
            windows_root
            / "data/03_normalized/reconciliations/nas_live/runs"
            / execution_id
            / "v01"
            / "domainedemoc_excel_nas_live_acquisitions_2026-10-06T08-05-38-733621Z.csv"
        )
        # On contrôle le résultat avec assertLessEqual et les valeurs attendues indiquées juste
        # dessous.
        self.assertLessEqual(len(str(planned)), 240)
        # On appelle p.check_windows_path_lengths avec [planned].
        p.check_windows_path_lengths([planned], windows=True)

    def test_windows_path_budget_rejects_old_long_layout(self):
        # On garde dans windows_root une représentation de chemin Windows, sans ouvrir ce chemin.
        windows_root = PureWindowsPath(
            r"C:\Users\utilisateur\Documents\GitHub\demo-data-stats\suivi_traitements_post_saison"
        )
        # On assemble les morceaux du chemin old avec l’opérateur / de pathlib ; aucun fichier n’est
        # créé par cette construction.
        old = (
            windows_root
            / "data/03_normalized/reconciliations/nas_live/runs"
            / "2026-10-06T08-04-53-307273Z_1e3639cd"
            / "domainedemoc_11c505c6"
            / "domainedemoc_excel_nas_live_acquisitions_2026-10-06T08-05-38-733621Z.csv"
        )
        # On attend ValueError avec un message correspondant au motif indiqué dans ce bloc ; si aucune
        # erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(ValueError, "Chemin local trop long"):
            # On appelle p.check_windows_path_lengths avec [old].
            p.check_windows_path_lengths([old], windows=True)
        # On appelle p.check_windows_path_lengths avec [old].
        p.check_windows_path_lengths([old], windows=False)

    def test_manifest_maps_short_folders_to_each_vineyard(self):
        # On répartit les valeurs renvoyées par self.execute entre (code, path) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        code, path = self.execute(["DomaineDemoD", "DomaineDemoB"])
        # On vérifie que code correspond à 0.
        self.assertEqual(code, 0)
        # On garde dans manifest les objets Python décodés depuis le JSON fourni.
        manifest = json.loads(path.read_text())
        # On vérifie que [(row['vineyard'], row['directory_name']) for row in manifest['vineyards']]
        # correspond à [('DomaineDemoD', 'v01'), ('DomaineDemoB', 'v02')].
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            [(row["vineyard"], row["directory_name"]) for row in manifest["vineyards"]],
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            [("DomaineDemoD", "v01"), ("DomaineDemoB", "v02")],
        )
        # On attend que Path(manifest['vineyards'][1]['reconciliation_directory']).is_dir() soit évalué
        # comme vrai pour ce cas de test.
        self.assertTrue(
            Path(manifest["vineyards"][1]["reconciliation_directory"]).is_dir()
        )


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On confie la découverte et l’exécution des tests de ce fichier au lanceur unittest.
    unittest.main()
