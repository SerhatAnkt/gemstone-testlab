# İlk sürümün kabul durumu

Bu dosya bir yayımlama onayı veya GitHub release kaydı değildir. Yerel yazılım
kanıtı ile uzak runner ve donanım doğrulamasını ayrı tutar.

| Madde | Durum | Kapatmak için gereken |
| --- | --- | --- |
| WP-01…WP-08 yerel teknik kapsam | Kanıtlı tarihsel teslimler | İlgili iş paketi raporları korunuyor |
| WP-09 ortak CI, matris ve fail-closed denetim | Yerel kabul geçti | Host/seri/gerçek vcan ve AArch64 kanıtları mevcut |
| WP-09 gerçek GitHub Actions kabulü | **Açık** | [SerhatAnkt/gemstone-testlab](https://github.com/SerhatAnkt/gemstone-testlab) içinde dört profil ve acceptance'ın aynı gerçek koşuda geçmesi; run URL'si ve artifact'ler |
| WP-10 temiz kurulum/kaynak dağıtımı | **Yerel kabul geçti**; temiz ZIP/venv/SDK ile dört profil yeniden çalıştı | `artifacts/wp10-verification.json` ve `RESULTS.md` |
| Beş uygulama düzeltmesi | Ayrı taslaklar, gönderilmedi | Hedef dalda güncel yeniden üretim ve küçük PR'lar |
| Mimari plandaki on ardışık tam tekrar hedefi | Bu aşamada tamamlanmadı | Aynı kaynak/ortamda on tam koşuyu gerçek sonuç ve temizlik kayıtlarıyla değerlendirmek |
| AArch64 hedefte çalışma | Yapılmadı | Hedef işletim sistemi/cihaz üzerinde ayrı çalışma doğrulaması |
| Fiziksel O1, CAN/UART elektriksel doğrulama | Kapsam dışında, yapılmadı | Gerçek kart ve uygun donanım test düzeni |

Önerilen yayın sırası: sade kaynağı belirlenen TestLab deposuna aktarın, tüm
workflow'u tek attempt'ta çalıştırın, gerçek kanıtları inceleyin, açık tekrar
hedefini değerlendirin ve ardından sürümü etiketleyin. Seri/CAN yamaları kaynaklara
entegre edilmişse workflow'da `proposed-fixes` yerine `working-tree` seçilmelidir.

GitHub deposu oluşturuldu ve kaynaklar aktarılıyor. İlk hosted kabul henüz
doğrulanmadı. Yerel sonuçlar uzak runner başarısı olarak gösterilmez. Önceki yerel Git commit deneyi yalnızca
CI'nin seçilen çalışma ağacındaki gerçek değişimi gördüğünü kanıtlar; uzak
runner üzerinde koşulmuş sayılmaz.
