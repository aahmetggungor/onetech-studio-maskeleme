# Prompt koruması: ilk sentetik değerlendirme

`evaluate_prompt.py`, elle etiketlenmiş 16 kısa Türkçe istemi ortak `prompt_guard.py` motoruyla karşılaştırır. 15 hassas ifade etiketlendi. Sonuç: **13 doğru eşleşme, 0 yanlış alarm, 2 kaçırma**; bu küçük kümede precision `%100`, recall `%86,7`.

Kaçan iki örnek: `destek [at] ornek [nokta] com` biçiminde gizlenmiş e-posta ve cümle içinde geçen etiketsiz `Ayşe Örnek` adı. Bunlar mevcut kuralların tasarım sınırıdır; değerlendirmede hassas ifade olarak etiketlendi. Eklenti kullanıcıya eşleşmeleri sunar ama bu tür kaçırmaları kendi başına bulamaz.

Bu skor sentetik, küçük ve kural geliştirme sırasında görülen bir kümeden geldiği için gerçek web istemlerindeki başarı tahmini değildir. Sonraki aşama, ayrı tutulmuş ve farklı yazım biçimleri içeren daha büyük bir test kümesinde tekrar ölçmektir. Gerçek müşteri verisi kullanılmamalıdır.

Yeniden çalıştırma: proje kökünde `.\.venv\Scripts\python.exe .\maskeleme_demo\evaluate_prompt.py`.
