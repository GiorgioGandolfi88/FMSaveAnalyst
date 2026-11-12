# Assistenti AI

## Configurazione

Nelle **Impostazioni → Assistenti AI** scegli il provider (Anthropic Claude, OpenAI o Google Gemini), il modello e la chiave API.

- **Chiave:** viene salvata cifrata nel **Gestore credenziali di Windows**, con nome `FMSaveAnalyst` e una voce per ogni provider. Non finisce mai in `settings.json`, nel database della carriera o nei log, e dopo il salvataggio non viene più mostrata.
- **Modello:** "Test connessione" mostra i modelli disponibili per la tua chiave. Per Claude, se il campo è vuoto, si usa `claude-opus-5-5`. Per OpenAI e Gemini il modello va indicato.

## Gli assistenti

| Assistente | Si occupa di |
|---|---|
| Analista | domande generali sui dati della carriera |
| Osservatore e mercato | obiettivi di mercato, giocatori a fine contratto, prestiti |
| Analista della rosa | copertura dei ruoli, profilo d'età, rinnovi e cessioni |
| Sviluppo giovani | crescita nel tempo (dallo storico degli import) |
| Direttore finanziario | saldo, budget, ingaggi, sponsor |
| Analista partite | risultati, classifiche, statistiche stagionali |

Ogni assistente lavora con tre strumenti, tutti in sola lettura:
- `list_tables`: elenca le tabelle disponibili;
- `describe_table`: mostra le colonne di una tabella;
- `run_sql`: esegue una query e restituisce al massimo 200 righe, ridotte se il testo supera i 24.000 caratteri.

Le query passano dalla stessa sessione usata dal resto dell'app: le colonne mascherate risultano vuote e non vengono mai inviate.

## Cosa viene inviato al provider

- Il prompt di sistema: nome della carriera, edizione, data di gioco, club allenato, quali dati sono nascosti e la lingua delle risposte.
- Le tue domande.
- I risultati delle query eseguite dall'assistente.

Con **"Chiedi conferma prima di inviare dati al provider"** (attiva di default), ogni volta vedi la query, un'anteprima delle righe e una stima dei token prima che i dati partano. Puoi scegliere **Invia** oppure **Non inviare**: in quel caso l'assistente riceve solo un avviso che i dati non sono stati condivisi.

Le conversazioni restano in memoria e si perdono alla chiusura dell'app.

## Note tecniche

- **Claude:** SDK ufficiale `anthropic` con un ciclo di tool use scritto a mano. Il ciclo si ferma per chiedere la tua conferma tra un passo e l'altro, perché la conferma arriva con una richiesta HTTP separata. Il contenuto dell'assistente, compresi i blocchi di thinking, viene rimandato invariato a ogni richiesta. Per i modelli che la supportano è attivo il fallback lato server (`fallbacks: "default"`) in caso di rifiuto da parte dei classificatori di sicurezza.
- **OpenAI:** SDK `openai` con l'API Chat Completions e i tool come funzioni.
- **Gemini:** SDK `google-genai` con le dichiarazioni di funzione; la chiamata automatica delle funzioni è disattivata, così il ciclo resta sotto il controllo dell'app.
