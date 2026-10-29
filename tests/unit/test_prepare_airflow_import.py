# Lecture du fichier — Tests de prepare airflow import.
#

"""Tests sur fichiers temporaires et identifiants fictifs ; aucun acces reseau."""

# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On importe tempfile. On prépare des fichiers ou dossiers temporaires pour les cas isolés.
import tempfile
# On importe unittest. On décrit les scénarios et les vérifications de la suite de tests.
import unittest
# On rend disponibles patch depuis unittest.mock, pour les appels de ce fichier.
from unittest.mock import patch

# On ajoute ce dossier aux chemins de recherche Python pour rendre les modules locaux importables dans
# ce contexte.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
# On importe prepare_airflow_import sous le nom preparation. Ce module sera utilisé par les opérations
# de ce fichier.
import prepare_airflow_import as preparation


class TestPrepareAirflowImport(unittest.TestCase):
    def setUp(self):
        # On garde dans temp un dossier temporaire distinct des données du projet.
        temp = tempfile.TemporaryDirectory()
        # On enregistre cette opération de nettoyage pour qu’elle soit appelée après le test, même si
        # celui-ci échoue.
        self.addCleanup(temp.cleanup)
        # On garde dans self.root un objet chemin local ; sa construction seule ne prouve pas que le
        # fichier existe.
        self.root = Path(temp.name)
        # On assemble les morceaux du chemin self.source avec l’opérateur / de pathlib ; aucun fichier
        # n’est créé par cette construction.
        self.source = self.root / ".env"
        # On écrit le contenu préparé dans self.source ; cette opération remplace le contenu du fichier
        # s’il existe déjà.
        self.source.write_text(
            "PROJECT12_IMPORT_USER=projet12_importer\n"
            'PROJECT12_IMPORT_PASSWORD="synthetic-${NOT_INTERPOLATED}-#quoted"\n'
            "PROJECT12_POSTGRES_PASSWORD=synthetic-admin-only\n"
            "PROJECT12_DASHBOARD_PASSWORD=synthetic-reader-only\n",
            # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas être
            # décodé selon un réglage implicite du poste.
            encoding="utf-8",
        )
        # On garde dans self.original les octets lus depuis self.source, avant toute conversion en
        # texte. Les contrôles de contenu pourront ainsi repartir de cette lecture.
        self.original = self.source.read_bytes()

    def test_only_importer_credentials_are_copied(self):
        # On garde dans destination la valeur renvoyée par preparation.prepare.
        destination = preparation.prepare(self.root)
        # On garde dans raw le texte lu depuis destination avec l’encodage indiqué.
        raw = destination.read_text(encoding="utf-8")
        # On vérifie que 'PROJECT12_IMPORT_PASSWORD=synthetic-${NOT_INTERPOLATED}-#quoted\n' figure
        # dans raw.
        self.assertIn(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            "PROJECT12_IMPORT_PASSWORD=synthetic-${NOT_INTERPOLATED}-#quoted\n", raw
        )
        # On vérifie que 'PROJECT12_IMPORT_HOST=projet12-suivi-postgres-1\n' figure dans raw.
        self.assertIn("PROJECT12_IMPORT_HOST=projet12-suivi-postgres-1\n", raw)
        # On vérifie que 'PROJECT12_IMPORT_PORT=5432\n' figure dans raw.
        self.assertIn("PROJECT12_IMPORT_PORT=5432\n", raw)
        # On vérifie que 'PROJECT12_IMPORT_CONNECTION_MODE=environment\n' figure dans raw.
        self.assertIn("PROJECT12_IMPORT_CONNECTION_MODE=environment\n", raw)
        # On vérifie que 'PROJECT12_POSTGRES_PASSWORD' ne figure pas dans raw.
        self.assertNotIn("PROJECT12_POSTGRES_PASSWORD", raw)
        # On vérifie que 'synthetic-admin-only' ne figure pas dans raw.
        self.assertNotIn("synthetic-admin-only", raw)
        # On vérifie que 'PROJECT12_DASHBOARD_PASSWORD' ne figure pas dans raw.
        self.assertNotIn("PROJECT12_DASHBOARD_PASSWORD", raw)
        # On vérifie que self.source.read_bytes() correspond à self.original.
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_ignore_rule_added_without_losing_existing_content(self):
        # On assemble les morceaux du chemin ignore avec l’opérateur / de pathlib ; aucun fichier n’est
        # créé par cette construction.
        ignore = self.root / ".gitignore"
        # On écrit le contenu préparé dans ignore ; cette opération remplace le contenu du fichier s’il
        # existe déjà.
        ignore.write_text("/data/", encoding="utf-8")
        # On appelle preparation.prepare avec self.root.
        preparation.prepare(self.root)
        # On garde dans text le texte lu depuis ignore avec l’encodage indiqué.
        text = ignore.read_text(encoding="utf-8")
        # On attend que text.startswith('/data/\n') soit évalué comme vrai pour ce cas de test.
        self.assertTrue(text.startswith("/data/\n"))
        # On vérifie que text.splitlines().count(preparation.RULE) correspond à 1.
        self.assertEqual(text.splitlines().count(preparation.RULE), 1)

    def test_existing_ignore_rule_not_duplicated(self):
        # On assemble les morceaux du chemin ignore avec l’opérateur / de pathlib ; aucun fichier n’est
        # créé par cette construction.
        ignore = self.root / ".gitignore"
        # On écrit le contenu préparé dans ignore ; cette opération remplace le contenu du fichier s’il
        # existe déjà.
        ignore.write_text(preparation.RULE + "\n", encoding="utf-8")
        # On appelle preparation.prepare avec self.root.
        preparation.prepare(self.root)
        # On vérifie que ignore.read_text(encoding='utf-8') correspond à preparation.RULE + '\n'.
        self.assertEqual(ignore.read_text(encoding="utf-8"), preparation.RULE + "\n")

    def test_existing_secret_is_not_overwritten(self):
        # On calcule ce quotient pour construire destination.
        destination = self.root / preparation.DESTINATION
        # On écrit le contenu préparé dans destination ; cette opération remplace le contenu du fichier
        # s’il existe déjà.
        destination.write_text("previous-synthetic", encoding="utf-8")
        # On attend ValueError avec un message correspondant au motif indiqué dans ce bloc ; si aucune
        # erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(ValueError, "aucun ecrasement"):
            # On appelle preparation.prepare avec self.root.
            preparation.prepare(self.root)
        # On vérifie que destination.read_text() correspond à 'previous-synthetic'.
        self.assertEqual(destination.read_text(), "previous-synthetic")

    def test_missing_env_rejected(self):
        # On supprime ce fichier local selon le chemin préparé ; on ne nettoie pas arbitrairement
        # d’autres fichiers.
        self.source.unlink()
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle preparation.prepare avec self.root.
            preparation.prepare(self.root)
        # On attend que (self.root / preparation.DESTINATION).exists() soit évalué comme faux pour ce
        # cas de test.
        self.assertFalse((self.root / preparation.DESTINATION).exists())

    def test_admin_user_rejected(self):
        # On écrit le contenu préparé dans self.source ; cette opération remplace le contenu du fichier
        # s’il existe déjà.
        self.source.write_text(
            "PROJECT12_IMPORT_USER=projet12_admin\nPROJECT12_IMPORT_PASSWORD=synthetic\n"
        )
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle preparation.prepare avec self.root.
            preparation.prepare(self.root)
        # On attend que (self.root / preparation.DESTINATION).exists() soit évalué comme faux pour ce
        # cas de test.
        self.assertFalse((self.root / preparation.DESTINATION).exists())

    def test_missing_password_no_admin_fallback(self):
        # On écrit le contenu préparé dans self.source ; cette opération remplace le contenu du fichier
        # s’il existe déjà.
        self.source.write_text(
            "PROJECT12_IMPORT_USER=projet12_importer\nPROJECT12_POSTGRES_PASSWORD=synthetic-admin\n"
        )
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle preparation.prepare avec self.root.
            preparation.prepare(self.root)
        # On attend que (self.root / preparation.DESTINATION).exists() soit évalué comme faux pour ce
        # cas de test.
        self.assertFalse((self.root / preparation.DESTINATION).exists())

    def test_empty_password_rejected(self):
        # On écrit le contenu préparé dans self.source ; cette opération remplace le contenu du fichier
        # s’il existe déjà.
        self.source.write_text(
            "PROJECT12_IMPORT_USER=projet12_importer\nPROJECT12_IMPORT_PASSWORD=\n"
        )
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle preparation.prepare avec self.root.
            preparation.prepare(self.root)
        # On attend que (self.root / preparation.DESTINATION).exists() soit évalué comme faux pour ce
        # cas de test.
        self.assertFalse((self.root / preparation.DESTINATION).exists())

    def test_password_line_break_and_nul_rejected(self):
        # On parcourt ('synthetic\nline', 'synthetic\rline', 'synthetic\x00line') ; password désigne
        # l’élément courant de ce scénario.
        for password in ("synthetic\nline", "synthetic\rline", "synthetic\x00line"):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with (
                self.subTest(invalid=True),
                patch(
                    "dotenv.dotenv_values",
                    # On fixe la réponse de ce double de test ; aucune vraie opération de la dépendance
                    # n’est nécessaire pour obtenir cette valeur.
                    return_value={
                        # On associe la clé 'PROJECT12_IMPORT_USER' à cette valeur dans les données de
                        # ce scénario.
                        "PROJECT12_IMPORT_USER": "projet12_importer",
                        # On associe la clé 'PROJECT12_IMPORT_PASSWORD' à cette valeur dans les données
                        # de ce scénario.
                        "PROJECT12_IMPORT_PASSWORD": password,
                    },
                ),
            ):
                # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit
                # échouer.
                with self.assertRaises(ValueError):
                    # On appelle preparation.prepare avec self.root.
                    preparation.prepare(self.root)
                # On attend que (self.root / preparation.DESTINATION).exists() soit évalué comme faux
                # pour ce cas de test.
                self.assertFalse((self.root / preparation.DESTINATION).exists())

    def test_utf8_bom_supported(self):
        # On écrit le contenu préparé dans self.source ; cette opération remplace le contenu du fichier
        # s’il existe déjà.
        self.source.write_text(
            "PROJECT12_IMPORT_USER=projet12_importer\nPROJECT12_IMPORT_PASSWORD=synthetic\n",
            # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas être
            # décodé selon un réglage implicite du poste.
            encoding="utf-8-sig",
        )
        # On attend que preparation.prepare(self.root).is_file() soit évalué comme vrai pour ce cas de
        # test.
        self.assertTrue(preparation.prepare(self.root).is_file())


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On confie la découverte et l’exécution des tests de ce fichier au lanceur unittest.
    unittest.main()
