# Suivi post-saison des traitements et des livrables

## Contexte

Dans l’entreprise où j’ai réalisé mon alternance, des images de vignobles sont acquises puis traitées pour produire différents livrables. Le suivi des acquisitions est renseigné dans des fichiers Excel, tandis que les images et les résultats sont stockés sur un NAS.

Pour savoir où en étaient les traitements, il fallait croiser ces informations : ce qui était déclaré dans Excel, les fichiers réellement présents et les associations entre acquisitions, parcelles et passages. J’ai développé ce pipeline pour automatiser ce rapprochement et consulter les résultats dans un tableau de bord.

Ce travail correspond à **l’option A — mission en entreprise du projet 12** du parcours Data Engineer OpenClassrooms.

## Fonctionnement

```text
Excel de suivi ──► Lecture, normalisation et versionnement
                                    │
NAS en lecture seule ──► Contrôle des fichiers et rapprochement
                                    │
                               PostgreSQL
                         Historique et vues métier
                                    │
                              Dashboard Dash
```

**Airflow** planifie le traitement quotidien. Le pipeline vérifie les données Excel, observe les fichiers sur le périmètre prévu, puis charge les résultats dans PostgreSQL. Un journal permet de suivre les étapes et de retrouver les erreurs.

Deux bases PostgreSQL ont des rôles distincts : **la base technique d’Airflow** conserve les runs et les états des tâches ; **la base métier** conserve les résultats, leur historique et le journal du workflow. Cette dernière est organisée en trois schémas : `staging` pour les lignes reçues du pipeline, `core` pour les versions et leurs liens, `mart` pour les vues de consultation.

Pendant une exécution, les étapes s’appuient sur la même version des données Excel. Les contrôles évitent de mélanger deux versions si un fichier change entre-temps.

## Ce que montre le dashboard

- L’avancement des traitements et la présence des livrables.
- Les écarts entre les statuts Excel et les fichiers observés sur le NAS.
- Les points à vérifier et les résultats des contrôles précédents.
- L’évolution entre deux états enregistrés.

L’absence d’un fichier ne signifie pas forcément qu’un livrable est en retard : il peut ne pas avoir été commandé pour le vignoble, la parcelle ou la période concernée. De même, une erreur de lecture ne permet pas de conclure qu’il manque. Le rapprochement avec le suivi Excel aide à interpréter ces situations.

## Organisation du code

| Dossier | Rôle |
|---|---|
| `src/` | Lecture des sources, normalisation et rapprochement |
| `scripts/` | Assemblage des étapes, contrôles et chargements |
| `dags/` | Orchestration Airflow |
| `sql/` | Historisation, vues métier et droits PostgreSQL |
| `app/` | Accès aux résultats et interface Dash |
| `tests/`, `tests_browser/` | Tests du pipeline, des règles métier et de l’interface |

**Stack :** Python, pandas, openpyxl, PostgreSQL, Airflow, Docker, Dash et Plotly.

## Essayer le dashboard

Démonstration sur données fictives, sans NAS ni PostgreSQL : **5 vignobles, 50 acquisitions au dernier scan et 4 états historiques**. Les scans recensent successivement 25, 40, 45 puis 50 acquisitions. On peut observer des traitements qui progressent, des statuts Excel modifiés, des rattachements complétés et une erreur de lecture résolue. Quelques traitements restent incomplets et un contrôle reste impossible.

Les exemples sont fixes : recharger la page ne tire pas de nouvelles valeurs au hasard. Les petits cas de tests des règles métier sont conservés séparément dans `tests/mock_fixture.py`. Depuis la racine du projet, avec Python 3.12 ou 3.13 et PowerShell :

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:DASHBOARD_USE_MOCK = "1"
.\.venv\Scripts\python.exe app/dash_app.py
```

Ouvrir `http://127.0.0.1:8050`. Le badge **DÉMONSTRATION** confirme l’utilisation des données fictives.

Pour les tests locaux :

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest tests
```

## Vérifications et périmètre

**851 tests locaux réussis**, ainsi que les deux scénarios navigateur, sur l’environnement Linux utilisé pour vérifier cette version. Cela ne remplace pas une validation du pipeline complet sur son infrastructure cible.

Ce dépôt présente le code du pipeline réalisé en entreprise, avec des exemples anonymisés. Le dashboard peut être essayé séparément sur des données fictives. L’exécution du pipeline complet nécessite des sources Excel et un stockage NAS compatibles, ainsi que la configuration de PostgreSQL et d’Airflow.

Les noms de domaines et les exemples identifiants ont été anonymisés. Les données professionnelles, secrets et journaux d’exploitation ne sont pas inclus.
