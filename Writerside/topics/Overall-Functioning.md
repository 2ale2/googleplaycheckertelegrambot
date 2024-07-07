# Overall Functioning

## Settaggio Iniziale del Bot

### 💾 Persistenza
Quando il bot viene avviato, viene verificata la presenza della persistenza e i dati,
qualora presenti, vengono caricati all'interno della sua istanza.

### ⚙ _Post-Init_
Una volta verificata (o meno) la presenza di informazioni nella persistenza, viene
eseguito un passaggio _compensativo_, che entra in gioco qualora all'interno della 
persistenza non fossero state trovate informazioni, o queste non fossero state 
caricate correttamente o completamente.

Tale passaggio è eseguito dalla funzione <shortcut>set_data</shortcut>.

Essa verifica il contenuto di `bot_data`: tipicamente, se almeno una delle chiavi
(`initialized`, `apps`, `settings`, `last_checks`) non è presente, vuol dire che la
persistenza non è stata caricata; tuttavia, il controllo viene fatto su ogni singola
chiave per mera questione di completezza.

<procedure>
        <p>Se alcune chiavi sono presenti e altre no, significa che la persistenza non
è stata caricata correttamente. In tal caso, potrebbe essere opportuno loggare l'evento
siccome è alcune informazioni, così facendo, vanno perse perché sostituite con valori di
default.</p>
</procedure>

In particolare, se `initialized` non è presente in `bot_data`, viene aggiunta e settata
a `False` (di default, infatti, le applicazioni non sono settate ed è l'utente a doverlo fare).

Se `apps` non è presente in `bot_data`, viene aggiunta come dizionario vuoto e viene
tentata l'apertura del file <shortcut>config.json</shortcut> contenente eventuali link 
iniziali. Se tale file non è presente, non ci sono applicazioni da settare e il parametro
`initialized` viene impostato a `True`.

Viceversa, se il file <shortcut>config.json</shortcut> è presente, viene letto e viene
verificata la presenza di link all'interno della lista corrispondente. 

Se vengono trovati link, l'evento viene loggato e, per ognuno di essi, viene creata una
voce nel dizionario `bot_data[apps]` contenente il link in questione (`app_link`), il 
nome dell'app (`app_name` – tramite <shortcut>get_app_name_with_link()</shortcut>, 
che assume il nome del link indicato) e `check_interval`, ovvero il tempo tra due controlli,
che viene impostato a `None` di default.

Se non vengono trovati link, la variabile `initialized` viene impostata a `True`, siccome non ci
sono applicazione da settare.

Se la voce `settings` non è presente in `bot_data`, viene creato un dizionario con i valori 
di impostazione default.

Analogamente, se la voce `last_checks` non è in `bot_data`, viene creato un dizionario vuoto
destinato allo scopo di tenere traccia l'ultimo controllo per ogni applicazione.

### ⏯ Avvio del Bot
Quando Linxay invia <shortcut>/start</shortcut>, viene verificata la presenza di applicazioni
da settare: se vengono trovate (`bot_data[...]["settled"] == False`), viene richiesto 
se impostarle ora, dopo oppure mostrare l'elenco di tali applicazioni.