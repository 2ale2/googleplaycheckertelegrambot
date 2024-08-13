# Overall Functioning

<procedure>

Questo bot è in grado di verificare la presenza di aggiornamenti sul Play Store relativamente
ad applicazioni scelte dall'utente, a intervalli regolari. L'utente può aggiungere, modificare o rimuovere applicazioni
in modo da adattare il bot alle proprie esigenze. Ogni passaggio è guidato e mediato da tastiere _inline_.
</procedure>

##  🟢 Settaggio Iniziale del Bot

### 💾 Persistenza
Quando il bot viene avviato, viene verificata la presenza della persistenza e i dati,
qualora presenti, vengono caricati all'interno della sua istanza. La persistenza costituisce, di fatto,
la memoria del bot e contiene le impostazioni di default, le applicazioni aggiunte (con relativi valori) e le task
programmate.

### ⚙ _Post-Init_
Una volta verificata (o meno) la presenza di informazioni nella persistenza, viene
eseguito un passaggio _compensativo_, che entra in gioco qualora all'interno della 
persistenza non fossero state trovate informazioni, o queste non fossero state 
caricate correttamente o completamente.

Tale passaggio è eseguito dalla funzione <shortcut>set_data</shortcut>.

Essa verifica il contenuto di `bot_data`: tipicamente, se almeno una delle chiavi
(`apps`, `settings`, `last_checks`) non è presente, vuol dire che la
persistenza non è stata caricata; tuttavia, il controllo viene fatto su ogni singola
chiave per mera questione di completezza.

### 🔧 Valori di Default
Quando verrà aggiunta o modificata un'applicazione, all'utente viene data la possibilità di
settare valori manualmente oppure di usare quelli di default. In questa fare, il bot guida 
l'utente nel settaggio di tali valori:
- *Intervallo di Default* – l'intervallo di controllo tra due check;
- *Condizione di Invio del Messaggio* – se il messaggio viene mandato a ogni check o solo 
quando viene trovato un aggiornamento.

## ⏭ Fase Successiva
Dopo il settaggio delle impostazioni di default, il bot è pronto per essere utilizzato; di 
seguito le varie opzioni.

- 1️⃣ _Primo Menu_ – Il primo menù permette di modificare le impostazioni o stampare gli ultimi controlli 
effettuati.

  -  2️⃣.1️⃣ _Modifica delle Impostazioni_ – Questo menù consente di gestire le applicazioni
  e modificare le impostazioni di default.
        - 3️⃣.1️⃣ _Gestione delle Applicazioni_ - Questo menù consente di aggiungere, modificare o rimuovere
        applicazioni.

        - 3️⃣.2️⃣ _Modifica delle Impostazioni di Default_ – Quest'opzione guida l'utente nella reimpostazione 
        dei valori di default del bot.

  -  2️⃣.2️⃣ _Stampare gli Ultimi Controlli_ – Questa opzione consente di visualizzare gli ultimi 10 controlli effettuati. Gli elementi 
  della lista contengono informazioni su quando il check di una certa app è stato fatto, il nome
  dell'applicazione e se è stato trovato un aggiornamento oppure no.

### 🗂 _Gestione delle Applicazioni_
Le applicazioni possono essere aggiunte, modificate o rimosse.

Quando nessuna applicazione è in lista, ogni opzione rimanda all'aggiunta. 

L'**aggiunta** prevede l'indicazione del _link al Play Store_ dell'applicazione di interesse. I controlli richiedono che
il messaggio inviato sia un link e il dominio del link sia corretto. Il bot 
chiede se l'applicazione rilevata è corretta e, in caso affermativo, viene avviata la procedura 
di settaggio.

La fase di settaggio richiede l'_impostazione dell'intervallo tra due check_ e la _condizione di invio_
del messaggio. Alternativamente, è possibile settare direttamente _i valori di default_ tramite 
apposito tasto, per impostarla più velocemente.

<procedure>

⚠️ Se si tenta di aggiungere un'applicazione già presente, il bot avvisa e rimanda alla modifica della stessa.
</procedure>

La **modifica** delle applicazioni prevede la _ripetizione della procedura_ eseguita per aggiungerle; è possibile 
selezionare l'applicazione tramite indicazione del nome o del numero corrispondente.

Analogamente, la **rimozione** richiede la scelta dell'applicazione. Prima di rimuovere l'applicazione,
all'utente è offerta la possibilità di sospenderla.

La **sospensione** è un meccanismo tramite cui si possono interrompere rapidamente gli aggiornamenti di una
certa applicazione. 

I metodi per sospendere un'applicazione sono 2: il primo è seguendo il menù di rimozione,
l'altro è tramite un messaggio di controllo della stessa applicazione: tra le opzioni offerte sotto a esso,
compare un tasto per applicare la sospensione. 

Quando si sospende un'applicazione, all'interno del menù di gestione delle applicazioni compare un altro tasto 
che consente di rimuovere la sospensione; qualora premuto, il bot consente di rimuovere la sospensione di una certa 
app premendo il tasto contenente il nome dell'applicazione sospesa.

Inoltre, è possibile modificare le impostazioni di un'app direttamente da un messaggio di controllo
tramite apposito tasto.