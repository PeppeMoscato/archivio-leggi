from datetime import date

import pytest

from archivio.catalogo import numero_pulito, unisci_pubblicazioni
from archivio.governi import carica as carica_governi
from archivio.governi import governo_alla_data
from archivio.modelli import Atto, Nota, Riferimento
from archivio.note import PRONUNCIA, cita_conversione, classifica
from archivio.pipeline import riga_legge, unisci
from archivio.relazioni import Risolutore, conversioni_dai_titoli, convertito_dal_titolo, data_decadenza, relazioni_di, stato_di
from archivio.storia import chiave_urn, leggi_storie
from fixture_export import aggiornamento, articolo, metadati, scrivi_export

MERLONI = "urn:nir:stato:legge:1994-02-11;109"
CODICE_APPALTI = "urn:nir:stato:decreto.legislativo:2006-04-12;163"
RDC = "urn:nir:stato:decreto.legge:2019-01-28;4"
CONVERSIONE_RDC = "urn:nir:stato:legge:2019-03-28;26"


def atto(urn: str, tipo: str = "legge", **campi) -> Atto:
    base = dict(urn=urn, tipo=tipo, numero="1", data=date(2003, 1, 16), titolo="Titolo")
    return Atto(**(base | campi))


# --- note --------------------------------------------------------------------


# Note reali, dalla sonda del 27/10/2026.
@pytest.mark.parametrize(
    ("testo", "attese"),
    [
        ("ha disposto (con l'art. 2268, comma 1) l'abrogazione dell'intero provvedimento.",
         [("abroga", "art. 2268, comma 1", None)]),
        ("Il D.L.25 giugno 2008, n.112 (in S.O. n.152 relativo alla G.U. 25/6/2008, n. 147) convertito, con modificazioni, "
         "dalla L. 6 agosto 2008, n. 133 (in S.O. n. 196, relativo alla G.U. 21/8/2008, n. 195) ha disposto (con l'art. 24) "
         "l'abrogazione dell' intero provvedimento.",
         [("abroga", "art. 24", None)]),
        (", convertito, con modificazioni, dalla L. 6 agosto 2008, n. 133 (in S.O. n. 196, relativo alla G.U. 21/8/2008, n. 195) "
         "ha confermato (con l'art. 24) l'abrogazione dell'intero provvedimento.",
         [("abroga", "art. 24", None)]),
        ("ha disposto (con l'art. 11, comma 5, lettera c)) l'abrogazione del comma 14 dell'art. 10.",
         [("abroga_parziale", "art. 11, comma 5, lettera c)", "comma 14 dell'art. 10")]),
        ("ha disposto (con l'art. 12, comma 1) la modifica dell'art. 26, comma 1.",
         [("modifica", "art. 12, comma 1", "art. 26, comma 1")]),
        (", di conversione,ha disposto (con l'art. 1, comma 1) l'introduzione dell'art. 4-sexies.",
         [("modifica", "art. 1, comma 1", "art. 4-sexies")]),
        ("ha disposto (con l'art. 1, comma 1) la conversione, con modificazioni, del D.L. 16 luglio 2020, n. 76 "
         "(in S.O. n. 24, relativo alla G.U. 16/07/2020, n. 178).",
         [("converte", "art. 1, comma 1", None)]),
        ("ha disposto (con l'art. 24, comma 1) la modifica dell'art. 51, comma 1-bis; (con l'art. 24, comma 2) "
         "l'introduzione del comma 1-ter all'art. 51; (con l'art. 24, comma 5) la modifica dell'art. 51, commi 1-bis e 1-ter.",
         [("modifica", "art. 24, comma 1", "art. 51, comma 1-bis"),
          ("modifica", "art. 24, comma 2", "comma 1-ter all'art. 51"),
          ("modifica", "art. 24, comma 5", "art. 51, commi 1-bis e 1-ter")]),
        (", convertito con modificazioni dalla L. 23 luglio 2021, n. 106 (in S.O. n. 25, relativo alla G.U. 24/07/2021, n. 176), "
         "nel modificare l'art. 43-bis, comma 1 del D.Lgs. 28 febbraio 2021, n. 40 (in G.U. 19/03/2021, n. 68) ha "
         "conseguentemente disposto (con l'art. 10, comma 13-quater, lettera f)) la modifica dell'art. 20.",
         [("modifica", "art. 10, comma 13-quater, lettera f)", "art. 20")]),
        ("convertito con modificazioni dalla L. 3 agosto 1998, n. 267, (in G.U. 7/8/1998 n. 183) ha disposto "
         "(con l'art. 6-bis, comma 1)la modifica dell'art. 15-sexies, comma 3.",
         [("modifica", "art. 6-bis, comma 1", "art. 15-sexies, comma 3")]),
        ("ha disposto (con gli artt. 7, comma 1) la modifica dell'art. 7 comma 1.",
         [("modifica", "artt. 7, comma 1", "art. 7 comma 1")]),
        ("ha disposto (con l'art. 1, comma 1) la modifica delle tabelle dalla 1 alla 15.",
         [("modifica", "art. 1, comma 1", "tabelle dalla 1 alla 15")]),
        ("Il D.L. 30 dicembre 2005, n. 273 ha disposto (con l'art. 1, comma 1) la proroga del termine previsto dall'art. 3.",
         [("proroga", "art. 1, comma 1", "termine previsto dall'art. 3")]),
        ("La L. 4 aprile 2012, n. 35 ha disposto la conversione in legge, con modificazioni, del D.L. 9 febbraio 2012, n. 5.",
         [("converte", None, None)]),
        # "conversione" in una citazione non è una conversione (L. 241/1990, 30/10/2026).
        ("Il D.L. 9 febbraio 2012, n. 5, convertito con modificazioni dalla L. 4 aprile 2012, n. 35, ha disposto "
         "(con l'art. 62, comma 2) che \"Le disposizioni di cui al comma 1 si applicano dalla data di entrata in vigore "
         "della legge di conversione del presente decreto\".",
         [("modifica", None, None)]),
        ("ha disposto (con l'art. 3, comma 1) la modifica dell'art. 2, comma 2, nel testo risultante dalla legge di conversione.",
         [("modifica", "art. 3, comma 1", "art. 2, comma 2, nel testo risultante dalla legge di conversione")]),
    ],
)
def test_classifica_note(testo, attese):
    esiti = classifica(testo)
    assert [(e.tipo, e.articolo_origine, e.articolo_destinazione) for e in esiti] == attese


@pytest.mark.parametrize(
    ("testo", "articolo"),
    [
        ("ha dichiarato l'illegittimita' costituzionale dell'art. 10, comma 6.", "art. 10, comma 6"),
        ("ha dichiarato l'illegittimità costituzionale dell'art. 21-bis, comma 1.", "art. 21-bis, comma 1"),
    ],
)
def test_classifica_pronuncia(testo, articolo):
    (esito,) = classifica(testo)
    assert (esito.tipo, esito.articolo_destinazione, esito.numero_sentenza) == (PRONUNCIA, articolo, None)


# --- governi -----------------------------------------------------------------


def test_governi_contigui_e_assegnazione():
    governi = carica_governi()
    for precedente, successivo in zip(governi, governi[1:]):
        assert precedente.fine == successivo.inizio
    assert governi[-1].fine is None
    assert governo_alla_data(governi, date(2003, 1, 16)) == "berlusconi-2"
    assert governo_alla_data(governi, date(1994, 2, 11)) == "ciampi"
    assert governo_alla_data(governi, date(2019, 1, 28)) == "conte-1"
    # Il giorno del giuramento conta per il governo nuovo; prima, affari correnti del vecchio.
    assert governo_alla_data(governi, date(2011, 11, 16)) == "monti"
    assert governo_alla_data(governi, date(1992, 5, 1)) == "andreotti-7"
    assert governo_alla_data(governi, date(1980, 1, 1)) is None


# --- catalogo ----------------------------------------------------------------


def test_doppia_pubblicazione_tiene_la_piu_vecchia():
    originale = atto(RDC, "decreto-legge", gazzetta_data=date(2019, 1, 28), gazzetta_numero=23)
    seconda = atto(RDC, "decreto-legge", gazzetta_data=date(2019, 4, 9), gazzetta_numero=84)
    assert unisci_pubblicazioni([seconda, originale])[RDC].gazzetta_numero == 23


def test_numero_pulito():
    assert numero_pulito("1 (Raccolta 2019)") == "1"
    assert numero_pulito("326") == "326"


# --- storia (export) ---------------------------------------------------------


def test_leggi_storie(tmp_path):
    percorso = scrivi_export(
        tmp_path / "export.zip",
        [
            {
                "cartella": "merloni",
                "metadati": metadati(MERLONI, "LEGGE", "109", "19940211", "si", [
                    aggiornamento("ha disposto (con l'art. 256, comma 1) l'abrogazione dell'intero provvedimento.",
                                  "006G0181", "20060502", "art_256"),
                ]),
                "versioni": [None, "1995-06-02", "2006-07-01"],
                "articoli": [articolo("1", "19940304"), articolo("2", "19940219")],
            },
            {
                "cartella": "DECRETO-LEGGE_19950107_1",
                "metadati": metadati("urn:nir:stato:decreto.legge:1995-01-07;1", "DECRETO-LEGGE", "1", "1995-01-07", "si")
                | {"titoloDoc": "Disciplina operativa ... (095G0013)\nEntrata in vigore del decreto: 8/1/1995.Decreto-Legge decaduto per mancata conversione."},
                "versioni": [None, "1995-03-09", "1996-03-09"],
                "articoli": [articolo("1", "1995-01-08") | {"dataVigoreVersione": [{"inizioVigore": "1995-01-08", "fineVigore": "1995-03-08"}]}],
            },
        ],
    )
    merloni, decreto = sorted(leggi_storie(percorso), key=lambda s: s.urn, reverse=True)
    assert merloni.urn == MERLONI
    assert (merloni.abrogato, merloni.decaduto) == (True, False)
    assert merloni.versioni == 3
    assert merloni.data_abrogazione == date(2006, 7, 1)
    assert merloni.data_entrata_vigore == date(1994, 2, 19)
    (nota,) = merloni.note
    assert nota.riferimenti == (Riferimento("006G0181", date(2006, 5, 2), "art_256"),)
    # Decaduto: la data viene dalla fine di vigenza del testo originale, non dall'ultima versione.
    assert decreto.decaduto is True
    assert decreto.data_entrata_vigore == date(1995, 1, 8)
    assert decreto.data_abrogazione == date(1995, 3, 9)


def test_unisci_conta_discrepanze():
    from archivio.storia import Storia

    catalogo = {MERLONI: atto(MERLONI), RDC: atto(RDC, "decreto-legge")}
    storie = [Storia(MERLONI, "LEGGE", "109", None, True, False, 3, date(2006, 7, 1), None)]
    uniti, conti = unisci(catalogo, storie, abrogati={MERLONI, RDC})
    per_urn = {a.urn: a for a in uniti}
    assert per_urn[MERLONI].abrogato is True
    assert per_urn[RDC].abrogato is True  # nessun export: vale la classe della ricerca
    assert conti == {"senza_export": 1}


def test_chiave_urn_canonica():
    assert chiave_urn("URN:NIR:STATO:LEGGE:1994-02-11;109") == MERLONI


# --- relazioni e stato -------------------------------------------------------


class ClientFinto:
    def __init__(self):
        self.chiamate = []

    def dettaglio_da_gazzetta(self, codice, giorno):
        from normattiva import NotFoundError

        self.chiamate.append(codice)
        raise NotFoundError("assente")


def test_relazioni_risolte_dal_catalogo_e_deduplicate():
    nota = Nota(
        "Il D.Lgs. 12 aprile 2006, n. 163 ha disposto (con l'art. 256, comma 1) l'abrogazione dell'intero provvedimento.",
        (Riferimento("006G0181", date(2006, 5, 2)),),
    )
    merloni = atto(MERLONI, abrogato=True, note=[nota, nota])
    risolutore = Risolutore({("006G0181", date(2006, 5, 2)): (CODICE_APPALTI, "decreto legislativo")}, {})
    relazioni, pronunce = relazioni_di(merloni, risolutore)
    assert len(relazioni) == 1 and not pronunce
    assert relazioni[0].urn_origine == CODICE_APPALTI
    assert relazioni[0].tipo == "abroga"
    assert relazioni[0].data == date(2006, 5, 2)
    assert stato_di(merloni, relazioni) == "abrogata"


def test_riferimento_sconosciuto_va_in_cache_una_volta():
    client, salvati = ClientFinto(), []
    risolutore = Risolutore({}, {}, client, lambda *riga: salvati.append(riga))
    riferimento = Riferimento("99X00001", date(2010, 1, 1))
    assert risolutore.risolvi(riferimento) is None
    assert risolutore.risolvi(riferimento) is None
    assert client.chiamate == ["99X00001"]
    assert salvati == [("99X00001", date(2010, 1, 1), None, None)]


def test_decreto_legge_abrogato_senza_conversione_e_decaduto():
    assert stato_di(atto(RDC, "decreto-legge", abrogato=True, decaduto=True), []) == "decaduta"
    dl = atto(RDC, "decreto-legge", abrogato=True)  # senza export: decaduto se manca la conversione
    assert stato_di(dl, []) == "decaduta"
    conversione = Nota(
        "La L. 28 marzo 2019, n. 26 ha disposto (con l'art. 1, comma 1) la conversione con modificazioni del D.L. 28 gennaio 2019, n. 4.",
        (Riferimento("19G00033", date(2019, 3, 29)),),
    )
    dl.note = [conversione]
    relazioni, _ = relazioni_di(dl, Risolutore({("19G00033", date(2019, 3, 29)): (CONVERSIONE_RDC, "legge")}, {}))
    assert relazioni[0].tipo == "converte" and relazioni[0].urn_origine == CONVERSIONE_RDC
    assert stato_di(dl, relazioni) == "abrogata"
    dl.decaduto = False
    assert stato_di(dl, []) == "abrogata"
    dl.abrogato = False
    assert stato_di(dl, relazioni) == "vigente"


def test_converte_solo_verso_decreti_legge():
    # La L. 241/1990 risultava "convertita": su un atto che non è un D.L. la conversione diventa una modifica.
    legge = atto("urn:nir:stato:legge:1990-08-07;241")
    legge.note = [
        Nota("La L. 4 aprile 2012, n. 35 ha disposto (con l'art. 1, comma 1) la conversione, con modificazioni, del D.L. 9 febbraio 2012, n. 5.",
             (Riferimento("12G00055", date(2012, 4, 6)),)),
    ]
    relazioni, _ = relazioni_di(legge, Risolutore({}, {}))
    assert [r.tipo for r in relazioni] == ["modifica"]
    assert stato_di(legge, relazioni) == "vigente"


def test_cita_conversione():
    assert cita_conversione("ha disposto (con l'art. 2) che \"... dalla legge di conversione del presente decreto\".")
    assert not cita_conversione("ha disposto (con l'art. 1, comma 1) la conversione, con modificazioni, del D.L. 9 febbraio 2012, n. 5.")
    assert not cita_conversione(", di conversione, ha disposto (con l'art. 1, comma 1) l'introduzione dell'art. 4-sexies.")


def test_citazione_della_legge_di_conversione_non_salva_il_decreto_decaduto():
    dl = atto("urn:nir:stato:decreto.legge:1995-01-07;1", "decreto-legge", data=date(1995, 1, 7), gazzetta_data=date(1995, 1, 7),
              abrogato=True, decaduto=None)
    dl.note = [
        Nota("Il D.L. 7 marzo 1995, n. 66 ha disposto (con l'art. 1, comma 2) che \"restano validi gli atti adottati sulla base del "
             "D.L. 7 gennaio 1995, n. 1, fino alla data di entrata in vigore della legge di conversione del presente decreto\".",
             (Riferimento("095G0090", date(1995, 3, 8)),)),
    ]
    relazioni, _ = relazioni_di(dl, Risolutore({}, {}))
    assert [r.tipo for r in relazioni] == ["modifica"]
    assert stato_di(dl, relazioni) == "decaduta"


def test_decreto_legge_decaduto_senza_frase_nel_titolo():
    # Come nell'export del 27/10/2026: titolo senza "decaduto", testo originale in vigore per 60 giorni.
    dl = atto(
        "urn:nir:stato:decreto.legge:1995-01-07;1", "decreto-legge", data=date(1995, 1, 7), gazzetta_data=date(1995, 1, 7),
        abrogato=True, decaduto=False, fine_vigore_originale=date(1995, 3, 8), data_abrogazione=date(1996, 3, 9),
    )
    assert stato_di(dl, []) == "decaduta"
    assert data_decadenza(dl) == date(1995, 3, 9)
    assert riga_legge(dl, "decaduta", carica_governi()).data_abrogazione == date(1995, 3, 9)
    # Convertito, o abrogato quando il testo originale valeva da anni: non è decaduto.
    dl.fine_vigore_originale = date(1999, 1, 1)
    assert stato_di(dl, []) == "abrogata"


@pytest.mark.parametrize(
    ("titolo", "atteso"),
    [
        ("Conversione in legge, con modificazioni, del decreto-legge 28 gennaio 2019, n. 4, recante disposizioni urgenti "
         "in materia di reddito di cittadinanza e di pensioni.", "urn:nir:stato:decreto.legge:2019-01-28;4"),
        ("Conversione in legge del decreto-legge 1° marzo 1995, n. 58, recante ...", "urn:nir:stato:decreto.legge:1995-03-01;58"),
        ("Conversione in legge, con\nmodificazioni, del decreto-legge 7 gennaio 1995, n. 1", "urn:nir:stato:decreto.legge:1995-01-07;1"),
        ("Disposizioni per disincentivare l'esodo del personale militare.", None),
    ],
)
def test_convertito_dal_titolo(titolo, atteso):
    assert convertito_dal_titolo(titolo) == atteso


def test_conversione_dal_titolo_evita_la_decadenza():
    legge = atto(CONVERSIONE_RDC, "legge", titolo="Conversione in legge, con modificazioni, del decreto-legge 28 gennaio 2019, n. 4.",
                 gazzetta_data=date(2019, 3, 29), gazzetta_codice="19G00033")
    conversione = conversioni_dai_titoli([legge])[RDC]
    assert (conversione.urn_origine, conversione.tipo, conversione.data) == (CONVERSIONE_RDC, "converte", date(2019, 3, 29))
    dl = atto(RDC, "decreto-legge", data=date(2019, 1, 28), abrogato=True, decaduto=False, fine_vigore_originale=date(2019, 3, 29))
    assert stato_di(dl, []) == "decaduta"
    assert stato_di(dl, [conversione]) == "abrogata"


def test_riga_legge():
    governi = carica_governi()
    merloni = atto(MERLONI, data=date(1994, 2, 11), abrogato=True, data_abrogazione=date(2006, 7, 1))
    riga = riga_legge(merloni, "abrogata", governi)
    assert riga.link_normattiva == "https://www.normattiva.it/uri-res/N2Ls?" + MERLONI
    assert riga.data_abrogazione == date(2006, 7, 1)
    assert riga.governo_id == "ciampi"
    assert riga_legge(merloni, "vigente", governi).data_abrogazione is None


def test_atto_json_andata_e_ritorno():
    originale = atto(MERLONI, abrogato=True, note=[Nota("testo", (Riferimento("X", date(2006, 5, 2), "art_1"),))])
    assert Atto.da_json(originale.in_json()) == originale


# --- estrazione completa, con un client finto ---------------------------------


class ClienteNormattivaFinto:
    """Risponde come Normattiva per le leggi del 2003: due atti, uno abrogato."""

    def __init__(self, cartella):
        self.cartella = cartella

    def ricerca_avanzata(self, *, denominazione, anno, classe=None, pagina=1, per_pagina=20, **_):
        from normattiva import AttoTrovato, EsitoRicerca, EstremiAtto, PubblicazioneGazzetta

        if denominazione != "LEGGE":
            return EsitoRicerca((), 0)
        atti = [
            AttoTrovato(EstremiAtto("LEGGE", date(2003, 1, 16), "3"), PubblicazioneGazzetta(date(2003, 1, 20), 15, "003G0007"), "Sirchia"),
            AttoTrovato(EstremiAtto("LEGGE", date(2003, 12, 22), "365"), PubblicazioneGazzetta(date(2004, 1, 7), 4, "003G0396"), "Esodo"),
        ]
        if classe is not None:
            atti = atti[1:]
        return EsitoRicerca(tuple(atti), len(atti))

    def start_export(self, **criteri):
        cartella = self.cartella

        class Export:
            def wait(self, timeout):
                return None

            def save(self, percorso):
                return scrivi_export(percorso, [
                    {"cartella": "LEGGE_20030116_3", "metadati": metadati("urn:nir:stato:legge:2003-01-16;3", "LEGGE", "3", "2003-01-16"),
                     "versioni": [None], "articoli": [articolo("1", "2003-02-04")]},
                    {"cartella": "LEGGE_20031222_365",
                     "metadati": metadati("urn:nir:stato:legge:2003-12-22;365", "LEGGE", "365", "2003-12-22", "si", [
                         aggiornamento("ha disposto (con l'art. 2268, comma 1) l'abrogazione dell'intero provvedimento.", "010G0091", "20100508")]),
                     "versioni": [None, "2010-10-09"], "articoli": [articolo("1", "2004-01-22")]},
                ])

        return Export()


def test_estrai_scrive_un_jsonl_per_anno(tmp_path):
    from archivio.pipeline import estrai, leggi_atti

    rapporto = estrai(ClienteNormattivaFinto(tmp_path), [2003], tmp_path / "dati")
    atti = {a.numero: a for a in leggi_atti(tmp_path / "dati")}
    assert set(atti) == {"3", "365"}
    assert atti["3"].abrogato is False and atti["3"].data_entrata_vigore == date(2003, 2, 4)
    assert atti["365"].abrogato is True and atti["365"].data_abrogazione == date(2010, 10, 9)
    assert atti["365"].note[0].riferimenti[0].codice == "010G0091"
    assert "2003 LEGGE: 2 atti, export 2, abrogati 1" in rapporto.testo()


def test_leggi_storie_salta_i_file_vuoti(tmp_path):
    import zipfile

    percorso = scrivi_export(
        tmp_path / "export.zip",
        [{"cartella": "merloni", "metadati": metadati(MERLONI, "LEGGE", "109", "19940211"), "versioni": [None, "2006-07-01"],
          "articoli": [articolo("1", "19940219")]}],
    )
    with zipfile.ZipFile(percorso, "a") as archivio:
        archivio.writestr("merloni/merloni_VIGENZA_2010-01-01_V3.json", "")
        archivio.writestr("vuoto/vuoto_ORIGINALE_V1.json", "")
    (storia,) = list(leggi_storie(percorso))
    assert storia.urn == MERLONI
    assert storia.versioni == 3
