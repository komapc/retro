import json
from pathlib import Path

SAMPLE_DATA = {
    "A01": {
        "ynet": "נתניהו יתקשה להקים ממשלה, אבל בנט ולפיד קרובים לסיכום היסטורי. ייתכן שיוכרז על השבעת הממשלה בתוך שבועיים.",
        "haaretz": "The Bennett-Lapid government is a fragile construct. Analysts expect it will be sworn in by mid-June despite Likud pressure.",
        "n12": "דרמה פוליטית: ממשלת השינוי יוצאת לדרך. בנט ולפיד יציגו את ההסכמים הקואליציוניים בקרוב.",
        "israel_hayom": "ממשלת בנט-לפיד היא סכנה לימין. פרשנים מעריכים כי הממשלה לא תחזיק מעמד זמן רב.",
        "globes": "השווקים מגיבים בחיוב לאפשרות של יציבות שלטונית תחת ממשלת בנט-לפיד שתקום בקרוב."
    },
    "A02": {
        "ynet": "פרישת סילמן זעזעה את הקואליציה. הממשלה איבדה את הרוב בכנסת וצפויה להתקשות בהעברת חוקים.",
        "haaretz": "Idit Silman's resignation marks the beginning of the end for the 36th government. A new election seems likely by year-end.",
        "n12": "סילמן הודיעה על פרישה: 'איבדתי את האמון'. הקואליציה בדרך למבוי סתום.",
        "israel_hayom": "הימין חוגג את קריסת ממשלת בנט. הדרך לבחירות חדשות נראית סלולה מתמיד.",
        "globes": "חוסר יציבות פוליטית: השקל נחלש בעקבות פרישת סילמן והאפשרות לבחירות."
    },
    "A03": {
        "ynet": "הכנסת תצביע היום על פיזורה. יאיר לפיד יהפוך לראש ממשלת המעבר בחצות.",
        "haaretz": "The 24th Knesset is set to dissolve today. Lapid will assume the premiership during one of Israel's most volatile periods.",
        "n12": "סוף הממשלה: הכנסת התפזרה. לפיד ייכנס לתפקיד ראש הממשלה באופן מיידי.",
        "israel_hayom": "לפיד הופך לראש ממשלה ללא בחירות. הציבור יכריע בקרוב בקלפי.",
        "globes": "פיזור הכנסת: מה המשמעות הכלכלית של כניסת לפיד לתפקיד ראש ממשלת המעבר?"
    },
    "A04": {
        "ynet": "המדגמים חוזים ניצחון לגוש נתניהו. נראה כי הליכוד והשותפות ישיגו 64 מנדטים.",
        "haaretz": "The right-wing bloc has won a clear majority. Netanyahu is expected to return to power with a stable 64-seat coalition.",
        "n12": "תוצאות אמת: גוש הימין ניצח. נתניהו בדרך להרכבת הממשלה השישית שלו.",
        "israel_hayom": "ניצחון ענק לימין: נתניהו חוזר. הבוחרים אמרו את דברם בקול ברור.",
        "globes": "תוצאות הבחירות והבורסה: מה מצפה למשק תחת ממשלת נתניהו החדשה?"
    },
    "A05": {
        "ynet": "הממשלה ה-37 יוצאת לדרך. נתניהו והשרים נשבעו אמונים במליאת הכנסת.",
        "haaretz": "Netanyahu's 6th government is sworn in. Concerns grow over the influence of Ben Gvir and Smotrich in the new cabinet.",
        "n12": "טקס ההשבעה: ממשלת נתניהו החלה לפעול. השרים יכנסו למשרדיהם מחר בבוקר.",
        "israel_hayom": "יום חג לימין: הממשלה הלאומית הושבעה. נתניהו: 'נחזיר את המשילות'.",
        "globes": "הממשלה החדשה והאתגרים הכלכליים: האם נתניהו יצליח לעצור את עליות המחירים?"
    }
}

def main():
    root = Path(__file__).parent.parent.parent.parent
    ingest_dir = root / "data" / "raw_ingest"
    
    for eid, sources in SAMPLE_DATA.items():
        for sid, text in sources.items():
            source_dir = ingest_dir / sid / eid
            source_dir.mkdir(parents=True, exist_ok=True)
            
            data = {
                "headline": f"Sample Report on {eid} from {sid}",
                "text": text,
                "published_at": "2023-01-01", # Placeholder
                "author": f"Reporter from {sid}",
                "url": f"https://www.{sid}.co.il/news/{eid}"
            }
            
            with open(source_dir / "article_1.json", "w") as f:
                json.dump(data, f, indent=2)
                
    print(f"Created 25 sample articles in {ingest_dir}")

if __name__ == "__main__":
    main()
