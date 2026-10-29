# Lecture du fichier — Scénario navigateur : v6 ui.
# On utilise le dashboard en mode fictif et on vérifie les interactions visibles. Les téléchargements
# et captures produits par ce scénario ne sont pas des résultats professionnels.
#

"""Test UI facultatif : lancer d'abord la V6 en mode DEMONSTRATION.
Dépendance de test uniquement : Playwright + Chromium. Ne pas utiliser sur les données réelles.
BASE_URL et CHROMIUM_PATH sont facultatifs. Captures/CSV dans un dossier temporaire.
"""

# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On importe csv sous le nom csv_lib. On transforme les tableaux entre lignes Python et fichiers CSV.
import csv as csv_lib
# On importe io. On peut fournir des flux en mémoire aux lecteurs et aux captures de sortie.
import io
# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On importe shutil. On réalise les copies et nettoyages de fichiers explicitement prévus.
import shutil
# On importe tempfile. On prépare des fichiers ou dossiers temporaires pour les cas isolés.
import tempfile
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path

# On garde dans OUT un objet chemin local ; sa construction seule ne prouve pas que le fichier existe.
OUT = Path(tempfile.mkdtemp(prefix="dashboard-v6-ui-"))
# On importe re. On reconnaît ou transforme des motifs de texte avec les expressions régulières.
import re
# On rend disponibles sync_playwright, expect depuis playwright.sync_api, pour les appels de ce
# fichier.
from playwright.sync_api import sync_playwright, expect

# On garde dans URL la valeur renvoyée par os.getenv pour 'BASE_URL'.
URL = os.getenv("BASE_URL", "http://127.0.0.1:8050/")


def tid(page, key):
    # On fournit à l’appelant le sélecteur navigateur ciblant '[id=\'{"key":"' + key +
    # '","role":"table"}\']'.
    return page.locator('[id=\'{"key":"' + key + '","role":"table"}\']')


def pid(page, role, key):
    # On fournit à l’appelant le sélecteur navigateur ciblant '[id=\'{"key":"' + key + '","role":"' +
    # role + '"}\']'.
    return page.locator('[id=\'{"key":"' + key + '","role":"' + role + "\"}']")


def choose(page, id_, part):
    # On garde dans loc le sélecteur navigateur ciblant '#' + id_.
    loc = page.locator("#" + id_)
    # On vérifie ce cas avant la suite : id_ correspond au texte 'compare-dates'.
    if id_ == "compare-dates":
        # On appelle loc.locator('label').filter(has_text=part).locator('input').check sans argument
        # positionnel.
        loc.locator("label").filter(has_text=part).locator("input").check()
        # On laisse à l’interface le délai indiqué en millisecondes ; cette pause seule ne prouve pas
        # que le résultat attendu est apparu.
        page.wait_for_timeout(1200)
        # On quitte cette fonction à cet endroit ; les instructions situées après ce retour ne sont pas
        # exécutées.
        return
    # Cette branche traite le cas où la condition loc.locator('.Select-menu-outer').is_visible() n’est
    # pas remplie.
    if not loc.locator(".Select-menu-outer").is_visible():
        # On clique sur loc.locator('.Select-arrow-zone') dans le navigateur de test pour provoquer
        # l’action de l’interface.
        loc.locator(".Select-arrow-zone").click()
        # On laisse à l’interface le délai indiqué en millisecondes ; cette pause seule ne prouve pas
        # que le résultat attendu est apparu.
        page.wait_for_timeout(200)
    # On clique sur loc.locator('.VirtualizedSelectOption').filter(has_text=part).f… dans le navigateur
    # de test pour provoquer l’action de l’interface.
    loc.locator(".VirtualizedSelectOption").filter(has_text=part).first.click()
    # On laisse à l’interface le délai indiqué en millisecondes ; cette pause seule ne prouve pas que
    # le résultat attendu est apparu.
    page.wait_for_timeout(900)
    # On appelle page.keyboard.press avec 'Escape'.
    page.keyboard.press("Escape")


# On utilise sync_playwright() dans son contexte de gestion ; les opérations de sortie sont exécutées
# en quittant le bloc.
with sync_playwright() as p:
    # On retient pour browser_path la première valeur évaluée comme vraie dans cette chaîne de replis ;
    # une valeur vide fera donc passer à la suivante.
    browser_path = os.getenv("CHROMIUM_PATH") or shutil.which("chromium")
    # On garde dans b la valeur renvoyée par p.chromium.launch.
    b = p.chromium.launch(
        **({"executable_path": browser_path} if browser_path else {}),
        headless=True,
        # On fournit les options de la commande via le paramètre args de cet appel.
        args=["--no-sandbox"],
    )
    # On garde dans c la valeur renvoyée par b.new_context.
    c = b.new_context(
        viewport={"width": 1440, "height": 1050},
        permissions=["clipboard-read", "clipboard-write"],
        accept_downloads=True,
    )
    # On garde dans page la valeur renvoyée par c.new_page.
    page = c.new_page()
    # On prépare errors comme liste vide ; on la remplira au fil des opérations suivantes.
    errors = []
    # On prépare badresponses comme liste vide ; on la remplira au fil des opérations suivantes.
    badresponses = []
    # On appelle page.on avec 'pageerror'.
    page.on("pageerror", lambda e: errors.append(str(e)))
    # On appelle page.on avec 'response'.
    page.on(
        "response",
        lambda r: badresponses.append((r.status, r.url)) if r.status >= 400 else None,
    )
    # On prépare comparison_requests comme liste vide ; on la remplira au fil des opérations suivantes.
    comparison_requests = []
    # On prépare payload_sizes comme liste vide ; on la remplira au fil des opérations suivantes.
    payload_sizes = []

    def observe_request(request):
        # Cette branche traite le cas où request.method correspond au texte 'POST' et le texte
        # '_dash-update-component' appartient à request.url.
        if request.method == "POST" and "_dash-update-component" in request.url:
            # On garde request.post_data_json sous le nom data ; cette affectation ne copie pas à elle
            # seule un objet mutable.
            data = request.post_data_json
            # On ajoute len(request.post_data or '') à la fin de payload_sizes ; les éléments
            # précédents restent conservés.
            payload_sizes.append(len(request.post_data or ""))
            # On vérifie ce cas avant la suite : le texte 'evolution-summary-results' appartient à
            # data.get('output', '').
            if "evolution-summary-results" in data.get("output", ""):
                # On ajoute data à la fin de comparison_requests ; les éléments précédents restent
                # conservés.
                comparison_requests.append(data)

    # On appelle page.on avec 'request'.
    page.on("request", observe_request)
    # On ouvre l’adresse prévue par le test dans cette page, avant d’observer son rendu.
    page.goto(URL)
    # On appelle expect(page.locator('#mode-badge')).to_contain_text avec 'DÉMONSTRATION'.
    expect(page.locator("#mode-badge")).to_contain_text("DÉMONSTRATION")
    # On appelle page.locator('.metric-card').first.wait_for sans argument positionnel.
    page.locator(".metric-card").first.wait_for(timeout=60000)
    # On laisse à l’interface le délai indiqué en millisecondes ; cette pause seule ne prouve pas que
    # le résultat attendu est apparu.
    page.wait_for_timeout(800)
    # Les deux derniers scans évoluent : le résumé doit montrer les différences.
    assert "Aucun changement détecté" not in page.locator(".evolution-summary").inner_text()
    # On attend que page.locator('.overview-charts').bounding_box()['y'] est inférieur à
    # page.locator('.metrics-grid').bounding_box()['y']. Si ce contrôle échoue, le scénario s’arrête
    # sur cette assertion.
    assert (
        page.locator(".overview-charts").bounding_box()["y"]
        < page.locator(".metrics-grid").bounding_box()["y"]
    )
    # On attend que le texte 'catégorie déduite des informations' appartient à
    # page.locator('.chart-legend').first.inner_text(). Si ce contrôle échoue, le scénario s’arrête sur
    # cette assertion.
    assert (
        "catégorie déduite des informations"
        in page.locator(".chart-legend").first.inner_text()
    )
    # On attend que le texte 'Pour Vitimap comme pour Vitiparcel' appartient à
    # page.locator('.overview-charts').inner_text(). Si ce contrôle échoue, le scénario s’arrête sur
    # cette assertion.
    assert (
        "Pour Vitimap comme pour Vitiparcel"
        in page.locator(".overview-charts").inner_text()
    )
    # On attend que le texte 'Acquisitions recensées' appartient à
    # page.locator('.metric-card').first.inner_text(). Si ce contrôle échoue, le scénario s’arrête sur
    # cette assertion.
    assert "Acquisitions recensées" in page.locator(".metric-card").first.inner_text()
    # On attend que le texte 'Tous statuts confondus' appartient à
    # page.locator('.metric-card').first.inner_text(). Si ce contrôle échoue, le scénario s’arrête sur
    # cette assertion.
    assert "Tous statuts confondus" in page.locator(".metric-card").first.inner_text()
    # On attend que le texte '10h01–10h09 ⇒ Dernier scan' appartient à
    # page.locator('#snapshot-select').inner_text(). Si ce contrôle échoue, le scénario s’arrête sur
    # cette assertion.
    assert "10h01–10h09 ⇒ Dernier scan" in page.locator("#snapshot-select").inner_text()
    # opaque tooltip
    graph = page.locator(".overview-charts .js-plotly-plot").first
    # On appelle graph.locator('.bars .point path').first.hover sans argument positionnel.
    graph.locator(".bars .point path").first.hover(force=True)
    # On laisse à l’interface le délai indiqué en millisecondes ; cette pause seule ne prouve pas que
    # le résultat attendu est apparu.
    page.wait_for_timeout(300)
    # On attend que le texte 'Quantité :' appartient à graph.locator('.hoverlayer').text_content(). Si
    # ce contrôle échoue, le scénario s’arrête sur cette assertion.
    assert "Quantité :" in graph.locator(".hoverlayer").text_content()
    # On attend que graph.locator('.hoverlayer .hovertext path').first.evaluate('(e)=>getComp…
    # correspond au texte 'rgb(255, 255, 255)'. Si ce contrôle échoue, le scénario s’arrête sur cette
    # assertion.
    assert (
        graph.locator(".hoverlayer .hovertext path").first.evaluate(
            "(e)=>getComputedStyle(e).fill"
        )
        == "rgb(255, 255, 255)"
    )
    # all metrics still work
    for key in [
        "all",
        "production",
        "treated",
        "review",
        "map",
        "parcel",
        "test",
        "blocked",
        "outside",
    ]:
        # On clique sur pid(page, 'metric', key) dans le navigateur de test pour provoquer l’action de
        # l’interface.
        pid(page, "metric", key).click()
        # On appelle expect(pid(page, 'metric', key)).to_have_class avec re.compile('selected').
        expect(pid(page, "metric", key)).to_have_class(
            # On borne la durée d’attente de cet appel ; dépasser ce délai ne vaut pas confirmation de
            # réussite.
            re.compile("selected"), timeout=20000
        )
        # On appelle page.locator('#metric-detail-section').wait_for sans argument positionnel.
        page.locator("#metric-detail-section").wait_for(timeout=20000)
    # On attend que la condition page.locator('#vineyard-summary').get_attribute('open') n’est pas
    # remplie. Si ce contrôle échoue, le scénario s’arrête sur cette assertion.
    assert not page.locator("#vineyard-summary").get_attribute("open")
    # NAS presentation: safe bold labels, one finding per line, plain copy/CSV.
    pid(page, "metric", "all").click()
    # On appelle expect(pid(page, 'metric', 'all')).to_have_class avec re.compile('selected').
    expect(pid(page, "metric", "all")).to_have_class(
        # On borne la durée d’attente de cet appel ; dépasser ce délai ne vaut pas confirmation de
        # réussite.
        re.compile("selected"), timeout=20000
    )
    # On laisse à l’interface le délai indiqué en millisecondes ; cette pause seule ne prouve pas que
    # le résultat attendu est apparu.
    page.wait_for_timeout(500)
    # On garde dans cols la valeur renvoyée par pid.
    cols = pid(page, "columns", "metric-detail")
    # On renseigne le champ cols.locator('input').first avec la valeur de ce scénario.
    cols.locator("input").first.fill("Constats enregistrés sur le NAS")
    # On clique sur cols.locator('.VirtualizedSelectOption').filter(has_text='Const… dans le navigateur
    # de test pour provoquer l’action de l’interface.
    cols.locator(".VirtualizedSelectOption").filter(
        has_text="Constats enregistrés sur le NAS"
    ).first.click()
    # On clique sur page.locator('#metric-detail-section h3') dans le navigateur de test pour provoquer
    # l’action de l’interface.
    page.locator("#metric-detail-section h3").click()
    # On laisse à l’interface le délai indiqué en millisecondes ; cette pause seule ne prouve pas que
    # le résultat attendu est apparu.
    page.wait_for_timeout(500)
    # On garde dans table la valeur renvoyée par tid.
    table = tid(page, "metric-detail")
    # On garde dans cells le sélecteur navigateur ciblant
    # 'td.dash-cell[data-dash-column="nas_observations_display"]'.
    cells = table.locator('td.dash-cell[data-dash-column="nas_observations_display"]')
    # On appelle expect(cells).to_have_count avec 50.
    expect(cells).to_have_count(50)
    # On attend que cells.first.locator('strong').count() correspond à 6. Si ce contrôle échoue, le
    # scénario s’arrête sur cette assertion.
    assert cells.first.locator("strong").count() == 6
    # On attend que len(cells.first.inner_text().splitlines()) correspond à 6. Si ce contrôle échoue,
    # le scénario s’arrête sur cette assertion.
    assert len(cells.first.inner_text().splitlines()) == 6
    # On attend que cells.first.bounding_box()['width'] est au moins égal à 320. Si ce contrôle échoue,
    # le scénario s’arrête sur cette assertion.
    assert cells.first.bounding_box()["width"] >= 320
    # On attend que cells.first.evaluate('(e)=>getComputedStyle(e).verticalAlign') correspond à le
    # texte 'top'. Si ce contrôle échoue, le scénario s’arrête sur cette assertion.
    assert cells.first.evaluate("(e)=>getComputedStyle(e).verticalAlign") == "top"
    # On attend que cells.first.locator('strong').first.evaluate('(e)=>parseInt(getComputedSt… est au
    # moins égal à 600. Si ce contrôle échoue, le scénario s’arrête sur cette assertion.
    assert (
        cells.first.locator("strong").first.evaluate(
            "(e)=>parseInt(getComputedStyle(e).fontWeight)"
        )
        >= 600
    )
    # On appelle cells.first.scroll_into_view_if_needed sans argument positionnel.
    cells.first.scroll_into_view_if_needed()
    # On appelle page.screenshot sans argument positionnel.
    page.screenshot(path=str(OUT / "v6_nas_list.png"))
    # On appelle cells.first.screenshot sans argument positionnel.
    cells.first.screenshot(path=str(OUT / "v6_nas_cell.png"))
    # Removing/re-adding the column must retain its Markdown presentation.
    cols.locator(".Select-value").filter(
        has_text="Constats enregistrés sur le NAS"
    ).locator(".Select-value-icon").click()
    # On laisse à l’interface le délai indiqué en millisecondes ; cette pause seule ne prouve pas que
    # le résultat attendu est apparu.
    page.wait_for_timeout(300)
    # On renseigne le champ cols.locator('input').first avec la valeur de ce scénario.
    cols.locator("input").first.fill("Constats enregistrés sur le NAS")
    # On clique sur cols.locator('.VirtualizedSelectOption').filter(has_text='Const… dans le navigateur
    # de test pour provoquer l’action de l’interface.
    cols.locator(".VirtualizedSelectOption").filter(
        has_text="Constats enregistrés sur le NAS"
    ).first.click()
    # On clique sur page.locator('#metric-detail-section h3') dans le navigateur de test pour provoquer
    # l’action de l’interface.
    page.locator("#metric-detail-section h3").click()
    # On laisse à l’interface le délai indiqué en millisecondes ; cette pause seule ne prouve pas que
    # le résultat attendu est apparu.
    page.wait_for_timeout(400)
    # On attend que cells.first.locator('strong').count() correspond à 6. Si ce contrôle échoue, le
    # scénario s’arrête sur cette assertion.
    assert cells.first.locator("strong").count() == 6
    # On garde dans filter_input le sélecteur navigateur ciblant
    # 'th.dash-filter[data-dash-column="vineyard_name"] input[type="text"]'.
    filter_input = table.locator(
        'th.dash-filter[data-dash-column="vineyard_name"] input[type="text"]'
    )
    # On renseigne le champ filter_input avec la valeur de ce scénario.
    filter_input.fill("Domaine démo A")
    # On appelle filter_input.press avec 'Enter'.
    filter_input.press("Enter")
    # On appelle expect(cells).to_have_count avec 10.
    expect(cells).to_have_count(10)
    # On appelle table.locator('th.dash-header[data-dash-column="nas_observations_display"]
    # input[type="radio"]').check sans argument positionnel.
    table.locator(
        'th.dash-header[data-dash-column="nas_observations_display"] input[type="radio"]'
    ).check()
    # On laisse à l’interface le délai indiqué en millisecondes ; cette pause seule ne prouve pas que
    # le résultat attendu est apparu.
    page.wait_for_timeout(500)
    # On clique sur page.locator('#metric-detail-section [title="Copier toute la co… dans le navigateur
    # de test pour provoquer l’action de l’interface.
    page.locator(
        '#metric-detail-section [title="Copier toute la colonne filtrée, toutes pages confondues"]'
    ).first.click()
    # On laisse à l’interface le délai indiqué en millisecondes ; cette pause seule ne prouve pas que
    # le résultat attendu est apparu.
    page.wait_for_timeout(250)
    # On garde dans copied la valeur renvoyée par page.evaluate pour 'navigator.clipboard.readText()'.
    copied = page.evaluate("navigator.clipboard.readText()")
    # On attend que le texte 'Dossier Brut : présent' appartient à copied et le texte 'Images WEBP'
    # appartient à copied. Si ce contrôle échoue, le scénario s’arrête sur cette assertion.
    assert "Dossier Brut : présent" in copied and "Images WEBP" in copied
    # On attend que le texte '**' ne figure pas dans copied et le texte '<strong>' ne figure pas dans
    # copied. Si ce contrôle échoue, le scénario s’arrête sur cette assertion.
    assert "**" not in copied and "<strong>" not in copied
    # On attend que len(copied.splitlines()) correspond à 60. Si ce contrôle échoue, le scénario
    # s’arrête sur cette assertion.
    assert len(copied.splitlines()) == 60
    # On attend que len(list(csv_lib.reader(io.StringIO(copied), delimiter='\t'))) correspond à 10. Si
    # ce contrôle échoue, le scénario s’arrête sur cette assertion.
    assert len(list(csv_lib.reader(io.StringIO(copied), delimiter="\t"))) == 10
    # On utilise page.expect_download() dans son contexte de gestion ; les opérations de sortie sont
    # exécutées en quittant le bloc.
    with page.expect_download() as info:
        # On clique sur pid(page, 'plain-export', 'metric-detail') dans le navigateur de test pour
        # provoquer l’action de l’interface.
        pid(page, "plain-export", "metric-detail").click()
    # On garde info.value sous le nom download ; cette affectation ne copie pas à elle seule un objet
    # mutable.
    download = info.value
    # On appelle download.save_as avec str(OUT / 'v6_nas_filtered.csv').
    download.save_as(str(OUT / "v6_nas_filtered.csv"))
    # On ouvre la ressource indiquée pour la durée du bloc ; sa fermeture est assurée à la sortie, y
    # compris après une erreur.
    with open(OUT / "v6_nas_filtered.csv", encoding="utf-8-sig", newline="") as f:
        # On garde dans exported une liste matérialisée à partir de csv_lib.DictReader(f).
        exported = list(csv_lib.DictReader(f))
    # On attend que len(exported) correspond à 10. Si ce contrôle échoue, le scénario s’arrête sur cette
    # assertion.
    assert len(exported) == 10
    # On attend que tous les éléments satisfont le test indiqué. Si ce contrôle échoue, le scénario
    # s’arrête sur cette assertion.
    assert all(row["Vignoble"] == "Domaine démo A" for row in exported)
    # On attend que tous les éléments satisfont le test indiqué. Si ce contrôle échoue, le scénario
    # s’arrête sur cette assertion.
    assert all(
        "\n" in row["Constats enregistrés sur le NAS"]
        # On exige aussi que le texte '**' ne figure pas dans row['Constats enregistrés sur le NAS'].
        and "**" not in row["Constats enregistrés sur le NAS"]
        for row in exported
    )
    # focus local filtering and independence
    page.get_by_text("Ce qui resterait à faire", exact=True).first.click()
    # On appelle page.locator('#criterion-vitimap').wait_for sans argument positionnel.
    page.locator("#criterion-vitimap").wait_for()
    # On attend que page.locator('[id^="criterion-"][open]').count() correspond à 0. Si ce contrôle
    # échoue, le scénario s’arrête sur cette assertion.
    assert page.locator('[id^="criterion-"][open]').count() == 0
    # On garde dans order la valeur renvoyée par page.locator('[id^="criterion-"]').evaluate_all pour
    # '(els)=>els.map(e=>e.id)'.
    order = page.locator('[id^="criterion-"]').evaluate_all("(els)=>els.map(e=>e.id)")
    # On attend que order.index('criterion-stocks') + 1 correspond à order.index('criterion-both'). Si
    # ce contrôle échoue, le scénario s’arrête sur cette assertion.
    assert order.index("criterion-stocks") + 1 == order.index("criterion-both")
    # On attend que order.index('criterion-both') + 1 correspond à order.index('criterion-status'). Si
    # ce contrôle échoue, le scénario s’arrête sur cette assertion.
    assert order.index("criterion-both") + 1 == order.index("criterion-status")
    # On attend que le texte 'Passages identifiés dont le dossier est absent' appartient à
    # page.locator('#criterion-passage > summary').inner_text(). Si ce contrôle échoue, le scénario
    # s’arrête sur cette assertion.
    assert (
        "Passages identifiés dont le dossier est absent"
        in page.locator("#criterion-passage > summary").inner_text()
    )
    # On attend que le texte 'Passages dont le lien à la production reste à vérifier' appartient à
    # page.locator('#data-clarification').inner_text(). Si ce contrôle échoue, le scénario s’arrête sur
    # cette assertion.
    assert (
        "Passages dont le lien à la production reste à vérifier"
        in page.locator("#data-clarification").inner_text()
    )
    # On attend que le texte 'pas comptés comme du travail restant' appartient à
    # page.locator('#data-clarification').text_content(). Si ce contrôle échoue, le scénario s’arrête
    # sur cette assertion.
    assert (
        "pas comptés comme du travail restant"
        in page.locator("#data-clarification").text_content()
    )
    # On clique sur page.locator('#criterion-both > summary') dans le navigateur de test pour provoquer
    # l’action de l’interface.
    page.locator("#criterion-both > summary").click()
    # On attend que ce texte explicite appartient à page.locator('#criterion-both').inner_text(). Si ce
    # contrôle échoue, le scénario s’arrête sur cette assertion.
    assert (
        "Ces passages figurent déjà dans les deux listes précédentes"
        in page.locator("#criterion-both").inner_text()
    )
    # On appelle page.locator('#criterion-both').scroll_into_view_if_needed sans argument positionnel.
    page.locator("#criterion-both").scroll_into_view_if_needed()
    # On appelle page.screenshot sans argument positionnel.
    page.screenshot(path=str(OUT / "v6_criteria_reordered.png"))
    # On clique sur page.locator('#criterion-both > summary') dans le navigateur de test pour provoquer
    # l’action de l’interface.
    page.locator("#criterion-both > summary").click()
    # On parcourt ['vitimap', 'stocks'] ; key désigne l’élément courant de ce scénario.
    for key in ["vitimap", "stocks"]:
        # On clique sur page.locator('#criterion-' + key + ' > summary') dans le navigateur de test
        # pour provoquer l’action de l’interface.
        page.locator("#criterion-" + key + " > summary").click()
    # On laisse à l’interface le délai indiqué en millisecondes ; cette pause seule ne prouve pas que
    # le résultat attendu est apparu.
    page.wait_for_timeout(300)
    # On attend que tid(page, 'focus-vitimap').locator('td.dash-cell[data-dash-column="vineya…
    # correspond à 5. Si ce contrôle échoue, le scénario s’arrête sur cette assertion.
    assert (
        tid(page, "focus-vitimap")
        .locator('td.dash-cell[data-dash-column="vineyard_name"]')
        .count()
        == 5
    )
    # On garde dans other le texte rendu de l’élément ciblé dans la page.
    other = tid(page, "focus-stocks").inner_text()
    # On garde dans g la valeur renvoyée par pid.
    g = pid(page, "focus-chart", "vitimap")
    # On appelle g.scroll_into_view_if_needed sans argument positionnel.
    g.scroll_into_view_if_needed()
    # On clique sur g.locator('.bars .point path').first dans le navigateur de test pour provoquer
    # l’action de l’interface.
    g.locator(".bars .point path").first.click(force=True)
    # On laisse à l’interface le délai indiqué en millisecondes ; cette pause seule ne prouve pas que
    # le résultat attendu est apparu.
    page.wait_for_timeout(750)
    # On attend que le texte 'Filtre local : Domaine démo A' appartient à pid(page, 'focus-local',
    # 'vitimap').inner_text(). Si ce contrôle échoue, le scénario s’arrête sur cette assertion.
    assert (
        "Filtre local : Domaine démo A"
        in pid(page, "focus-local", "vitimap").inner_text()
    )
    # On attend que tid(page, 'focus-vitimap').locator('td.dash-cell[data-dash-column="vineya…
    # correspond à 1. Si ce contrôle échoue, le scénario s’arrête sur cette assertion.
    assert (
        tid(page, "focus-vitimap")
        .locator('td.dash-cell[data-dash-column="vineyard_name"]')
        .count()
        == 1
    )
    # On attend que tid(page, 'focus-stocks').inner_text() correspond à other. Si ce contrôle échoue,
    # le scénario s’arrête sur cette assertion.
    assert tid(page, "focus-stocks").inner_text() == other
    # On attend que g.locator('.bars .point path').count() correspond à 5. Si ce contrôle échoue, le
    # scénario s’arrête sur cette assertion.
    assert g.locator(".bars .point path").count() == 5
    # filtered clipboard and CSV
    pid(page, "focus-local", "vitimap").locator(
        '[title="Copier toute la colonne filtrée, toutes pages confondues"]'
    ).click()
    # On laisse à l’interface le délai indiqué en millisecondes ; cette pause seule ne prouve pas que
    # le résultat attendu est apparu.
    page.wait_for_timeout(250)
    # On attend que page.evaluate('navigator.clipboard.readText()') correspond au texte 'Domaine démo
    # A'. Si ce contrôle échoue, le scénario s’arrête sur cette assertion.
    assert page.evaluate("navigator.clipboard.readText()") == "Domaine démo A"
    # On utilise page.expect_download() dans son contexte de gestion ; les opérations de sortie sont
    # exécutées en quittant le bloc.
    with page.expect_download() as info:
        # On clique sur tid(page, 'focus-vitimap').locator('button.export') dans le navigateur de test
        # pour provoquer l’action de l’interface.
        tid(page, "focus-vitimap").locator("button.export").click()
    # On garde info.value sous le nom download ; cette affectation ne copie pas à elle seule un objet
    # mutable.
    download = info.value
    # On appelle download.save_as avec str(OUT / 'v6_filtered.csv').
    download.save_as(str(OUT / "v6_filtered.csv"))
    # On garde dans csv le contenu lu depuis open(str(OUT / 'v6_filtered.csv'), encoding='utf-8-sig')
    # selon les paramètres fournis.
    csv = open(str(OUT / "v6_filtered.csv"), encoding="utf-8-sig").read()
    # On attend que le texte 'Domaine démo A' appartient à csv et le texte 'Domaine démo B' ne figure
    # pas dans csv. Si ce contrôle échoue, le scénario s’arrête sur cette assertion.
    assert "Domaine démo A" in csv and "Domaine démo B" not in csv
    # On clique sur pid(page, 'focus-clear', 'vitimap') dans le navigateur de test pour provoquer
    # l’action de l’interface.
    pid(page, "focus-clear", "vitimap").click()
    # On laisse à l’interface le délai indiqué en millisecondes ; cette pause seule ne prouve pas que
    # le résultat attendu est apparu.
    page.wait_for_timeout(500)
    # On attend que tid(page, 'focus-vitimap').locator('td.dash-cell[data-dash-column="vineya…
    # correspond à 5. Si ce contrôle échoue, le scénario s’arrête sur cette assertion.
    assert (
        tid(page, "focus-vitimap")
        .locator('td.dash-cell[data-dash-column="vineyard_name"]')
        .count()
        == 5
    )
    # same bar clickable again after clear
    g.locator(".bars .point path").first.click(force=True)
    # On laisse à l’interface le délai indiqué en millisecondes ; cette pause seule ne prouve pas que
    # le résultat attendu est apparu.
    page.wait_for_timeout(600)
    # On attend que tid(page, 'focus-vitimap').locator('td.dash-cell[data-dash-column="vineya…
    # correspond à 1. Si ce contrôle échoue, le scénario s’arrête sur cette assertion.
    assert (
        tid(page, "focus-vitimap")
        .locator('td.dash-cell[data-dash-column="vineyard_name"]')
        .count()
        == 1
    )
    # On appelle page.locator('#criterion-vitimap').scroll_into_view_if_needed sans argument
    # positionnel.
    page.locator("#criterion-vitimap").scroll_into_view_if_needed()
    # On appelle page.screenshot sans argument positionnel.
    page.screenshot(path=str(OUT / "v6_focus_local.png"))
    # global vineyard resets local filters and restricts all criteria
    choose(page, "vineyard-filter", "Domaine démo B")
    # On attend que pid(page, 'focus-local', 'vitimap').inner_text().find('Filtre local :') est
    # inférieur à 0. Si ce contrôle échoue, le scénario s’arrête sur cette assertion.
    assert pid(page, "focus-local", "vitimap").inner_text().find("Filtre local :") < 0
    # On attend que le texte 'Domaine démo A' ne figure pas dans tid(page,
    # 'focus-vitimap').inner_text(). Si ce contrôle échoue, le scénario s’arrête sur cette assertion.
    assert "Domaine démo A" not in tid(page, "focus-vitimap").inner_text()
    # On appelle choose avec page.
    choose(page, "vineyard-filter", "Tous les vignobles")
    # Evolution: automatic latest pair, no recomputation until Apply.
    page.get_by_text("Évolution", exact=True).first.click()
    # On appelle page.locator('#evolution-summary-results .evolution-summary').wait_for sans argument
    # positionnel.
    page.locator("#evolution-summary-results .evolution-summary").wait_for(
        # On borne la durée d’attente de cet appel ; dépasser ce délai ne vaut pas confirmation de
        # réussite.
        timeout=30000
    )
    # On laisse à l’interface le délai indiqué en millisecondes ; cette pause seule ne prouve pas que
    # le résultat attendu est apparu.
    page.wait_for_timeout(600)
    # On conserve le résumé affiché pour vérifier que choisir des dates ne le recalcule pas.
    initial_summary = page.locator("#evolution-summary-results").inner_text()
    assert "présentent un changement" in initial_summary
    # On attend que la condition page.locator('#compare-dates-wrap').is_visible() n’est pas remplie. Si
    # ce contrôle échoue, le scénario s’arrête sur cette assertion.
    assert not page.locator("#compare-dates-wrap").is_visible()
    # On garde dans initial_requests le nombre d’éléments de comparison_requests.
    initial_requests = len(comparison_requests)
    # On clique sur page.get_by_text('Choisir les dates', exact=False).first dans le navigateur de test
    # pour provoquer l’action de l’interface.
    page.get_by_text("Choisir les dates", exact=False).first.click()
    # On appelle choose avec page.
    choose(page, "compare-dates", "19/10/2026")
    # On appelle choose avec page.
    choose(page, "compare-dates", "15/10/2026")
    # On attend que le texte 'non appliquée' appartient à
    # page.locator('#compare-selection-note').inner_text(). Si ce contrôle échoue, le scénario s’arrête
    # sur cette assertion.
    assert "non appliquée" in page.locator("#compare-selection-note").inner_text()
    # La sélection n’est pas encore appliquée : le résumé doit rester strictement identique.
    assert page.locator("#evolution-summary-results").inner_text() == initial_summary
    # On attend que len(comparison_requests) correspond à initial_requests. Si ce contrôle échoue, le
    # scénario s’arrête sur cette assertion.
    assert len(comparison_requests) == initial_requests, (
        "dates changed results before Apply"
    )
    # On appelle page.screenshot sans argument positionnel.
    page.screenshot(path=str(OUT / "v6_selection_pending.png"))
    # On clique sur page.locator('#compare-apply') dans le navigateur de test pour provoquer l’action
    # de l’interface.
    page.locator("#compare-apply").click()
    # Le nouveau résumé peut déjà contenir les mêmes mots ; on attend la fin réelle du calcul.
    expect(page.locator("#compare-selection-note")).not_to_contain_text("non appliquée", timeout=30000)
    # On appelle expect(page.locator('#evolution-summary-results .evolution-summary')).to_contain_text
    # avec 'présentent un changement'.
    expect(
        page.locator("#evolution-summary-results .evolution-summary")
    # On borne la durée d’attente de cet appel ; dépasser ce délai ne vaut pas confirmation de
    # réussite.
    ).to_contain_text("présentent un changement", timeout=30000)
    # On attend que le texte 'WEBP' appartient à tid(page, 'evolution-diff').inner_text(). Si ce
    # contrôle échoue, le scénario s’arrête sur cette assertion.
    expect(tid(page, "evolution-diff")).to_contain_text("WEBP", timeout=30000)
    # On attend que le texte 'Commentaire du suivi Excel' appartient à tid(page,
    # 'evolution-diff').inner_text(). Si ce contrôle échoue, le scénario s’arrête sur cette assertion.
    expect(tid(page, "evolution-diff")).to_contain_text("Commentaire du suivi Excel", timeout=30000)
    # On attend que le texte 'non appliquée' ne figure pas dans
    # page.locator('#compare-selection-note').inner_text(). Si ce contrôle échoue, le scénario s’arrête
    # sur cette assertion.
    assert "non appliquée" not in page.locator("#compare-selection-note").inner_text()
    # On clique sur page.get_by_text('Consulter les volumes, dates et références',… dans le navigateur
    # de test pour provoquer l’action de l’interface.
    page.get_by_text("Consulter les volumes, dates et références", exact=True).click()
    # On attend que tid(page, 'evolution-timeline').locator('td.dash-cell[data-dash-column="V…
    # correspond à 20. Si ce contrôle échoue, le scénario s’arrête sur cette assertion.
    assert (
        tid(page, "evolution-timeline")
        .locator('td.dash-cell[data-dash-column="Vignoble"]')
        .count()
        == 20
    )
    # On appelle choose avec page.
    choose(page, "evolution-family", "Excel · commentaires")
    # On attend que tid(page, 'evolution-diff').locator('td.dash-cell[data-dash-column="Infor…
    # correspond à 36. Si ce contrôle échoue, le scénario s’arrête sur cette assertion.
    # On attend le tableau filtré, pas seulement le retour du sélecteur.
    expect(tid(page, "evolution-diff").locator(
        'td.dash-cell[data-dash-column="Information"]'
    )).to_have_count(36, timeout=30000)
    # On attend que le texte 'Commentaire du suivi Excel' appartient à tid(page,
    # 'evolution-diff').inner_text(). Si ce contrôle échoue, le scénario s’arrête sur cette assertion.
    expect(tid(page, "evolution-diff")).to_contain_text("Commentaire du suivi Excel", timeout=30000)
    # Fewer than two selected scans disables Apply and leaves preceding results intact.
    for text in ["19/10/2026", "15/10/2026", "21/10/2026"]:
        # On appelle page.locator('#compare-dates
        # label').filter(has_text=text).locator('input').uncheck sans argument positionnel.
        page.locator("#compare-dates label").filter(has_text=text).locator(
            "input"
        ).uncheck()
    # On laisse à l’interface le délai indiqué en millisecondes ; cette pause seule ne prouve pas que
    # le résultat attendu est apparu.
    page.wait_for_timeout(400)
    # On appelle expect(page.locator('#compare-apply')).to_be_disabled sans argument positionnel.
    expect(page.locator("#compare-apply")).to_be_disabled()
    # On attend que le texte 'non appliquée' appartient à
    # page.locator('#compare-selection-note').inner_text(). Si ce contrôle échoue, le scénario s’arrête
    # sur cette assertion.
    assert "non appliquée" in page.locator("#compare-selection-note").inner_text()
    # On attend que tid(page, 'evolution-diff').locator('td.dash-cell[data-dash-column="Infor…
    # correspond à 36. Si ce contrôle échoue, le scénario s’arrête sur cette assertion.
    # On attend le tableau filtré, pas seulement le retour du sélecteur.
    expect(tid(page, "evolution-diff").locator(
        'td.dash-cell[data-dash-column="Information"]'
    )).to_have_count(36, timeout=30000)
    # Restore four dates and confirm explicitly.
    for text in ["19/10/2026", "15/10/2026", "21/10/2026"]:
        # On appelle choose avec page.
        choose(page, "compare-dates", text)
    # On clique sur page.locator('#compare-apply') dans le navigateur de test pour provoquer l’action
    # de l’interface.
    page.locator("#compare-apply").click()
    # On laisse à l’interface le délai indiqué en millisecondes ; cette pause seule ne prouve pas que
    # le résultat attendu est apparu.
    page.wait_for_timeout(700)
    # On appelle choose avec page.
    choose(page, "evolution-family", "Toutes")
    # On appelle page.locator('#evolution-results').scroll_into_view_if_needed sans argument
    # positionnel.
    page.locator("#evolution-results").scroll_into_view_if_needed()
    # On appelle page.screenshot sans argument positionnel.
    page.screenshot(path=str(OUT / "v6_evolution_changes.png"))
    # Changing the state selector must not reset the independent applied comparison.
    before_requests = len(comparison_requests)
    # On appelle choose avec page.
    choose(page, "snapshot-select", "15/10/2026")
    # On attend que len(comparison_requests) correspond à before_requests. Si ce contrôle échoue, le
    # scénario s’arrête sur cette assertion.
    assert len(comparison_requests) == before_requests
    # On attend que page.locator('#compare-dates input:checked').count() correspond à 10. Si ce contrôle
    # échoue, le scénario s’arrête sur cette assertion.
    assert page.locator("#compare-dates input:checked").count() == 4
    # On attend que le texte 'présentent un changement' appartient à
    # page.locator('#evolution-summary-results').inner_text(). Si ce contrôle échoue, le scénario
    # s’arrête sur cette assertion.
    assert (
        "présentent un changement"
        in page.locator("#evolution-summary-results").inner_text()
    )
    # Historic entire state (not a current/historic mixture)
    choose(page, "snapshot-select", "15/10/2026")
    # On attend que le texte 'État historique' appartient à
    # page.locator('#snapshot-banner').inner_text(). Si ce contrôle échoue, le scénario s’arrête sur
    # cette assertion.
    assert "État historique" in page.locator("#snapshot-banner").inner_text()
    # On clique sur page.get_by_text('Vue d’ensemble', exact=True).first dans le navigateur de test
    # pour provoquer l’action de l’interface.
    page.get_by_text("Vue d’ensemble", exact=True).first.click()
    # On appelle page.locator('.metric-card').first.wait_for sans argument positionnel.
    page.locator(".metric-card").first.wait_for()
    # On laisse à l’interface le délai indiqué en millisecondes ; cette pause seule ne prouve pas que
    # le résultat attendu est apparu.
    page.wait_for_timeout(600)
    # On attend que le texte '25' correspond à pid(page, 'metric',
    # 'all').locator('.metric-value').inner_text(). Si ce contrôle échoue, le scénario s’arrête sur
    # cette assertion.
    assert "25" == pid(page, "metric", "all").locator(".metric-value").inner_text()
    # On attend que le texte 'État historique' appartient à page.locator('#tab-content').inner_text().
    # Si ce contrôle échoue, le scénario s’arrête sur cette assertion.
    assert "État historique" in page.locator("#tab-content").inner_text()
    # On appelle page.screenshot sans argument positionnel.
    page.screenshot(path=str(OUT / "v6_historical.png"))
    # On clique sur page.get_by_text('Rechercher', exact=True).first dans le navigateur de test pour
    # provoquer l’action de l’interface.
    page.get_by_text("Rechercher", exact=True).first.click()
    # On appelle page.locator('#search-query').wait_for sans argument positionnel.
    page.locator("#search-query").wait_for()
    # On renseigne le champ page.locator('#search-query') avec la valeur de ce scénario.
    page.locator("#search-query").fill("DEMO_A_004")
    # On appelle page.locator('#search-query').press avec 'Enter'.
    page.locator("#search-query").press("Enter")
    # On laisse à l’interface le délai indiqué en millisecondes ; cette pause seule ne prouve pas que
    # le résultat attendu est apparu.
    page.wait_for_timeout(600)
    # On attend que le texte 'Aucun résultat' appartient à
    # page.locator('#search-results').inner_text(). Si ce contrôle échoue, le scénario s’arrête sur
    # cette assertion.
    assert "Aucun résultat" in page.locator("#search-results").inner_text()
    # On renseigne le champ page.locator('#search-query') avec la valeur de ce scénario.
    page.locator("#search-query").fill("DEMO_A_001")
    # On appelle page.locator('#search-query').press avec 'Enter'.
    page.locator("#search-query").press("Enter")
    # On laisse à l’interface le délai indiqué en millisecondes ; cette pause seule ne prouve pas que
    # le résultat attendu est apparu.
    page.wait_for_timeout(600)
    # On clique sur page.locator('#search-results summary').filter(has_text='Acquis… dans le navigateur
    # de test pour provoquer l’action de l’interface.
    page.locator("#search-results summary").filter(
        has_text="Acquisitions"
    ).first.click()
    # On appelle page.locator('#search-results input[name^="row-select-"]').first.check sans argument
    # positionnel.
    page.locator('#search-results input[name^="row-select-"]').first.check()
    # On laisse à l’interface le délai indiqué en millisecondes ; cette pause seule ne prouve pas que
    # le résultat attendu est apparu.
    page.wait_for_timeout(500)
    # On clique sur page.locator('#search-results summary').filter(has_text='Consul… dans le navigateur
    # de test pour provoquer l’action de l’interface.
    page.locator("#search-results summary").filter(
        has_text="Consulter la ligne"
    ).first.click()
    # On laisse à l’interface le délai indiqué en millisecondes ; cette pause seule ne prouve pas que
    # le résultat attendu est apparu.
    page.wait_for_timeout(400)
    # On attend que le texte 'En cours' appartient à page.locator('#search-results').inner_text(). Si
    # ce contrôle échoue, le scénario s’arrête sur cette assertion.
    assert "En cours" in page.locator("#search-results").inner_text()
    # On attend que le texte 'Passage 1' appartient à page.locator('#search-results').inner_text(). Si
    # ce contrôle échoue, le scénario s’arrête sur cette assertion.
    assert "Passage 1" in page.locator("#search-results").inner_text()
    # On appelle choose avec page.
    choose(page, "snapshot-select", "Dernier scan")
    # On clique sur page.get_by_text('Vue d’ensemble', exact=True).first dans le navigateur de test
    # pour provoquer l’action de l’interface.
    page.get_by_text("Vue d’ensemble", exact=True).first.click()
    # On laisse à l’interface le délai indiqué en millisecondes ; cette pause seule ne prouve pas que
    # le résultat attendu est apparu.
    page.wait_for_timeout(700)
    # On attend que le texte '50' correspond à pid(page, 'metric',
    # 'all').locator('.metric-value').inner_text(). Si ce contrôle échoue, le scénario s’arrête sur
    # cette assertion.
    assert "50" == pid(page, "metric", "all").locator(".metric-value").inner_text()
    # Category changes the census subtitle
    choose(page, "perimeter-filter", "Test")
    # On attend que le texte 'Catégorie sélectionnée : Test' appartient à pid(page, 'metric',
    # 'all').inner_text(). Si ce contrôle échoue, le scénario s’arrête sur cette assertion.
    assert "Catégorie sélectionnée : Test" in pid(page, "metric", "all").inner_text()
    # On appelle choose avec page.
    choose(page, "perimeter-filter", "Toutes les catégories")
    # reload server data should reset local interaction state without error
    page.locator("#reload-button").click()
    # On laisse à l’interface le délai indiqué en millisecondes ; cette pause seule ne prouve pas que
    # le résultat attendu est apparu.
    page.wait_for_timeout(1000)
    # On attend que le texte '50' correspond à pid(page, 'metric',
    # 'all').locator('.metric-value').inner_text(). Si ce contrôle échoue, le scénario s’arrête sur
    # cette assertion.
    assert "50" == pid(page, "metric", "all").locator(".metric-value").inner_text()
    # Mobile width and all tabs usable
    page.set_viewport_size({"width": 390, "height": 844})
    # On ouvre l’adresse prévue par le test dans cette page, avant d’observer son rendu.
    page.goto(URL)
    # On appelle page.locator('.metric-card').first.wait_for sans argument positionnel.
    page.locator(".metric-card").first.wait_for()
    # On laisse à l’interface le délai indiqué en millisecondes ; cette pause seule ne prouve pas que
    # le résultat attendu est apparu.
    page.wait_for_timeout(700)
    # On attend que le contrôle page.evaluate('document.documentElement.scrollWidth<=innerWidth') est
    # positif. Si ce contrôle échoue, le scénario s’arrête sur cette assertion.
    assert page.evaluate("document.documentElement.scrollWidth<=innerWidth"), (
        "mobile overflow overview"
    )
    # On appelle page.screenshot sans argument positionnel.
    page.screenshot(path=str(OUT / "v6_mobile.png"))
    # On clique sur page.get_by_text('Évolution', exact=True).first dans le navigateur de test pour
    # provoquer l’action de l’interface.
    page.get_by_text("Évolution", exact=True).first.click()
    # On appelle page.locator('#evolution-summary-results .evolution-summary').wait_for sans argument
    # positionnel.
    page.locator("#evolution-summary-results .evolution-summary").wait_for()
    # On laisse à l’interface le délai indiqué en millisecondes ; cette pause seule ne prouve pas que
    # le résultat attendu est apparu.
    page.wait_for_timeout(500)
    # On attend que le contrôle page.evaluate('document.documentElement.scrollWidth<=innerWidth') est
    # positif. Si ce contrôle échoue, le scénario s’arrête sur cette assertion.
    assert page.evaluate("document.documentElement.scrollWidth<=innerWidth"), (
        "mobile overflow evolution"
    )
    # On appelle page.screenshot sans argument positionnel.
    page.screenshot(path=str(OUT / "v6_mobile_evolution.png"))
    # Repeated fast tab changes settle on the correct content, never an old page.
    page.set_viewport_size({"width": 1440, "height": 1050})
    # On parcourt [('Vue d’ensemble', 'overview'), ('Évolution', 'evolution'), ('Rechercher… ; (target,
    # value) désigne l’élément courant de ce scénario.
    for target, value in [
        ("Vue d’ensemble", "overview"),
        ("Évolution", "evolution"),
        ("Rechercher", "search"),
        ("Ce qui resterait à faire", "focus"),
        ("Évolution", "evolution"),
    ]:
        # On clique sur page.get_by_text(target, exact=True).first dans le navigateur de test pour
        # provoquer l’action de l’interface.
        page.get_by_text(target, exact=True).first.click()
        # On appelle page.locator('[data-rendered-tab="' + value + '"]').wait_for sans argument
        # positionnel.
        page.locator('[data-rendered-tab="' + value + '"]').wait_for(timeout=30000)
    # On appelle expect(page.locator('#tab-content [data-rendered-tab]')).to_have_attribute avec
    # 'data-rendered-tab'.
    expect(page.locator("#tab-content [data-rendered-tab]")).to_have_attribute(
        "data-rendered-tab", "evolution"
    )
    # No raw frame bundles in browser Stores or callback state parameters.
    for data in comparison_requests:
        # On parcourt data.get('state', []) ; state désigne l’élément courant de ce scénario.
        for state in data.get("state", []):
            # On vérifie ce cas avant la suite : state.get('id') correspond au texte
            # 'dashboard-store'.
            if state.get("id") == "dashboard-store":
                # On attend que le texte '_store_id' appartient à la valeur reçue dans state et le
                # texte 'frames' ne figure pas dans la valeur reçue dans state. Si ce contrôle échoue,
                # le scénario s’arrête sur cette assertion.
                assert "_store_id" in state["value"] and "frames" not in state["value"]
    # On attend que la condition errors n’est pas remplie. Si ce contrôle échoue, le scénario s’arrête
    # sur cette assertion.
    assert not errors, errors
    # On attend que la condition badresponses n’est pas remplie. Si ce contrôle échoue, le scénario
    # s’arrête sur cette assertion.
    assert not badresponses, badresponses
    # On affiche cette information de suivi dans la sortie du programme.
    print(
        json.dumps(
            {
                # On renseigne le résultat de cette opération sous la clé 'result'.
                "result": "PASS",
                # On renseigne les indicateurs sous la clé 'metrics'.
                "metrics": 9,
                # On associe la clé 'criteria' à cette valeur dans les données de ce scénario.
                "criteria": 10,
                # On associe la clé 'latestUnchanged' à cette valeur dans les données de ce scénario.
                "latestChangesVisible": True,
                # On associe la clé 'fourSnapshots' à cette valeur dans les données de ce scénario.
                "fourSnapshots": True,
                # On associe la clé 'historicalStateAndSearch' à cette valeur dans les données de ce
                # scénario.
                "historicalStateAndSearch": True,
                # On associe la clé 'localFilterIndependence' à cette valeur dans les données de ce
                # scénario.
                "localFilterIndependence": True,
                # On associe la clé 'clipboardAndCSV' à cette valeur dans les données de ce scénario.
                "clipboardAndCSV": True,
                # On associe la clé 'globalReset' à cette valeur dans les données de ce scénario.
                "globalReset": True,
                # On associe la clé 'sameBarAfterClear' à cette valeur dans les données de ce scénario.
                "sameBarAfterClear": True,
                # On associe la clé 'mobile' à cette valeur dans les données de ce scénario.
                "mobile": True,
                # On associe la clé 'explicitApply' à cette valeur dans les données de ce scénario.
                "explicitApply": True,
                # On associe la clé 'pendingDates' à cette valeur dans les données de ce scénario.
                "pendingDates": True,
                # On associe la clé 'independentSnapshot' à cette valeur dans les données de ce
                # scénario.
                "independentSnapshot": True,
                # On associe la clé 'thinBrowserStores' à cette valeur dans les données de ce scénario.
                "thinBrowserStores": True,
                # On associe la clé 'tabCoherence' à cette valeur dans les données de ce scénario.
                "tabCoherence": True,
                # On associe la clé 'compactDates' à cette valeur dans les données de ce scénario.
                "compactDates": True,
                # On associe la clé 'nasListFormatting' à cette valeur dans les données de ce scénario.
                "nasListFormatting": True,
                # On associe la clé 'plainNasClipboard' à cette valeur dans les données de ce scénario.
                "plainNasClipboard": True,
                # On associe la clé 'plainNasCSV' à cette valeur dans les données de ce scénario.
                "plainNasCSV": True,
                # On associe la clé 'columnReselection' à cette valeur dans les données de ce scénario.
                "columnReselection": True,
                # On associe la clé 'criterionOrder' à cette valeur dans les données de ce scénario.
                "criterionOrder": True,
                # On associe la clé 'separateDataQuality' à cette valeur dans les données de ce
                # scénario.
                "separateDataQuality": True,
                # On associe la clé 'comparisonRequests' à cette valeur dans les données de ce
                # scénario.
                "comparisonRequests": len(comparison_requests),
                # On associe la clé 'maxRequestBytes' à cette valeur dans les données de ce scénario.
                "maxRequestBytes": max(payload_sizes),
                # On associe la clé 'screenshots' à cette valeur dans les données de ce scénario.
                "screenshots": str(OUT),
                # On renseigne les erreurs relevées sous la clé 'errors'.
                "errors": errors,
                # On associe la clé 'httpErrors' à cette valeur dans les données de ce scénario.
                "httpErrors": badresponses,
            }
        )
    )
    # On ferme b pour libérer la ressource associée après son utilisation.
    b.close()
