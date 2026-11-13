# Modello dati del database carriera (`.fmsa`)

Ogni carriera è un file SQLite separato. Lo crea e lo aggiorna solo l'importatore, `backend/fmsa/ingest/`. Tutto il resto dell'app lo apre in sola lettura.

## Import

```bash
uv run python -m fmsa.ingest "data/careers/Mia carriera.fmsa" "Season 1.fm" "Season 2.fm"
```

- Il save viene prima copiato in una cartella temporanea, calcolandone lo SHA-256. Il file originale non viene mai toccato.
- Ogni import è **un'unica transazione**: se qualcosa va storto, il database resta com'era.
- Ogni import scrive anche un file di testo con lo stesso dettaglio di `_import_log`, nella cartella `logs\imports` dei dati dell'app. Il file ha questo nome: `<carriera>_importNNN_<data-ora>.log`. Dall'app lo apri con il pulsante **Log** nello storico degli import.
- I reader vengono letti a gruppi, riaprendo il save per ogni gruppo, perché fmsave tiene in memoria tutte le tabelle lette.
- Un reader non supportato per la build del save (es. `officials` su FM27 27.0.1) viene registrato come `unsupported` e saltato. Le sue tabelle restano vuote ma esistono.
- Un import viene rifiutato (`ImportRejected`) se:
  - l'edizione è diversa da quella della carriera (FM26 contro FM27);
  - quello stesso file è già stato importato (stesso SHA-256);
  - la data di gioco non è successiva a quella dell'ultimo import;
  - la carriera è stata creata con un formato di database precedente (`schema_version`).

  I controlli completi di continuità arrivano con lo Step 4.

### Import parziale

Alla creazione della carriera e a ogni import si sceglie quali dati importare, per gruppi (Persone, Club, Nazioni, Competizioni e partite, Statistiche stagionali, Infortuni, Club allenato: `IMPORT_GROUPS` in `backend/fmsa/ingest/readers.py`) o, con **Avanzate**, reader per reader.
- I reader non scelti sono registrati in `_import_readers` con stato `skipped`. Le loro tabelle esistono comunque (vuote, se non sono mai state importate) e **conservano quello che avevano gli import precedenti**: un import parziale non cancella e non "chiude" niente.
- La scelta dell'ultimo import è in `_meta.import_readers` e viene riproposta all'import successivo.
- Esempio: solo classifiche e club su FM26 Season 1 richiede circa 10 secondi invece di circa 3,5 minuti.

### Rinomina ed eliminazione

Dalla pagina Carriere, menu "…":
- **Rinomina** cambia il nome della carriera (`_meta.career_name`) e anche il file `.fmsa`, le query salvate (`queries\`), la shortlist (`shortlists\`) e i log degli import (`logs\imports\`, con il percorso aggiornato in `_imports.log_file`).
- **Elimina** cancella definitivamente gli stessi file (prima li mostra). I save di Football Manager non vengono toccati.
- Entrambe le operazioni sono rifiutate mentre è in corso un import in quella carriera.

## Le tabelle: le stesse di `normalize()` in pandas

Le tabelle base sono **esattamente** i DataFrame che la funzione `normalize()` della guida (`guida_fmsave_tabelle.ipynb`) produce dai reader di fmsave, con `_` al posto del `.` nel nome:

- **una tabella per reader**, con lo stesso nome del reader (`players`, `clubs`, `league_tables`, …);
- **una tabella figlia per ogni campo che è una lista di sotto-record**, chiamata `<padre>_<campo>` (`league_tables.rows` → `league_tables_rows`, `league_tables.rows.matches` → `league_tables_rows_matches`). È ricorsivo.

Con fmsave 0.12.2 i 31 reader del notebook danno 44 tabelle; in più ci sono `team_match_stats` e `squad_planner` (solo FM27), per un totale di 46:

| Gruppo | Tabelle |
|---|---|
| Persone | `players`, `players_suspensions`, `contracts`, `contracts_clauses`, `contracts_chain`, `suspensions`, `staff`, `staff_lists` |
| Club | `clubs`, `clubs_teams`, `facilities`, `stadiums`, `finances`, `sponsorships`, `affiliates`, `job_vacancies` |
| Nazioni | `nations` |
| Competizioni | `stages`, `competitions`, `fixtures`, `officials`, `league_tables`, `league_tables_rows`, `league_tables_rows_matches`, `transfer_windows`, `competition_rules`, `competition_rules_rounds`, `player_match_stats`, `team_match_stats` |
| Statistiche stagionali | `player_season_stats`, `player_season_history` |
| Infortuni | `injury_types`, `injuries` |
| Solo club allenato | `managed_clubs`, `tactics`, `tactics_slots`, `tactics_slots_in_possession_settings`, `tactics_slots_out_of_possession_settings`, `set_pieces`, `selections`, `training`, `training_weeks`, `training_weeks_days`, `training_schedule_library`, `mentoring`, `squad_planner` |

I metadati del save (`Save.info`) sono in `_imports`, non in una tabella a parte.

### Colonne

Le colonne fmsave di ogni tabella sono `fmsave.export.column_names(<tipo>)` **senza** i campi lista-di-record (che sono le tabelle figlie), nello stesso ordine, con i valori di `fmsave.export.flat_rows(..., json_ready=True)`. Quindi, come in `to_pandas()` e in `normalize()`:
- i gruppi sono colonne con prefisso (`players.attributes_finishing`, `players.contract_wage`, `league_tables_rows.home_points`) e **non** sono tabelle a sé;
- i valori codificati sono `<campo>` (etichetta) e `<campo>_code` (numero grezzo);
- i campi calcolati di fmsave (es. `goals_per_90`) sono in fondo;
- le liste di valori semplici (es. `competitions.stage_ids`) e le mappe sono testo JSON; le date testo ISO; i booleani 0/1.

### Chiavi e join

Prima delle colonne fmsave ci sono le chiavi, come in `normalize()`:
- tabelle di un reader: `<reader>_idx`, la posizione del record nel reader;
- tabelle figlie: le chiavi di tutti i padri e poi `<campo>_idx`, la posizione nella lista (es. `league_tables_rows_matches`: `league_tables_idx`, `rows_idx`, `matches_idx`).

Ogni riga ha anche `_import_id`, l'import che l'ha scritta. Le chiavi `_idx` sono posizioni **dentro quell'import** (una riga che non cambia tra due import conserva il suo `_import_id` e il suo `_idx`), quindi **un figlio si collega al padre con `_import_id` + le chiavi `_idx` del padre**:

```sql
SELECT lt.competition_name, r.position, r.club_name, m.matches_idx, m.opponent_club_name, m.outcome
FROM league_tables lt
JOIN league_tables_rows r
  ON r._import_id = lt._import_id AND r.league_tables_idx = lt.league_tables_idx
JOIN league_tables_rows_matches m
  ON m._import_id = r._import_id AND m.league_tables_idx = r.league_tables_idx AND m.rows_idx = r.rows_idx
WHERE lt.competition_name = 'Serie A'
```

Le altre chiavi di join sono quelle di fmsave:

| Chiave | Dove si trova |
|---|---|
| `competitions.id` | `stages.competition_id`, `fixtures.competition_id`, `league_tables.competition_id`, `suspensions.competition_id`, `player_match_stats.competition_id` (id interno al save; `competitions.database_id` è l'id stabile del gioco) |
| `stages.id` | `fixtures.stage_id`, `competitions.stage_ids` (lista JSON) |
| `clubs_teams.team_id` | `league_tables_rows.team_id`, `fixtures.home_team_id/away_team_id`, `player_season_stats.team_id` |
| `clubs.uid` | `club_uid`, `home_club_uid`, … in quasi tutte le tabelle (`0` è un uid valido) |
| `players.uid` | `player_uid` (contracts, player_season_stats, injuries, …) |
| `officials.referee_id` | `fixtures.referee_id` |
| `nations.nation_id` | `clubs.nation_id`, `players` (`nations.database_id` è l'id stabile) |

Colonne tecniche (tutte con `_` iniziale): `_rid` (id interno della riga), `_import_id`, `_key` e `_hash` (entità ed eventi: confronto tra import, sempre nascoste), `_first_seen` / `_last_seen` (eventi: primo e ultimo import in cui compariva), `_valid_to` (solo `_history` / `_all`).

### Stato attuale e storico (`backend/fmsa/ingest/readers.py`)

Ogni tabella contiene lo **stato attuale**. Quello che gli import precedenti avevano e che poi è cambiato non si perde:

| Tipo | Reader | Comportamento |
|---|---|---|
| **entità** | `players`, `contracts`, `staff`, `clubs`, `facilities`, `stadiums`, `nations`, `competitions`, `stages`, `officials`, `injury_types` | Una versione per chiave. Se qualcosa cambia (anche in una tabella figlia), la versione vecchia con tutti i suoi figli passa in `<tabella>_history`, con `_valid_to` = import che l'ha sostituita. Lo stesso per chi sparisce dal save. |
| **evento** | `fixtures`, `player_season_history`, `injuries`, `suspensions`, `finances`, `player_match_stats`, `team_match_stats` | Si accumulano nella tabella import dopo import, deduplicati per chiave, perché ogni save conserva solo una finestra temporale. Un evento che cambia (una partita poi giocata) viene aggiornato. |
| **snapshot** | `league_tables`, `competition_rules`, `sponsorships`, `staff_lists`, `job_vacancies`, `transfer_windows`, … | La tabella contiene la copia dell'ultimo import; le copie precedenti passano in `<tabella>_history`. |
| **ultimo** | `player_season_stats` | Resta solo l'ultimo import. Le stagioni concluse sono già in `player_season_history`. |

Per entità e snapshot, **tabelle figlie comprese**, la vista `<tabella>_all` unisce stato attuale e storico (per esempio la progressione di CA e attributi in `players_all`, le classifiche di ogni import in `league_tables_all` + `league_tables_rows_all`). I join padre/figlio funzionano uguali anche sulle `_all`.

Chiavi delle entità/eventi principali:
- `players` e `staff`: (`uid`, `birth_date`). Così un regen che eredita l'uid di un ritirato diventa una persona nuova.
- `fixtures`: (`date`, `home_team_id`, `away_team_id`).
- `player_season_history`: (`player_uid`, `season_year`, `club_uid`, `kind`, `competition_reference`).

Se nello stesso import ci sono righe con la stessa chiave, ricevono un ordinale, così i duplicati identici restano distinti.

### Tabelle vuote

Una tabella vuota vuol dire che fmsave non ha restituito record per quel save:
- le tabelle "Solo club allenato" sono vuote se nel save l'allenatore non ha un club;
- `squad_planner` non è supportata da fmsave 0.12.2 su FM26 (`UnsupportedGameError`, registrato nel log);
- `player_match_stats`: sui save FM26 di test fmsave 0.12.2 restituisce 0 righe anche chiamato direttamente; `fmsave validate` riporta che nessun giocatore ha uno storico partite non vuoto (`history_nonempty: 0`).

## Tabelle di sistema

| Tabella | Contenuto |
|---|---|
| `_meta` | edizione (`game`), data di creazione, nome del primo save, stringa di configurazione della partita |
| `_imports` | un record per import: file, SHA-256, build, data di gioco, `summary_strings`, versioni di fmsave e dell'app, durata |
| `_import_readers` | esito di ogni reader in ogni import: righe, nuove, aggiornate, invariate, chiuse, tempo, avvisi |
| `_import_log` | log dettagliato: per ogni reader **e per ogni tabella di destinazione** (figlie comprese) chiamata fmsave, inizio, fine lettura e fine con i millisecondi, ms di lettura e di scrittura, righe lette, inserite, aggiornate, invariate e chiuse, esito e messaggi |
| `_tables`, `_columns` | catalogo di tabelle e colonne: reader, tipo di memorizzazione, tabella padre e colonne di join (`join_columns`), percorso del campo fmsave (`players.ability.potential`) e suo stato (verified/unconfirmed/computed). Lo usano query builder, mascheramento e AI. |

## Misure (FM27, 3 stagioni)

Ogni import richiede circa 2 minuti. Il file `.fmsa` occupa 180 MB dopo il primo import e 630 MB dopo il terzo.

## Accesso in sola lettura e mascheramento (Step 5)

Ogni query dell'interfaccia, delle dashboard e degli assistenti AI passa da `ReadOnlySession` (`backend/fmsa/query/session.py`), che ha tre protezioni indipendenti:

1. il file viene aperto con `mode=ro`;
2. `PRAGMA query_only = ON`;
3. un **authorizer SQLite** che permette solo la lettura (SELECT, lettura di colonne, funzioni, CTE ricorsive) e rifiuta tutto il resto prima che venga eseguito: INSERT/UPDATE/DELETE, CREATE/DROP/ALTER, ATTACH, PRAGMA, transazioni, `load_extension`.

È ammessa una sola istruzione per query. Ogni query ha inoltre un limite di tempo (30 s) e di righe (10.000 di default, 200.000 al massimo).

**Mascheramento** (`backend/fmsa/query/masking.py`): le regole sono legate ai percorsi dei campi fmsave (`_columns.source_path`, es. `players.ability.potential`), quindi valgono per ogni tabella che contiene quel campo (`players`, `staff` e i loro storici `_all`). Le colonne nascoste risultano **NULL ovunque compaiano**: in SELECT, WHERE, ORDER BY, JOIN, aggregazioni e sottoquery. Non si possono ricavare filtrando o ordinando.

| Impostazione | Campi nascosti |
|---|---|
| Potenziale (attiva di default) | `ability.potential`, `ability.potential_range_code` |
| Abilità attuale | `ability.current` |
| Attributi nascosti | `attributes.consistency`, `dirtiness`, `important_matches`, `injury_proneness`, `versatility` |
| Personalità | tutti i `personality.*` |
| Colonne extra | voci `tabella.colonna` scelte dall'utente |

Le colonne interne `_hash` e `_key` sono sempre nascoste, perché cambiano ogni volta che cambia un qualunque valore, compresi quelli nascosti.

Limite noto: nelle tabelle `_all`, un valore nascosto che cambia crea comunque una nuova versione del record. Si vede che qualcosa è cambiato, ma non cosa.

Nota: i valori che arrivano da enum testuali di fmsave sono salvati in minuscolo (es. `player_season_history.kind = 'league'`).
