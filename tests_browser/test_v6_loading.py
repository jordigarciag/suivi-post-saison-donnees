# Lecture du fichier — Scénario navigateur : v6 loading.
# On utilise le dashboard en mode fictif et on vérifie les interactions visibles. Les téléchargements
# et captures produits par ce scénario ne sont pas des résultats professionnels.
#

"""Simulate network latency to verify explicit loading and stale-page masking."""

# On importe json, time, os, shutil, tempfile. On lit ou écrit les objets et manifestes au format JSON.
import json, time, os, shutil, tempfile
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path

# On garde dans OUT un objet chemin local ; sa construction seule ne prouve pas que le fichier existe.
OUT = Path(tempfile.mkdtemp(prefix="dashboard-v6-loading-"))
# On rend disponibles sync_playwright, expect depuis playwright.sync_api, pour les appels de ce
# fichier.
from playwright.sync_api import sync_playwright, expect

# On utilise sync_playwright() dans son contexte de gestion ; les opérations de sortie sont exécutées
# en quittant le bloc.
with sync_playwright() as p:
    # On garde dans b la valeur renvoyée par p.chromium.launch.
    b = p.chromium.launch(
        **(
            {"executable_path": os.getenv("CHROMIUM_PATH") or shutil.which("chromium")}
            if os.getenv("CHROMIUM_PATH") or shutil.which("chromium")
            else {}
        ),
        headless=True,
        # On fournit les options de la commande via le paramètre args de cet appel.
        args=["--no-sandbox"],
    )
    # On garde dans page la valeur renvoyée par b.new_page.
    page = b.new_page(viewport={"width": 1440, "height": 1050})
    # On crée le dictionnaire vide checks pour y ranger ensuite les éléments par clé.
    checks = {}
    # On ouvre l’adresse prévue par le test dans cette page, avant d’observer son rendu.
    page.goto(os.getenv("BASE_URL", "http://127.0.0.1:8050"))
    # On appelle expect(page.locator('#mode-badge')).to_contain_text avec 'DÉMONSTRATION'.
    expect(page.locator("#mode-badge")).to_contain_text("DÉMONSTRATION")
    # On appelle page.locator('.metric-card').first.wait_for sans argument positionnel.
    page.locator(".metric-card").first.wait_for(timeout=30000)

    def route_handler(route):
        # On garde route.request.post_data_json sous le nom data ; cette affectation ne copie pas à
        # elle seule un objet mutable.
        data = route.request.post_data_json
        # On garde dans output le champ 'output' de data avec le repli indiqué si la clé est absente.
        output = data.get("output", "")
        # Cette branche traite le cas où la sortie préparée correspond au texte
        # 'tab-content.children' et le texte 'tabLoading' ne figure pas dans checks.
        if output == "tab-content.children" and "tabLoading" not in checks:
            # On appelle time.sleep avec 0.45.
            time.sleep(0.45)
            # On garde dans checks['tabLoading'] la valeur renvoyée par page.get_by_text('Chargement de
            # l’onglet…', exact=True).is_visible.
            checks["tabLoading"] = page.get_by_text(
                "Chargement de l’onglet…", exact=True
            ).is_visible()
            # On inverse la valeur de vérité de page.locator('.overview-charts').is_visible() pour
            # obtenir checks['oldOverviewHidden'].
            checks["oldOverviewHidden"] = not page.locator(
                ".overview-charts"
            ).is_visible()
            # On appelle page.screenshot sans argument positionnel.
            page.screenshot(path=str(OUT / "v6_tab_loading.png"))
        # Cette branche traite le cas où le texte 'evolution-summary-results' appartient à la sortie
        # préparée et le texte 'comparisonLoading' ne figure pas dans checks.
        elif (
            "evolution-summary-results" in output and "comparisonLoading" not in checks
        ):
            # On appelle time.sleep avec 0.45.
            time.sleep(0.45)
            # On garde dans checks['comparisonLoading'] la valeur renvoyée par
            # page.get_by_text('Comparaison en cours…', exact=True).is_visible.
            checks["comparisonLoading"] = page.get_by_text(
                "Comparaison en cours…", exact=True
            ).is_visible()
            # On appelle page.screenshot sans argument positionnel.
            page.screenshot(path=str(OUT / "v6_comparison_loading.png"))
        # On appelle route.continue_ sans argument positionnel.
        route.continue_()

    # On appelle page.route avec '**/_dash-update-component'.
    page.route("**/_dash-update-component", route_handler)
    # On clique sur page.get_by_text('Évolution', exact=True).first dans le navigateur de test pour
    # provoquer l’action de l’interface.
    page.get_by_text("Évolution", exact=True).first.click()
    # On appelle page.locator('#evolution-summary-results .evolution-summary').wait_for sans argument
    # positionnel.
    page.locator("#evolution-summary-results .evolution-summary").wait_for(
        # On borne la durée d’attente de cet appel ; dépasser ce délai ne vaut pas confirmation de
        # réussite.
        timeout=30000
    )
    # On appelle expect(page.locator('#tab-content [data-rendered-tab]')).to_have_attribute avec
    # 'data-rendered-tab'.
    expect(page.locator("#tab-content [data-rendered-tab]")).to_have_attribute(
        "data-rendered-tab", "evolution"
    )
    # Tous les indicateurs de chargement relevés pendant ce scénario doivent avoir été observés.
    assert all(checks.values()), checks
    # On affiche json.dumps({'result': 'PASS', 'loadingChecks': checks}) dans la sortie du programme.
    print(json.dumps({"result": "PASS", "loadingChecks": checks}))
    # On ferme b pour libérer la ressource associée après son utilisation.
    b.close()
