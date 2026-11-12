# Step 0 – Risultati dello spike su fmsave

Data: 2026-11-12 · fmsave 0.12.2 · Python 3.13 · 13 save analizzati.

| Carriera | File | Build | Date di gioco |
|---|---|---|---|
| FM26 | `Season 1.fm` … `Season 10.fm` (150–300 MB) | 26.3.2+2329565 (`known_build=True`) | 2026-06-15 → 2035-06-15 |
| FM27 | `FM27 Season 1.fm` … `Season 3.fm` (115–155 MB) | 27.0.1+2494687 (`known_build=False`) | 2027-06-15 → 2029-06-15 |

Strumenti (ripetibili su nuovi save/versioni di fmsave):
- `spikes/inspect_save.py <save> <out>`: legge tutti i reader e produce lo schema appiattito, i tempi, la memoria e le colonne chiave.
- `spikes/compare_saves.py <out> <stem1> <stem2> …`: confronta save consecutivi (stabilità degli id, sovrapposizione degli eventi).
- `spikes/model_docs.py > docs/fmsave-models.md`: genera il riferimento di tutti i 60 tipi di record (tipo, stato verified/unconfirmed, descrizione).

L'output grezzo è in `spikes/out/` (ignorato da git: contiene dati dei save).

## 1. Copertura dei reader

| Reader | Righe FM26 S1 → S10 | Righe FM27 S3 | Note |
|---|---|---|---|
| players / contracts | 114k → 119k | 86k | 52 attributi, CA/PA, posizioni, tratti, contratto annidato |
| staff / staff_lists | 33k → 13k | 20k | il calo nel tempo è da capire (persone create/ritirate?) |
| clubs | 28 422 | 20 883 | insieme fisso per tutta la carriera |
| competitions / stages | 2.4k / 5.4k → 2.6k / 6.6k | 2.3k / 6.2k | `database_id` → nome dal DB anagrafiche |
| fixtures | 33k → 46k | 45k | solo una finestra temporale (vedi §3) |
| player_season_stats | 329k → 417k | 280k | stagione in corso, per giocatore × tipo competizione × club |
| player_season_history | 59k → **1,7 M** | 399k | cresce con la carriera: è il reader più pesante |
| injuries | 38k → 78k | 59k | finestra di circa 2 anni |
| league_tables, finances, sponsorships, facilities, stadiums, nations, … | OK | OK | |
| officials, team_match_stats | OK | **errore** | la build FM27 27.0.1 non è ancora registrata in fmsave |
| squad_planner | **errore** | **errore** | richiede un allenatore umano con un club |
| managed_clubs, training, mentoring, tactics, set_pieces, selections, player_match_stats | 0 righe | 0 righe | allenatore disoccupato: da riverificare con una carriera vera |

Avvisi ricevuti: `UnknownBuildWarning` su FM27 27.0.1 e alcuni `ReaderCheckWarning` (sponsorships, player_season_stats) da segnalare a fmsave.
**Conseguenza:** l'importatore deve tollerare i reader non supportati (tabella vuota + stato registrato in `imports`) e mostrare all'utente la copertura per ogni import.

## 2. Stabilità degli identificatori (decisiva per l'import incrementale)

| Id | Risultato tra save consecutivi della stessa carriera |
|---|---|
| `clubs.uid` ↔ `unique_id`, nome | identici al 100% in tutte le coppie (anche S1 → S10) |
| `nations.nation_id`, `competitions.id`, `stages.id` | stabili al 100%; i nuovi id vengono solo aggiunti |
| `players`/`staff`: `unique_id → uid` | **100%**: una persona del DB di gioco tiene sempre lo stesso uid |
| `players.uid → stessa persona` | 99,3–99,7%: **lo 0,3–0,7% degli uid viene riusato** |

Il riuso riguarda i giocatori generati (regen): quando uno si ritira, il suo `uid` **e** il suo `unique_id` vengono dati a un nuovo giocatore (es. uid 2000434080: "Regan Whelpdale" nato nel 2009 → "Anwar Sanusi" nato nel 2018). Tra S9 e S10 i casi sono 732.

**Decisione per lo Step 2:** la chiave di una persona nel nostro DB è una chiave surrogata `person_key` assegnata alla prima comparsa di (`uid`, `birth_date`). Se un uid ricompare con un'altra data di nascita, nasce una nuova persona. Tutte le tabelle collegate (contratti, statistiche, infortuni, storico) si agganciano a `person_key` tramite l'uid **del save in cui sono state lette**.

## 3. Finestre di conservazione dei dati nel save

| Dato | Cosa resta nel save | Coppie consecutive: righe di A ancora in B |
|---|---|---|
| fixtures giocate | dal 1° gennaio dell'anno precedente fino alla data del save (~18 mesi) | 28–40%, **punteggi identici al 100%** |
| fixtures future | fino a ~2,5 anni avanti | — |
| injuries | ~2 anni | 50–93% |
| suspensions | quelle in corso o recenti | 27–52% |
| player_season_history | tutte le stagioni dall'inizio della carriera (non si perde nulla di rilevante) | 92–94%, valori identici al 99,9% |
| player_season_stats | solo la stagione in corso | i valori cambiano (atteso) |
| attributi, CA/PA, valore | fotografia alla data del save | CA/PA invariati solo per il 33–43% |

Tra S1 e S10 le partite e gli infortuni in comune sono **zero**.

**Conseguenze:**
- Il DB di FMSaveAnalyst diventa **più completo di ogni singolo save**: partite e infortuni vanno accumulati import dopo import.
- Rilevamento dei buchi: se la prima partita giocata del nuovo save è successiva all'ultima partita importata, mancano dei dati. L'app avvisa, ma l'import resta possibile. Indicazione all'utente: importare almeno una volta per stagione.
- Chiavi naturali verificate:
  - fixtures: (`date`, `home_team_id`, `away_team_id`), 0 duplicati.
  - player_season_history: (`player_uid`, `season_year`, `club_uid`, `kind`, `competition_reference`) ha il 2–4% di righe **identiche duplicate** (più spezzoni nella stessa stagione). Serve un ordinale nella chiave.
  - injuries: (`player_uid`, `date`, `type_id`) ha pochi duplicati, quindi va aggiunto un ordinale.
- Tabelle a snapshot (Step 2): players (attributi/CA/PA/valore/condizione), contracts, staff, clubs (reputazione), finances, league_tables, player_season_stats.

## 4. Segnali per il controllo di continuità (Step 4)

Tutti verificati sulle due carriere:
1. **Stessa edizione/build compatibile** (`info.game`, `info.build`, `db_version`).
2. **Data di gioco successiva** a quella dell'ultimo import.
3. **`summary_strings`**: contengono il nome del manager ("Giorgio Gandolfi"), i campionati caricati e una stringa di configurazione della partita (es. `765,MALE,5,0,769,…`) che resta identica per tutta la carriera.
4. **Mappa club `uid → unique_id`**: identica al 100% per tutta la carriera, anche a 9 stagioni di distanza.
5. **Partite già importate**: quelle che cadono nella finestra del nuovo save devono avere stessa data, stesse squadre e stesso risultato (decine di migliaia di confronti, 100% di corrispondenza).
6. **Storico stagionale**: le stagioni passate devono coincidere al ≥ 99%.

Limite di questo spike: non c'era una **seconda carriera diversa della stessa versione**. Serve per verificare che i segnali 3–4 distinguano davvero due carriere nuove avviate dallo stesso database (è possibile che anche gli uid dei club coincidano). In quel caso il segnale 5 resta comunque decisivo.

## 5. Prestazioni e memoria

- Apertura del save: ~0,02 s; copia in temp: < 0,1 s (SSD).
- Lettura di tutti i reader: 50–60 s (FM27), 60–115 s (FM26 S1 → S10). I reader più lenti sono players (~20 s) e player_season_history (47 s a S10).
- Memoria: fmsave **tiene in cache tutte le tabelle lette finché il save è aperto**. Con lo spike, che in più accumula le colonne chiave, il picco va da 1,6 GB (FM27 S1) a **7,4 GB** (FM26 S10). Solo player_season_history, a S10, aggiunge ~1,6 GB.

**Decisioni per lo Step 2:**
- Import per gruppi di reader, con save riaperto per ogni gruppo e scrittura in SQLite a blocchi (`executemany` in transazione). Obiettivo: picco < 2,5 GB anche con save da 10+ stagioni.
- Lo storico stagionale è già nel DB dopo il primo import, quindi negli import successivi si inseriscono solo le righe nuove.
- Import in background con barra di avanzamento per reader: la durata realistica è 1–3 minuti.

## 6. Dati "spoiler" da mascherare (Step 5)

Presenti e leggibili: `ability.current` e `ability.potential` (marcati *unconfirmed*), i 52 attributi (inclusi quelli nascosti) e `personality.*`. Su FM27 alcuni giocatori hanno `personality = None`: va gestito come blocco opzionale. L'elenco completo dei campi con il loro stato è in `docs/fmsave-models.md`.

## 7. Da segnalare/approfondire con fmsave (possibili PR o issue)
- Registrazione della build FM27 27.0.1+2494687 (officials, team_match_stats, squad_planner).
- `ReaderCheckWarning` su sponsorships (FM27) e player_season_stats (FM27 S3).
- Opzione per non tenere in cache le tabelle (o `Save.release(reader)`), per contenere la memoria.
- Il calo del numero di staff (33k → 13k) nel corso della carriera: è un fatto del gioco o un limite del reader?
