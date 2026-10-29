from archivio.premesse import premessa_da_html

# HTML reale del testo originale del D.L. 223/2006 (sonda contesto del 29/10/2026), accorciato dopo l'art. 1.
DL_223_2006 = """<div class="bodyTesto">
        <h2 class="preamble-title-akn">IL PRESIDENTE DELLA REPUBBLICA</h2>
        <div class="preamble-citations-akn">
            <citations eId="cits_1">
                <citation eId="cits_1__cit_1">
                    <div class="preamble-citation-akn">Visti gli <a href="http://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:costituzione:1947-12-27~art77" target="_blank">articoli 77</a> e <a href="http://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:costituzione:1947-12-27~art87" target="_blank">87 della Costituzione</a>;</div>
                </citation>
            </citations>
        </div>
        <div>
            <div class="preamble-text-akn">Ritenuta la straordinaria necessit&agrave; ed urgenza di rafforzare la libera scelta dei consumatori e di rendere pi&ugrave; concorrenziali gli assetti di mercato, favorendo anche il rilancio dell'economia e dell'occupazione;</div>
        </div>
        <div>
            <div class="preamble-text-akn">Ritenuta altres&igrave; la straordinaria necessit&agrave; ed urgenza di adottare interventi intesi a razionalizzare e contenere i livelli di spesa pubblica, nonch&egrave; in tema di entrate e di contrasto all'evasione ed elusione fiscale;</div>
        </div>
        <div class="preamble-citations-akn">
            <citations eId="cits_2">
                <citation eId="cits_2__cit_1">
                    <div class="preamble-citation-akn">Vista la deliberazione del Consiglio dei Ministri, adottata nella riunione del 30 giugno 2006;</div>
                </citation>
            </citations>
        </div>
        <div>
            <div class="preamble-text-akn">Sulla proposta del Presidente del Consiglio dei Ministri, del Ministro dell'economia e delle finanze e del Ministro dello sviluppo economico;</div>
        </div>
        <h2 class="preamble-end-akn">Emana</h2>
        <p class="formula-introduttiva"> il seguente decreto-legge:</p>
        <h2 class="article-num-akn" id="art_1">Art. 1</h2>
        <div class="art-commi-div-akn"><div class="art-comma-div-akn"><span class="comma-num-akn">1. </span>
        <span class="art_text_in_comma">Le norme del presente titolo ...<br></span></div></div>
</div>"""

# HTML reale della L. 76/2016: nessuna premessa, solo la formula.
L_76_2016 = """<div class="bodyTesto">
        <div class="preamble-before-title-akn">La Camera dei deputati ed il Senato della Repubblica hanno approvato;</div>
        <h2 class="preamble-title-akn">IL PRESIDENTE DELLA REPUBBLICA</h2>
        <h2 class="preamble-end-akn">Promulga</h2>
        <p class="formula-introduttiva"> la seguente legge:</p>
        <h2 class="article-num-akn" id="art_1">Art. 1</h2>
</div>"""

# Forma di un decreto legislativo, con le stesse classi del D.L. (testo del D.Lgs. 23/2015).
DLGS = """<div class="bodyTesto">
    <div class="preamble-citation-akn">Visti gli articoli 76 e 87 della Costituzione;<br/></div>
    <div class="preamble-citation-akn">Vista la <a href="http://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:2014-12-10;183">legge 10 dicembre 2014, n. 183</a>, recante deleghe al Governo in materia di riforma degli ammortizzatori sociali;</div>
    <div class="preamble-citation-akn">Visto l'<a href="http://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1988-08-23;400~art14">articolo 14 della legge 23 agosto 1988, n. 400</a>;</div>
    <div class="preamble-text-akn">Sulla proposta del Presidente del Consiglio dei ministri e del Ministro del lavoro e delle politiche sociali;</div>
    <h2 class="preamble-end-akn">Emana</h2>
    <div class="preamble-citation-akn">Visto dopo la fine: non fa parte della premessa;</div>
</div>"""


def test_decreto_legge_motivazioni_e_citazioni():
    premessa = premessa_da_html(DL_223_2006)
    assert premessa.motivazioni == [
        "Ritenuta la straordinaria necessità ed urgenza di rafforzare la libera scelta dei consumatori e di rendere "
        "più concorrenziali gli assetti di mercato, favorendo anche il rilancio dell'economia e dell'occupazione;",
        "Ritenuta altresì la straordinaria necessità ed urgenza di adottare interventi intesi a razionalizzare e "
        "contenere i livelli di spesa pubblica, nonchè in tema di entrate e di contrasto all'evasione ed elusione fiscale;",
    ]
    assert premessa.citazioni == [
        "Visti gli articoli 77 e 87 della Costituzione;",
        "Vista la deliberazione del Consiglio dei Ministri, adottata nella riunione del 30 giugno 2006;",
    ]
    assert premessa.proposta.startswith("Sulla proposta del Presidente del Consiglio dei Ministri, del Ministro dell'economia")
    assert premessa.urn_delega == []


def test_legge_ordinaria_senza_premessa():
    assert premessa_da_html(L_76_2016).vuota


def test_decreto_legislativo_legge_delega():
    premessa = premessa_da_html(DLGS)
    assert premessa.motivazioni == []
    assert len(premessa.citazioni) == 3
    assert premessa.urn_delega == ["urn:nir:stato:legge:2014-12-10;183"]
    assert "fine" not in " ".join(premessa.citazioni)
