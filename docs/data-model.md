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
- Un reader non supportato per la build del save (es. `officials` su FM27 27.0.1) viene registrato come `unsupported` e saltato. La sua tabella resta vuota ma esiste.
- Un import viene rifiutato (`ImportRejected`) se:
  - l'edizione è diversa da quella della carriera (FM26 contro FM27);
  - quello stesso file è già stato importato (stesso SHA-256);
  - la data di gioco non è successiva a quella dell'ultimo import;
  - la carriera è stata creata con un formato di database precedente (`schema_version`).

  I controlli completi di continuità arrivano con lo Step 4.

## Una tabella per ogni tipo di record fmsave

Il database contiene **una tabella fisica per ogni tipo di record fmsave**, con lo stesso nome del tipo nella documentazione di fmsave. Raggruppate come nella documentazione:

| Gruppo | Tabelle |
|---|---|
| Persone | `Player`, `Attributes`, `Ability`, `Reputation`, `Positions`, `Personality`, `Contract`, `Clause`, `ContractChainEntry`, `PlayerSuspension`, `Suspension`, `Staff`, `StaffAttributes`, `StaffPreferences`, `StaffList` |
| Club | `Club`, `Team`, `ClubFacilities`, `Stadium`, `FinanceMonth`, `Sponsorship`, `AffiliateGroup`, `JobVacancy` |
| Nazioni | `Nation` |
| Competizioni | `Stage`, `Competition`, `Fixture`, `Official`, `LeagueTable`, `LeagueTableSplit`, `LeagueTableMatch`, `LeagueTableRow`, `TransferWindow`, `CompetitionRules`, `RulesRound`, `PlayerMatchStats`, `TeamMatchStats` |
| Statistiche stagionali | `PlayerSeasonStats`, `PlayerSeasonHistory` |
| Infortuni | `InjuryType`, `InjuryRecord` |
| Solo club allenato | `ManagedClub`, `Tactic`, `TacticSlot`, `TacticSettingUnit`, `SetPieceRoutine`, `Selection`, `TeamTraining`, `TrainingSchedule`, `TrainingWeek`, `TrainingDay`, `MentoringGroup`, `SquadPlannerSlot` |
| Salvataggio | `SaveInfo` (metadati del save, uno per import), `Fm27Span` (record grezzi sperimentali FM27) |

### Colonne

Le colonne di ogni tabella sono **esattamente** `fmsave.export.column_names(<tipo>)`, nello stesso ordine, e i valori sono quelli di `fmsave.export.flat_rows(..., json_ready=True)`: le stesse righe piatte che dà `Table.to_pandas()`. Quindi:
- i gruppi sono colonne con prefisso (`Player.attributes_finishing`, `LeagueTableRow.home_points`);
- i valori codificati sono `<campo>` (etichetta) e `<campo>_code` (numero grezzo);
- i campi calcolati di fmsave (es. `goals_per_90`) sono in fondo, come in fmsave;
- le liste (anche di record, es. `Club.teams`, `LeagueTable.rows`) e le mappe sono testo JSON; le date testo ISO; i booleani 0/1.

Prima delle colonne di fmsave ci sono le colonne tecniche, tutte con `_` iniziale:

| Colonna | Dove | Contenuto |
|---|---|---|
| `_rid` | tutte | id della riga, unico anche rispetto allo storico |
| `_key`, `_hash` | entità ed eventi | chiave e impronta usate per il confronto tra import |
| `_valid_from` | entità | import da cui la versione è valida |
| `_first_seen`, `_last_seen` | eventi | primo e ultimo import in cui l'evento compariva |
| `_import_id` | snapshot e "ultimo" | import da cui arriva la riga |
| `_parent_table`, `_parent_field`, `_parent_rid`, `_ord` | record annidati | il record che li contiene (`_parent_rid = <padre>._rid`), il campo e la posizione nella lista |

### Record annidati

Un record annidato è **sia** nelle colonne del padre (come fa fmsave) **sia** come riga della tabella del suo tipo, collegata al padre:
- `Attributes`: una riga per `Player.attributes` e una per `Player.raw_attributes` (`_parent_field`);
- `Ability` e `Personality`: righe di `Player` e di `Staff` (`_parent_table`);
- `LeagueTableSplit`: quattro righe per ogni `LeagueTableRow` (`home`, `away`, `first_half`, `second_half`);
- `LeagueTableRow` → `LeagueTable`, `LeagueTableMatch` → `LeagueTableRow`, `Team` → `Club`, `Clause` e `ContractChainEntry` → `Contract`, `PlayerSuspension` → `Player`, `RulesRound` → `CompetitionRules`, `TacticSlot` → `Tactic`, `TacticSettingUnit` → `TacticSlot`, `TrainingWeek` e `TrainingSchedule` → `TeamTraining`, `TrainingDay` → `TrainingWeek`.

Eccezione: `Player.contract` resta solo nelle colonne `contract_*` di `Player`, perché gli stessi contratti sono già le righe di `Contract` (lette da `Save.contracts()`).

### Stato attuale e storico (`backend/fmsa/ingest/readers.py`)

Ogni tabella contiene lo **stato attuale**. Quello che gli import precedenti avevano e che poi è cambiato non si perde:

| Tipo | Tabelle | Comportamento |
|---|---|---|
| **entità** | `Player`, `Contract`, `Staff`, `Club`, `ClubFacilities`, `Stadium`, `Nation`, `Competition`, `Stage`, `Official`, `InjuryType` | Una versione per chiave. Se qualcosa cambia, la versione vecchia (con i suoi record annidati) passa in `<Tipo>_history`, con `_valid_to` = import che l'ha sostituita. Lo stesso per chi sparisce dal save. |
| **evento** | `Fixture`, `PlayerSeasonHistory`, `InjuryRecord`, `Suspension`, `FinanceMonth`, `PlayerMatchStats`, `TeamMatchStats` | Si accumulano nella tabella import dopo import, deduplicati per chiave, perché ogni save conserva solo una finestra temporale. Un evento che cambia (una partita poi giocata) viene aggiornato. |
| **snapshot** | `LeagueTable`, `CompetitionRules`, `Sponsorship`, `StaffList`, `JobVacancy`, `SaveInfo`, … | La tabella contiene la copia dell'ultimo import; le copie precedenti passano in `<Tipo>_history`. |
| **ultimo** | `PlayerSeasonStats` | Resta solo l'ultimo import. Le stagioni concluse sono già in `PlayerSeasonHistory`. |

Per entità e snapshot la vista `<Tipo>_all` unisce stato attuale e storico (per esempio la progressione di CA e attributi in `Player_all`).

Chiavi delle entità/eventi principali:
- `Player` e `Staff`: (`uid`, `birth_date`). Così un regen che eredita l'uid di un ritirato diventa una persona nuova.
- `Fixture`: (`date`, `home_team_id`, `away_team_id`).
- `PlayerSeasonHistory`: (`player_uid`, `season_year`, `club_uid`, `kind`, `competition_reference`).

Se nello stesso import ci sono righe con la stessa chiave, ricevono un ordinale, così i duplicati identici restano distinti.

### Tabelle vuote

Una tabella vuota vuol dire che fmsave non ha restituito record per quel save:
- le tabelle "Solo club allenato" sono vuote se nel save l'allenatore non ha un club;
- `SquadPlannerSlot` non è supportata da fmsave 0.12.2 su FM26 (`UnsupportedGameError`, registrato nel log);
- `PlayerMatchStats`: sui save FM26 di test fmsave 0.12.2 restituisce 0 righe anche chiamato direttamente; `fmsave validate` riporta che nessun giocatore ha uno storico partite non vuoto (`history_nonempty: 0`).

## Tabelle di sistema

| Tabella | Contenuto |
|---|---|
| `_meta` | edizione (`game`), data di creazione, nome del primo save, stringa di configurazione della partita |
| `_imports` | un record per import: file, SHA-256, build, data di gioco, `summary_strings`, versioni di fmsave e dell'app, durata |
| `_import_readers` | esito di ogni reader in ogni import: righe, nuove, aggiornate, invariate, chiuse, tempo, avvisi |
| `_import_log` | log dettagliato: per ogni reader **e per ogni tabella di destinazione** (figlie comprese) chiamata fmsave, inizio, fine lettura e fine con i millisecondi, ms di lettura e di scrittura, righe lette, inserite, aggiornate, invariate e chiuse, esito e messaggi |
| `_tables`, `_columns` | catalogo di tabelle e colonne: reader, tipo di memorizzazione, tabelle padre, percorso del campo fmsave (`Player.ability.potential`) e suo stato (verified/unconfirmed/computed). Lo usano query builder, mascheramento e AI. |

## Misure (FM27, 3 stagioni)

Ogni import richiede circa 2 minuti. Il file `.fmsa` occupa 180 MB dopo il primo import e 630 MB dopo il terzo.

## Accesso in sola lettura e mascheramento (Step 5)

Ogni query dell'interfaccia, delle dashboard e degli assistenti AI passa da `ReadOnlySession` (`backend/fmsa/query/session.py`), che ha tre protezioni indipendenti:

1. il file viene aperto con `mode=ro`;
2. `PRAGMA query_only = ON`;
3. un **authorizer SQLite** che permette solo la lettura (SELECT, lettura di colonne, funzioni, CTE ricorsive) e rifiuta tutto il resto prima che venga eseguito: INSERT/UPDATE/DELETE, CREATE/DROP/ALTER, ATTACH, PRAGMA, transazioni, `load_extension`.

È ammessa una sola istruzione per query. Ogni query ha inoltre un limite di tempo (30 s) e di righe (10.000 di default, 200.000 al massimo).

**Mascheramento** (`backend/fmsa/query/masking.py`): le regole sono legate ai percorsi dei campi fmsave (`_columns.source_path`), quindi valgono per ogni tabella che contiene quel campo (`players`, `staff` e i loro storici `_all`). Le colonne nascoste risultano **NULL ovunque compaiano**: in SELECT, WHERE, ORDER BY, JOIN, aggregazioni e sottoquery. Non si possono ricavare filtrando o ordinando.

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
