# Lecture du fichier — Tests de manifest paths posix.
#

"""Contrat des chemins : fichiers synthetiques locaux, aucun NAS ni SQL."""

# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On importe tempfile. On prépare des fichiers ou dossiers temporaires pour les cas isolés.
import tempfile
# On importe unittest. On décrit les scénarios et les vérifications de la suite de tests.
import unittest

# On ajoute ce dossier aux chemins de recherche Python pour rendre les modules locaux importables dans
# ce contexte.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
# On rend disponibles ManifestPaths depuis import_nas_reconciliation, pour les appels de ce fichier.
from import_nas_reconciliation import ManifestPaths
# On rend disponibles LocalFiles, ValidationError depuis load_excel_publication, pour les appels de ce
# fichier.
from load_excel_publication import LocalFiles, ValidationError


class ManifestPathsTests(unittest.TestCase):
    def setUp(self):
        # On garde dans self.tmp un dossier temporaire distinct des données du projet.
        self.tmp = tempfile.TemporaryDirectory()
        # On enregistre cette opération de nettoyage pour qu’elle soit appelée après le test, même si
        # celui-ci échoue.
        self.addCleanup(self.tmp.cleanup)
        # On assemble les morceaux du chemin self.root avec l’opérateur / de pathlib ; aucun fichier
        # n’est créé par cette construction.
        self.root = Path(self.tmp.name) / "project"
        # On prépare le dossier self.root / 'data' avec les règles de création indiquées ; aucun
        # résultat métier n’est encore produit par cette création.
        (self.root / "data").mkdir(parents=True)
        # On utilise ce texte pour self.reference ; il ne dépend pas d’une valeur récupérée ailleurs à
        # cet endroit.
        self.reference = "data/03_normalized/publications/example/reference.csv"
        # On garde dans self.paths la valeur renvoyée par ManifestPaths.
        self.paths = ManifestPaths(self.root, self.reference)

    def test_relative_posix(self):
        # On vérifie que self.paths.relative(self.reference) correspond à self.reference.
        self.assertEqual(self.paths.relative(self.reference), self.reference)

    def test_relative_windows_separators(self):
        # On vérifie que self.paths.relative(self.reference.replace('/', '\\')) correspond à
        # self.reference.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            self.paths.relative(self.reference.replace("/", "\\")), self.reference
        )

    @unittest.skipIf(os.name == "nt", "Cas POSIX natif")
    def test_absolute_current_project(self):
        # On vérifie que self.paths.relative((self.root / self.reference).as_posix()) correspond à
        # self.reference.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            self.paths.relative((self.root / self.reference).as_posix()), self.reference
        )

    @unittest.skipIf(os.name == "nt", "Cas POSIX natif")
    def test_posix_reference_constructor(self):
        # On garde dans source l’écriture de self.root / self.reference avec des / comme séparateurs.
        source = (self.root / self.reference).as_posix()
        # On vérifie que ManifestPaths(self.root, source).relative(source) correspond à self.reference.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            ManifestPaths(self.root, source).relative(source), self.reference
        )

    @unittest.skipIf(
        os.name == "nt", "Compatibilite historique des fixtures Windows sous Linux"
    )
    def test_windows_absolute_legacy(self):
        # On garde dans p la valeur renvoyée par ManifestPaths.
        p = ManifestPaths(self.root, r"C:\origin\project\data\pub\reference.csv")
        # On vérifie que p.relative('C:\\origin\\project\\data\\pub\\reference.csv') correspond à
        # 'data/pub/reference.csv'.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            p.relative(r"C:\origin\project\data\pub\reference.csv"),
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            "data/pub/reference.csv",
        )
        # On vérifie que p.relative('C:\\origin\\project\\data\\run\\snapshot.csv') correspond à
        # 'data/run/snapshot.csv'.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            p.relative(r"C:\origin\project\data\run\snapshot.csv"),
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            "data/run/snapshot.csv",
        )

    def test_relative_traversals(self):
        # On parcourt ('../data/file', 'data/../file', 'data/a/../../file', 'data\\..\\file') ; value
        # désigne l’élément courant de ce scénario.
        for value in (
            "../data/file",
            "data/../file",
            "data/a/../../file",
            r"data\..\file",
        ):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(value=value), self.assertRaises(ValidationError):
                # On appelle self.paths.relative avec value.
                self.paths.relative(value)

    def test_other_relative_destinations(self):
        # On parcourt ('state/file', 'logs/file', 'scripts/file', 'database/file') ; value désigne
        # l’élément courant de ce scénario.
        for value in ("state/file", "logs/file", "scripts/file", "database/file"):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(value=value), self.assertRaises(ValidationError):
                # On appelle self.paths.relative avec value.
                self.paths.relative(value)

    def test_windows_drive_relative_or_rooted(self):
        # On parcourt ('C:data\\file', '\\data\\file', 'C:\\other\\data\\file') ; value désigne
        # l’élément courant de ce scénario.
        for value in (r"C:data\file", r"\data\file", r"C:\other\data\file"):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(value=value), self.assertRaises(ValidationError):
                # On appelle self.paths.relative avec value.
                self.paths.relative(value)

    @unittest.skipIf(os.name == "nt", "Cas POSIX natif")
    def test_outside_absolute(self):
        # On parcourt ('/etc/passwd', '/opt/nas/processing/file', '/data/file', str(self.root)… ; value
        # désigne l’élément courant de ce scénario.
        for value in (
            "/etc/passwd",
            "/opt/nas/processing/file",
            "/data/file",
            str(self.root) + "_other/data/file",
        ):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(value=value), self.assertRaises(ValidationError):
                # On appelle self.paths.relative avec value.
                self.paths.relative(value)

    @unittest.skipIf(os.name == "nt", "Cas POSIX natif")
    def test_absolute_state_or_logs(self):
        # On parcourt ('state', 'logs', 'scripts') ; folder désigne l’élément courant de ce scénario.
        for folder in ("state", "logs", "scripts"):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(folder=folder), self.assertRaises(ValidationError):
                # On appelle self.paths.relative avec (self.root / folder / 'file').as_posix().
                self.paths.relative((self.root / folder / "file").as_posix())

    @unittest.skipIf(os.name == "nt", "Cas POSIX natif")
    def test_absolute_parent_segments(self):
        # On parcourt ('data/../data/file', 'data/a/../../file') ; suffix désigne l’élément courant de
        # ce scénario.
        for suffix in ("data/../data/file", "data/a/../../file"):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(suffix=suffix), self.assertRaises(ValidationError):
                # On appelle self.paths.relative avec self.root.as_posix() + '/' + suffix.
                self.paths.relative(self.root.as_posix() + "/" + suffix)

    @unittest.skipIf(os.name == "nt", "Cas POSIX natif")
    def test_mixed_posix_separators(self):
        # On attend ValidationError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValidationError):
            # On appelle self.paths.relative avec self.root.as_posix() + '/data/a\\file'.
            self.paths.relative(self.root.as_posix() + r"/data/a\file")

    @unittest.skipIf(os.name == "nt", "Cas POSIX natif")
    def test_symlink_file_outside(self):
        # On assemble les morceaux du chemin outside avec l’opérateur / de pathlib ; aucun fichier
        # n’est créé par cette construction.
        outside = Path(self.tmp.name) / "outside"
        # On écrit le contenu préparé dans outside ; cette opération remplace le contenu du fichier
        # s’il existe déjà.
        outside.write_text("untouched")
        # On appelle (self.root / 'data' / 'link').symlink_to avec outside.
        (self.root / "data" / "link").symlink_to(outside)
        # On attend ValidationError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValidationError):
            # On appelle self.paths.relative avec (self.root / 'data' / 'link').as_posix().
            self.paths.relative((self.root / "data" / "link").as_posix())
        # On vérifie que outside.read_text() correspond à 'untouched'.
        self.assertEqual(outside.read_text(), "untouched")

    @unittest.skipIf(os.name == "nt", "Cas POSIX natif")
    def test_data_anchor_outside(self):
        # On appelle (self.root / 'data').rmdir sans argument positionnel.
        (self.root / "data").rmdir()
        # On assemble les morceaux du chemin outside avec l’opérateur / de pathlib ; aucun fichier
        # n’est créé par cette construction.
        outside = Path(self.tmp.name) / "outside-dir"
        # On prépare le dossier outside avec les règles de création indiquées ; aucun résultat métier
        # n’est encore produit par cette création.
        outside.mkdir()
        # On appelle (self.root / 'data').symlink_to avec outside.
        (self.root / "data").symlink_to(outside, target_is_directory=True)
        # On attend ValidationError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValidationError):
            # On appelle self.paths.relative avec (self.root / 'data' / 'file').as_posix().
            self.paths.relative((self.root / "data" / "file").as_posix())

    def test_localfiles_preserves_absolute_refusal(self):
        # On attend ValidationError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValidationError):
            # On appelle LocalFiles(self.root).path avec (self.root / self.reference).as_posix().
            LocalFiles(self.root).path((self.root / self.reference).as_posix())

    def test_relative_empty(self):
        # On parcourt ('', None, 42) ; value désigne l’élément courant de ce scénario.
        for value in ("", None, 42):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(value=value), self.assertRaises(ValidationError):
                # On appelle self.paths.relative avec value.
                self.paths.relative(value)


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On confie la découverte et l’exécution des tests de ce fichier au lanceur unittest.
    unittest.main()
