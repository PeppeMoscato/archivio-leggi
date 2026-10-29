-- Dati per le prove dell'API. Le prime tre leggi sono vere (titolo, data, Gazzetta); il decreto-legge, le relazioni,
-- la pronuncia, l'iter, i senatori e i voti sono inventati: servono solo a provare le query.

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

INSERT INTO fase_iter (id, iter_id, progressivo, ramo, numero, titolo, data_presentazione, stato, data_stato, fonte_url) VALUES
    ('senato:15001', 'senato:15000', 2, 'camera', 'C.2122', NULL, '2001-12-10', 'approvato con modificazioni', '2002-10-17', 'http://dati.senato.it/ddl/15001'),
    ('senato:15002', 'senato:15000', 1, 'senato', 'S.795', NULL, '2001-09-12', 'approvato', '2001-11-28', 'http://dati.senato.it/ddl/15002');

INSERT INTO parlamentare (id, codice, ramo, nome, cognome, fonte_url) VALUES
    (1, 'senato:1', 'senato', 'Mario', 'Rossi', 'http://dati.senato.it/senatore/1'),
    (2, 'senato:2', 'senato', 'Anna', 'Bianchi', 'http://dati.senato.it/senatore/2');

INSERT INTO firmatario (fase_id, nome, tipo, primo_firmatario, parlamentare_id) VALUES
    ('senato:15002', 'Firmatario di prova (Gov. Berlusconi-II)', 'governativa', true, NULL);

INSERT INTO votazione (id, fase_id, ramo, legislatura, data, tipo, descrizione, esito, presenti, votanti, favorevoli, contrari,
                       astenuti, maggioranza, voti_favorevoli, voti_contrari, voti_astenuti, fonte_url) VALUES
    ('senato:v1', 'senato:15002', 'senato', 14, '2001-11-28', 'finale', 'Disegno di legge n. 795. Votazione finale', 'approvato',
     2, 2, 1, 1, 0, 2, '{1}', '{2}', '{}', 'http://dati.senato.it/votazione/1'),
    ('senato:v2', 'senato:15002', 'senato', 14, '2001-11-27', 'emendamento', 'Emendamento 1.1', 'respinto',
     NULL, NULL, NULL, NULL, NULL, NULL, '{}', '{}', '{}', 'http://dati.senato.it/votazione/2');
