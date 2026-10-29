# Lecture du fichier — Tests de workflow business wiring.
#

"""Configuration fictive et raccordement paresseux : aucune connexion NAS/SQL."""

# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On rend disponibles MappingProxyType, SimpleNamespace depuis types, pour les appels de ce fichier.
from types import MappingProxyType, SimpleNamespace
# On importe contextlib. Ce module sera utilisé par les opérations de ce fichier.
import contextlib
# On importe io. On peut fournir des flux en mémoire aux lecteurs et aux captures de sortie.
import io
# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
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
# On importe workflow_business_config sous le nom config. Ce module sera utilisé par les opérations de
# ce fichier.
import workflow_business_config as config
# On importe workflow_business_wiring sous le nom wiring. Ce module sera utilisé par les opérations de
# ce fichier.
import workflow_business_wiring as wiring
# On importe check_workflow_business sous le nom cli. Ce module sera utilisé par les opérations de ce
# fichier.
import check_workflow_business as cli


class TestWorkflowBusinessWiring(unittest.TestCase):
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
        self.root = self.base / "project"
        # On prépare le dossier self.root avec les règles de création indiquées ; aucun résultat métier
        # n’est encore produit par cette création.
        self.root.mkdir()
        # On parcourt config.REQUIRED_FILES ; relative désigne l’élément courant de ce scénario.
        for relative in config.REQUIRED_FILES:
            # On calcule ce quotient pour construire path.
            path = self.root / relative
            # On prépare le dossier path.parent avec les règles de création indiquées ; aucun résultat
            # métier n’est encore produit par cette création.
            path.parent.mkdir(parents=True, exist_ok=True)
            # On écrit le contenu préparé dans path ; cette opération remplace le contenu du fichier
            # s’il existe déjà.
            path.write_text("# fixture", encoding="utf-8")
        # On garde dans self.brut la représentation textuelle de self.base / 'fake_nas_brut'.
        self.brut = str(self.base / "fake_nas_brut")
        # On garde dans self.processing la représentation textuelle de self.base /
        # 'fake_nas_processing'.
        self.processing = str(self.base / "fake_nas_processing")
        # On utilise ce texte pour self.password ; il ne dépend pas d’une valeur récupérée ailleurs à
        # cet endroit.
        self.password = "secret-$-#-sentinel"
        # On regroupe dans self.env ces champs nommés ; on pourra les retrouver par leur clé plutôt que
        # par leur position.
        self.env = {
            # On associe la clé 'PROJECT12_IMPORT_CONNECTION_MODE' à cette valeur dans les données de
            # ce scénario.
            "PROJECT12_IMPORT_CONNECTION_MODE": "environment",
            # On associe la clé 'PROJECT12_IMPORT_USER' à cette valeur dans les données de ce scénario.
            "PROJECT12_IMPORT_USER": "projet12_importer",
            # On associe la clé 'PROJECT12_IMPORT_HOST' à cette valeur dans les données de ce scénario.
            "PROJECT12_IMPORT_HOST": "fake-server",
            # On associe la clé 'PROJECT12_IMPORT_PORT' à cette valeur dans les données de ce scénario.
            "PROJECT12_IMPORT_PORT": "5432",
            # On associe la clé 'PROJECT12_IMPORT_PASSWORD' à cette valeur dans les données de ce
            # scénario.
            "PROJECT12_IMPORT_PASSWORD": self.password,
            # On associe la clé 'NAS_BRUT_ROOT' à cette valeur dans les données de ce scénario.
            "NAS_BRUT_ROOT": self.brut,
            # On associe la clé 'NAS_PROCESSING_ROOT' à cette valeur dans les données de ce scénario.
            "NAS_PROCESSING_ROOT": self.processing,
        }

    def environment_config(self):
        # On remplace temporairement os.environ dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.dict(os.environ, self.env, clear=True):
            # On fournit à l’appelant la valeur renvoyée par config.load_business_configuration.
            return config.load_business_configuration(
                self.root, configuration_mode="environment"
            )

    def test_environment_config_does_not_read_dotenv(self):
        # On remplace temporairement 'dotenv.dotenv_values' dans ce bloc de test ; le réglage initial
        # sera rétabli à sa sortie.
        with patch("dotenv.dotenv_values") as values:
            # On garde dans result la configuration d’environnement isolée pour le scénario.
            result = self.environment_config()
        # On vérifie que values n’a pas été appelé dans ce scénario.
        values.assert_not_called()
        # On vérifie que result.importer['user'] correspond à 'projet12_importer'.
        self.assertEqual(result.importer["user"], "projet12_importer")
        # On vérifie que result.importer['dbname'] correspond à 'suivi_acquisitions'.
        self.assertEqual(result.importer["dbname"], "suivi_acquisitions")
        # On attend que Path(self.brut).exists() soit évalué comme faux pour ce cas de test.
        self.assertFalse(Path(self.brut).exists())
        # On attend que (self.root / 'state').exists() soit évalué comme faux pour ce cas de test.
        self.assertFalse((self.root / "state").exists())

    def test_local_config_retains_only_importer_and_nas_parameters(self):
        # On assemble ces deux éléments pour construire source.
        source = (
            "NAS_BRUT_ROOT="
            + self.brut
            + "\nNAS_PROCESSING_ROOT="
            + self.processing
            + "\nPROJECT12_IMPORT_USER=projet12_importer\nPROJECT12_IMPORT_PASSWORD="
            + self.password
            + "\nPROJECT12_POSTGRES_PASSWORD=admin-sentinel\nPROJECT12_DASHBOARD_PASSWORD=dashboard-sentinel\n"
        )
        # On écrit le contenu préparé dans self.root / '.env' ; cette opération remplace le contenu du
        # fichier s’il existe déjà.
        (self.root / ".env").write_text(source, encoding="utf-8")
        # On remplace temporairement os.environ dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.dict(os.environ, {}, clear=True):
            # On garde dans result la valeur renvoyée par config.load_business_configuration.
            result = config.load_business_configuration(self.root)
        # On vérifie que result.importer['password'] correspond à self.password.
        self.assertEqual(result.importer["password"], self.password)
        # On vérifie que result.importer['host'] correspond à '127.0.0.1'.
        self.assertEqual(result.importer["host"], "127.0.0.1")
        # On vérifie que result.importer['port'] correspond à 5433.
        self.assertEqual(result.importer["port"], 5433)
        # On vérifie que 'admin-sentinel' ne figure pas dans repr(result).
        self.assertNotIn("admin-sentinel", repr(result))
        # On vérifie que self.password ne figure pas dans repr(result).
        self.assertNotIn(self.password, repr(result))
        # On vérifie que 'dashboard' ne figure pas dans str(dict(result.importer)).
        self.assertNotIn("dashboard", str(dict(result.importer)))

    def test_environment_changed_during_capture_refused(self):
        def changing(root):
            # On garde dans os.environ['NAS_BRUT_ROOT'] la représentation textuelle de self.base /
            # 'changed'.
            os.environ["NAS_BRUT_ROOT"] = str(self.base / "changed")
            # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver
            # chaque information par sa clé.
            return {
                # On associe la clé 'password' à cette valeur dans les données de ce scénario.
                "password": self.password,
                # On associe la clé 'dbname' à cette valeur dans les données de ce scénario.
                "dbname": "suivi_acquisitions",
                # On associe la clé 'user' à cette valeur dans les données de ce scénario.
                "user": "projet12_importer",
            }

        # On remplace temporairement os.environ dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with (
            patch.dict(os.environ, self.env, clear=True),
            patch.object(config, "database_config", side_effect=changing),
        ):
            # On attend config.BusinessConfigurationError avec un message correspondant au motif
            # indiqué dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaisesRegex(
                config.BusinessConfigurationError, "ENVIRONMENT_CONFIGURATION_CHANGED"
            ):
                # On appelle config.load_business_configuration avec self.root.
                config.load_business_configuration(
                    self.root, configuration_mode="environment"
                )

    def test_local_file_changed_during_capture_refused(self):
        # On assemble les morceaux du chemin source avec l’opérateur / de pathlib ; aucun fichier n’est
        # créé par cette construction.
        source = self.root / ".env"
        # On écrit le contenu préparé dans source ; cette opération remplace le contenu du fichier s’il
        # existe déjà.
        source.write_text(
            "NAS_BRUT_ROOT="
            + self.brut
            + "\nNAS_PROCESSING_ROOT="
            + self.processing
            + "\n",
            # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas être
            # décodé selon un réglage implicite du poste.
            encoding="utf-8",
        )

        def changing(root):
            # On écrit le contenu préparé dans source ; cette opération remplace le contenu du fichier
            # s’il existe déjà.
            source.write_text("changed", encoding="utf-8")
            # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver
            # chaque information par sa clé.
            return {"password": self.password}

        # On remplace temporairement os.environ dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(config, "database_config", side_effect=changing),
        ):
            # On attend config.BusinessConfigurationError avec un message correspondant au motif
            # indiqué dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaisesRegex(
                config.BusinessConfigurationError, "LOCAL_CONFIGURATION_CHANGED"
            ):
                # On appelle config.load_business_configuration avec self.root.
                config.load_business_configuration(self.root)

    def test_configuration_is_immutable(self):
        # On garde dans result la configuration d’environnement isolée pour le scénario.
        result = self.environment_config()
        # On attend TypeError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(TypeError):
            # On utilise ce texte pour result.importer['password'] ; il ne dépend pas d’une valeur
            # récupérée ailleurs à cet endroit.
            result.importer["password"] = "other"

    def test_unknown_mode_refused(self):
        # On attend config.BusinessConfigurationError dans ce bloc ; si aucune erreur n’est levée, le
        # test doit échouer.
        with self.assertRaises(config.BusinessConfigurationError):
            # On appelle config.load_business_configuration avec self.root.
            config.load_business_configuration(self.root, configuration_mode="auto")

    def test_inherited_mode_not_silently_overridden(self):
        # On remplace temporairement os.environ dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.dict(os.environ, self.env, clear=True):
            # On attend config.BusinessConfigurationError avec un message correspondant au motif
            # indiqué dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaisesRegex(
                config.BusinessConfigurationError, "IMPORT_CONFIGURATION_MODE_MISMATCH"
            ):
                # On appelle config.load_business_configuration avec self.root.
                config.load_business_configuration(
                    self.root, configuration_mode="local"
                )

    def test_missing_local_env_refused(self):
        # On remplace temporairement os.environ dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.dict(os.environ, {}, clear=True):
            # On attend config.BusinessConfigurationError avec un message correspondant au motif
            # indiqué dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaisesRegex(
                config.BusinessConfigurationError, "LOCAL_CONFIGURATION_MISSING"
            ):
                # On appelle config.load_business_configuration avec self.root.
                config.load_business_configuration(self.root)

    def test_admin_user_refused_without_fallback(self):
        # On remplace temporairement os.environ dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.dict(
            os.environ,
            dict(self.env, PROJECT12_IMPORT_USER="projet12_admin"),
            # On indique si les anciennes entrées doivent être retirées pendant ce remplacement
            # temporaire de dictionnaire.
            clear=True,
        ):
            # On attend config.BusinessConfigurationError avec un message correspondant au motif
            # indiqué dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaisesRegex(
                config.BusinessConfigurationError, "IMPORT_CONFIGURATION_INVALID"
            ):
                # On appelle config.load_business_configuration avec self.root.
                config.load_business_configuration(
                    self.root, configuration_mode="environment"
                )

    def test_missing_password_refused_without_fallback(self):
        # On garde dans env un nouveau dictionnaire construit avec les valeurs indiquées (la copie
        # reste superficielle).
        env = dict(self.env)
        # On retire env['PROJECT12_IMPORT_PASSWORD'] de son emplacement ; la suite ne doit plus
        # s’appuyer sur cette entrée.
        del env["PROJECT12_IMPORT_PASSWORD"]
        # On remplace temporairement os.environ dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.dict(os.environ, env, clear=True):
            # On attend config.BusinessConfigurationError avec un message correspondant au motif
            # indiqué dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaisesRegex(
                config.BusinessConfigurationError, "IMPORT_CONFIGURATION_INVALID"
            ):
                # On appelle config.load_business_configuration avec self.root.
                config.load_business_configuration(
                    self.root, configuration_mode="environment"
                )

    def test_bad_password_not_in_error_message(self):
        # On remplace temporairement os.environ dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.dict(
            os.environ,
            dict(self.env, PROJECT12_IMPORT_PASSWORD="private\nvalue"),
            # On indique si les anciennes entrées doivent être retirées pendant ce remplacement
            # temporaire de dictionnaire.
            clear=True,
        ):
            # On attend config.BusinessConfigurationError dans ce bloc ; si aucune erreur n’est levée,
            # le test doit échouer.
            with self.assertRaises(config.BusinessConfigurationError) as error:
                # On appelle config.load_business_configuration avec self.root.
                config.load_business_configuration(
                    self.root, configuration_mode="environment"
                )
        # On vérifie que 'private' ne figure pas dans str(error.exception).
        self.assertNotIn("private", str(error.exception))

    def test_missing_nas_root_refused_without_local_fallback(self):
        # On garde dans env un nouveau dictionnaire construit avec les valeurs indiquées (la copie
        # reste superficielle).
        env = dict(self.env)
        # On retire env['NAS_BRUT_ROOT'] de son emplacement ; la suite ne doit plus s’appuyer sur cette
        # entrée.
        del env["NAS_BRUT_ROOT"]
        # On remplace temporairement os.environ dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.dict(os.environ, env, clear=True):
            # On attend config.BusinessConfigurationError avec un message correspondant au motif
            # indiqué dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaisesRegex(
                config.BusinessConfigurationError, "NAS_CONFIGURATION_INVALID"
            ):
                # On appelle config.load_business_configuration avec self.root.
                config.load_business_configuration(
                    self.root, configuration_mode="environment"
                )

    def test_wrong_os_or_relative_nas_path_refused(self):
        # On remplace temporairement os.environ dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.dict(
            # On indique si les anciennes entrées doivent être retirées pendant ce remplacement
            # temporaire de dictionnaire.
            os.environ, dict(self.env, NAS_BRUT_ROOT="relative"), clear=True
        ):
            # On attend config.BusinessConfigurationError avec un message correspondant au motif
            # indiqué dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaisesRegex(
                config.BusinessConfigurationError, "NAS_CONFIGURATION_INVALID"
            ):
                # On appelle config.load_business_configuration avec self.root.
                config.load_business_configuration(
                    self.root, configuration_mode="environment"
                )

    def test_missing_source_refused(self):
        # On supprime ce fichier local selon le chemin préparé ; on ne nettoie pas arbitrairement
        # d’autres fichiers.
        (self.root / config.REQUIRED_FILES[0]).unlink()
        # On attend config.BusinessConfigurationError avec un message correspondant au motif indiqué
        # dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(
            config.BusinessConfigurationError, "REQUIRED_SOURCE_OR_CONFIG_MISSING"
        ):
            # On appelle self.environment_config sans argument positionnel.
            self.environment_config()

    def test_network_project_refused_before_files(self):
        # On attend config.BusinessConfigurationError avec un message correspondant au motif indiqué
        # dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(
            config.BusinessConfigurationError, "PROJECT_MUST_BE_LOCAL"
        ):
            # On appelle config.local_project avec '//fake-server/shared/project'.
            config.local_project("//fake-server/shared/project")

    def modules(self):
        # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
        # information par sa clé.
        return {
            # On associe la clé 'suivi_traitements_post_saison.ingestion.tracking_versioning' à cette
            # valeur dans les données de ce scénario.
            "suivi_traitements_post_saison.ingestion.tracking_versioning": SimpleNamespace(
                run_ingestion=Mock()
            ),
            # On associe la clé 'import_excel_publication' à cette valeur dans les données de ce
            # scénario.
            "import_excel_publication": SimpleNamespace(
                prepare_bundle=Mock(), check_still_current=Mock(), import_bundle=Mock()
            ),
            # On associe la clé 'load_nas_reconciliation' à cette valeur dans les données de ce
            # scénario.
            "load_nas_reconciliation": SimpleNamespace(
                prepare_bundle=Mock(), check_files=Mock(), import_bundle=Mock()
            ),
            # On associe la clé 'run_local_pipeline' à cette valeur dans les données de ce scénario.
            "run_local_pipeline": SimpleNamespace(
                select_vineyards=Mock(),
                execute_pipeline=Mock(return_value=(0, "fake_manifest")),
            ),
        }

    # On assemble les éléments de présentation prévus par ce bloc local.
    def build(self, cfg, **kwargs):
        # On garde dans self.modules_used la valeur renvoyée par self.modules.
        self.modules_used = self.modules()
        # On garde dans self.executor un double de test dont les réponses et les appels pourront être
        # contrôlés.
        self.executor = Mock(return_value=0)
        # On remplace temporairement wiring dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with (
            patch.object(
                wiring,
                "_project_module",
                # On définit le comportement simulé de l’appel, qui peut notamment lever une erreur ou
                # suivre une fonction de test.
                side_effect=lambda root, name, rel: self.modules_used[name],
            ),
            patch.object(
                # On fixe la réponse de ce double de test ; aucune vraie opération de la dépendance
                # n’est nécessaire pour obtenir cette valeur.
                wiring, "build_nas_executor", return_value=self.executor
            ) as factory,
            patch.object(wiring, "connect_importer") as connect,
        ):
            # On garde dans plan la valeur renvoyée par wiring.build_business_plan.
            plan = wiring.build_business_plan(cfg, all_vineyards=True, **kwargs)
            # On garde factory.call_args sous le nom self.factory_arguments ; cette affectation ne
            # copie pas à elle seule un objet mutable.
            self.factory_arguments = factory.call_args
            # On vérifie que connect n’a pas été appelé : le refus doit intervenir avant cette
            # opération.
            connect.assert_not_called()
        # On remet plan à l’appelant ; les étapes suivantes de cette fonction ne sont plus parcourues.
        return plan

    def test_plan_build_does_not_ingest_extract_load_or_connect(self):
        # On garde dans plan la valeur renvoyée par self.build.
        plan = self.build(self.environment_config())
        # On vérifie que len(plan.steps) correspond à 8.
        self.assertEqual(len(plan.steps), 8)
        # On parcourt self.modules_used.values() ; module désigne l’élément courant de ce scénario.
        for module in self.modules_used.values():
            # On parcourt vars(module).values() ; fn désigne l’élément courant de ce scénario.
            for fn in vars(module).values():
                # On vérifie que fn n’a pas été appelé : le refus doit intervenir avant cette
                # opération.
                fn.assert_not_called()
        # On attend que (self.root / 'state').exists() soit évalué comme faux pour ce cas de test.
        self.assertFalse((self.root / "state").exists())
        # On vérifie que self.password ne figure pas dans repr(plan).
        self.assertNotIn(self.password, repr(plan))

    def test_executor_receives_paths_not_database_secret(self):
        # On appelle self.build avec self.environment_config().
        self.build(self.environment_config())
        # On garde self.factory_arguments.kwargs sous le nom options ; cette affectation ne copie pas à
        # elle seule un objet mutable.
        options = self.factory_arguments.kwargs
        # On vérifie que options['nas_brut_root'] correspond à self.brut.
        self.assertEqual(options["nas_brut_root"], self.brut)
        # On vérifie que self.password ne figure pas dans repr(options).
        self.assertNotIn(self.password, repr(options))
        # On vérifie que 'importer' ne figure pas dans options.
        self.assertNotIn("importer", options)

    def test_nas_wrapper_passes_secure_executor_to_original_pilot(self):
        # On garde dans plan la valeur renvoyée par self.build.
        plan = self.build(self.environment_config())
        # On appelle plan.dependencies.execute_nas avec self.root.
        plan.dependencies.execute_nas(
            # On décide si le parcours s’arrête dès la première erreur, au lieu de laisser ce choix
            # implicite.
            self.root, self.root / "fake.csv", ["Synthetic"], 2026, stop_on_error=True
        )
        # On garde self.modules_used['run_local_pipeline'].execute_pipeline sous le nom pilot ; cette
        # affectation ne copie pas à elle seule un objet mutable.
        pilot = self.modules_used["run_local_pipeline"].execute_pipeline
        # On vérifie l’identité de pilot.call_args.kwargs['executor'] avec self.executor, et pas
        # seulement une égalité de valeur.
        self.assertIs(pilot.call_args.kwargs["executor"], self.executor)
        # On vérifie l’identité de pilot.call_args.kwargs['stop_on_error'] avec True, et pas
        # seulement une égalité de valeur.
        self.assertIs(pilot.call_args.kwargs["stop_on_error"], True)

    def test_original_import_functions_reused(self):
        # On garde dans plan la valeur renvoyée par self.build.
        plan = self.build(self.environment_config())
        # On vérifie l’identité de plan.dependencies.import_excel avec
        # self.modules_used['import_excel_publication'].import_bundle, et pas seulement une égalité
        # de valeur.
        self.assertIs(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            plan.dependencies.import_excel,
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            self.modules_used["import_excel_publication"].import_bundle,
        )
        # On vérifie l’identité de plan.dependencies.import_nas avec
        # self.modules_used['load_nas_reconciliation'].import_bundle, et pas seulement une égalité de
        # valeur.
        self.assertIs(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            plan.dependencies.import_nas,
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            self.modules_used["load_nas_reconciliation"].import_bundle,
        )

    def test_selection_failure_does_not_open_connection(self):
        # On garde dans cfg la configuration d’environnement isolée pour le scénario.
        cfg = self.environment_config()
        # On remplace temporairement wiring dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with (
            patch.object(
                # On définit le comportement simulé de l’appel, qui peut notamment lever une erreur ou
                # suivre une fonction de test.
                wiring, "_project_module", side_effect=lambda r, n, p: self.modules()[n]
            ),
            patch.object(wiring, "build_nas_executor", return_value=Mock()),
            patch.object(wiring, "connect_importer") as connect,
        ):
            # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaises(ValueError):
                # On appelle wiring.build_business_plan avec cfg.
                wiring.build_business_plan(cfg)
        # On vérifie que connect n’a pas été appelé dans ce scénario.
        connect.assert_not_called()

    def test_cli_has_no_run_option(self):
        # On remplace temporairement cli dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with (
            patch.object(cli, "load_business_configuration") as load,
            contextlib.redirect_stderr(io.StringIO()),
        ):
            # On attend SystemExit dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaises(SystemExit):
                # On appelle cli.main avec ['--run', '--all-vineyards'].
                cli.main(["--run", "--all-vineyards"])
        # On vérifie que load n’a pas été appelé dans ce scénario.
        load.assert_not_called()

    def test_cli_requires_check_only(self):
        # On remplace temporairement cli dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with (
            patch.object(cli, "load_business_configuration") as load,
            contextlib.redirect_stderr(io.StringIO()),
        ):
            # On attend SystemExit dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaises(SystemExit):
                # On appelle cli.main avec ['--all-vineyards'].
                cli.main(["--all-vineyards"])
        # On vérifie que load n’a pas été appelé dans ce scénario.
        load.assert_not_called()

    def test_cli_requires_selection(self):
        # On utilise contextlib.redirect_stderr(io.StringIO()) dans son contexte de gestion ; les
        # opérations de sortie sont exécutées en quittant le bloc.
        with contextlib.redirect_stderr(io.StringIO()):
            # On attend SystemExit dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaises(SystemExit):
                # On appelle cli.main avec ['--check-only'].
                cli.main(["--check-only"])

    def test_cli_success_does_not_execute_steps_or_print_configuration(self):
        # On garde dans cfg la configuration d’environnement isolée pour le scénario.
        cfg = self.environment_config()
        # On garde dans action un double de test dont les réponses et les appels pourront être
        # contrôlés.
        action = Mock()
        # On garde dans plan un objet de test regroupant les attributs fournis.
        plan = SimpleNamespace(steps=[("stage", action)], journal_sink=Mock())
        # On garde dans stream un flux texte en mémoire, utilisable comme un fichier par le lecteur
        # CSV.
        stream = io.StringIO()
        # On remplace temporairement cli dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with (
            patch.object(cli, "load_business_configuration", return_value=cfg),
            patch.object(cli, "build_business_plan", return_value=plan),
            contextlib.redirect_stdout(stream),
        ):
            # On garde dans code la valeur renvoyée par cli.main.
            code = cli.main(["--check-only", "--all-vineyards"])
        # On vérifie que code correspond à 0.
        self.assertEqual(code, 0)
        # On vérifie que action n’a pas été appelé dans ce scénario.
        action.assert_not_called()
        # On vérifie que plan.journal_sink n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        plan.journal_sink.assert_not_called()
        # On vérifie que self.password ne figure pas dans stream.getvalue().
        self.assertNotIn(self.password, stream.getvalue())
        # On vérifie que self.brut ne figure pas dans stream.getvalue().
        self.assertNotIn(self.brut, stream.getvalue())

    def test_cli_unknown_exception_is_not_printed_raw(self):
        # On garde dans stream un flux texte en mémoire, utilisable comme un fichier par le lecteur
        # CSV.
        stream = io.StringIO()
        # On remplace temporairement cli dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with (
            patch.object(
                cli,
                "load_business_configuration",
                # On définit le comportement simulé de l’appel, qui peut notamment lever une erreur ou
                # suivre une fonction de test.
                side_effect=RuntimeError(self.password),
            ),
            contextlib.redirect_stdout(stream),
        ):
            # On garde dans code la valeur renvoyée par cli.main.
            code = cli.main(["--check-only", "--all-vineyards"])
        # On vérifie que code correspond à 1.
        self.assertEqual(code, 1)
        # On vérifie que self.password ne figure pas dans stream.getvalue().
        self.assertNotIn(self.password, stream.getvalue())

    def test_cli_safe_configuration_code_displayed(self):
        # On garde dans stream un flux texte en mémoire, utilisable comme un fichier par le lecteur
        # CSV.
        stream = io.StringIO()
        # On remplace temporairement cli dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with (
            patch.object(
                cli,
                "load_business_configuration",
                # On définit le comportement simulé de l’appel, qui peut notamment lever une erreur ou
                # suivre une fonction de test.
                side_effect=config.BusinessConfigurationError(
                    "IMPORT_CONFIGURATION_INVALID"
                ),
            ),
            contextlib.redirect_stdout(stream),
        ):
            # On garde dans code la valeur renvoyée par cli.main.
            code = cli.main(["--check-only", "--all-vineyards"])
        # On vérifie que code correspond à 1.
        self.assertEqual(code, 1)
        # On vérifie que 'IMPORT_CONFIGURATION_INVALID' figure dans stream.getvalue().
        self.assertIn("IMPORT_CONFIGURATION_INVALID", stream.getvalue())
