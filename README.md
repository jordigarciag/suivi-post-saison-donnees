# Suivi post-saison des traitements et des livrables

![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED.svg)
![Airflow](https://img.shields.io/badge/Apache%20Airflow-enabled-017CEE.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Data-336791.svg)

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

*Note sur l'orchestration :* Le DAG principal du pipeline métier est `project12_eight_vineyards_business.py` (traitant un périmètre de 8 vignobles simulés). Les autres DAGs présents assurent les tests d'intégration (smoke tests, vérification des connexions) et la génération de l'environnement de démonstration.

**Stack :** Python, pandas, openpyxl, PostgreSQL, Airflow, Docker, Dash et Plotly.

## Déploiement de l'infrastructure complète (Docker & Airflow)

L'ensemble de l'architecture est conteneurisé pour garantir sa reproductibilité locale avec des données simulées.

### 1. Démarrer l'environnement
Depuis la racine du projet, lancez la construction et le démarrage des services :
```bash
docker-compose up -d --build
```

### 2. Exécuter le pipeline métier
1. Accédez à l'interface Airflow via `http://localhost:8080` (identifiants par défaut : `airflow` / `airflow`).
2. Activez les DAGs techniques de préparation, puis lancez le DAG métier principal (`project12_eight_vineyards_business`). 
3. Le pipeline va simuler le rapprochement entre les exports Excel et l'arborescence NAS virtuels, puis charger les résultats dans l'entrepôt PostgreSQL.

### 3. Consulter les résultats
Une fois le DAG terminé, le tableau de bord exploitant la base de données finalisée est accessible sur : `http://localhost:8050`.

Pour éteindre proprement l'infrastructure :
```bash
docker-compose down
```

## Essayer le dashboard en mode local (sans Docker)

Il est également possible de lancer uniquement l'interface Dash en local avec un jeu de données mocké en mémoire (**5 vignobles, 50 acquisitions au dernier scan et 4 états historiques**), sans nécessiter PostgreSQL ou Airflow. 

Les exemples sont fixes : recharger la page ne tire pas de nouvelles valeurs au hasard. Les petits cas de tests des règles métier sont conservés séparément dans `tests/mock_fixture.py`. Depuis la racine du projet, avec Python 3.12 ou 3.13 et PowerShell :

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:DASHBOARD_USE_MOCK = "1"
.\.venv\Scripts\python.exe app/dash_app.py
```
Le badge **DÉMONSTRATION** confirmera l’utilisation des données en mémoire sur l'adresse `http://127.0.0.1:8050`.

## Vérifications et périmètre

**851 tests locaux réussis**, ainsi que les deux scénarios navigateur, sur l’environnement Linux utilisé pour vérifier cette version. Cela ne remplace pas une validation du pipeline complet sur son infrastructure cible.
    
Pour lancer la suite de tests locaux :
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest tests
```

Ce dépôt présente le code du pipeline réalisé en entreprise, expurgé et adapté. L’exécution en conditions réelles nécessite des sources Excel et un stockage NAS compatibles. Les noms de domaines et les exemples identifiants ont été strictement anonymisés. Les données professionnelles, secrets (`.env`) et journaux d’exploitation ne sont pas inclus.