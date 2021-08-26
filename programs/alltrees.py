import sys
import os

from tf.fabric import Fabric

from tree import Tree


GH = "~/github"
ORG = "etcbc"

TYPE_INFO = (
    ("word", ""),
    ("subphrase", "U"),
    ("phrase", "P"),
    ("clause", "C"),
    ("sentence", "S"),
)
TYPE_TABLE = dict(t for t in TYPE_INFO)
TYPE_ORDER = [t[0] for t in TYPE_INFO]


POS_TABLE = {
    "adjv": "aj",
    "adjective": "aj",
    "advb": "av",
    "adverb": "av",
    "art": "dt",
    "article": "dt",
    "conj": "cj",
    "conjunction": "cj",
    "inrg": "ir",
    "interrogative": "ir",
    "intj": "ij",
    "interjection": "ij",
    "nega": "ng",
    "negative": "ng",
    "nmpr": "n-pr",
    "pronoun": "pr",
    "prde": "pr-dem",
    "prep": "pp",
    "preposition": "pp",
    "prin": "pr-int",
    "prps": "pr-ps",
    "subs": "n",
    "noun": "n",
    "verb": "vb",
}

CCR_INFO = {
    "Adju": ("r", "Cadju"),
    "Appo": ("r", "Cappo"),
    "Attr": ("r", "Cattr"),
    "Cmpl": ("r", "Ccmpl"),
    "Coor": ("x", "Ccoor"),
    "CoVo": ("n", "Ccovo"),
    "Link": ("r", "Clink"),
    "Objc": ("r", "Cobjc"),
    "Para": ("r", "Cpara"),
    "PrAd": ("r", "Cprad"),
    "PreC": ("r", "Cprec"),
    "Pred": ("r", "Cpred"),
    "ReVo": ("n", "Crevo"),
    "Resu": ("n", "Cresu"),
    "RgRc": ("r", "Crgrc"),
    "Sfxs": ("r", "Csfxs"),
    "Spec": ("r", "Cspec"),
    "Subj": ("r", "Csubj"),
    "NA": ("n", "C"),
    "none": ("n", "C"),
}

EXPECTED_MISMATCHES = {
    "3": 13,
    "4": 3,
    "4b": 0,
    "2016": 0,
    "2017": 0,
    "2021": 0,
}

VERSIONS = ("3", "4", "4b", "2016", "2017", "2021")


def setVersion(version):
    bhsa = f"bhsa/tf/{version}"
    tfDir = f"{GH}/{ORG}/trees/tf/{version}"

    os.makedirs(tfDir, exist_ok=True)

    sp = "part_of_speech" if version == "3" else "sp"
    rela = "clause_constituent_relation" if version == "3" else "rela"
    ptyp = "phrase_type" if version == "3" else "typ"
    ctyp = "clause_atom_type" if version == "3" else "typ"
    g_word_utf8 = "text" if version == "3" else "g_word_utf8"

    class C:
        pass

    setattr(C, "bhsa", bhsa)
    setattr(C, "tfDir", tfDir)
    setattr(C, "sp", sp)
    setattr(C, "rela", rela)
    setattr(C, "ptyp", ptyp)
    setattr(C, "ctyp", ctyp)
    setattr(C, "g_word_utf8", g_word_utf8)

    return C


def genTrees(version):
    C = setVersion(version)
    bhsa = C.bhsa
    sp = C.sp
    rela = C.rela
    ptyp = C.ptyp
    ctyp = C.ctyp
    g_word_utf8 = C.g_word_utf8
    tfDir = C.tfDir

    TF = Fabric(locations=f"{GH}/{ORG}", modules=bhsa)
    api = TF.load(f"{sp} {rela} {ptyp} {ctyp} {g_word_utf8} mother")

    E = api.E
    F = api.F
    Fs = api.Fs

    def getTag(node):
        otype = F.otype.v(node)
        tag = TYPE_TABLE[otype]
        if tag == "P":
            tag = Fs(ptyp).v(node)
        elif tag == "C":
            tag = ccrTable[Fs(rela).v(node)]
        isWord = tag == ""
        pos = POS_TABLE[Fs(sp).v(node)] if isWord else None
        slot = node if isWord else None
        text = f'"{Fs(g_word_utf8).v(node)}"' if isWord else None
        return (tag, pos, slot, text, isWord)

    def getTagN(node):
        otype = F.otype.v(node)
        tag = TYPE_TABLE[otype]
        if tag == "P":
            tag = Fs(ptyp).v(node)
        elif tag == "C":
            tag = ccrTable[Fs(rela).v(node)]
        isWord = tag == ""
        if not isWord:
            tag += "{" + str(node) + "}"
        pos = POS_TABLE[Fs(sp).v(node)] if isWord else None
        slot = node if isWord else None
        text = f'"{Fs(g_word_utf8).v(node)}"' if isWord else None
        return (tag, pos, slot, text, isWord)

    treeTypes = ("sentence", "clause", "phrase", "subphrase", "word")
    (rootType, leafType, clauseType, phraseType) = (
        treeTypes[0],
        treeTypes[-1],
        treeTypes[1],
        treeTypes[2],
    )
    ccrTable = dict((c[0], c[1][1]) for c in CCR_INFO.items())
    ccrClass = dict((c[0], c[1][0]) for c in CCR_INFO.items())

    tree = Tree(
        TF,
        otypes=treeTypes,
        phraseType=phraseType,
        clauseType=clauseType,
        ccrFeature=rela,
        ptFeature=ptyp,
        posFeature=sp,
        motherFeature="mother",
    )

    tree.restructureClauses(ccrClass)
    results = tree.relations()
    TF.info("Ready for processing")

    skip = set()
    TF.info("Verifying whether all slots are preserved under restructuring")
    TF.info(f"Expected mismatches: {EXPECTED_MISMATCHES.get(version, '??')}")

    errors = []
    # i = 10
    for snode in F.otype.s(rootType):
        declaredSlots = set(E.oslots.s(snode))
        results = {}
        thisgood = {}
        for kind in ("e", "r"):
            results[kind] = set(
                lt for lt in tree.getLeaves(snode, kind) if F.otype.v(lt) == leafType
            )
            thisgood[kind] = declaredSlots == results[kind]
            # if not thisgood[kind]:
            #    print(f"{kind} D={declaredSlots}\n  L={results[kind]}")
            #    i -= 1
        # if i == 0: break
        if False in thisgood.values():
            errors.append((snode, thisgood["e"], thisgood["r"]))
    nErrors = len(errors)
    if nErrors:
        TF.error(f"{len(errors)} mismatches:")
        mine = min(20, len(errors))
        skip |= {e[0] for e in errors}
        for (s, e, r) in errors[0:mine]:
            TF.error(
                (
                    f"{s} embedding: {'OK' if e else 'XX'};"
                    f" restructd: {'OK' if r else 'XX'}"
                ),
                tm=False,
            )
    else:
        TF.info(f"{len(errors)} mismatches")

    TF.info(f"Exporting {rootType} trees to TF")
    s = 0
    chunk = 10000
    sc = 0
    treeData = {}
    treeDataN = {}
    for node in F.otype.s(rootType):
        if node in skip:
            continue
        (treeRep, wordsRep, bSlot) = tree.writeTree(
            node, "r", getTag, rev=False, leafNumbers=True
        )
        (treeNRep, wordsNRep, bSlotN) = tree.writeTree(
            node, "r", getTagN, rev=False, leafNumbers=True
        )
        treeData[node] = treeRep
        treeDataN[node] = treeNRep
        s += 1
        sc += 1
        if sc == chunk:
            TF.info(f"{s} trees composed")
            sc = 0
    TF.info(f"{s} trees composed")

    nodeFeatures = dict(tree=treeData, treen=treeDataN)
    metaData = dict(
        tree=dict(
            valueType="str",
            description="penn treebank represententation for sentences",
            converter="Dirk Roorda",
            convertor="trees.ipynb",
            url="https://github.com/etcbc/trees/trees.ipynb",
            coreData="BHSA",
            coreVersion=version,
        ),
        treen=dict(
            valueType="str",
            description="penn treebank represententation for sentences with node numbers included",
            converter="Dirk Roorda",
            convertor="trees.ipynb",
            url="https://github.com/etcbc/trees/trees.ipynb",
            coreData="BHSA",
            coreVersion=version,
        ),
    )
    TF.info("Writing tree feature to TF")
    TFw = Fabric(locations=tfDir, silent=True)
    TFw.save(nodeFeatures=nodeFeatures, edgeFeatures={}, metaData=metaData)


def main():
    versions = VERSIONS if len(sys.argv) < 2 else sys.argv[1:]
    print(versions)
    for version in versions:
        genTrees(version)


if __name__ == "__main__":
    sys.exit(main())
