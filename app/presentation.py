# Lecture du fichier — Mise en forme des valeurs pour les tableaux, la copie et les exports.
# On adapte le texte au support : le Markdown sert à l’affichage, tandis que la copie et le CSV
# conservent une représentation lisible sans balises.
#

"""Présentation seulement : aucune règle métier, aucun accès aux sources.

Les cellules NAS sont formatées en Markdown sûr pour l'écran. La copie et le
CSV utilisent toujours le texte brut conservé à part, sans balises ni astérisques.
"""

# On importe csv. On transforme les tableaux entre lignes Python et fichiers CSV.
import csv
# On importe io. On peut fournir des flux en mémoire aux lecteurs et aux captures de sortie.
import io
# On importe re. On reconnaît ou transforme des motifs de texte avec les expressions régulières.
import re

# On fixe NAS_COLUMN à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même
# réglage.
NAS_COLUMN = "nas_observations_display"
# On fixe NAS_PLAIN à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même
# réglage.
NAS_PLAIN = "_nas_observations_plain"


# On protège les caractères qui auraient sinon un sens de mise en forme Markdown.
def escape_markdown(value):
    # On fournit à l’appelant le texte après les remplacements définis par le motif.
    return re.sub(r"([\\`*{}\[\]<>()!#_|~])", r"\\\1", str(value))


# On met en forme les constats pour l’affichage, sans changer leur interprétation métier.
def nas_markdown(value):
    # On prépare lines comme liste vide ; on la remplira au fil des opérations suivantes.
    lines = []
    # On traite le texte ligne par ligne pour conserver la séparation des enregistrements.
    for line in str(value or "").splitlines():
        # On répartit les valeurs renvoyées par line.partition entre (title, separator, content) ; leur
        # ordre doit correspondre à celui prévu par cet appel.
        title, separator, content = line.partition(" : ")
        # Cette branche traite le cas où separator est évalué comme vrai.
        if separator:
            # On ajoute '**' + escape_markdown(title) + ' :** ' + escape_markdown(content) à la fin de
            # lines ; les éléments précédents restent conservés.
            lines.append(
                "**" + escape_markdown(title) + " :** " + escape_markdown(content)
            )
        else:
            # On ajoute escape_markdown(line) à la fin de lines ; les éléments précédents restent
            # conservés.
            lines.append(escape_markdown(line))
    # On fournit à l’appelant le texte formé en réunissant les éléments avec '  \n' comme séparateur.
    return "  \n".join(lines)


# On décrit les colonnes affichées en distinguant leur identifiant technique et leur libellé.
def table_columns(columns, label):
    # On remet [dict(name=label(c), id=c, selectable=True, **{'presentation': 'markdown'… à l’appelant
    # ; les étapes suivantes de cette fonction ne sont plus parcourues.
    return [
        dict(
            # On fournit le nom en cours via le paramètre name de cet appel.
            name=label(c),
            # On donne au composant son identifiant, utilisé ensuite pour les callbacks et les
            # sélecteurs.
            id=c,
            selectable=True,
            **({"presentation": "markdown"} if c == NAS_COLUMN else {}),
        )
        for c in (columns or [])
    ]


# On prépare le texte d’une cellule sans les balises destinées à la mise en forme du tableau.
def plain_column_value(row, column):
    # On choisit la valeur de value selon ce test : column correspond à NAS_COLUMN. Les deux résultats
    # possibles restent définis explicitement ici.
    value = (
        row.get(NAS_PLAIN, row.get(column)) if column == NAS_COLUMN else row.get(column)
    )
    # On renvoie l’une des deux valeurs selon le test indiqué ; ce choix termine la fonction pour ce
    # cas.
    return "" if value is None else str(value)


# On prépare un CSV de valeurs brutes ; cela ne neutralise pas automatiquement les formules d’un
# tableur.
def plain_csv(rows, columns):
    # On garde dans out un flux texte en mémoire, utilisable comme un fichier par le lecteur CSV.
    out = io.StringIO(newline="")
    # On garde dans writer la valeur renvoyée par csv.writer.
    writer = csv.writer(out)
    # On appelle writer.writerow avec [c['name'] for c in columns].
    writer.writerow([c["name"] for c in columns])
    # On parcourt rows or [] ; row désigne l’élément courant à chaque passage dans la boucle.
    for row in rows or []:
        # On appelle writer.writerow avec [plain_column_value(row, c['id']) for c in columns].
        writer.writerow([plain_column_value(row, c["id"]) for c in columns])
    # UTF-8 BOM improves Excel's recognition of accented French column names.
    return "\ufeff" + out.getvalue()


# On prépare les valeurs copiables sans reprendre les balises destinées à l’affichage.
def plain_clipboard(rows, column):
    # On construit values comme une liste à partir de plain_column_value(row, column), pour chaque row
    # de rows or [].
    values = [plain_column_value(row, column) for row in rows or []]
    # On vérifie ce cas avant la suite : column diffère de NAS_COLUMN.
    if column != NAS_COLUMN:
        # On fournit à l’appelant le texte formé en réunissant les éléments avec '\n' comme séparateur.
        return "\n".join(values)
    # Quoted TSV protects embedded line breaks when pasted into a spreadsheet:
    # one source acquisition remains one cell, rather than six spreadsheet rows.
    out = io.StringIO(newline="")
    # On garde dans writer la valeur renvoyée par csv.writer.
    writer = csv.writer(out, delimiter="\t")
    # On appelle writer.writerows avec [[value] for value in values].
    writer.writerows([[value] for value in values])
    # On fournit à l’appelant la valeur renvoyée par out.getvalue().rstrip pour '\r\n'.
    return out.getvalue().rstrip("\r\n")
