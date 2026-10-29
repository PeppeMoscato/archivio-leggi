"""Prove offline: come si legge il campo di ricerca."""

import pytest

from archivio_api.query import CampoRicerca, interpreta


@pytest.mark.parametrize(
    ("q", "atteso"),
    [
        (None, CampoRicerca()),
        ("   ", CampoRicerca()),
        ("fumo locali pubblici", CampoRicerca(parole="fumo locali pubblici")),
        ("urn:nir:stato:legge:1990-08-07;241", CampoRicerca(urn="urn:nir:stato:legge:1990-08-07;241")),
        ("3/2003", CampoRicerca(numero="3", anno=2003)),
        ("L. 3/2003", CampoRicerca(tipo="legge", numero="3", anno=2003)),
        ("legge n. 3/2003", CampoRicerca(tipo="legge", numero="3", anno=2003)),
        ("d.lgs. 81/2008", CampoRicerca(tipo="decreto legislativo", numero="81", anno=2008)),
        ("D.Lgs n 81 / 2008", CampoRicerca(tipo="decreto legislativo", numero="81", anno=2008)),
        ("decreto-legge n. 18/2020", CampoRicerca(tipo="decreto-legge", numero="18", anno=2020)),
        ("DL 18/2020", CampoRicerca(tipo="decreto-legge", numero="18", anno=2020)),
        ("l. cost. 1/2001", CampoRicerca(tipo="legge costituzionale", numero="1", anno=2001)),
        ("sicurezza lavoro 81/2008", CampoRicerca(parole="sicurezza lavoro", numero="81", anno=2008)),
    ],
)
def test_interpreta(q, atteso):
    assert interpreta(q) == atteso
