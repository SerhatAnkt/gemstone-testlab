# İlk sürümün kabul durumu

Bu dosya bir yayımlama onayı veya GitHub release kaydı değildir. Yerel yazılım
kanıtı ile uzak runner ve donanım doğrulamasını ayrı tutar.

| Madde | Durum | Kapatmak için gereken |
| --- | --- | --- |
| WP-01…WP-08 yerel teknik kapsam | Kanıtlı tarihsel teslimler | İlgili iş paketi raporları korunuyor |
| WP-09 ortak CI, matris ve fail-closed denetim | Yerel kabul geçti | Host/seri/gerçek vcan ve AArch64 kanıtları mevcut |
| WP-09 gerçek GitHub Actions kabulü | **Geçti**; beş iş aynı koşuda başarılı | [Koşu #2](https://github.com/SerhatAnkt/gemstone-testlab/actions/runs/39155570890); `docs/ci-runs/39155570890.json`; indirilen kanıtlar yeniden doğrulandı |
| WP-10 temiz kurulum/kaynak dağıtımı | **Yerel kabul geçti**; temiz ZIP/venv/SDK ile dört profil yeniden çalıştı | `artifacts/wp10-verification.json` ve `RESULTS.md` |
| Beş uygulama düzeltmesi | Ayrı taslaklar, gönderilmedi | Hedef dalda güncel yeniden üretim ve küçük PR'lar |
| Mimari plandaki on ardışık tam tekrar hedefi | Bu aşamada tamamlanmadı | Aynı kaynak/ortamda on tam koşuyu gerçek sonuç ve temizlik kayıtlarıyla değerlendirmek |
| AArch64 hedefte çalışma | Yapılmadı | Hedef işletim sistemi/cihaz üzerinde ayrı çalışma doğrulaması |
| Fiziksel O1, CAN/UART elektriksel doğrulama | Kapsam dışında, yapılmadı | Gerçek kart ve uygun donanım test düzeni |

GitHub'a aktarım ve ilk gerçek hosted kabul tamamlandı. Sürümü etiketlemeden
önce açık tekrar hedefini değerlendirin ve katkı paketlerini hedef dalda
yeniden doğrulayın. Seri/CAN yamaları kaynaklara
entegre edilmişse workflow'da `proposed-fixes` yerine `working-tree` seçilmelidir.

Hosted kabulün gerçek commit'i `b26d6eddb6da44d16dc0ab2dfe5af85c98166042`
ve koşu bağlantısı yukarıda kayıtlıdır. İlk koşudaki modül/eksik artifact
hataları da `docs/ci-runs/39155256787.json` içinde korunur. Önceki yerel Git
commit deneyi bu hosted koşudan ayrı tarihsel kanıttır.
