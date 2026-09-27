"""Sentetik Türkçe istemlerde kural tabanlı korumanın ölçülebilir sınaması."""

from collections import Counter

from prompt_guard import analyze_prompt


# Her beklenen öğe (görünen metin, tür) olarak elle etiketlendi.
# Buradaki skorlar yalnızca bu küçük sentetik kümeyi anlatır.
CASES = [
    ("Mail adresim ayse.ornek@example.com, cevabı oraya yolla.",
     [("ayse.ornek@example.com", "E-posta")]),
    ("Kopya: AHMET+TEST@EXAMPLE.ORG ve bilgi@example.net",
     [("AHMET+TEST@EXAMPLE.ORG", "E-posta"), ("bilgi@example.net", "E-posta")]),
    ("Telefonum 0532 123 45 67, arayabilirsin.",
     [("0532 123 45 67", "Telefon")]),
    ("İletişim: +90 (532) 123 45 67", [("+90 (532) 123 45 67", "Telefon")]),
    ("Kimlik numarası 10000000146; başka sayı 10000000147.",
     [("10000000146", "T.C. kimlik")]),
    ("IBAN TR33 0006 1005 1978 6457 8413 26 hesabına aktar.",
     [("TR33 0006 1005 1978 6457 8413 26", "IBAN")]),
    ("Ödeme testi 4111 1111 1111 1111 ile yapıldı.",
     [("4111 1111 1111 1111", "Kart numarası")]),
    ("ad soyad: Ayşe Örnek\nBana bir özgeçmiş yaz.",
     [("Ayşe Örnek", "Ad soyad")]),
    ("Bu kod MAVI-42 gizlidir; sakla.", [("MAVI-42", "Özel kural")]),
    ("Herhangi bir e-posta yok; destek [at] ornek [nokta] com.",
     [("destek [at] ornek [nokta] com", "E-posta")]),
    ("Sürüm 1.2.3, telefon modeli 5320, tarih 26.09.2026.", []),
    ("Geçersiz kimlik 12345678901 ve geçersiz kart 4111 1111 1111 1112.", []),
    ("Geçersiz IBAN TR00 0000 0000 0000 0000 0000 00.", []),
    ("Kişi adı Ayşe Örnek; etiket bulunmuyor.", [("Ayşe Örnek", "Ad soyad")]),
    ("Örnek değer: bilgi@example.net; bilgi@example.net tekrar geçti.",
     [("bilgi@example.net", "E-posta"), ("bilgi@example.net", "E-posta")]),
    ("Özel kural mavi-42 küçük harfle de geçebilir.", [("mavi-42", "Özel kural")]),
]


def evaluate() -> tuple[int, int, int]:
    tp = fp = fn = 0
    for index, (prompt, expected) in enumerate(CASES, 1):
        predicted = Counter((item["original"], item["type"])
                            for item in analyze_prompt(prompt, rules=["MAVI-42"])["matches"])
        labelled = Counter(expected)
        hits = sum((predicted & labelled).values())
        missed = sum((labelled - predicted).values())
        extra = sum((predicted - labelled).values())
        tp += hits
        fn += missed
        fp += extra
        if missed or extra:
            print(f"Vaka {index}: TP={hits}, FP={extra}, FN={missed} | {prompt}")
    return tp, fp, fn


if __name__ == "__main__":
    tp, fp, fn = evaluate()
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    print(f"{len(CASES)} istem | TP={tp}, FP={fp}, FN={fn} | "
          f"precision={precision:.1%}, recall={recall:.1%}")
