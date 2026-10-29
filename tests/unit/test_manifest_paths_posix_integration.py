# Lecture du fichier — Tests de manifest paths posix integration.
#

"""Controle complet sur un manifeste POSIX synthetique ; aucune source reelle."""

# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On importe unittest. On décrit les scénarios et les vérifications de la suite de tests.
import unittest
# On importe manifest_paths_posix_fixtures sous le nom fixtures. Ce module sera utilisé par les
# opérations de ce fichier.
import manifest_paths_posix_fixtures as fixtures


@unittest.skipIf(os.name == "nt", "Integration POSIX native")
class PosixManifestIntegration(unittest.TestCase):
    def fixture(self):
        # On garde dans case la valeur renvoyée par fixtures.TestNasReconciliationCheck pour
        # 'test_valid_bundle_and_separate_nonverifiable_s….
        case = fixtures.TestNasReconciliationCheck(
            "test_valid_bundle_and_separate_nonverifiable_status"
        )
        # On initialise les ressources du scénario case avec sa méthode setUp.
        case.setUp()
        # On enregistre cette opération de nettoyage pour qu’elle soit appelée après le test, même si
        # celui-ci échoue.
        self.addCleanup(case.doCleanups)

        def absolute(value):
            # On réserve cette branche à value lorsqu’il est de type dict.
            if isinstance(value, dict):
                # On remet {k: absolute(v) for k, v in value.items()} à l’appelant ; les étapes
                # suivantes de cette fonction ne sont plus parcourues.
                return {k: absolute(v) for k, v in value.items()}
            # On réserve cette branche à value lorsqu’il est de type list.
            if isinstance(value, list):
                # On remet [absolute(v) for v in value] à l’appelant ; les étapes suivantes de cette
                # fonction ne sont plus parcourues.
                return [absolute(v) for v in value]
            # Cette branche traite le cas où la valeur reçue est du type str et la valeur reçue
            # commence par le texte 'data/'.
            if isinstance(value, str) and value.startswith("data/"):
                # On fournit à l’appelant l’écriture de case.root / value avec des / comme séparateurs.
                return (case.root / value).as_posix()
            # On remet la valeur reçue à l’appelant ; les étapes suivantes de cette fonction ne sont
            # plus parcourues.
            return value

        # On garde dans case.manifest la valeur renvoyée par absolute.
        case.manifest = absolute(case.manifest)
        # On recalcule le manifeste de test après les modifications du scénario.
        case.sync_manifest()
        # On remet case à l’appelant ; les étapes suivantes de cette fonction ne sont plus parcourues.
        return case

    def test_full_posix_manifest_accepted_without_modification(self):
        # On garde dans case la valeur renvoyée par self.fixture.
        case = self.fixture()
        # On indexe before par p.relative_to(case.root).as_posix() ; chaque clé sera associée à
        # p.read_bytes(). Une même clé ne peut garder qu’une valeur.
        before = {
            p.relative_to(case.root).as_posix(): p.read_bytes()
            for p in case.root.rglob("*")
            if p.is_file()
        }
        # On garde dans report la valeur renvoyée par case.run_check.
        report = case.run_check()
        # On vérifie que report['pipeline_execution_id'] correspond à case.execution.
        self.assertEqual(report["pipeline_execution_id"], case.execution)
        # On indexe after par p.relative_to(case.root).as_posix() ; chaque clé sera associée à
        # p.read_bytes(). Une même clé ne peut garder qu’une valeur.
        after = {
            p.relative_to(case.root).as_posix(): p.read_bytes()
            for p in case.root.rglob("*")
            if p.is_file()
        }
        # On vérifie que before correspond à after.
        self.assertEqual(before, after)

    def test_corrupt_posix_reference_still_refused(self):
        # On garde dans case la valeur renvoyée par self.fixture.
        case = self.fixture()
        # On écrit case.reference_path dans case ; le mode d’ouverture du flux détermine s’il s’agit
        # d’un ajout ou d’un remplacement.
        case.write(case.reference_path, b"changed")
        # On attend fixtures.checker.ValidationError dans ce bloc ; si aucune erreur n’est levée, le
        # test doit échouer.
        with self.assertRaises(fixtures.checker.ValidationError):
            # On appelle case.run_check sans argument positionnel.
            case.run_check()
