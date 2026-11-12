# Database anagrafiche di gioco

Questa cartella conterrà `fm_reference.sqlite`, il database con i dati che i salvataggi non contengono:
nomi di competizioni, nazioni, città e stadi, divisi per build di Football Manager.

Lo si manutiene tramite file CSV in `reference/src/<build>/` e lo script `reference/build_reference.py`. Arrivano entrambi con lo Step 3.

L'eseguibile cerca il database in `<cartella dell'exe>/reference/fm_reference.sqlite`. Il percorso si può cambiare dalle Impostazioni.
