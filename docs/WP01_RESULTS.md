# WP-01 — önceki teslimin gerçek çalışma sonuçları

Bu tarihsel rapor ilk teslimdeki kanıtları korur. Güncel proje durumu için
`../RESULTS.md` dosyasına bakın. Aşağıda geçen eski `wp01.yml` iş akışı, sonraki
teslimde `testlab.yml` olarak genişletildi. Eski kaynak kilidi `wp01-source.lock.json`
içinde korunur.

Tarih: 17 Ekim 2026 UTC. Kaynak sürümü:
`2619a7584d39203a057abc08ab7c6698dc476868`.

## Kabul durumu

| Mimari plandaki kabul maddesi | Sonuç | Kanıt |
| --- | --- | --- |
| C CAN göndericisi ile bağımsız referans alıcı çalışır | **Geçti** — x86 Linux konuğunun gerçek vcan arayüzünde | `artifacts/can-linux-guest/run.json`, `guest-console.log` |
| PTY üzerinden bir seri örneği çalışır | **Geçti** — Linux host üzerinde iki yönde | `artifacts/native-final/run.json`, `serial.console.log` |
| CI runner önkoşulları doğrulanır | **Açık** — yerel engel doğrulandı; gerçek GitHub runner'ı çalıştırılmadı | `artifacts/native-preflight/run.json`, `artifacts/native-runner-attempt/`; iş akışı `.github/workflows/wp01.yml` |

WP-01'in yerel teknik deneyi tamamlandı. **Tüm kabul maddeleri kapanmadı.** Uzak
runner kanıtı alınana kadar CI kabul maddesi açık tutulmalıdır.

## Derleme

Özgün `canbus/c/sender` ve `serial/c` Makefile'ları, özgün `common.mk` uyarı
bayraklarıyla GCC 13.3.0 kullanılarak çalıştırıldı. İki derleme de 0 ile bitti.
Altı upstream dosyanın SHA-256 özetleri kaynak kilidiyle eşleşti.
Kullanılan komutlar ve binary özetleri native `run.json` içinde bulunur.

## Seri port

- Ayrı seri cihaz ve konsol PTY çiftleri açıldı.
- Seri → konsol: `SERIAL_RX_WP01_012345\n`; beklenen ve gözlenen baytlar eşit.
- Konsol → seri: `SERIAL_TX_WP01_987654\n`; beklenen ve gözlenen baytlar eşit.
- Konsola `0x03` gönderildi; uygulama çıkış kodu `0`.
- Süreç toplandı; testin sahip olduğu PTY dosya tanımlayıcıları kapandı.

Kapanış sonrası uygulamanın terminal ayarlarını geri yüklemesi ayrıca
ölçülmedi. Fiziksel baud hızı veya UART elektriksel davranışı ölçülmedi.

## CAN

Host ortamında `PF_CAN/SOCK_RAW/CAN_RAW` soketi `EPERM` ile engellendi.
Arayüz oluşturma denemesi de yetki hatası verdi. Host CAN raporu bu nedenle
`blocked`; bu kayıt başarılı diye dönüştürülmedi.

Ayrı Linux 6.8.0-138-generic konuğu QEMU 8.2.2, TCG ve tek sanal CPU ile
başlatıldı. `can`, `can-raw`, `can-dev`, `vcan` modülleri yüklendi. Referans
alıcı göndericiden önce bağlandı.

| Olay | CAN ID | DLC | Gözlenen veri (hex) | Sonuç |
| --- | --- | --- | --- | --- |
| İlk mesaj | `0x123` | 8 | `4d53475f30303000` (`MSG_000` + NUL) | Tam eşleşti |
| SIGINT sonrası | `0x124` | 3 | `454e44` (`END`) | Tam eşleşti |

Gönderici çıkışı `0`; bağımsız alıcı soketi kapandı ve alt süreç toplandı.
Konuk `vcan0` arayüzünü sildi; konuk betiği ve QEMU `0` ile kapandı. Ham
günlükte çerçeveler, gönderici çıktısı, temizlik işareti ve kapanış bulunur.

Beklentiler, Gemstone alıcısının çıktısından veya paylaşılan bir protokol
fonksiyonundan üretilmedi; yeni alıcı doğrudan Linux CAN çerçevelerini kontrol etti.

Bu sonuç host Linux uygulama davranışına yöneliktir. O1, AM67A, R5, gerçek CAN
veriyolu, hata sayaçları, bus-off veya gerçek zamanlı zamanlama doğrulanmadı.

## CI için kapatma ölçütü

Hazırlanan iş akışı gerçek depoda çalıştırıldığında aşağıdakilerin hepsi gerekir:

1. Run URL'si ve sınanan commit SHA kaydedilmiş olmalı.
2. `preflight/run.json`: `host_preflight=passed`.
3. `probes/run.json`: iki derleme, `serial_pty`, `can_vcan` kontrollerinin hepsi `passed`.
4. `runner-cleanup.json`: `exit_code=0`, `interface_created=true`, `interface_removed=true`.
5. İş akışı artifact'ında bu raporlar ve ham günlükler bulunmalı.

Bu teslimde GitHub'a depo/PR oluşturulmadı ve iş akışı tetiklenmedi.
Hazırlanmış YAML dosyası, uzak runner'ın çalıştığına dair kanıt değildir.
