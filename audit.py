#!/usr/bin/env python3
"""Contrôles automatiques de l'Auditeur sur un fichier Markdown.

Usage : python3 audit.py FICHIER.md [--sources SOURCES.md] [--pages N]
                         [--mots-par-page 300] [--json]
        python3 audit.py --selftest
"""
import argparse, json, re, sys

# [1] · [1, 2] · [3–5] · [19]–[25]
CIT = re.compile(r"\[(\d+(?:\s*[,–-]\s*\d+)*)\](?:\s*[–-]\s*\[(\d+)\])?")
# Bibliographie : ligne de tableau « | 12 | … » ou ligne commençant par « [12] »
SRC_ROW = re.compile(r"^\s*(?:\|\s*(\d+)\s*\||\[(\d+)\])", re.M)
SEP = re.compile(r"^\s*\|?[\s:|-]+\|?\s*$")  # ligne |---|---|
# Nombre avec unité, ou grand nombre écrit avec espaces (6 500, 143 100 000)
CHIFFRE = re.compile(r"\d\s?(%|M€|Md€|€|millions?\b|milliards?\b)|\b\d{1,3}(?:[   ]\d{3})+\b")
SOURCE_OK = re.compile(r"\[\d+(?:\s*[,–-]\s*\d+)*\]|\[HYP\]|\[EST\]")


def citations(text):
    nums = set()
    for inner, end in CIT.findall(text):
        last = None
        for part in inner.split(","):
            a, _, b = re.sub(r"\s", "", part).replace("–", "-").partition("-")
            nums.update(range(int(a), int(b) + 1) if b else [int(a)])
            last = int(b or a)
        if end:
            nums.update(range(last, int(end) + 1))
    return nums


def unites(text):
    """(n° de ligne, texte) : une ligne de tableau = une unité, sinon une phrase."""
    for i, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#") or SEP.match(s):
            continue
        if s.startswith("|"):
            yield i, s
        else:
            # ponytail: découpage naïf des phrases (« Déc. 2019 » coupe en deux), suffisant pour une alerte
            for p in re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý«(*`-])", s):
                yield i, p


def audit(text, sources_text=None, pages_max=None, mpp=300):
    cites = citations(text)
    r = {"unknown_citations": [], "uncited_sources": []}
    if sources_text is not None:
        biblio = {int(a or b) for a, b in SRC_ROW.findall(sources_text)}
        r["unknown_citations"] = sorted(cites - biblio)
        r["uncited_sources"] = sorted(biblio - cites)
    r["hyp"], r["est"] = text.count("[HYP]"), text.count("[EST]")
    propre = "\n".join(l for l in text.splitlines() if not SEP.match(l.strip()) or not l.strip())
    propre = re.sub(r"<br\s*/?>|[|#*`]", " ", propre)
    r["words"] = len(propre.split())
    r["pages"] = round(r["words"] / mpp, 2)
    r["warnings"] = [{"ligne": i, "texte": u} for i, u in unites(text)
                     if CHIFFRE.search(u) and not SOURCE_OK.search(u)]
    err = []
    if r["unknown_citations"]:
        err.append("Citations inconnues de la bibliographie : " + ", ".join(f"[{n}]" for n in r["unknown_citations"]))
    if pages_max is not None and r["pages"] > pages_max:
        err.append(f"Trop long : {r['pages']} pages estimées pour {pages_max} autorisées")
    r["errors"], r["ok"] = err, not err
    return r


def rapport(r, avec_sources, pages_max, mpp):
    print("== Citations ==")
    if not avec_sources:
        print("  (non vérifiées : --sources absent)")
    else:
        print("  Inconnues :", ", ".join(map(str, r["unknown_citations"])) or "aucune")
        print("  Sources jamais citées dans ce fichier (info) :", ", ".join(map(str, r["uncited_sources"])) or "aucune")
    print("== Marqueurs ==")
    print(f"  [HYP] : {r['hyp']}   [EST] : {r['est']}")
    print("== Longueur ==")
    lim = f" (limite : {pages_max})" if pages_max is not None else ""
    print(f"  {r['words']} mots, soit {r['pages']} pages à {mpp} mots/page{lim}")
    w = r["warnings"]
    print(f"== Chiffres non sourcés (heuristique, à vérifier) : {len(w)} ==")
    for x in w[:30]:
        t = x["texte"]
        print(f"  l.{x['ligne']} : {t[:160] + '…' if len(t) > 160 else t}")
    if len(w) > 30:
        print(f"  … et {len(w) - 30} autre(s)")
    if r["errors"]:
        print("== Erreurs ==")
        for e in r["errors"]:
            print("  -", e)
    n = len(r["errors"])
    print("VERDICT : validé" if not n else f"VERDICT : rejeté ({n} erreur(s))")


def selftest():
    assert citations("voir [19]–[25] et [3]-[4], [7]") == {3, 4, 7, *range(19, 26)}
    src = "| # | Réf |\n|---|---|\n| 1 | A |\n| 2 | B |\n"
    doc = ("# Titre 2024 : 50 %\n"
           "Le CA est de 878 M€ [1].\n"
           "Il emploie 6 500 personnes.\n"
           "La marge serait de 12 % `[HYP]`.\n"
           "| Taille | 40 000 clients | [2] |\n"
           "|---|---|---|\n"
           "Voir [9].\n")
    r = audit(doc, src, pages_max=1)
    assert r["unknown_citations"] == [9], r
    assert r["uncited_sources"] == [], r
    assert [w["ligne"] for w in r["warnings"]] == [3], r  # seul « 6 500 » est non sourcé
    assert r["hyp"] == 1 and not r["ok"]
    # listes et plages à l'intérieur des crochets
    assert citations("selon [1, 2] et [3–5]") == {1, 2, 3, 4, 5}
    r = audit("Les sources [1, 2] et [3–5] disent 40 %.", src)
    assert r["unknown_citations"] == [3, 4, 5] and not r["warnings"], r
    # bibliographie au format « [n] … »
    assert audit("Le CA est de 120 M€ [1].", "[1] Exemple SA. (2025). Rapport annuel.\n")["ok"]
    print("selftest OK")


def main():
    if "--selftest" in sys.argv:
        return selftest()
    ap = argparse.ArgumentParser(description="Contrôles automatiques de l'Auditeur sur un fichier Markdown.")
    ap.add_argument("fichier", help="fichier Markdown à auditer")
    ap.add_argument("--sources", help="bibliographie Markdown (lignes « | n | … »)")
    ap.add_argument("--pages", type=float, help="nombre de pages maximal autorisé")
    ap.add_argument("--mots-par-page", type=int, default=300, help="mots par page (défaut : 300)")
    ap.add_argument("--json", action="store_true", help="sortie JSON au lieu du rapport")
    a = ap.parse_args()
    try:
        text = open(a.fichier, encoding="utf-8").read()
        src = open(a.sources, encoding="utf-8").read() if a.sources else None
    except OSError as e:
        sys.exit(f"Erreur : impossible de lire le fichier ({e.filename}) : {e.strerror}")
    r = audit(text, src, a.pages, a.mots_par_page)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        rapport(r, src is not None, a.pages, a.mots_par_page)
    sys.exit(0 if r["ok"] else 1)


if __name__ == "__main__":
    main()
