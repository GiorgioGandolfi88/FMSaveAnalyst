# Dashboard

Le dashboard incluse sono in `backend/fmsa/dashboards/defs/` (una per file JSON). Puoi aggiungerne di tue, o sostituire quelle incluse, mettendo file JSON nella sottocartella `dashboards` della cartella dati dell'app:
- `%APPDATA%\FMSaveAnalyst\dashboards\`;
- oppure `data\dashboards\` in modalità portabile.

Un file con lo stesso `id` di una dashboard inclusa la sostituisce. I file non validi vengono ignorati e l'errore finisce nel log.

## Creare, modificare, eliminare dall'app

Nella pagina Dashboard: **Nuova dashboard**, oppure il menu "…" di ogni dashboard (**Modifica**, **Duplica**, **Elimina**, **Ripristina predefinita**). L'editor ha un modulo (titoli IT/EN, filtri, valori modificabili, widget con SQL) e una vista **JSON**. **Prova** esegue le query senza salvare e mostra righe ed errori sotto ogni widget.
- Le dashboard tue vengono salvate come `<id>.json` nella cartella `dashboards`.
- Modificare una dashboard inclusa crea una tua copia con lo stesso `id`, che la sostituisce.
- Eliminare una dashboard inclusa la nasconde (elenco in `dashboards\_hidden.json`). **Ripristina predefinita** cancella la tua copia e la fa ricomparire così com'è nell'app.
- Eliminare una dashboard tua cancella il file.

## Formato

```json
{
  "id": "mia_dashboard",
  "order": 50,
  "title": {"it": "Titolo", "en": "Title"},
  "description": {"it": "…", "en": "…"},
  "params": ["club"],
  "widgets": [
    {"id": "n", "type": "kpi", "span": 3, "format": "int",
     "title": {"it": "Giocatori", "en": "Players"},
     "sql": "SELECT count(*) AS value FROM players WHERE club_uid = :club"},
    {"id": "ca", "type": "bar", "span": 6, "horizontal": true, "x": "name", "y": "ability_current",
     "title": {"it": "Abilità attuale", "en": "Current ability"},
     "sql": "SELECT name, ability_current FROM players WHERE club_uid = :club ORDER BY 2 DESC LIMIT 20"}
  ]
}
```

- **`params`**: i filtri mostrati sopra la dashboard. I valori possibili sono `club`, `competition`, `season`, `nation` e `league`. Nell'SQL si usano come `:club`, `:competition`, `:season`, `:nation` e `:league`. `nation` (nazione del club) e `league` (lega) sono facoltativi: valgono `NULL` quando l'utente sceglie "Tutte", quindi nell'SQL si scrivono come `(:nation IS NULL OR club_nation_id = :nation)`. Nelle dashboard con `club` la nazione e la lega compaiono comunque, per restringere l'elenco dei club. È sempre disponibile anche `:today`, la data di gioco dell'ultimo import.
- **`inputs`**: numeri che l'utente può cambiare (soglie, età, mesi, quanti giocatori mostrare). Esempio: `{"id": "min_ca", "default": 120, "min": 1, "max": 200, "label": {"it": "Abilità attuale minima", "en": "Minimum current ability"}}`. Nell'SQL si usa `:min_ca` (anche in `LIMIT :top`); nei titoli dei widget `{min_ca}` mostra il valore scelto. Il pulsante accanto ai campi ripristina i valori predefiniti.
- **`span`**: la larghezza del widget su 12 colonne.
- **Tipi di widget**:

| `type` | Campi | Risultato atteso dalla query |
|---|---|---|
| `kpi` | `format`: `int`, `decimal`, `money` (compatto) o `text` | una riga, colonna `value` |
| `table` | — | qualsiasi |
| `bar` | `x`, `y` (una colonna o una lista), `horizontal`, `stacked` | una riga per categoria |
| `line` | `x`, `y`; `series` per il formato lungo; `invert_y` (es. posizioni in classifica) | una riga per punto |
| `scatter` | `x`, `y`, `label` | una riga per punto |

Ogni widget passa dalla sessione in sola lettura: il mascheramento vale anche qui (le colonne nascoste risultano vuote) e ogni query ha un limite di 5.000 righe.

Ogni grafico ha la vista tabella e l'esportazione in CSV, CSV per Excel o JSON. Con "Esporta dashboard (ZIP)" si ottiene invece un file per widget, più i parametri usati.

## Grafici

I colori seguono la palette di riferimento validata dello skill `dataviz`:
- 8 colori categoriali, sempre nello stesso ordine;
- tonalità separate per il tema chiaro e per quello scuro;
- al massimo 6 serie per i grafici a linee;
- un solo asse;
- barre larghe al massimo 24 px, con l'estremità arrotondata;
- legenda solo quando ci sono almeno due serie;
- tooltip al passaggio del mouse.

Tre colori chiari (acqua, giallo, magenta) hanno un contrasto inferiore a 3:1 sullo sfondo chiaro: per questo ogni grafico ha la vista tabella.
