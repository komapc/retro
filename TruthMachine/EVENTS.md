# TruthMachine: MVP Event Seed List (80 Verified Events)

> **Status:** MVP Finalized | **Last updated:** 2026-03-19

**Metadata fields**:
- `outcome` — Boolean (True if event happened)
- `outcome_date` — when the outcome was determined
- `search_keywords` — terms for article ingestion (Hebrew/English)
- `llm_referee_criteria` — instructions for relevance verification
- `tags` — comma-separated domain codes (primary domain = event ID prefix)

**Domain codes**: A=Politics, B=Gaza/Oct7, C=Iran/Regional, D=Economy, E=Global, F=Society, G=Tech/AI, H=Israeli Tech, I=Energy

---

## Domain A: Israeli Politics & Elections

| # | Event | Outcome | Outcome Date | Search Keywords | LLM Referee Criteria | Tags |
|---|---|---|---|---|---|---|
| A01 | Bennett-Lapid coalition sworn in as government | True | 2021-06-13 | "ממשלת בנט-לפיד", "Bennett-Lapid government", "sworn in" | Must discuss the formation of the 36th government. | A |
| A02 | Bennett coalition loses Knesset majority | True | 2022-04-06 | "עידית סילמן", "Idit Silman resignation", "majority lost" | Must focus on the 61-seat majority loss citing Silman. | A |
| A03 | Knesset dissolves — Lapid becomes caretaker PM | True | 2022-06-30 | "פיזור הכנסת ה-24", "dissolution 24th Knesset", "Lapid caretaker" | Must discuss the bill to dissolve or the transition to Lapid. | A |
| A04 | 2022 Israeli election — right bloc wins majority | True | 2022-11-03 | "תוצאות הבחירות 2022", "election results right bloc", "64 seats" | Must discuss the final results showing a 64-seat win. | A |
| A05 | Netanyahu forms new government (6th government) | True | 2022-12-29 | "ממשלת נתניהו השישית", "Netanyahu 6th government", "sworn in" | Must discuss the swearing-in of the 37th government. | A |
| A06 | Ben Gvir appointed National Security Minister | True | 2022-12-29 | "בן גביר השר לביטחון לאומי", "Ben Gvir appointment" | Must confirm appointment as part of government formation. | A |
| A07 | Smotrich West Bank civilian powers transferred | True | 2023-02-23 | "סמולטריץ' סמכויות ביו\"ש", "Smotrich West Bank powers" | Must discuss the specific Feb 23 transfer agreement. | A, C |
| A08 | Reasonableness clause passes first reading | True | 2023-07-11 | "צמצום עילת הסבירות קריאה ראשונה", "reasonableness first reading" | Must discuss the July 11 legislative vote. | A, F |
| A09 | Reasonableness clause passes final vote | True | 2023-07-24 | "חוק עילת הסבירות עבר", "reasonableness final vote" | Must discuss the 64-0 passage on July 24. | A, F |
| A10 | Netanyahu pauses judicial reform after strike | True | 2023-03-27 | "נתניהו השהיית החקיקה", "Netanyahu pause reform" | Must focus on the March 27 announcement after mass protests. | A, F |
| A11 | Histadrut declares general strike against reform | True | 2023-03-27 | "שביתה כללית הסתדרות", "Histadrut general strike" | Must discuss the nationwide shutdown on March 27. | A, F |
| A12 | Supreme Court strikes down reasonableness clause | True | 2024-01-01 | "בג\"ץ ביטול עילת הסבירות", "Court strikes down reasonableness" | Must focus on the Jan 1 historic 8-7 ruling. | A, F |
| A13 | Gantz joins emergency war cabinet | True | 2023-10-12 | "גנץ מצטרף לממשלת חירום", "Gantz joins cabinet" | Must discuss the swearing-in after the Oct 7 attack. | A, B |
| A14 | Gantz leaves emergency war cabinet | True | 2024-06-09 | "גנץ פורש מהממשלה", "Gantz resigns war cabinet" | Must focus on Gantz's official exit on June 9. | A, B |
| A15 | Gallant fired as Defense Minister (second time) | True | 2024-11-05 | "פיטורי גלנט נובמבר", "Gallant fired second time" | Must focus on the Nov 5 dismissal by Netanyahu. | A, B |
| A16 | Budget 2023 passes Knesset | True | 2023-05-24 | "אישור תקציב המדינה 2023", "Israel budget 2023 passed" | Must discuss the final passage of the 2023 budget. | A, D |
| A17 | Budget 2024 passes Knesset | True | 2024-03-13 | "תקציב 2024 עבר", "Israel budget 2024 passed" | Must discuss the March 13 legislative approval. | A, D |
| A18 | Ultra-orthodox military draft law passes Knesset | False | 2026-03-17 | "חוק הגיוס עבר", "Haredi draft law passed" | Mark False if only delays or rulings occurred by this date. | A, F |
| A19 | ICC issues arrest warrant for Netanyahu | True | 2024-11-21 | "צו מעצר נגד נתניהו", "ICC arrest warrant Netanyahu" | Must focus on the official warrant issuance on Nov 21. | A, E |

---

## Domain B: October 7 & Gaza War

| # | Event | Outcome | Outcome Date | Search Keywords | LLM Referee Criteria | Tags |
|---|---|---|---|---|---|---|
| B01 | Hamas launches mass surprise attack (Oct 7) | True | 2023-10-07 | "מתקפת חמאס 7 באוקטובר", "Hamas surprise attack" | Must focus on the initial infiltration and attack. | B, C |
| B02 | Israel formally declares state of war | True | 2023-10-08 | "הכרזת מלחמה ישראל", "Israel declares war Article 40" | Must focus on the cabinet's formal invocation. | B, A |
| B03 | IDF ground invasion of Gaza begins | True | 2023-10-27 | "כניסה קרקעית לעזה", "ground invasion begins" | Must focus on the start of the large-scale incursion. | B |
| B04 | First hostage deal reached (pause in fighting) | True | 2023-11-22 | "עסקת חטופים ראשונה", "first hostage deal" | Must focus on the agreement reached on Nov 22. | B, E |
| B05 | First phase hostage releases completed | True | 2023-11-30 | "שחרור חטופים פעימה ראשונה", "hostage releases completed" | Must focus on the end of the initial release window. | B |
| B06 | Fighting resumes after first deal pause | True | 2023-12-01 | "חזרה ללחימה עזה", "fighting resumes Gaza" | Must focus on the expiration of the truce on Dec 1. | B |
| B07 | IDF enters and controls central Khan Yunis | True | 2023-12-05 | "צה\"ל במרכז חאן יונס", "IDF central Khan Yunis" | Must focus on the entry into the city's heart. | B |
| B08 | IDF begins Rafah ground operation | True | 2024-05-07 | "פעולה ברפיח", "Rafah operation begins" | Must focus on the start of the ground offensive in Rafah. | B, E |
| B09 | Haniyeh assassinated in Tehran | True | 2024-07-31 | "חיסול הנייה בטהרן", "Haniyeh assassinated Tehran" | Must focus on the July 31 event in Iran. | B, C |
| B10 | Sinwar killed in Gaza | True | 2024-10-16 | "חיסול סינוואר", "Sinwar killed Gaza" | Must focus on the Oct 16 confirmation of his death. | B |
| B11 | ICJ orders Israel to prevent genocide / halt Rafah | True | 2024-05-24 | "צו בית הדין בהאג רפיח", "ICJ Rafah order" | Must focus on the May 24 ruling. | B, E |
| B12 | Hamas operational after 1 year (Oct 7, 2024) | True | 2024-10-07 | "חמאס אחרי שנה למלחמה", "Hamas status Oct 2024" | Must discuss Hamas still fighting/ruling parts of Gaza. | B |
| B13 | US halts weapons shipment to Israel | True | 2024-05-08 | "עיכוב משלוחי נשק ארה\"ב", "US halts weapons shipment" | Must focus on the May 8 confirmation of the pause. | B, E |

---

## Domain C: Iran & Regional

| # | Event | Outcome | Outcome Date | Search Keywords | LLM Referee Criteria | Tags |
|---|---|---|---|---|---|---|
| C01 | JCPOA revival negotiations collapse | True | 2022-09-01 | "כישלון שיחות הגרעין", "JCPOA negotiations collapse" | Must focus on the late 2022 impasse. | C, E |
| C02 | Mahsa Amini protests erupt in Iran | True | 2022-09-16 | "מהסא אמיני הפגנות", "Mahsa Amini protests begin" | Must focus on the start of the movement in Sept 2022. | C, F |
| C03 | Iran confirmed supplying drones to Russia | True | 2022-11-05 | "כטב\"מים איראניים ברוסיה", "Iran drones Russia" | Must focus on the official confirmation in Nov 2022. | C, E |
| C04 | Saudi-Iran normalization deal signed (Beijing) | True | 2023-03-10 | "הסכם סעודיה איראן", "Saudi-Iran deal Beijing" | Must focus on the March 10 signing. | C, E |
| C05 | Iran launches direct missile attack on Israel | True | 2024-04-14 | "מתקפה איראנית ישירה", "Iran missile attack Israel" | Must focus on the April 14 multi-drone/missile barrage. | C, B |
| C06 | Israel retaliates with strike inside Iran | True | 2024-04-19 | "תקיפה ישראלית באיראן", "Israel retaliates Iran April" | Must focus on the specific April 19 response. | C, B |
| C07 | Nasrallah assassinated | True | 2024-09-27 | "חיסול נסראללה", "Nasrallah assassinated" | Must focus on the Sept 27 strike in Beirut. | C, B |
| C08 | Lebanon ceasefire agreement reached | True | 2024-11-27 | "הפסקת אש בלבנון", "Lebanon ceasefire 2024" | Must focus on the Nov 27 effective date. | C, E |
| C09 | Assad regime falls in Syria | True | 2024-12-08 | "נפילת אסד", "Assad regime falls Syria" | Must focus on the Dec 8 total collapse. | C, E |

---

## Domain D: Israeli Economy

| # | Event | Outcome | Outcome Date | Search Keywords | LLM Referee Criteria | Tags |
|---|---|---|---|---|---|---|
| D01 | Shekel drops below 4.0 NIS/USD | True | 2023-10-16 | "דולר מעל 4 שקלים", "Shekel below 4.0 USD" | Must focus on the exchange rate milestone. | D, B |
| D02 | Moody's downgrades Israel credit rating | True | 2024-02-09 | "מודי'ס הורדת דירוג אשראי", "Moody's downgrade Israel" | Must focus on the first downgrade in Feb 2024. | D, B |
| D03 | S&P downgrades Israel credit rating | True | 2024-04-19 | "S&P הורדת דירוג", "S&P downgrade Israel" | Must focus on the April 2024 downgrade. | D, B |
| D04 | Bank of Israel raises interest rate to 4.75% | True | 2023-05-22 | "ריבית בנק ישראל 4.75", "Bank of Israel raise rate" | Must focus on the May 22 peak rate hike. | D |
| D05 | Israel GDP growth turns negative (war quarter) | True | 2024-01-31 | "ירידת תוצר ישראל", "Israel GDP negative growth war" | Must focus on Q4 2023 GDP contraction data release. | D, B |
| D06 | Israeli unemployment reaches 4.5%+ during war | True | 2024-01-15 | "אבטלה ישראל מלחמה", "Israel unemployment war spike" | Must focus on official CBS data showing spike above 4.5%. | D, B |

---

## Domain E: Global Events

| # | Event | Outcome | Outcome Date | Search Keywords | LLM Referee Criteria | Tags |
|---|---|---|---|---|---|---|
| E01 | Russia launches full-scale invasion of Ukraine | True | 2022-02-24 | "פלישה רוסיה אוקראינה", "Russia invades Ukraine full-scale" | Must focus on the Feb 24 ground offensive start. | E, C |
| E02 | Ukraine recaptures Kherson city | True | 2022-11-11 | "שחרור חרסון", "Ukraine recaptures Kherson" | Must focus on the Nov 11 Ukrainian flag raising. | E |
| E03 | US midterm elections — Democrats retain Senate | True | 2022-11-12 | "בחירות ביניים דמוקרטים סנאט", "US midterms Democrats Senate" | Must focus on final Senate majority determination. | E |
| E04 | FTX collapses — SBF arrested | True | 2022-11-11 | "קריסת FTX", "FTX collapse SBF arrested" | Must focus on the exchange halt and SBF's arrest. | E, G |
| E05 | SVB (Silicon Valley Bank) collapses | True | 2023-03-10 | "קריסת SVB", "Silicon Valley Bank collapse" | Must focus on the FDIC seizure on March 10. | E, D |
| E06 | Trump indicted (first federal indictment) | True | 2023-06-09 | "כתב אישום נגד טראמפ", "Trump federal indictment" | Must focus on the June 9 federal charges. | E |
| E07 | Trump wins 2024 US presidential election | True | 2024-11-06 | "טראמפ נבחר נשיא 2024", "Trump wins 2024 election" | Must focus on the Nov 6 projection/call of the race. | E |
| E08 | US Federal Reserve begins rate cut cycle | True | 2024-09-18 | "הפד מוריד ריבית", "Fed first rate cut 2024" | Must focus on the Sept 18 first cut announcement. | E, D |
| E09 | UK PM Liz Truss resigns after 45 days | True | 2022-10-20 | "התפטרות טראס", "Liz Truss resigns UK PM" | Must focus on the Oct 20 resignation announcement. | E |
| E10 | Finland joins NATO | True | 2023-04-04 | "פינלנד נאטו", "Finland joins NATO" | Must focus on the April 4 accession ceremony. | E, C |

---

## Domain F: Israeli Society & Culture

| # | Event | Outcome | Outcome Date | Search Keywords | LLM Referee Criteria | Tags |
|---|---|---|---|---|---|---|
| F01 | Judicial reform protest movement reaches 100K+ weekly | True | 2023-02-11 | "מאה אלף מפגינים", "100000 protesters judicial reform" | Must cite crowd estimates of 100K+ in a single event. | F, A |
| F02 | Israeli Arab MK joins coalition (Ra'am) | True | 2021-06-13 | "רע\"ם קואליציה", "Ra'am joins coalition" | Must confirm Ra'am's formal entry into the 36th government. | F, A |
| F03 | Mass emigration wave reported post-Oct 7 (yerida spike) | True | 2024-03-01 | "עלייה בירידה מישראל", "emigration spike Israel post-war" | Must cite official CBS or airport data showing spike. | F, B |
| F04 | Israel-diaspora relations crisis over Kotel agreement cancellation | True | 2023-07-01 | "הסכם הכותל ביטול", "Kotel agreement cancelled diaspora" | Must focus on formal cancellation and diaspora reaction. | F, A |
| F05 | Ultra-orthodox draft evasion ruling by Supreme Court | True | 2024-06-25 | "פסיקת בג\"ץ גיוס חרדים", "Supreme Court Haredi draft ruling" | Must focus on the June 25 unanimous ruling on state funding. | F, A |

---

## Domain G: Technology & AI

| # | Event | Outcome | Outcome Date | Search Keywords | LLM Referee Criteria | Tags |
|---|---|---|---|---|---|---|
| G01 | ChatGPT launches publicly (OpenAI) | True | 2022-11-30 | "השקת צ'אט GPT", "ChatGPT launch" | Must focus on the Nov 30 public release. | G |
| G02 | OpenAI board fires then reinstates Sam Altman | True | 2023-11-22 | "פיטורי סם אלטמן", "Sam Altman fired OpenAI" | Must focus on the Nov 2023 crisis and resolution. | G |
| G03 | Nvidia market cap exceeds $1 trillion USD | True | 2023-05-30 | "אנבידיה טריליון דולר", "Nvidia 1 trillion market cap" | Must focus on the May 30 valuation milestone. | G |
| G04 | Elon Musk completes acquisition of Twitter (X) | True | 2022-10-27 | "אילון מאסק קנה את טוויטר", "Musk completes Twitter deal" | Must focus on the Oct 27 finalization. | G |
| G05 | DeepSeek R1 release shocks AI market | True | 2025-01-20 | "השקת DeepSeek R1", "DeepSeek R1 release" | Must focus on the Jan 2025 release impact. | G |
| G06 | EU AI Act formally adopted | True | 2024-03-13 | "חוק הבינה המלאכותית האירופי", "EU AI Act adopted" | Must focus on the European Parliament vote on March 13. | G, E |
| G07 | GPT-4 released publicly | True | 2023-03-14 | "GPT-4 השקה", "GPT-4 release OpenAI" | Must focus on the March 14 public launch. | G |
| G08 | Google Gemini Ultra surpasses GPT-4 on benchmarks | True | 2024-02-08 | "גמיני אולטרה גוגל", "Gemini Ultra launch benchmark" | Must focus on the Feb 8 launch and benchmark claims. | G |

---

## Domain H: Israeli Tech

| # | Event | Outcome | Outcome Date | Search Keywords | LLM Referee Criteria | Tags |
|---|---|---|---|---|---|---|
| H01 | Mobileye IPO on Nasdaq | True | 2022-10-26 | "הנפקת מובילאיי נאסדק", "Mobileye IPO Nasdaq" | Must focus on the Oct 26 trading debut. | H, D |
| H02 | Intel cancels Tower Semiconductor acquisition | True | 2023-08-16 | "ביטול רכישת טאואר אינטל", "Intel Tower acquisition cancelled" | Must focus on the Aug 16 termination announcement. | H, D |
| H03 | IronSource completes merger with Unity | True | 2022-11-07 | "מיזוג אירון סורס יוניטי", "IronSource Unity merger complete" | Must focus on the Nov 7 closing of the deal. | H |
| H04 | Israeli VC investment drops 50%+ YoY (2022→2023) | True | 2023-12-31 | "ירידה השקעות הייטק ישראל", "Israeli VC investment drop 2023" | Must cite IVC/Start-Up Nation Central data showing 50%+ decline. | H, D |
| H05 | Wiz rejects Google $23B acquisition offer | True | 2024-07-22 | "ויז דחתה גוגל", "Wiz rejects Google acquisition" | Must focus on the July 22 rejection announcement. | H, G |
| H06 | Google agrees to acquire Wiz for $32B | True | 2025-03-18 | "גוגל רוכשת ויז", "Google acquires Wiz $32B" | Must focus on the definitive agreement announcement. | H, G |
| H07 | Check Point acquires Cyberint | True | 2024-08-01 | "צ'ק פוינט רוכשת סייברינט", "Check Point acquires Cyberint" | Must focus on the acquisition announcement in Aug 2024. | H |
| H08 | Israeli AI startup raises $100M+ round (multiple) | True | 2024-06-01 | "סטארטאפ ישראלי בינה מלאכותית גיוס", "Israeli AI startup $100M raise" | Must cite at least one Israeli AI company closing a $100M+ round in 2024. | H, G, D |
| H09 | Israeli tech layoffs exceed 15,000 cumulative (2023) | True | 2023-12-31 | "פיטורים הייטק ישראל 2023", "Israeli tech layoffs 2023" | Must cite cumulative layoff figures above 15,000 for 2023. | H, D |
| H10 | Start-Up Nation Central: Israel drops out of top 5 startup ecosystems | True | 2024-06-01 | "מדד אקוסיסטם ישראל", "Israel startup ecosystem ranking drop" | Must cite a specific global ranking report showing Israel below top 5. | H, D |

---

## Domain I: Energy

| # | Event | Outcome | Outcome Date | Search Keywords | LLM Referee Criteria | Tags |
|---|---|---|---|---|---|---|
| I01 | Brent crude oil exceeds $100/barrel (Russia-Ukraine) | True | 2022-02-24 | "נפט מעל 100 דולר", "Brent crude 100 dollars barrel" | Must focus on the Feb 24 price spike above $100 triggered by invasion. | I, E |
| I02 | Israel-EU natural gas export MOU signed | True | 2022-06-15 | "הסכם גז ישראל אירופה", "Israel EU gas export MOU" | Must focus on the June 15 tripartite agreement (Israel, Egypt, EU). | I, E, D |
| I03 | Karish gas field begins production | True | 2022-10-27 | "שדה קריש ייצור גז", "Karish gas field production" | Must focus on the first gas production from Karish. | I, D |
| I04 | Europe reduces Russian gas dependency below 15% of supply | True | 2023-12-31 | "אירופה גז רוסי תלות", "Europe reduces Russian gas dependency" | Must cite IEA or Eurostat data confirming below 15% share by end 2023. | I, E |
| I05 | Global oil price drops below $70/barrel (demand fears) | True | 2023-06-12 | "נפט מתחת 70 דולר", "oil price below $70 demand" | Must focus on Brent closing below $70 citing global demand slowdown. | I, E, D |

---

*"The past is our data. The future is our product."*
