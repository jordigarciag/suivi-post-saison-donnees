# Lecture du fichier — Tests de nas environment mode.
#

"""Configuration et adaptation uniquement : aucun acces aux racines NAS."""

# On importe importlib.util. Ce module sera utilisé par les opérations de ce fichier.
import importlib.util
# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
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
# On importe prepare_nas_environment_mode sous le nom installer. Ce module sera utilisé par les
# opérations de ce fichier.
import prepare_nas_environment_mode as installer

# On garde dans spec la valeur renvoyée par importlib.util.spec_from_file_location pour
# 'nas_environment_helper_test'.
spec = importlib.util.spec_from_file_location(
    "nas_environment_helper_test", ROOT / installer.HELPER
)
# On garde dans helper la valeur renvoyée par importlib.util.module_from_spec.
helper = importlib.util.module_from_spec(spec)
# On appelle spec.loader.exec_module avec helper.
spec.loader.exec_module(helper)


class TestNasEnvironmentMode(unittest.TestCase):
    def setUp(self):
        # On garde dans temp un dossier temporaire distinct des données du projet.
        temp = tempfile.TemporaryDirectory()
        # On enregistre cette opération de nettoyage pour qu’elle soit appelée après le test, même si
        # celui-ci échoue.
        self.addCleanup(temp.cleanup)
        # On garde dans self.root un objet chemin local ; sa construction seule ne prouve pas que le
        # fichier existe.
        self.root = Path(temp.name)
        # On regroupe dans self.env ces champs nommés ; on pourra les retrouver par leur clé plutôt que
        # par leur position.
        self.env = {
            helper.MODE_VARIABLE: "environment",
            # On associe la clé 'NAS_BRUT_ROOT' à cette valeur dans les données de ce scénario.
            "NAS_BRUT_ROOT": str(self.root / "fake_brut"),
            # On associe la clé 'NAS_PROCESSING_ROOT' à cette valeur dans les données de ce scénario.
            "NAS_PROCESSING_ROOT": str(self.root / "fake_processing"),
        }
        # On assemble ces deux éléments pour construire self.source.
        self.source = (
            "from dotenv import load_dotenv\nPROJECT_ROOT = None\ndef main():\n"
            + installer.OLD
            + "\n"
        )

    def test_explicit_mode_does_not_load_dotenv_or_probe_nas(self):
        # On remplace temporairement os.environ dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with (
            patch.dict(os.environ, self.env, clear=True),
            patch("dotenv.load_dotenv") as load,
            patch.object(Path, "is_dir", side_effect=AssertionError("NAS probe")),
        ):
            # On appelle helper.configure_nas_environment avec self.root.
            helper.configure_nas_environment(self.root)
        # On vérifie que load n’a pas été appelé dans ce scénario.
        load.assert_not_called()

    def test_missing_parameter_never_falls_back_to_env_file(self):
        # On parcourt ('NAS_BRUT_ROOT', 'NAS_PROCESSING_ROOT') ; key désigne l’élément courant de ce
        # scénario.
        for key in ("NAS_BRUT_ROOT", "NAS_PROCESSING_ROOT"):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(key=key):
                # On garde dans env un nouveau dictionnaire construit avec les valeurs indiquées (la
                # copie reste superficielle).
                env = dict(self.env)
                # On retire env[key] de son emplacement ; la suite ne doit plus s’appuyer sur cette
                # entrée.
                del env[key]
                # On remplace temporairement os.environ dans ce bloc de test ; le réglage initial sera
                # rétabli à sa sortie.
                with (
                    patch.dict(os.environ, env, clear=True),
                    patch("dotenv.load_dotenv") as load,
                ):
                    # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit
                    # échouer.
                    with self.assertRaises(ValueError):
                        # On appelle helper.configure_nas_environment avec self.root.
                        helper.configure_nas_environment(self.root)
                # On vérifie que load n’a pas été appelé : le refus doit intervenir avant cette
                # opération.
                load.assert_not_called()

    def test_invalid_or_relative_paths_rejected(self):
        # On parcourt ('', 'relative/path', 'bad\npath', 'bad\x00path') ; value désigne l’élément
        # courant de ce scénario.
        for value in ("", "relative/path", "bad\npath", "bad\x00path"):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(value=value):
                # On remplace temporairement helper.os dans ce bloc de test ; le réglage initial sera
                # rétabli à sa sortie.
                with patch.object(
                    helper.os, "environ", dict(self.env, NAS_BRUT_ROOT=value)
                ):
                    # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit
                    # échouer.
                    with self.assertRaises(ValueError):
                        # On appelle helper.configure_nas_environment avec self.root.
                        helper.configure_nas_environment(self.root)

    def test_unknown_mode_rejected(self):
        # On remplace temporairement os.environ dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with (
            patch.dict(os.environ, {helper.MODE_VARIABLE: "automatic"}, clear=True),
            patch("dotenv.load_dotenv") as load,
        ):
            # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaises(ValueError):
                # On appelle helper.configure_nas_environment avec self.root.
                helper.configure_nas_environment(self.root)
        # On vérifie que load n’a pas été appelé dans ce scénario.
        load.assert_not_called()

    def test_default_local_preserves_original_call(self):
        # On remplace temporairement os.environ dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("dotenv.load_dotenv") as load,
        ):
            # On appelle helper.configure_nas_environment avec self.root.
            helper.configure_nas_environment(self.root)
        # On vérifie que ce double a reçu un seul appel avec exactement les arguments indiqués ; une
        # valeur correcte obtenue par le mauvais appel ne suffirait pas.
        load.assert_called_once_with(self.root / ".env")

    def test_explicit_local_preserves_original_call(self):
        # On remplace temporairement os.environ dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with (
            patch.dict(os.environ, {helper.MODE_VARIABLE: "local"}, clear=True),
            patch("dotenv.load_dotenv") as load,
        ):
            # On appelle helper.configure_nas_environment avec self.root.
            helper.configure_nas_environment(self.root)
        # On vérifie que ce double a reçu un seul appel avec exactement les arguments indiqués ; une
        # valeur correcte obtenue par le mauvais appel ne suffirait pas.
        load.assert_called_once_with(self.root / ".env")

    def test_original_local_loader_hook_preserved(self):
        # On garde dans load un double de test dont les réponses et les appels pourront être contrôlés.
        load = Mock()
        # On remplace temporairement os.environ dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.dict(os.environ, {}, clear=True):
            # On appelle helper.configure_nas_environment avec self.root.
            helper.configure_nas_environment(self.root, local_loader=load)
        # On vérifie que ce double a reçu un seul appel avec exactement les arguments indiqués ; une
        # valeur correcte obtenue par le mauvais appel ne suffirait pas.
        load.assert_called_once_with(self.root / ".env")

    def test_environment_never_calls_provided_local_loader(self):
        # On garde dans load un double de test dont les réponses et les appels pourront être contrôlés.
        load = Mock()
        # On remplace temporairement os.environ dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.dict(os.environ, self.env, clear=True):
            # On appelle helper.configure_nas_environment avec self.root.
            helper.configure_nas_environment(self.root, local_loader=load)
        # On vérifie que load n’a pas été appelé dans ce scénario.
        load.assert_not_called()

    def test_transform_only_call_and_import(self):
        # On répartit les valeurs renvoyées par installer.transform entre (output, changed) ; leur
        # ordre doit correspondre à celui prévu par cet appel.
        output, changed = installer.transform(self.source)
        # On attend que changed soit évalué comme vrai pour ce cas de test.
        self.assertTrue(changed)
        # On vérifie que installer.NEW figure dans output.
        self.assertIn(installer.NEW, output)
        # On vérifie que installer.OLD ne figure pas dans output.
        self.assertNotIn(installer.OLD, output)
        # On vérifie que output.replace(installer.ANCHOR + installer.IMPORT, installer.ANCHOR).repla…
        # correspond à self.source.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            output.replace(
                installer.ANCHOR + installer.IMPORT, installer.ANCHOR
            ).replace(installer.NEW, installer.OLD),
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            self.source,
        )

    def test_transform_idempotent(self):
        # On répartit les valeurs renvoyées par installer.transform entre (output, _) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        output, _ = installer.transform(self.source)
        # On répartit les valeurs renvoyées par installer.transform entre (again, changed) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        again, changed = installer.transform(output)
        # On attend que changed soit évalué comme faux pour ce cas de test.
        self.assertFalse(changed)
        # On vérifie que again correspond à output.
        self.assertEqual(again, output)

    def test_unknown_source_refused(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle installer.transform avec 'print("different")'.
            installer.transform('print("different")')

    def test_duplicate_call_refused(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle installer.transform avec self.source + installer.OLD + '\n'.
            installer.transform(self.source + installer.OLD + "\n")

    def test_partial_patch_refused(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle installer.transform avec self.source.replace(installer.OLD, installer.NEW).
            installer.transform(self.source.replace(installer.OLD, installer.NEW))

    def test_backup_and_line_endings_preserved(self):
        # On calcule ce quotient pour construire path.
        path = self.root / installer.RELATIVE
        # On prépare le dossier path.parent avec les règles de création indiquées ; aucun résultat
        # métier n’est encore produit par cette création.
        path.parent.mkdir(parents=True)
        # On écrit le contenu préparé dans self.root / installer.HELPER ; cette opération remplace le
        # contenu du fichier s’il existe déjà.
        (self.root / installer.HELPER).write_text("# test helper", encoding="utf-8")
        # On assemble ces deux éléments pour construire original.
        original = b"\xef\xbb\xbf" + self.source.replace("\n", "\r\n").encode("utf-8")
        # On écrit le contenu préparé dans path ; cette opération remplace le contenu du fichier s’il
        # existe déjà.
        path.write_bytes(original)
        # On garde dans relative le résultat de la fonction appliquée aux éléments ou à l’axe indiqué
        # de installer.
        relative = installer.apply(self.root)
        # On vérifie que (self.root / relative / 'nas_live_evidence_extractor.before.py').read_bytes…
        # correspond à original.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            (
                self.root / relative / "nas_live_evidence_extractor.before.py"
            ).read_bytes(),
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            original,
        )
        # On attend que path.read_bytes().startswith(b'\xef\xbb\xbf') soit évalué comme vrai pour ce
        # cas de test.
        self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
        # On vérifie que b'\n' ne figure pas dans path.read_bytes().replace(b'\r\n', b'').
        self.assertNotIn(b"\n", path.read_bytes().replace(b"\r\n", b""))
        # On garde dans after les octets lus depuis path, avant toute conversion en texte. Les
        # contrôles de contenu pourront ainsi repartir de cette lecture.
        after = path.read_bytes()
        # On attend None pour installer.apply(self.root) : aucune valeur n’est confirmée dans ce cas.
        self.assertIsNone(installer.apply(self.root))
        # On vérifie que path.read_bytes() correspond à after.
        self.assertEqual(path.read_bytes(), after)

    def test_missing_helper_blocks_patch(self):
        # On calcule ce quotient pour construire path.
        path = self.root / installer.RELATIVE
        # On prépare le dossier path.parent avec les règles de création indiquées ; aucun résultat
        # métier n’est encore produit par cette création.
        path.parent.mkdir(parents=True)
        # On écrit le contenu préparé dans path ; cette opération remplace le contenu du fichier s’il
        # existe déjà.
        path.write_text(self.source, encoding="utf-8")
        # On garde dans before les octets lus depuis path, avant toute conversion en texte. Les
        # contrôles de contenu pourront ainsi repartir de cette lecture.
        before = path.read_bytes()
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle installer.apply avec self.root.
            installer.apply(self.root)
        # On vérifie que path.read_bytes() correspond à before.
        self.assertEqual(path.read_bytes(), before)
