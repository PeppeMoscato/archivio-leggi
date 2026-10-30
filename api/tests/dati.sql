-- Dati per le prove dell'API. Le prime tre leggi sono vere (titolo, data, Gazzetta); il decreto-legge, le relazioni,
-- la pronuncia, l'iter, i senatori, i gruppi e i voti sono inventati: servono solo a provare le query.

INSERT INTO governo (id, nome, presidente, inizio, fine, fonte_url) VALUES
    ('andreotti-6', 'Andreotti VI', 'Giulio Andreotti', '1989-07-22', '1991-04-12', 'https://www.senato.it/legislature/repubblica/governi-della-repubblica'),
    ('berlusconi-2', 'Berlusconi II', 'Silvio Berlusconi', '2001-06-11', '2005-04-23', 'https://www.senato.it/legislature/repubblica/governi-della-repubblica'),
    ('prodi-2', 'Prodi II', 'Romano Prodi', '2006-05-17', '2008-05-08', 'https://www.senato.it/legislature/repubblica/governi-della-repubblica');

INSERT INTO governo_partito (governo_id, partito, ruolo, fonte_url) VALUES
    ('berlusconi-2', 'Forza Italia', 'governo', 'https://example.org/fonte');

INSERT INTO legge (urn, tipo, numero, data, titolo, link_normattiva, stato, data_abrogazione, data_entrata_vigore,
                   gazzetta_data, gazzetta_numero, gazzetta_codice, governo_id) VALUES
    ('urn:nir:stato:legge:1990-08-07;241', 'legge', '241', '1990-08-07',
     'Nuove norme in materia di procedimento amministrativo e di diritto di accesso ai documenti amministrativi.',
     'https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1990-08-07;241', 'vigente', NULL, '1990-09-03',
     '1990-08-18', 192, '090G0294', 'andreotti-6'),
    ('urn:nir:stato:legge:2003-01-16;3', 'legge', '3', '2003-01-16',
     'Disposizioni ordinamentali in materia di pubblica amministrazione.',
     'https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:2003-01-16;3', 'vigente', NULL, '2003-02-05',
     '2003-01-20', 15, '003G0007', 'berlusconi-2'),
    ('urn:nir:stato:decreto.legislativo:2008-04-09;81', 'decreto legislativo', '81', '2008-04-09',
     'Attuazione dell''articolo 1 della legge 3 agosto 2007, n. 123, in materia di tutela della salute e della sicurezza nei luoghi di lavoro.',
     'https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2008-04-09;81', 'vigente', NULL, '2008-05-15',
     '2008-04-30', 101, '008G0104', 'prodi-2'),
    ('urn:nir:stato:decreto.legge:2003-01-02;1', 'decreto-legge', '1', '2003-01-02',
     'Decreto-legge di prova non convertito.',
     'https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legge:2003-01-02;1', 'decaduta', '2003-03-04', '2003-01-03',
     '2003-01-02', 1, '003G0001', 'berlusconi-2');

INSERT INTO relazione_normativa (urn_origine, urn_destinazione, tipo, data, articolo_origine, articolo_destinazione, nota,
                                 origine_gazzetta_codice, origine_gazzetta_data) VALUES
    ('urn:nir:stato:legge:2003-01-16;3', 'urn:nir:stato:legge:1990-08-07;241', 'modifica', '2003-01-20', 'art. 21', 'art. 2',
     'Nota di prova: modifica dell''art. 2.', '003G0007', '2003-01-20'),
    (NULL, 'urn:nir:stato:legge:1990-08-07;241', 'modifica', '1999-01-05', NULL, 'art. 19',
     'Nota di prova: atto di origine fuori dal perimetro.', '099G0001', '1999-01-05'),
    ('urn:nir:stato:legge:2003-01-16;3', 'urn:nir:stato:decreto.legislativo:2008-04-09;81', 'abroga_parziale', '2009-01-01', NULL, 'art. 5',
     'Nota di prova con abrogazione parziale.', '003G0007', '2003-01-20');

INSERT INTO pronuncia_costituzionale (urn_legge, articolo, numero_sentenza, anno, data_gazzetta, gazzetta_codice, nota) VALUES
    ('urn:nir:stato:legge:1990-08-07;241', 'art. 4', NULL, 1995, '1995-11-22', '095C1234', 'ha dichiarato l''illegittimita'' costituzionale dell''art. 4.');

INSERT INTO iter (id, urn, legislatura, natura, titolo, iniziativa, data_presentazione, data_approvazione, numero_legge, data_legge, fonte_url) VALUES
    ('senato:15000', 'urn:nir:stato:legge:2003-01-16;3', 14, 'ordinaria', 'Disposizioni ordinamentali in materia di pubblica amministrazione',
     'governativa', '2001-09-12', '2002-12-18', 3, '2003-01-16', 'http://dati.senato.it/ddl/15000');

INSERT INTO fase_iter (id, iter_id, progressivo, ramo, numero, titolo, data_presentazione, stato, data_stato, fonte_url,
                       testo_presentato) VALUES
    ('senato:15001', 'senato:15000', 2, 'camera', 'C.2122', NULL, '2001-12-10', 'approvato con modificazioni', '2002-10-17', 'http://dati.senato.it/ddl/15001', NULL),
    ('senato:15002', 'senato:15000', 1, 'senato', 'S.795', NULL, '2001-09-12', 'approvato', '2001-11-28', 'http://dati.senato.it/ddl/15002',
     'urn:nir:senato.repubblica:disegno.legge:14.legislatura;795');

-- Premessa inventata, nella forma reale (D.L. 223/2006).
INSERT INTO premessa (urn, motivazioni, citazioni, proposta, fonte_url) VALUES
    ('urn:nir:stato:decreto.legge:2003-01-02;1',
     ARRAY['Ritenuta la straordinaria necessità ed urgenza di adottare misure di prova;'],
     ARRAY['Visti gli articoli 77 e 87 della Costituzione;', 'Vista la deliberazione del Consiglio dei Ministri, adottata nella riunione del 30 dicembre 2002;'],
     'Sulla proposta del Presidente del Consiglio dei Ministri;',
     'https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legge:2003-01-02;1');

INSERT INTO parlamentare (id, codice, ramo, nome, cognome, fonte_url) VALUES
    (1, 'senato:1', 'senato', 'Mario', 'Rossi', 'http://dati.senato.it/senatore/1'),
    (2, 'senato:2', 'senato', 'Anna', 'Bianchi', 'http://dati.senato.it/senatore/2'),
    (3, 'senato:3', 'senato', 'Luca', 'Verdi', 'http://dati.senato.it/senatore/3'),
    (4, 'senato:4', 'senato', 'Sara', 'Neri', 'http://dati.senato.it/senatore/4');

-- Il gruppo 1 ha cambiato nome nel 2006; il 2 non ha denominazioni (vale il nome in `gruppo`).
INSERT INTO gruppo (id, ramo, nome, sigla) VALUES
    ('senato:g1', 'senato', 'Nuovo nome del gruppo', 'NNG'),
    ('senato:g2', 'senato', 'Gruppo misto', 'MISTO');

INSERT INTO denominazione_gruppo (gruppo_id, inizio, fine, nome, sigla) VALUES
    ('senato:g1', '2001-05-30', '2006-04-27', 'Vecchio nome del gruppo', 'VNG'),
    ('senato:g1', '2006-04-28', NULL, 'Nuovo nome del gruppo', 'NNG');

-- La senatrice 2 passa dal gruppo 1 al 2 proprio il giorno del voto finale: vale l'adesione più recente.
-- Il senatore 3 non ha adesioni.
INSERT INTO adesione_gruppo (parlamentare_id, gruppo_id, inizio, fine) VALUES
    (1, 'senato:g1', '2001-05-30', NULL),
    (2, 'senato:g1', '2001-05-30', '2001-11-28'),
    (2, 'senato:g2', '2001-11-28', NULL),
    (4, 'senato:g1', '2001-05-30', NULL);

INSERT INTO firmatario (fase_id, nome, tipo, primo_firmatario, parlamentare_id) VALUES
    ('senato:15002', 'Firmatario di prova (Gov. Berlusconi-II)', 'governativa', true, NULL);

INSERT INTO votazione (id, fase_id, ramo, legislatura, data, tipo, descrizione, esito, presenti, votanti, favorevoli, contrari,
                       astenuti, maggioranza, voti_favorevoli, voti_contrari, voti_astenuti, fonte_url) VALUES
    ('senato:14/1', 'senato:15002', 'senato', 14, '2001-11-28', 'finale', 'Disegno di legge n. 795. Votazione finale', 'approvato',
     4, 4, 2, 1, 1, 3, '{1,4}', '{2}', '{3}', 'http://dati.senato.it/votazione/14/1'),
    ('senato:v2', 'senato:15002', 'senato', 14, '2001-11-27', 'emendamento', 'Emendamento 1.1', 'respinto',
     NULL, NULL, NULL, NULL, NULL, NULL, '{}', '{}', '{}', 'http://dati.senato.it/votazione/2');
