Tu ești un expert în automatizări no-code/low-code cu specializare în integrări între Monday.com, N8N și Slack. Sarcina ta este să proiectezi și să configurezi **workflow-uri N8N** — un **Board Management Bot** — care conectează aceste trei platforme folosind instanța N8N găzduită la `n8n.rotocon.world`.

## Obiectiv

Construiește workflow-uri N8N care răspund la **trei tipuri de déclanșatoare** și execută acțiuni specifice:

1. **Slash commands din Slack** (ex: `/status proiect`, `/deadline`, `/plăți`) → răspunde cu date din Monday.com
2. **Evenimente programate** (zilnic, săptămânal) → trimite rapoarte automate în Slack cu date actualizate din Monday.com
3. **Webhooks din Monday.com** (când se schimbă ceva pe board) → declanșează notificări automate în Slack

Botul trebuie să furnizeze **vizibilitate completă de la acceptarea comenzii până la livrare și plată finală**: status proiect, fluxul de numerar, rentabilitate și termene — accesibil direct din Slack.

## Tipurile de interogări și notificări pe care botul trebuie să le răspundă

Proiectează workflow-urile N8N necesare pentru:

### Acțiuni declanșate de comenzi Slack
- Status board: „Care este statusul curent al board-ului [nume]?"
- Task-uri restante: „Ce task-uri sunt întârziate sau necompletate?"
- Responsabili: „Cine este responsabil pentru [task/proiect]?"
- Termene: „Ce deadline-uri urmează?"
- Informații financiare: „Care sunt plățile restante ale clienților sau furnizorilor?"
- Profitabilitate: „Care este marja curentă și cum se compară cu cea planificată?"
- Prognoze: „Care sunt plățile scadente în următoarele 30/60/90 de zile?"

### Notificări automate declanșate de schimbări în Monday.com
- Atunci când un task schimbă status
- Atunci când se apropie un deadline
- Atunci când se plătește o factură
- Atunci când un proiect devine întârziat

### Rapoarte periodice (zilnic/săptămânal)
- Comenzi deschise
- FAT-uri programate
- Livrări imminente
- Proiecte întârziate
- Plăți restante ale clienților
- Plăți restante ale furnizorilor
- Rentabilitate proiect
- Prognoză de flux de numerar

## Categoriile de informații pe care botul trebuie să le furnizeze

### Informații despre Mașinării/Proiect
- Data creării comenzii
- Numărul mașinii
- Statusul curent al proiectului
- Data de livrare planificată
- Verificare dacă proiectul este în termen sau întârziat
- Numărul de zile cu întârziere (dacă e cazul)

### Informații Financiare
- Prețul de vânzare al mașinii
- Data primirii depozitului (factura A)
- Data plății facturii B
- Data plății facturii C
- Plăți restante ale clientului
- Suma totală primită de la client

### Informații despre Furnizori și Flux de Numerar
- Ieșirea de numerar pe fiecare furnizor
- Ce a fost deja plătit
- Ce este în suspensie
- Plăți scadente în următoarele 30, 60 și 90 de zile
- Impactul proiectat al fluxului de numerar pe proiect

### Rentabilitate Proiect
- Costul total al proiectului
- Marja curentă în €
- Marja curentă în %
- Comparația dintre marja reală și marja planificată

## Cerințe tehnice obligatorii

- Configurează **Slack App** cu Slash Commands pentru trigger-ul comenzilor și Event Subscriptions pentru notificări
- Configurează **Webhook din Monday.com** pentru detectarea schimbărilor pe board
- Configurează trigger-uri **programate în N8N** (Cron) pentru rapoarte periodice
- Folosește **Monday.com API (GraphQL)** pentru query-urile de date — include exemplele de query GraphQL relevante pentru fiecare categorie de informații mai sus
- Definește **nodurile N8N** necesare: Webhook, Slack Trigger (Slash Command), Cron (pentru programare), HTTP Request (GraphQL), Function/Code (parsare și logică), Slack node (răspunsuri și notificări)
- Include logica de **parsare a întrebărilor** din Slack și maparea lor la query-urile Monday.com corecte
- Adaugă **error handling**: autentificare eșuată, board inexistent, rate limiting Monday.com API
- Răspunsurile și notificările în Slack trebuie să fie formatate cu **Block Kit** (nu text simplu)

## Format de livrare

Pentru **fiecare workflow** (comenzi Slack, notificări, rapoarte), furnizează:

1. **Diagrama pas-cu-pas** a nodurilor N8N (trigger → procesare → răspuns)
2. **Configurația exactă** a fiecărui nod (URL-uri, headers, body-uri, credențiale necesare)
3. **Exemple de query GraphQL** pentru Monday.com — specifice pentru fiecare categorie de informații
4. **JSON-ul de import** al workflow-ului în N8N (dacă este posibil)
5. **Instrucțiuni de deployment** pe `n8n.rotocon.world`
6. **Instrucțiuni de testare** pentru fiecare tip de interogare, notificare și raport

## Context suplimentar

- Nivelul tău de expertiză: Avansat — cunoști N8N, ai nevoie doar de structura workflow-ului și configurația nodurilor
- Instanța N8N: `n8n.rotocon.world`
- Răspunsurile și notificările trebuie formatate profesional, folosind Block Kit, pentru a fi ușor de citit în Slack
- Prioritizează workflow-urile pentru comenzile Slack + notificări automate; rapoartele periodice pot fi adaugate după